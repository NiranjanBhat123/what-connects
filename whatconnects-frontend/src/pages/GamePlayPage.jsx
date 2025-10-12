import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Lightbulb, Trophy, CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';
import confetti from 'canvas-confetti';
import { useGameStore } from '@/store/gameStore';
import { websocketManager } from '@/services/websocket';

export default function GamePlayPage() {
    const { code } = useParams();
    const navigate = useNavigate();
    const { player } = useGameStore();

    // Game state
    const [currentQuestion, setCurrentQuestion] = useState(null);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [totalQuestions, setTotalQuestions] = useState(10);
    const [timeRemaining, setTimeRemaining] = useState(30);
    const [selectedOption, setSelectedOption] = useState(null);
    const [hasAnswered, setHasAnswered] = useState(false);
    const [answerResult, setAnswerResult] = useState(null);
    const [showHint, setShowHint] = useState(false);
    const [usedHint, setUsedHint] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isLoadingQuestion, setIsLoadingQuestion] = useState(true);
    const [leaderboard, setLeaderboard] = useState([]);
    const [showLeaderboard, setShowLeaderboard] = useState(false);
    const [isHost, setIsHost] = useState(false);

    const timerRef = useRef(null);
    const isInitialized = useRef(false);

    useEffect(() => {
        console.log('GamePlayPage mounted, player:', player);

        if (!player) {
            console.error('No player found, redirecting to home');
            navigate('/');
            return;
        }

        if (isInitialized.current) {
            return;
        }
        isInitialized.current = true;

        const navigationState = window.history.state?.usr;
        if (navigationState?.question) {
            console.log('Found question in navigation state:', navigationState.question);
            setCurrentQuestion(navigationState.question);
            setCurrentQuestionIndex(0);
            setTotalQuestions(navigationState.totalQuestions || 10);
            setTimeRemaining(navigationState.question.time_limit || 30);
            setIsLoadingQuestion(false);
        }

        setupWebSocketListeners();

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, []);

    const setupWebSocketListeners = () => {
        console.log('Setting up WebSocket listeners for game');

        websocketManager.on('game_started', (data) => {
            console.log('Game started event:', data);
            if (data.question) {
                setCurrentQuestion(data.question);
                setCurrentQuestionIndex(0);
                setTotalQuestions(data.total_questions || 10);
                setTimeRemaining(data.question.time_limit || 30);
                setIsLoadingQuestion(false);
            }
        });

        websocketManager.on('next_question', (data) => {
            console.log('Next question:', data);
            if (data.question) {
                setCurrentQuestion(data.question);
                setCurrentQuestionIndex(data.question_number - 1);
                setTimeRemaining(data.question.time_limit || 30);
                setSelectedOption(null);
                setHasAnswered(false);
                setAnswerResult(null);
                setShowHint(false);
                setUsedHint(false);
                setShowLeaderboard(false);
            }
        });

        websocketManager.on('answer_submitted', (data) => {
            console.log('Answer submitted event:', data);

            if (data.player_id === player?.id) {
                const isCorrect = data.is_correct;
                if (isCorrect) {
                    confetti({
                        particleCount: 50,
                        spread: 60,
                        origin: { y: 0.7 }
                    });
                }

                setHasAnswered(true);
                setAnswerResult({
                    is_correct: isCorrect,
                    points_earned: data.points_earned || 0,
                    total_score: data.total_score || 0,
                    correct_answer: data.correct_answer,
                    message: isCorrect ? 'Correct!' : 'Incorrect'
                });
                setIsSubmitting(false);
            }

            // Don't update leaderboard immediately - wait for timer or all_players_answered
        });

        websocketManager.on('all_players_answered', (data) => {
            console.log('All players answered:', data);
            updateLeaderboard();
        });

        websocketManager.on('question_time_ended', (data) => {
            console.log('Question time ended:', data);
            updateLeaderboard();
        });

        websocketManager.on('game_complete', (data) => {
            console.log('Game complete:', data);
            setTimeout(() => {
                navigate(`/results/${code}`);
            }, 3000);
        });

        websocketManager.on('hint', (data) => {
            console.log('Hint received:', data);
            if (data.hint && data.question_id === currentQuestion?.id) {
                setShowHint(true);
                setUsedHint(true);
                setCurrentQuestion(prev => ({
                    ...prev,
                    hint: data.hint
                }));
            }
        });

        websocketManager.on('room_state_update', (data) => {
            console.log('Room state update:', data);
            if (data.state?.players) {
                updateLeaderboardFromRoomState(data.state.players);
            }
        });

        websocketManager.on('leaderboard_update', (data) => {
            console.log('Leaderboard update:', data);
            if (data.leaderboard) {
                setLeaderboard(data.leaderboard);
                setShowLeaderboard(true);
            }
        });
    };

    const updateLeaderboard = async () => {
        try {
            const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/rooms/${code}/`);
            const roomData = await response.json();

            if (roomData.current_game?.id) {
                const leaderboardResponse = await fetch(
                    `${import.meta.env.VITE_API_BASE_URL}/api/games/${roomData.current_game.id}/leaderboard/`
                );
                const leaderboardData = await leaderboardResponse.json();

                if (leaderboardData.leaderboard) {
                    setLeaderboard(leaderboardData.leaderboard);
                    setShowLeaderboard(true);
                }
            }
        } catch (error) {
            console.error('Error fetching leaderboard:', error);
        }
    };

    const updateLeaderboardFromRoomState = (players) => {
        const sortedPlayers = [...players].sort((a, b) => b.score - a.score);
        const formattedLeaderboard = sortedPlayers.map(p => ({
            player_id: p.player_id || p.id,
            player_name: p.player_name || p.username,
            total_score: p.score || 0
        }));
        setLeaderboard(formattedLeaderboard);
        setShowLeaderboard(true);
    };

    useEffect(() => {
        if (currentQuestion && !hasAnswered && timeRemaining > 0) {
            timerRef.current = setInterval(() => {
                setTimeRemaining(prev => Math.max(0, prev - 1));
            }, 1000);
        } else {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        }

        if (timeRemaining === 0 && !hasAnswered && currentQuestion) {
            handleTimeUp();
        }

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, [timeRemaining, hasAnswered, currentQuestion]);

    useEffect(() => {
        const checkHostStatus = async () => {
            try {
                const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/rooms/${code}/`);
                const roomData = await response.json();
                setIsHost(roomData.host.id === player?.id);
            } catch (error) {
                console.error('Error checking host status:', error);
            }
        };

        if (player?.id) {
            checkHostStatus();
        }
    }, [code, player]);

    const handleTimeUp = () => {
        if (!hasAnswered && selectedOption) {
            handleSubmitAnswer();
        } else if (!hasAnswered) {
            setHasAnswered(true);
            setAnswerResult({
                is_correct: false,
                points_earned: 0,
                message: 'Time expired',
                correct_answer: currentQuestion.correct_answer
            });
        }
    };

    const handleOptionClick = (option) => {
        if (hasAnswered || isSubmitting) return;
        setSelectedOption(option);
    };

    const handleSubmitAnswer = () => {
        if (!selectedOption || hasAnswered || isSubmitting) return;

        const timeTaken = (currentQuestion.time_limit || 30) - timeRemaining;
        setIsSubmitting(true);

        websocketManager.submitAnswer(
            currentQuestion.id,
            selectedOption,
            timeTaken,
            usedHint
        );
    };

    const handleRequestHint = () => {
        if (!usedHint && currentQuestion && !hasAnswered) {
            websocketManager.requestHint(currentQuestion.id);
        }
    };

    const handleNextQuestion = () => {
        if (isHost) {
            websocketManager.requestNextQuestion();
        }
    };

    if (isLoadingQuestion || !currentQuestion) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-50 to-pink-50">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                    <Loader2 className="w-12 h-12 animate-spin text-purple-600 mx-auto mb-4" />
                    <p className="text-lg text-gray-600">Loading question...</p>
                </div>
            </div>
        );
    }

    const progress = ((currentQuestionIndex + 1) / totalQuestions) * 100;
    const timePercentage = (timeRemaining / (currentQuestion.time_limit || 30)) * 100;

    return (
        <div className="min-h-screen py-6 px-4 bg-gradient-to-br from-purple-50 to-pink-50">
            <div className="max-w-4xl mx-auto space-y-4">
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
                        <div className="flex items-center gap-2 bg-purple-100 px-3 py-1 rounded-full">
                            <Trophy className="w-4 h-4 text-purple-600" />
                            <span className="text-sm font-bold text-purple-600">
                                {player?.username || 'Player'}
                            </span>
                        </div>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-purple-600 to-pink-600 transition-all duration-300"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </motion.div>

                {/* Timer */}
                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="bg-white rounded-xl p-4 shadow-lg"
                >
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                            <Clock className={`w-6 h-6 ${timePercentage < 25 ? 'text-red-500 animate-pulse' : 'text-gray-600'}`} />
                            <span className={`text-3xl font-bold ${timePercentage < 25 ? 'text-red-500' : 'text-gray-800'}`}>
                                {timeRemaining}s
                            </span>
                        </div>
                        {!hasAnswered && !usedHint && currentQuestion.hint && (
                            <button
                                onClick={handleRequestHint}
                                className="flex items-center gap-2 px-4 py-2 bg-yellow-100 hover:bg-yellow-200 text-yellow-800 rounded-lg transition-colors font-medium"
                            >
                                <Lightbulb className="w-4 h-4" />
                                Get Hint
                            </button>
                        )}
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                        <div
                            className={`h-full transition-all duration-1000 ${
                                timePercentage > 50 ? 'bg-green-500' :
                                    timePercentage > 25 ? 'bg-yellow-500' :
                                        'bg-red-500'
                            }`}
                            style={{ width: `${timePercentage}%` }}
                        />
                    </div>
                </motion.div>

                {/* Question Card */}
                <motion.div
                    key={currentQuestion.id}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                    className="bg-white rounded-xl p-6 shadow-lg"
                >
                    <h2 className="text-2xl font-bold text-center mb-4 text-gray-900">
                        What connects these four items?
                    </h2>

                    {/* Items Grid */}
                    <div className="grid grid-cols-2 gap-3 mb-4">
                        {currentQuestion.items.map((item, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 1 }}
                                animate={{ opacity: 1 }}
                                className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg p-4 shadow-md"
                            >
                                <div className="text-center">
                                    <div className="text-xl font-bold text-purple-600 mb-1">
                                        {idx + 1}
                                    </div>
                                    <p className="text-base font-semibold text-gray-800">{item}</p>
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
                                className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-4 mb-4"
                            >
                                <div className="flex items-start gap-3">
                                    <Lightbulb className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                                    <div>
                                        <p className="font-semibold text-yellow-800 mb-1">Hint:</p>
                                        <p className="text-yellow-700">{currentQuestion.hint}</p>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* MCQ Options */}
                    {!hasAnswered ? (
                        <div className="space-y-3 mb-4">
                            {currentQuestion.options.map((option, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => handleOptionClick(option)}
                                    disabled={isSubmitting}
                                    className={`w-full p-4 rounded-lg text-left font-medium transition-all ${
                                        selectedOption === option
                                            ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg scale-105'
                                            : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:shadow-md'
                                    } ${isSubmitting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                                            selectedOption === option
                                                ? 'bg-white text-purple-600'
                                                : 'bg-gray-200 text-gray-600'
                                        }`}>
                                            {String.fromCharCode(65 + idx)}
                                        </div>
                                        <span className="text-lg">{option}</span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    ) : (
                        <div className="space-y-3 mb-4">
                            {currentQuestion.options.map((option, idx) => {
                                const correctAnswer = (answerResult?.correct_answer || currentQuestion.correct_answer || '').trim().toLowerCase();
                                const optionLower = option.trim().toLowerCase();
                                const isCorrectAnswer = optionLower === correctAnswer;
                                const wasSelected = option === selectedOption;

                                return (
                                    <div
                                        key={idx}
                                        className={`w-full p-4 rounded-lg ${
                                            isCorrectAnswer
                                                ? 'bg-green-100 border-2 border-green-500'
                                                : wasSelected && !isCorrectAnswer
                                                    ? 'bg-red-100 border-2 border-red-500'
                                                    : 'bg-gray-100'
                                        }`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                                                    isCorrectAnswer
                                                        ? 'bg-green-500 text-white'
                                                        : wasSelected && !isCorrectAnswer
                                                            ? 'bg-red-500 text-white'
                                                            : 'bg-gray-300 text-gray-600'
                                                }`}>
                                                    {String.fromCharCode(65 + idx)}
                                                </div>
                                                <span className="text-lg font-medium">{option}</span>
                                            </div>
                                            {isCorrectAnswer && (
                                                <CheckCircle className="w-6 h-6 text-green-600" />
                                            )}
                                            {wasSelected && !isCorrectAnswer && (
                                                <XCircle className="w-6 h-6 text-red-600" />
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Submit Button or Result */}
                    {!hasAnswered ? (
                        <button
                            onClick={handleSubmitAnswer}
                            disabled={!selectedOption || isSubmitting || timeRemaining === 0}
                            className={`w-full py-4 rounded-lg font-bold text-lg transition-all ${
                                selectedOption && !isSubmitting && timeRemaining > 0
                                    ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white hover:shadow-xl hover:scale-105'
                                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                            }`}
                        >
                            {isSubmitting ? (
                                <div className="flex items-center justify-center gap-2">
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    Submitting...
                                </div>
                            ) : (
                                'Submit Answer'
                            )}
                        </button>
                    ) : (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className={`rounded-lg p-6 ${
                                answerResult?.is_correct
                                    ? 'bg-green-50 border-2 border-green-300'
                                    : 'bg-red-50 border-2 border-red-300'
                            }`}
                        >
                            <div className="text-center space-y-3">
                                <div className="flex items-center justify-center gap-3">
                                    {answerResult?.is_correct ? (
                                        <>
                                            <CheckCircle className="w-10 h-10 text-green-600" />
                                            <p className="text-3xl font-bold text-green-800">
                                                Correct!
                                            </p>
                                        </>
                                    ) : (
                                        <>
                                            <XCircle className="w-10 h-10 text-red-600" />
                                            <p className="text-3xl font-bold text-red-800">
                                                {timeRemaining === 0 ? "Time's Up!" : "Incorrect"}
                                            </p>
                                        </>
                                    )}
                                </div>

                                <p className="text-xl">
                                    <span className={`font-bold ${
                                        (answerResult?.points_earned || 0) > 0 ? 'text-green-600' :
                                            (answerResult?.points_earned || 0) < 0 ? 'text-red-600' :
                                                'text-gray-600'
                                    }`}>
                                        {(answerResult?.points_earned || 0) > 0 ? '+' : ''}
                                        {answerResult?.points_earned || 0} points
                                    </span>
                                </p>

                                {!answerResult?.is_correct && answerResult?.correct_answer && (
                                    <p className="text-sm text-gray-600">
                                        Correct answer: <span className="font-bold text-green-600">{answerResult.correct_answer}</span>
                                    </p>
                                )}

                                {usedHint && (
                                    <p className="text-sm text-gray-600 flex items-center justify-center gap-2">
                                        <AlertCircle className="w-4 h-4" />
                                        Hint was used
                                    </p>
                                )}

                                {isHost ? (
                                    <button
                                        onClick={handleNextQuestion}
                                        className="mt-4 px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg font-bold hover:shadow-lg transition-all"
                                    >
                                        Next Question
                                    </button>
                                ) : (
                                    <p className="text-sm text-gray-600 mt-4 flex items-center justify-center gap-2">
                                        <Clock className="w-4 h-4 animate-pulse" />
                                        Waiting for next question...
                                    </p>
                                )}
                            </div>
                        </motion.div>
                    )}
                </motion.div>

                {/* Leaderboard */}
                {showLeaderboard && leaderboard.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-white rounded-xl p-6 shadow-lg"
                    >
                        <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                            <Trophy className="w-6 h-6 text-purple-600" />
                            Current Standings
                        </h3>
                        <div className="space-y-2">
                            {leaderboard.slice(0, 5).map((playerScore, idx) => (
                                <div
                                    key={idx}
                                    className={`flex items-center justify-between p-3 rounded-lg ${
                                        playerScore.player_id === player?.id
                                            ? 'bg-purple-100 border-2 border-purple-500'
                                            : 'bg-gray-50'
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <span className="text-xl font-bold text-gray-400">
                                            #{idx + 1}
                                        </span>
                                        <span className="font-medium">
                                            {playerScore.player_name}
                                        </span>
                                    </div>
                                    <div className="bg-purple-600 text-white px-3 py-1 rounded-full font-bold">
                                        {playerScore.total_score} pts
                                    </div>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </div>
        </div>
    );
}