import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Users, Copy, Check, Crown, LogOut, Play, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { useGameStore } from '@/store/gameStore';
import { roomAPI } from '@/services/api';
import { websocketManager } from '@/services/websocket';

export default function RoomLobbyPage() {
    const { code } = useParams();
    const navigate = useNavigate();
    const { player, room, setRoom, isHost } = useGameStore();

    const [copied, setCopied] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);
    const [localPlayers, setLocalPlayers] = useState([]);

    // Refs to prevent double-mounting issues
    const isInitialized = useRef(false);
    const cleanupTimeout = useRef(null);

    useEffect(() => {
        // Only initialize once
        if (isInitialized.current) {
            console.log('Already initialized, skipping');
            return;
        }

        if (!player) {
            console.log('No player, redirecting to home');
            navigate('/');
            return;
        }

        isInitialized.current = true;
        console.log('Initializing RoomLobby for code:', code, 'player:', player.username);

        loadRoom();
        setupWebSocket();

        return () => {
            console.log('RoomLobby cleanup triggered');

            // Delay cleanup to prevent issues with React's double-invoke
            cleanupTimeout.current = setTimeout(() => {
                console.log('Executing delayed cleanup');
                websocketManager.disconnect();
                isInitialized.current = false;
            }, 500);
        };
    }, []); // Empty deps - only run once

    // Cleanup effect
    useEffect(() => {
        return () => {
            if (cleanupTimeout.current) {
                clearTimeout(cleanupTimeout.current);
            }
        };
    }, []);

    // Update local players when room changes
    useEffect(() => {
        if (room && room.players) {
            setLocalPlayers(room.players);
        }
    }, [room]);

    const loadRoom = async () => {
        try {
            const response = await roomAPI.get(code);
            console.log('Room loaded:', response.data);
            setRoom(response.data);
            setLocalPlayers(response.data.players || []);
            setIsLoading(false);
        } catch (error) {
            console.error('Failed to load room:', error);
            toast.error('Failed to load room');
            navigate('/');
        }
    };

    const setupWebSocket = () => {
        console.log('Setting up WebSocket connection...');

        websocketManager.connect(code, player.id).then(() => {
            console.log('WebSocket connected successfully');
        }).catch((error) => {
            console.error('WebSocket connection failed:', error);
            toast.error('Failed to connect to game server');
        });

        // Handle player joined
        websocketManager.on('player_joined', (data) => {
            console.log('Player joined event:', data);

            if (data.player_id !== player.id) {
                toast.success(`${data.player_name} joined the room`);
            }

            if (data.room_state) {
                const roomState = {
                    ...data.room_state,
                    code: data.room_state.code || data.room_state.room_code || code,
                    players: data.room_state.players || []
                };
                setRoom(roomState);
                setLocalPlayers(roomState.players);
            }
        });

        // Handle player left
        websocketManager.on('player_left', (data) => {
            console.log('Player left event:', data);
            toast.info(`${data.player_name} left the room`);

            if (data.room_state) {
                setRoom(data.room_state);
                setLocalPlayers(data.room_state.players || []);
            }
        });

        // Handle room state updates
        websocketManager.on('room_state_update', (data) => {
            console.log('Room state update:', data);
            if (data.state) {
                // Ensure state has all required fields
                const roomState = {
                    ...data.state,
                    code: data.state.code || data.state.room_code || code,
                    players: data.state.players || []
                };
                setRoom(roomState);
                setLocalPlayers(roomState.players);
            }
        });

        websocketManager.on('game_started', (data) => {
            console.log('🎮 Game started event received:', data);

            // Stop the loading state
            setIsStarting(false);

            // Show success message
            toast.success('Game is starting!');

            // CRITICAL: Set flag to prevent cleanup
            isInitialized.current = false;

             // Navigate WITH the question data in state
            console.log('Navigating to game page...');
            navigate(`/game/${code}`, {
                replace: true,
                state: {
                    question: data.question,
                    totalQuestions: data.totalQuestions
                }
            });
        });

        // Handle game state updates
        websocketManager.on('game_state_update', (data) => {
            console.log('Game state update received:', data);
            if (data.state && data.state.room_status === 'in_progress') {
                console.log('Room status changed to in_progress');
            }
        });

        // Handle errors
        websocketManager.on('error', (data) => {
            console.error('WebSocket error:', data);
            toast.error(data.message || 'Connection error');
            setIsStarting(false);
        });

        // Handle connection status
        websocketManager.on('connected', () => {
            console.log('✅ WebSocket connected event');
        });

        websocketManager.on('disconnected', (data) => {
            console.log('❌ WebSocket disconnected event:', data);
            if (data.code !== 1000) {
                // Only show error if not a normal closure
                toast.error('Connection lost');
            }
        });
    };

    const copyRoomCode = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        toast.success('Room code copied!');
        setTimeout(() => setCopied(false), 2000);
    };

    const handleLeaveRoom = async () => {
        try {
            await roomAPI.leave(code, player.id);
            websocketManager.disconnect();
            toast.success('Left room');
            navigate('/');
        } catch (error) {
            console.error('Failed to leave room:', error);
            toast.error('Failed to leave room');
        }
    };

    const handleStartGame = async () => {
        if (!isHost) {
            toast.error('Only the host can start the game');
            return;
        }

        if (localPlayers.length < 2) {
            toast.error('Need at least 2 players to start');
            return;
        }

        setIsStarting(true);
        console.log('Starting game...');

        try {
            const response = await roomAPI.start(code, player.id);
            console.log('Start game response:', response.data);
            toast.info('Generating questions...');
        } catch (error) {
            console.error('Start game error:', error);
            setIsStarting(false);

            const errorData = error.response?.data?.error;
            if (errorData) {
                toast.error(errorData.message || 'Failed to start game');
            } else {
                toast.error('Failed to start game');
            }
        }
    };

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="w-12 h-12 animate-spin text-purple-600" />
            </div>
        );
    }

    const canStart = localPlayers.length >= 2 && isHost && room?.status === 'waiting';
    const playerCount = localPlayers.length;

    return (
        <div className="min-h-screen py-12 px-4">
            <div className="max-w-4xl mx-auto space-y-6">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center space-y-4"
                >
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                        {room?.name}
                    </h1>

                    <div className="inline-flex items-center gap-3 bg-white rounded-2xl px-6 py-3 shadow-lg">
                        <span className="text-gray-600 font-medium">Room Code:</span>
                        <span className="text-3xl font-bold text-purple-600 tracking-wider">{code}</span>
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={copyRoomCode}
                            className="hover:bg-purple-50"
                        >
                            {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                        </Button>
                    </div>

                    <p className="text-gray-600">
                        Share this code with friends to invite them!
                    </p>
                </motion.div>

                {/* Players Grid */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                >
                    <Card className="p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-2xl font-bold flex items-center gap-2">
                                <Users className="w-6 h-6 text-purple-600" />
                                Players ({playerCount}/{room?.max_players})
                            </h2>
                            {room?.status === 'waiting' && (
                                <Badge variant="secondary" className="text-lg px-4 py-1">
                                    Waiting to start
                                </Badge>
                            )}
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                            {localPlayers.map((roomPlayer, idx) => {
                                const playerId = roomPlayer.player?.id || roomPlayer.id || roomPlayer.player_id;
                                const playerName = roomPlayer.username || roomPlayer.player?.username || roomPlayer.player_name;
                                const isPlayerHost = playerId === room?.host?.id || roomPlayer.is_host;
                                const isCurrentPlayer = playerId === player.id;

                                return (
                                    <motion.div
                                        key={playerId || idx}
                                        initial={{ opacity: 0, scale: 0.8 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ delay: idx * 0.05 }}
                                        className={`relative p-4 rounded-xl border-2 ${
                                            isCurrentPlayer
                                                ? 'border-purple-500 bg-purple-50'
                                                : 'border-gray-200 bg-white'
                                        }`}
                                    >
                                        {isPlayerHost && (
                                            <Crown className="absolute -top-2 -right-2 w-6 h-6 text-yellow-500 fill-yellow-500" />
                                        )}

                                        <div className="flex flex-col items-center gap-2">
                                            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white text-2xl font-bold">
                                                {(playerName || 'U')[0].toUpperCase()}
                                            </div>
                                            <div className="text-center">
                                                <p className="font-semibold text-gray-900">
                                                    {playerName}
                                                </p>
                                                {isPlayerHost && (
                                                    <p className="text-xs text-yellow-600 font-medium">Host</p>
                                                )}
                                                {isCurrentPlayer && (
                                                    <p className="text-xs text-purple-600 font-medium">You</p>
                                                )}
                                            </div>
                                        </div>
                                    </motion.div>
                                );
                            })}

                            {/* Empty Slots */}
                            {[...Array(Math.max(0, (room?.max_players || 6) - playerCount))].map((_, idx) => (
                                <motion.div
                                    key={`empty-${idx}`}
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: (playerCount + idx) * 0.05 }}
                                    className="p-4 rounded-xl border-2 border-dashed border-gray-300 bg-gray-50 flex items-center justify-center"
                                >
                                    <Users className="w-8 h-8 text-gray-400" />
                                </motion.div>
                            ))}
                        </div>
                    </Card>
                </motion.div>

                {/* Game Info */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                >
                    <Card className="p-6 bg-gradient-to-r from-purple-50 to-pink-50">
                        <h3 className="text-xl font-bold mb-4">Game Rules</h3>
                        <ul className="space-y-2 text-gray-700">
                            <li className="flex items-start gap-2">
                                <span className="text-purple-600 font-bold">•</span>
                                <span>10 questions per game</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-purple-600 font-bold">•</span>
                                <span>30 seconds to answer each question</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-purple-600 font-bold">•</span>
                                <span>100 points for correct answers, 50 with hint</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-purple-600 font-bold">•</span>
                                <span>Highest score wins!</span>
                            </li>
                        </ul>
                    </Card>
                </motion.div>

                {/* Action Buttons */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="flex gap-4"
                >
                    <Button
                        variant="outline"
                        onClick={handleLeaveRoom}
                        className="flex-1"
                        disabled={isStarting}
                    >
                        <LogOut className="w-4 h-4 mr-2" />
                        Leave Room
                    </Button>

                    {isHost && (
                        <Button
                            onClick={handleStartGame}
                            disabled={!canStart || isStarting}
                            className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
                        >
                            {isStarting ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Starting...
                                </>
                            ) : (
                                <>
                                    <Play className="w-4 h-4 mr-2" />
                                    Start Game
                                </>
                            )}
                        </Button>
                    )}
                </motion.div>

                {!canStart && isHost && playerCount < 2 && (
                    <p className="text-center text-sm text-gray-600">
                        Need at least 2 players to start
                    </p>
                )}

                {isStarting && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-center"
                    >
                        <p className="text-gray-600">Generating questions...</p>
                        <p className="text-sm text-gray-500 mt-1">This may take a few seconds</p>
                    </motion.div>
                )}
            </div>
        </div>
    );
}