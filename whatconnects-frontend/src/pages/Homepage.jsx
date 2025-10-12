import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, Users, Trophy, Zap, Plus, LogIn, Github } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { playerAPI } from '@/services/api';
import { useGameStore } from '@/store/gameStore';

export default function HomePage() {
    const navigate = useNavigate();
    const { player, setPlayer } = useGameStore();
    const [showUsernameModal, setShowUsernameModal] = useState(false);
    const [username, setUsername] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [nextAction, setNextAction] = useState(null);

    const features = [
        {
            icon: Users,
            title: 'Multiplayer Fun',
            description: 'Play with friends or meet new people in real-time game rooms',
            color: 'from-purple-500 to-pink-500',
        },
        {
            icon: Zap,
            title: 'Fast-Paced',
            description: 'Quick rounds with time limits keep the energy high',
            color: 'from-blue-500 to-cyan-500',
        },
        {
            icon: Trophy,
            title: 'Compete & Win',
            description: 'Climb the leaderboard and prove your connection skills',
            color: 'from-orange-500 to-red-500',
        },
        {
            icon: Sparkles,
            title: 'AI-Generated',
            description: 'Fresh questions powered by Gemini AI every game',
            color: 'from-green-500 to-emerald-500',
        },
    ];

    const handleAction = (action) => {
        if (!player) {
            setNextAction(action);
            setShowUsernameModal(true);
        } else {
            navigate(action);
        }
    };

    const handleCreatePlayer = async () => {
        if (!username.trim() || username.length < 3) {
            toast.error('Username must be at least 3 characters');
            return;
        }

        setIsLoading(true);
        try {
            const response = await playerAPI.create(username.trim());
            setPlayer(response.data);
            toast.success(`Welcome, ${username}!`);
            setShowUsernameModal(false);

            if (nextAction) {
                navigate(nextAction);
            }
        } catch (error) {
            const errorMsg = error.response?.data?.error || 'Failed to create player';
            toast.error(errorMsg);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen relative overflow-hidden">
            {/* Animated Background */}
            <div className="absolute inset-0 bg-gradient-to-br from-purple-600 via-pink-500 to-blue-600 opacity-90" />
            <div className="absolute inset-0">
                {[...Array(20)].map((_, i) => (
                    <motion.div
                        key={i}
                        className="absolute rounded-full bg-white opacity-10"
                        style={{
                            width: Math.random() * 100 + 50,
                            height: Math.random() * 100 + 50,
                            left: `${Math.random() * 100}%`,
                            top: `${Math.random() * 100}%`,
                        }}
                        animate={{
                            y: [0, Math.random() * 100 - 50],
                            x: [0, Math.random() * 100 - 50],
                            scale: [1, 1.2, 1],
                        }}
                        transition={{
                            duration: Math.random() * 10 + 10,
                            repeat: Infinity,
                            repeatType: 'reverse',
                        }}
                    />
                ))}
            </div>

            {/* Content */}
            <div className="relative z-10 container mx-auto px-4 py-12">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -50 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center mb-16"
                >
                    <motion.div
                        className="inline-flex items-center gap-3 mb-6"
                        animate={{ scale: [1, 1.05, 1] }}
                        transition={{ duration: 2, repeat: Infinity }}
                    >
                        <Sparkles className="w-12 h-12 text-yellow-300" />
                        <h1 className="text-6xl font-bold text-white">
                            WhatConnects
                        </h1>
                        <Sparkles className="w-12 h-12 text-yellow-300" />
                    </motion.div>

                    <p className="text-xl text-white/90 mb-8 max-w-2xl mx-auto">
                        Find the hidden connections! A multiplayer trivia game where you discover what links four seemingly random items.
                    </p>

                    {player && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="bg-white/20 backdrop-blur-sm rounded-full px-6 py-2 inline-block mb-4"
                        >
              <span className="text-white font-medium">
                Playing as: <span className="font-bold">{player.username}</span>
              </span>
                        </motion.div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                        <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                            <Button
                                size="lg"
                                className="bg-white text-purple-600 hover:bg-gray-100 text-lg px-8 py-6 rounded-xl shadow-xl"
                                onClick={() => handleAction('/create')}
                            >
                                <Plus className="w-5 h-5 mr-2" />
                                Create Room
                            </Button>
                        </motion.div>

                        <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                            <Button
                                size="lg"
                                variant="outline"
                                className="bg-transparent border-2 border-white text-white hover:bg-white/20 text-lg px-8 py-6 rounded-xl"
                                onClick={() => handleAction('/join')}
                            >
                                <LogIn className="w-5 h-5 mr-2" />
                                Join Room
                            </Button>
                        </motion.div>
                    </div>
                </motion.div>

                {/* Features Grid */}
                <motion.div
                    initial={{ opacity: 0, y: 50 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12"
                >
                    {features.map((feature, idx) => (
                        <motion.div
                            key={idx}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 + idx * 0.1 }}
                            whileHover={{ y: -10 }}
                        >
                            <Card className="bg-white/10 backdrop-blur-md border-white/20 p-6 h-full">
                                <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4`}>
                                    <feature.icon className="w-6 h-6 text-white" />
                                </div>
                                <h3 className="text-xl font-bold text-white mb-2">{feature.title}</h3>
                                <p className="text-white/80 text-sm">{feature.description}</p>
                            </Card>
                        </motion.div>
                    ))}
                </motion.div>

                {/* How to Play */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.6 }}
                    className="bg-white/10 backdrop-blur-md rounded-2xl p-8 max-w-3xl mx-auto"
                >
                    <h2 className="text-3xl font-bold text-white mb-6 text-center">How to Play</h2>
                    <div className="space-y-4 text-white/90">
                        <div className="flex items-start gap-4">
                            <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center flex-shrink-0 font-bold">1</div>
                            <p>Create or join a game room with up to 6 players</p>
                        </div>
                        <div className="flex items-start gap-4">
                            <div className="w-8 h-8 rounded-full bg-pink-500 flex items-center justify-center flex-shrink-0 font-bold">2</div>
                            <p>Each round, you'll see 4 items that share a common connection</p>
                        </div>
                        <div className="flex items-start gap-4">
                            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0 font-bold">3</div>
                            <p>Type your answer before time runs out to earn points</p>
                        </div>
                        <div className="flex items-start gap-4">
                            <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0 font-bold">4</div>
                            <p>Compete on the leaderboard and become the connection master!</p>
                        </div>
                    </div>
                </motion.div>

                {/* Footer */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.8 }}
                    className="text-center mt-12 text-white/60"
                >
                    <p className="mb-2">Built with React, Django, and Gemini AI</p>
                    <a
                        href="https://github.com"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 hover:text-white transition-colors"
                    >
                        <Github className="w-4 h-4" />
                        View on GitHub
                    </a>
                </motion.div>
            </div>

            {/* Username Modal */}
            <Dialog open={showUsernameModal} onOpenChange={setShowUsernameModal}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Choose Your Username</DialogTitle>
                        <DialogDescription>
                            Pick a username to start playing. Make it memorable!
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <Input
                            placeholder="Enter username (min 3 characters)"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleCreatePlayer()}
                            maxLength={50}
                            className="text-lg"
                            autoFocus
                        />
                        <Button
                            onClick={handleCreatePlayer}
                            disabled={isLoading || username.length < 3}
                            className="w-full"
                        >
                            {isLoading ? 'Creating...' : 'Continue'}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}