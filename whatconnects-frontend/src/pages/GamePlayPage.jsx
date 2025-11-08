import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Lightbulb, Trophy, CheckCircle, XCircle, Loader2, TrendingUp, TrendingDown, Lock } from 'lucide-react';
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
    const [isAnswerLocked, setIsAnswerLocked] = useState(false);
    const [answerRevealed, setAnswerRevealed] = useState(false);
    const [myAnswerResult, setMyAnswerResult] = useState(null);
    const [allAnswers, setAllAnswers] = useState(null);

    // Hint state
    const [showHint, setShowHint] = useState(false);
    const [usedHint, setUsedHint] = useState(false);
    const [hintText, setHintText] = useState('');

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isLoadingQuestion, setIsLoadingQuestion] = useState(true);
    const [leaderboard, setLeaderboard] = useState([]);
    const [previousLeaderboard, setPreviousLeaderboard] = useState([]);
    const [showLeaderboardPopup, setShowLeaderboardPopup] = useState(false);

    const timerRef = useRef(null);
    const isInitialized = useRef(false);

    useEffect(() => {
        if (!player) {
            navigate('/');
            return;
        }

        if (isInitialized.current) return;
        isInitialized.current = true;

        const navigationState = window.history.state?.usr;
        if (navigationState?.question) {
            const question = navigationState.question;
            setCurrentQuestion(question);
            setCurrentQuestionIndex(0);
            setTotalQuestions(navigationState.totalQuestions || 10);
            setTimeRemaining(question.time_limit || 30);

            if (question.hint && question.hint.trim()) {
                setHintText(question.hint);
            }

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
        websocketManager.on('game_started', (data) => {
            if (data.question) {
                resetQuestionState(data.question, 0, data.total_questions);
            }
        });

        websocketManager.on('next_question', (data) => {
            if (data.question) {
                resetQuestionState(data.question, data.question_number - 1, data.total_questions);
            }
        });

        // Answer submitted - just show player answered
        websocketManager.on('answer_submitted', (data) => {
            if (data.player_id !== player?.id) {
                console.log(`✅ ${data.player_name} submitted their answer`);
            }
        });

        // Answer locked confirmation
        websocketManager.on('answer_locked', (data) => {
            console.log('🔒 Answer locked:', data.message);
            setIsAnswerLocked(true);
            setIsSubmitting(false);
        });

        // ===== ANSWERS REVEALED - ALL AT ONCE =====
        websocketManager.on('answers_revealed', (data) => {
            console.log('🔓 Answers revealed:', data);

            setAnswerRevealed(true);
            setAllAnswers(data.answers);

            // Find my result
            const myResult = data.answers.player_results?.find(
                r => r.player_id === player?.id
            );

            if (myResult) {
                setMyAnswerResult({
                    is_correct: myResult.is_correct,
                    points_earned: myResult.points_earned,
                    correct_answer: data.answers.correct_answer
                });

                if (myResult.is_correct) {
                    confetti({
                        particleCount: 100,
                        spread: 70,
                        origin: { y: 0.6 }
                    });
                }
            }
        });

        // Hint received
        websocketManager.on('hint', (data) => {
            if (data.hint && data.hint.trim()) {
                setHintText(data.hint);
                setShowHint(true);
                setUsedHint(true);
            }
        });

        // Leaderboard update
        websocketManager.on('leaderboard_update', (data) => {
            if (data.leaderboard) {
                setPreviousLeaderboard(leaderboard);
                setLeaderboard(data.leaderboard);
                setShowLeaderboardPopup(true);

                setTimeout(() => {
                    setShowLeaderboardPopup(false);
                }, 4500);
            }
        });

        websocketManager.on('game_complete', (data) => {
            setTimeout(() => {
                navigate(`/results/${code}`);
            }, 3000);
        });
    };

    const resetQuestionState = (question, index, total) => {
        setCurrentQuestion(question);
        setCurrentQuestionIndex(index);
        setTotalQuestions(total);
        setTimeRemaining(question.time_limit || 30);
        setSelectedOption(null);
        setIsAnswerLocked(false);
        setAnswerRevealed(false);
        setMyAnswerResult(null);
        setAllAnswers(null);
        setIsSubmitting(false);

        // Reset hint state
        setShowHint(false);
        setUsedHint(false);
        if (question.hint && question.hint.trim()) {
            setHintText(question.hint);
        } else {
            setHintText('');
        }

        setShowLeaderboardPopup(false);

        if (timerRef.current) {
            clearInterval(timerRef.current);
        }

        setIsLoadingQuestion(false);
    };

    // Timer continues regardless
    useEffect(() => {
        if (currentQuestion && timeRemaining > 0) {
            timerRef.current = setInterval(() => {
                setTimeRemaining(prev => {
                    const newTime = prev - 1;
                    if (newTime <= 0) {
                        clearInterval(timerRef.current);
                        // Auto-submit if selected but not submitted
                        if (!isAnswerLocked && selectedOption) {
                            handleSubmitAnswer();
                        }
                    }
                    return Math.max(0, newTime);
                });
            }, 1000);
        }

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, [currentQuestion, timeRemaining, isAnswerLocked, selectedOption]);

    const handleOptionClick = (option) => {
        if (isAnswerLocked || isSubmitting) return;
        setSelectedOption(option);
    };

    const handleSubmitAnswer = () => {
        if (!selectedOption || isAnswerLocked || isSubmitting) return;

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
        if (!usedHint && currentQuestion && !isAnswerLocked) {
            setUsedHint(true);
            websocketManager.requestHint(currentQuestion.id);
        }
    };

    const getPositionChange = (playerId) => {
        if (previousLeaderboard.length === 0) return null;

        const oldIndex = previousLeaderboard.findIndex(p => p.player_id === playerId);
        const newIndex = leaderboard.findIndex(p => p.player_id === playerId);

        if (oldIndex === -1 || newIndex === -1) return null;

        const change = oldIndex - newIndex;
        if (change > 0) return { direction: 'up', amount: change };
        if (change < 0) return { direction: 'down', amount: Math.abs(change) };
        return null;
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
            <div className="max-w-7xl mx-auto">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Main Game Area */}
                    <div className="lg:col-span-2 space-y-4">
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
                                {!isAnswerLocked && currentQuestion?.hint && currentQuestion.hint.trim() !== '' && (
                                    <button
                                        onClick={handleRequestHint}
                                        disabled={usedHint || showHint}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all font-medium ${
                                            usedHint || showHint
                                                ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                                                : 'bg-yellow-100 hover:bg-yellow-200 text-yellow-800 hover:scale-105'
                                        }`}
                                    >
                                        <Lightbulb className={`w-4 h-4 ${showHint ? 'fill-yellow-600' : ''}`} />
                                        {showHint ? 'Hint Shown' : usedHint ? 'Requesting...' : 'Show Hint'}
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
                                        initial={{ opacity: 0, scale: 0.8 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ delay: idx * 0.1 }}
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
                                {showHint && currentQuestion?.hint && currentQuestion.hint.trim() && (
                                    <motion.div
                                        initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                                        animate={{ opacity: 1, height: 'auto', marginBottom: 16 }}
                                        exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                                        className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-4 overflow-hidden"
                                    >
                                        <div className="flex items-start gap-3">
                                            <Lightbulb className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5 fill-yellow-600" />
                                            <div>
                                                <p className="font-bold text-yellow-900 mb-1">💡 Hint:</p>
                                                <p className="text-yellow-800 font-medium">{currentQuestion.hint}</p>
                                            </div>
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>

                            {/* MCQ Options */}
                            {!answerRevealed ? (
                                <div className="space-y-3 mb-4">
                                    {currentQuestion.options.map((option, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => handleOptionClick(option)}
                                            disabled={isSubmitting || isAnswerLocked}
                                            className={`w-full p-4 rounded-lg text-left font-medium transition-all ${
                                                selectedOption === option
                                                    ? isAnswerLocked
                                                        ? 'bg-gray-300 text-gray-700 cursor-not-allowed'
                                                        : 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg scale-105'
                                                    : isAnswerLocked
                                                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                                        : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:shadow-md cursor-pointer'
                                            }`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                                                    selectedOption === option
                                                        ? isAnswerLocked
                                                            ? 'bg-gray-400 text-white'
                                                            : 'bg-white text-purple-600'
                                                        : isAnswerLocked
                                                            ? 'bg-gray-300 text-gray-500'
                                                            : 'bg-gray-200 text-gray-600'
                                                }`}>
                                                    {String.fromCharCode(65 + idx)}
                                                </div>
                                                <span className="text-lg">{option}</span>
                                                {selectedOption === option && isAnswerLocked && (
                                                    <Lock className="w-5 h-5 ml-auto" />
                                                )}
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <div className="space-y-3 mb-4">
                                    {currentQuestion.options.map((option, idx) => {
                                        const correctAnswer = (myAnswerResult?.correct_answer || '').trim().toLowerCase();
                                        const optionLower = option.trim().toLowerCase();
                                        const isCorrectAnswer = optionLower === correctAnswer;
                                        const wasSelected = option === selectedOption;

                                        return (
                                            <motion.div
                                                key={idx}
                                                initial={{ opacity: 0, x: -20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: idx * 0.1 }}
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
                                            </motion.div>
                                        );
                                    })}
                                </div>
                            )}

                            {/* Submit Button or Result */}
                            {!isAnswerLocked && !answerRevealed ? (
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
                            ) : isAnswerLocked && !answerRevealed ? (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.9 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    className="rounded-lg p-6 bg-blue-50 border-2 border-blue-300"
                                >
                                    <div className="text-center space-y-3">
                                        <div className="flex items-center justify-center gap-3">
                                            <Lock className="w-10 h-10 text-blue-600 animate-pulse" />
                                            <p className="text-2xl font-bold text-blue-800">
                                                Answer Locked!
                                            </p>
                                        </div>
                                        <p className="text-blue-700">
                                            Waiting for timer to finish... ({timeRemaining}s)
                                        </p>
                                        <div className="flex items-center justify-center gap-2 text-sm text-blue-600">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Results will be shown to everyone at the same time
                                        </div>
                                    </div>
                                </motion.div>
                            ) : answerRevealed && myAnswerResult ? (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.9 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    className={`rounded-lg p-6 ${
                                        myAnswerResult?.is_correct
                                            ? 'bg-green-50 border-2 border-green-300'
                                            : 'bg-red-50 border-2 border-red-300'
                                    }`}
                                >
                                    <div className="text-center space-y-3">
                                        <div className="flex items-center justify-center gap-3">
                                            {myAnswerResult?.is_correct ? (
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
                                                        Incorrect
                                                    </p>
                                                </>
                                            )}
                                        </div>

                                        <p className="text-xl">
                                            <span className={`font-bold ${
                                                (myAnswerResult?.points_earned || 0) > 0 ? 'text-green-600' :
                                                    (myAnswerResult?.points_earned || 0) < 0 ? 'text-red-600' :
                                                        'text-gray-600'
                                            }`}>
                                                {(myAnswerResult?.points_earned || 0) > 0 ? '+' : ''}
                                                {myAnswerResult?.points_earned || 0} points
                                            </span>
                                        </p>

                                        {usedHint && (
                                            <p className="text-sm text-yellow-700 flex items-center justify-center gap-2 bg-yellow-50 rounded px-3 py-1">
                                                <Lightbulb className="w-4 h-4" />
                                                Hint was used
                                            </p>
                                        )}

                                        <p className="text-sm text-gray-600 mt-4 flex items-center justify-center gap-2">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Loading leaderboard and next question...
                                        </p>
                                    </div>
                                </motion.div>
                            ) : null}
                        </motion.div>
                    </div>

                    {/* Sidebar - Leaderboard */}
                    <div className="lg:col-span-1">
                        <div className="sticky top-6">
                            <motion.div
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="bg-white rounded-xl p-6 shadow-lg"
                            >
                                <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                                    <Trophy className="w-6 h-6 text-purple-600" />
                                    Leaderboard
                                </h3>
                                {leaderboard.length > 0 ? (
                                    <div className="space-y-2">
                                        {leaderboard.map((playerScore, idx) => (
                                            <motion.div
                                                key={playerScore.player_id}
                                                layout
                                                initial={{ opacity: 0, x: -20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                                className={`flex items-center justify-between p-3 rounded-lg transition-all ${
                                                    playerScore.player_id === player?.id
                                                        ? 'bg-purple-100 border-2 border-purple-500'
                                                        : 'bg-gray-50'
                                                }`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <span className={`text-lg font-bold ${
                                                        idx === 0 ? 'text-yellow-500' :
                                                            idx === 1 ? 'text-gray-400' :
                                                                idx === 2 ? 'text-orange-600' :
                                                                    'text-gray-400'
                                                    }`}>
                                                        {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `#${idx + 1}`}
                                                    </span>
                                                    <span className="font-medium text-sm">
                                                        {playerScore.player_name}
                                                    </span>
                                                </div>
                                                <div className="bg-purple-600 text-white px-2 py-1 rounded-full font-bold text-sm">
                                                    {playerScore.total_score}
                                                </div>
                                            </motion.div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-gray-500 text-center py-4">
                                        Scores will appear after questions
                                    </p>
                                )}
                            </motion.div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Leaderboard Popup */}
            <AnimatePresence>
                {showLeaderboardPopup && leaderboard.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50"
                        onClick={() => setShowLeaderboardPopup(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.8, y: 50 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.8, y: 50 }}
                            className="bg-white rounded-2xl p-8 shadow-2xl max-w-md w-full"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="text-center mb-6">
                                <Trophy className="w-16 h-16 text-yellow-500 mx-auto mb-3" />
                                <h2 className="text-3xl font-bold text-gray-800">Current Standings</h2>
                                <p className="text-sm text-gray-600 mt-1">After Question {currentQuestionIndex + 1}</p>
                            </div>
                            <div className="space-y-3">
                                {leaderboard.slice(0, 5).map((playerScore, idx) => {
                                    const positionChange = getPositionChange(playerScore.player_id);

                                    return (
                                        <motion.div
                                            key={playerScore.player_id}
                                            layout
                                            initial={{ opacity: 0, x: -20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ delay: idx * 0.1 }}
                                            className={`flex items-center justify-between p-4 rounded-lg ${
                                                playerScore.player_id === player?.id
                                                    ? 'bg-purple-100 border-2 border-purple-500'
                                                    : 'bg-gray-50'
                                            }`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="flex items-center gap-2">
                                                    <span className={`text-2xl font-bold ${
                                                        idx === 0 ? 'text-yellow-500' :
                                                            idx === 1 ? 'text-gray-400' :
                                                                idx === 2 ? 'text-orange-600' :
                                                                    'text-gray-400'
                                                    }`}>
                                                        {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `#${idx + 1}`}
                                                    </span>
                                                    {positionChange && (
                                                        <span className={`text-sm font-bold ${
                                                            positionChange.direction === 'up' ? 'text-green-600' : 'text-red-600'
                                                        }`}>
                                                            {positionChange.direction === 'up' ? (
                                                                <TrendingUp className="w-4 h-4" />
                                                            ) : (
                                                                <TrendingDown className="w-4 h-4" />
                                                            )}
                                                        </span>
                                                    )}
                                                </div>
                                                <div>
                                                    <p className="font-bold text-sm">
                                                        {playerScore.player_name}
                                                    </p>
                                                    <p className="text-xs text-gray-600">
                                                        {playerScore.correct_answers || 0} correct
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="bg-purple-600 text-white px-3 py-1 rounded-full font-bold">
                                                {playerScore.total_score}
                                            </div>
                                        </motion.div>
                                    );
                                })}
                            </div>
                            <button
                                onClick={() => setShowLeaderboardPopup(false)}
                                className="mt-6 w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg font-bold hover:shadow-lg transition-all"
                            >
                                Continue
                            </button>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}