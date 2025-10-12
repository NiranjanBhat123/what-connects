import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Lightbulb, Trophy, Send, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import confetti from 'canvas-confetti';
import { useGameStore } from '@/store/gameStore';
import { websocketManager } from '@/services/websocket';
import { gameAPI, roomAPI } from '@/services/api';

export default function GamePlayPage() {
    const { code } = useParams();
    const navigate = useNavigate();
    const {
        player,
        currentQuestion,
        setCurrentQuestion,
        currentQuestionIndex,
        totalQuestions,
        timeRemaining,
        decrementTime,
        resetTimer,
        currentAnswer,
        setCurrentAnswer,
        hasAnswered,
        setAnswerResult,
        clearAnswer,
        showHint,
        setShowHint,
        usedHint,
        setUsedHint,
        isHost,
        leaderboard,
        setLeaderboard,
    } = useGameStore();

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [gameId, setGameId] = useState(null);
    const timerRef = useRef(null);
    const answerInputRef = useRef(null);

    useEffect(() => {
        if (!player) {
            navigate('/');
            return;
        }

        initializeGame();
        setupWebSocket();

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
            // Don't disconnect WebSocket here - it may be needed for results page
        };
    }, []);

    // Timer countdown
    useEffect(() => {
        if (currentQuestion && !hasAnswered && timeRemaining > 0) {
            timerRef.current = setInterval(() => {
                decrementTime();
            }, 1000);
        } else {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        }

        // Auto-submit when time runs out
        if (timeRemaining === 0 && !hasAnswered && currentQuestion) {
            handleTimeUp();
        }

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, [timeRemaining, hasAnswered, currentQuestion]);

    const initializeGame = async () => {
        try {
            // Get current game state from room
            const roomResponse = await roomAPI.get(code);
            console.log('Room response:', roomResponse.data);

            if (roomResponse.data.current_game) {
                const currentGameId = roomResponse.data.current_game.id;
                setGameId(currentGameId);

                try {
                    const gameResponse = await gameAPI.getCurrentQuestion(currentGameId);
                    console.log('Current question response:', gameResponse.data);

                    if (gameResponse.data.current_question) {
                        setCurrentQuestion(
                            gameResponse.data.current_question,
                            gameResponse.data.current_question_index
                        );
                        resetTimer(gameResponse.data.current_question.time_limit || 30);
                    }
                } catch (error) {
                    console.error('Error fetching current question:', error);
                    toast.error('Failed to load current question');
                }
            } else {
                toast.error('No active game found');
                navigate(`/room/${code}`);
            }
        } catch (error) {
            console.error('Error initializing game:', error);
            toast.error('Failed to load game');
            navigate(`/room/${code}`);
        }
    };

    const setupWebSocket = () => {
        console.log('Setting up WebSocket for gameplay...');

        // Setup all event handlers first
        setupWebSocketHandlers();

        // Check if already connected - reuse existing connection
        if (websocketManager.isConnected() && websocketManager.roomCode === code) {
            console.log('WebSocket already connected, reusing connection');
            return;
        }

        // Connect if not already connected
        websocketManager.connect(code, player.id).then(() => {
            console.log('WebSocket connected for gameplay');
        }).catch(err => {
            console.error('WebSocket connection failed:', err);
            toast.error('Failed to connect to game');
        });
    };

    const setupWebSocketHandlers = () => {
        // Remove all existing listeners to prevent duplicates
        websocketManager.removeAllListeners('next_question');
        websocketManager.removeAllListeners('game_complete');
        websocketManager.removeAllListeners('answer_submitted');
        websocketManager.removeAllListeners('hint');
        websocketManager.removeAllListeners('game_state_update');
        websocketManager.removeAllListeners('all_players_answered');
        websocketManager.removeAllListeners('error');

        // Handle next question
        websocketManager.on('next_question', (data) => {
            console.log('Next question received:', data);
            clearAnswer();
            setShowHint(false);
            setCurrentQuestion(data.question, data.question_number - 1);
            resetTimer(data.question.time_limit || 30);
            toast.info(`Question ${data.question_number} of ${data.total_questions}`);
        });

        // Handle game complete
        websocketManager.on('game_complete', (data) => {
            console.log('Game complete:', data);
            setLeaderboard(data.results);
            toast.success('Game complete! 🎉');
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });
            setTimeout(() => {
                navigate(`/results/${code}`);
            }, 2000);
        });

        // Handle answer submissions from other players
        websocketManager.on('answer_submitted', (data) => {
            console.log('Answer submitted event:', data);
            if (data.player_id !== player.id) {
                const icon = data.is_correct ? '✅' : '❌';
                toast(`${icon} ${data.player_name} answered`, {
                    description: data.is_correct ? `+${data.points_earned} points` : 'Incorrect',
                });
            }
        });

        // Handle hint
        websocketManager.on('hint', (data) => {
            console.log('Hint received:', data);
            setShowHint(true);
            toast.info('Hint revealed!');
        });

        // Handle game state updates
        websocketManager.on('game_state_update', (data) => {
            console.log('Game state update received:', data);
            // Update any relevant state if needed
        });

        // Handle all players answered
        websocketManager.on('all_players_answered', (data) => {
            console.log('All players answered:', data);
            if (isHost) {
                toast.info('All players have answered!');
            }
        });

        // Handle errors
        websocketManager.on('error', (data) => {
            console.error('WebSocket error:', data);
            toast.error(data.message || 'Connection error');
        });

        // Handle disconnection
        websocketManager.on('disconnected', (data) => {
            console.log('WebSocket disconnected:', data);
            if (data.code !== 1000) {
                toast.error('Lost connection to game');
            }
        });
    };

    const handleSubmitAnswer = async () => {
        if (!currentAnswer.trim() || hasAnswered || isSubmitting) return;

        const timeTaken = (currentQuestion.time_limit || 30) - timeRemaining;
        setIsSubmitting(true);

        try {
            const response = await gameAPI.submitAnswer(gameId, {
                player_id: player.id,
                question_id: currentQuestion.id,
                answer_text: currentAnswer.trim(),
                used_hint: usedHint,
                time_taken: timeTaken,
            });

            setAnswerResult(response.data);

            if (response.data.is_correct) {
                toast.success(`Correct! +${response.data.points_earned} points`, {
                    description: `Total: ${response.data.total_score}`,
                });
                confetti({
                    particleCount: 50,
                    spread: 60,
                    origin: { y: 0.7 }
                });
            } else {
                toast.error('Incorrect answer', {
                    description: `Correct answer: ${response.data.correct_answer}`,
                });
            }
        } catch (error) {
            console.error('Submit answer error:', error);
            const errorData = error.response?.data?.error;
            if (errorData?.code === 'answer_already_submitted') {
                toast.warning('You already answered this question');
            } else if (errorData?.code === 'time_limit_exceeded') {
                toast.error('Time limit exceeded!');
            } else {
                toast.error('Failed to submit answer');
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleTimeUp = () => {
        if (!hasAnswered) {
            toast.error('Time\'s up!');
            setAnswerResult({
                is_correct: false,
                points_earned: 0,
                message: 'Time expired',
            });
        }
    };

    const handleRequestHint = () => {
        if (!usedHint && currentQuestion) {
            websocketManager.requestHint(currentQuestion.id);
            setUsedHint(true);
        }
    };

    const handleNextQuestion = () => {
        if (isHost) {
            websocketManager.requestNextQuestion();
        }
    };

    if (!currentQuestion) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Card className="p-8 text-center">
                    <Loader2 className="w-12 h-12 animate-spin text-purple-600 mx-auto mb-4" />
                    <p className="text-lg text-gray-600">Loading question...</p>
                </Card>
            </div>
        );
    }

    const progress = ((currentQuestionIndex + 1) / totalQuestions) * 100;
    const timePercentage = (timeRemaining / (currentQuestion.time_limit || 30)) * 100;
    const timeColor = timePercentage > 50 ? 'bg-green-500' : timePercentage > 25 ? 'bg-yellow-500' : 'bg-red-500';

    return (
        <div className="min-h-screen py-8 px-4">
            <div className="max-w-4xl mx-auto space-y-6">
                {/* Progress Bar */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white rounded-xl p-4 shadow-lg"
                >
                    <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-gray-600">
                            Question {currentQuestionIndex + 1} of {totalQuestions}
                        </span>
                        <Badge variant="secondary">
                            <Trophy className="w-3 h-3 mr-1" />
                            Playing as {player.username}
                        </Badge>
                    </div>
                    <Progress value={progress} className="h-2" />
                </motion.div>

                {/* Timer */}
                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="bg-white rounded-xl p-6 shadow-lg"
                >
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                            <Clock className={`w-6 h-6 ${timePercentage < 25 ? 'text-red-500 animate-pulse' : 'text-gray-600'}`} />
                            <span className="text-2xl font-bold">
                                {timeRemaining}s
                            </span>
                        </div>
                        {!hasAnswered && !usedHint && currentQuestion.hint && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={handleRequestHint}
                                className="gap-2"
                            >
                                <Lightbulb className="w-4 h-4" />
                                Hint (-50%)
                            </Button>
                        )}
                    </div>
                    <Progress value={timePercentage} className={`h-2 ${timeColor}`} />
                </motion.div>

                {/* Question Card */}
                <motion.div
                    key={currentQuestion.id}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                >
                    <Card className="p-8 bg-gradient-to-br from-purple-50 to-pink-50">
                        <h2 className="text-2xl font-bold text-center mb-6 text-gray-900">
                            What connects these four items?
                        </h2>

                        {/* Items Grid */}
                        <div className="grid grid-cols-2 gap-4 mb-6">
                            {currentQuestion.items.map((item, idx) => (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: idx * 0.1 }}
                                    className="bg-white rounded-lg p-6 shadow-md hover:shadow-xl transition-shadow"
                                >
                                    <div className="text-center">
                                        <div className="text-3xl mb-2">{['🎯', '⭐', '💎', '🎪'][idx]}</div>
                                        <p className="text-lg font-semibold text-gray-800">{item}</p>
                                    </div>
                                </motion.div>
                            ))}
                        </div>

                        {/* Hint Display */}
                        <AnimatePresence>
                            {showHint && currentQuestion.hint && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-4 mb-6"
                                >
                                    <div className="flex items-start gap-2">
                                        <Lightbulb className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                                        <div>
                                            <p className="font-semibold text-yellow-800 mb-1">Hint:</p>
                                            <p className="text-yellow-700">{currentQuestion.hint}</p>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Answer Input */}
                        {!hasAnswered ? (
                            <div className="space-y-4">
                                <div className="flex gap-2">
                                    <Input
                                        ref={answerInputRef}
                                        type="text"
                                        placeholder="Type your answer..."
                                        value={currentAnswer}
                                        onChange={(e) => setCurrentAnswer(e.target.value)}
                                        onKeyPress={(e) => e.key === 'Enter' && handleSubmitAnswer()}
                                        disabled={isSubmitting || timeRemaining === 0}
                                        className="text-lg"
                                        autoFocus
                                    />
                                    <Button
                                        onClick={handleSubmitAnswer}
                                        disabled={!currentAnswer.trim() || isSubmitting || timeRemaining === 0}
                                        className="bg-gradient-to-r from-purple-600 to-pink-600"
                                    >
                                        {isSubmitting ? (
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                        ) : (
                                            <>
                                                <Send className="w-5 h-5 mr-2" />
                                                Submit
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        ) : (
                            /* Answer Result */
                            <motion.div
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className={`rounded-lg p-6 ${
                                    hasAnswered && currentAnswer
                                        ? 'bg-green-50 border-2 border-green-300'
                                        : 'bg-red-50 border-2 border-red-300'
                                }`}
                            >
                                <div className="flex items-center justify-center gap-3 mb-4">
                                    {hasAnswered && currentAnswer ? (
                                        <>
                                            <CheckCircle className="w-8 h-8 text-green-600" />
                                            <p className="text-2xl font-bold text-green-800">
                                                Correct!
                                            </p>
                                        </>
                                    ) : (
                                        <>
                                            <XCircle className="w-8 h-8 text-red-600" />
                                            <p className="text-2xl font-bold text-red-800">
                                                {timeRemaining === 0 ? "Time's Up!" : "Incorrect"}
                                            </p>
                                        </>
                                    )}
                                </div>

                                <div className="text-center space-y-2">
                                    <p className="text-lg">
                                        <span className="font-semibold">Correct Answer:</span>{' '}
                                        <span className="text-gray-800">{currentQuestion.correct_answer}</span>
                                    </p>

                                    {isHost && (
                                        <Button
                                            onClick={handleNextQuestion}
                                            className="mt-4"
                                            variant="outline"
                                        >
                                            Next Question →
                                        </Button>
                                    )}
                                    {!isHost && (
                                        <p className="text-sm text-gray-600 mt-4">
                                            Waiting for host to continue...
                                        </p>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </Card>
                </motion.div>

                {/* Mini Leaderboard */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                >
                    <Card className="p-4">
                        <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                            <Trophy className="w-5 h-5 text-purple-600" />
                            Current Standings
                        </h3>
                        <div className="space-y-2">
                            {leaderboard.slice(0, 5).map((playerScore, idx) => (
                                <div
                                    key={playerScore.player_id}
                                    className={`flex items-center justify-between p-2 rounded ${
                                        playerScore.player_id === player.id ? 'bg-purple-50' : 'bg-gray-50'
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <span className="text-lg font-bold text-gray-400">#{idx + 1}</span>
                                        <span className="font-medium">{playerScore.player_name}</span>
                                    </div>
                                    <Badge variant="secondary">{playerScore.total_score} pts</Badge>
                                </div>
                            ))}
                        </div>
                    </Card>
                </motion.div>
            </div>
        </div>
    );
}