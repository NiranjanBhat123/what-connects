import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import Confetti from 'react-confetti';
import { Trophy, Medal, Award, Home, RotateCcw, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { useGameStore } from '@/store/gameStore';
import { gameAPI } from '@/services/api';

export default function GameResultsPage() {
    const { code } = useParams();
    const navigate = useNavigate();
    const { player, leaderboard, setLeaderboard } = useGameStore();
    const [showConfetti, setShowConfetti] = useState(true);
    const [windowSize, setWindowSize] = useState({
        width: window.innerWidth,
        height: window.innerHeight,
    });

    useEffect(() => {
        const handleResize = () => {
            setWindowSize({
                width: window.innerWidth,
                height: window.innerHeight,
            });
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    useEffect(() => {
        if (!player) {
            navigate('/');
            return;
        }

        loadResults();

        // Stop confetti after 5 seconds
        const timer = setTimeout(() => setShowConfetti(false), 5000);
        return () => clearTimeout(timer);
    }, []);

    const loadResults = async () => {
        try {
            // Load leaderboard if not already loaded
            if (leaderboard.length === 0) {
                const response = await gameAPI.getLeaderboard(code);
                setLeaderboard(response.data.leaderboard);
            }
        } catch (error) {
            toast.error('Failed to load results');
        }
    };

    const getMedalIcon = (rank) => {
        switch (rank) {
            case 1:
                return <Trophy className="w-8 h-8 text-yellow-500" />;
            case 2:
                return <Medal className="w-8 h-8 text-gray-400" />;
            case 3:
                return <Medal className="w-8 h-8 text-orange-600" />;
            default:
                return <Award className="w-6 h-6 text-gray-400" />;
        }
    };

    const getMedalColor = (rank) => {
        switch (rank) {
            case 1:
                return 'from-yellow-400 to-yellow-600';
            case 2:
                return 'from-gray-300 to-gray-500';
            case 3:
                return 'from-orange-400 to-orange-600';
            default:
                return 'from-gray-200 to-gray-300';
        }
    };

    const handleShare = () => {
        const text = `I just played WhatConnects and scored ${
            leaderboard.find(p => p.player_id === player.id)?.total_score || 0
        } points! Can you beat me?`;

        if (navigator.share) {
            navigator.share({
                title: 'WhatConnects Game Results',
                text: text,
            }).catch(() => {});
        } else {
            navigator.clipboard.writeText(text);
            toast.success('Results copied to clipboard!');
        }
    };

    const playerResult = leaderboard.find(p => p.player_id === player.id);
    const isWinner = playerResult?.rank === 1;

    return (
        <div className="min-h-screen py-12 px-4 relative">
            {showConfetti && (
                <Confetti
                    width={windowSize.width}
                    height={windowSize.height}
                    recycle={false}
                    numberOfPieces={500}
                />
            )}

            <div className="max-w-4xl mx-auto space-y-6">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -50 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center space-y-4"
                >
                    <motion.div
                        animate={{ rotate: [0, 10, -10, 0] }}
                        transition={{ duration: 1, repeat: 3 }}
                    >
                        <Trophy className="w-20 h-20 text-yellow-500 mx-auto" />
                    </motion.div>

                    <h1 className="text-5xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                        Game Complete!
                    </h1>

                    {isWinner ? (
                        <motion.p
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ delay: 0.3, type: 'spring' }}
                            className="text-2xl font-bold text-yellow-600"
                        >
                            🎉 Congratulations, {player.username}! You won! 🎉
                        </motion.p>
                    ) : (
                        <p className="text-xl text-gray-600">
                            Great game, {player.username}!
                        </p>
                    )}
                </motion.div>

                {/* Podium - Top 3 */}
                {leaderboard.length >= 3 && (
                    <motion.div
                        initial={{ opacity: 0, y: 50 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="grid grid-cols-3 gap-4 items-end mb-8"
                    >
                        {/* 2nd Place */}
                        <Card className="p-4 text-center bg-gradient-to-b from-gray-100 to-gray-200 h-48 flex flex-col justify-end">
                            <div className="mb-2">{getMedalIcon(2)}</div>
                            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-gray-400 to-gray-600 mx-auto mb-2 flex items-center justify-center text-white text-2xl font-bold">
                                {leaderboard[1]?.player_name?.[0]}
                            </div>
                            <p className="font-bold text-sm truncate">{leaderboard[1]?.player_name}</p>
                            <Badge variant="secondary" className="mt-1">
                                {leaderboard[1]?.total_score} pts
                            </Badge>
                        </Card>

                        {/* 1st Place */}
                        <Card className="p-4 text-center bg-gradient-to-b from-yellow-100 to-yellow-200 h-56 flex flex-col justify-end">
                            <div className="mb-2">{getMedalIcon(1)}</div>
                            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-600 mx-auto mb-2 flex items-center justify-center text-white text-3xl font-bold">
                                {leaderboard[0]?.player_name?.[0]}
                            </div>
                            <p className="font-bold truncate">{leaderboard[0]?.player_name}</p>
                            <Badge className="mt-1 bg-yellow-600">
                                {leaderboard[0]?.total_score} pts
                            </Badge>
                        </Card>

                        {/* 3rd Place */}
                        <Card className="p-4 text-center bg-gradient-to-b from-orange-100 to-orange-200 h-40 flex flex-col justify-end">
                            <div className="mb-2">{getMedalIcon(3)}</div>
                            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 mx-auto mb-2 flex items-center justify-center text-white text-xl font-bold">
                                {leaderboard[2]?.player_name?.[0]}
                            </div>
                            <p className="font-bold text-sm truncate">{leaderboard[2]?.player_name}</p>
                            <Badge variant="secondary" className="mt-1">
                                {leaderboard[2]?.total_score} pts
                            </Badge>
                        </Card>
                    </motion.div>
                )}

                {/* Full Leaderboard */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                >
                    <Card className="p-6">
                        <h2 className="text-2xl font-bold mb-4">Final Standings</h2>
                        <div className="space-y-2">
                            {leaderboard.map((result, idx) => {
                                const isCurrentPlayer = result.player_id === player.id;
                                return (
                                    <motion.div
                                        key={result.player_id}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.5 + idx * 0.1 }}
                                        className={`flex items-center justify-between p-4 rounded-lg ${
                                            isCurrentPlayer
                                                ? 'bg-purple-50 border-2 border-purple-500'
                                                : 'bg-gray-50'
                                        }`}
                                    >
                                        <div className="flex items-center gap-4">
                                            <div className="flex-shrink-0">
                                                {getMedalIcon(result.rank || idx + 1)}
                                            </div>

                                            <div className="flex items-center gap-3">
                                                <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${getMedalColor(result.rank || idx + 1)} flex items-center justify-center text-white font-bold`}>
                                                    {result.player_name[0]}
                                                </div>
                                                <div>
                                                    <p className="font-bold text-lg">
                                                        {result.player_name}
                                                        {isCurrentPlayer && (
                                                            <Badge variant="secondary" className="ml-2">You</Badge>
                                                        )}
                                                    </p>
                                                    <p className="text-sm text-gray-600">
                                                        {result.correct_answers} correct • {result.accuracy}% accuracy
                                                    </p>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="text-right">
                                            <p className="text-2xl font-bold text-purple-600">
                                                {result.total_score}
                                            </p>
                                            <p className="text-sm text-gray-600">points</p>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </div>
                    </Card>
                </motion.div>

                {/* Actions */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.6 }}
                    className="flex flex-col sm:flex-row gap-4"
                >
                    <Button
                        onClick={() => navigate('/')}
                        variant="outline"
                        className="flex-1"
                    >
                        <Home className="w-4 h-4 mr-2" />
                        Home
                    </Button>

                    <Button
                        onClick={handleShare}
                        variant="outline"
                        className="flex-1"
                    >
                        <Share2 className="w-4 h-4 mr-2" />
                        Share Results
                    </Button>

                    <Button
                        onClick={() => navigate('/create')}
                        className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600"
                    >
                        <RotateCcw className="w-4 h-4 mr-2" />
                        Play Again
                    </Button>
                </motion.div>
            </div>
        </div>
    );
}