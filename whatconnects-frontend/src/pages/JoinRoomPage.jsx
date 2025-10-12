import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LogIn, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { toast } from 'sonner';
import { useGameStore } from '@/store/gameStore';
import { roomAPI } from '@/services/api';

export function JoinRoomPage() {
    const navigate = useNavigate();
    const { player, setRoom } = useGameStore();
    const [roomCode, setRoomCode] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleJoinRoom = async (e) => {
        e.preventDefault();

        if (!player) {
            toast.error('Please create a username first');
            navigate('/');
            return;
        }

        const code = roomCode.trim().toUpperCase();
        if (code.length !== 6) {
            toast.error('Room code must be 6 characters');
            return;
        }

        setIsLoading(true);
        try {
            // First check if room exists
            const roomResponse = await roomAPI.get(code);

            // Then join the room
            const joinResponse = await roomAPI.join(code, player.id);
            setRoom(joinResponse.data);

            toast.success('Joined room successfully!');
            navigate(`/room/${code}`);
        } catch (error) {
            const errorData = error.response?.data?.error;
            if (errorData?.code === 'room_full') {
                toast.error('Room is full');
            } else if (errorData?.code === 'game_already_started') {
                toast.error('Game has already started');
            } else if (error.response?.status === 404) {
                toast.error('Room not found');
            } else {
                toast.error('Failed to join room');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-md"
            >
                <Button
                    variant="ghost"
                    onClick={() => navigate('/')}
                    className="mb-4"
                >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back
                </Button>

                <Card className="p-8">
                    <div className="text-center mb-6">
                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 mb-4">
                            <LogIn className="w-8 h-8 text-white" />
                        </div>
                        <h1 className="text-3xl font-bold mb-2">Join Room</h1>
                        <p className="text-gray-600">Enter a room code to join</p>
                    </div>

                    <form onSubmit={handleJoinRoom} className="space-y-6">
                        <div className="space-y-2">
                            <Label htmlFor="roomCode">Room Code</Label>
                            <Input
                                id="roomCode"
                                placeholder="ABC123"
                                value={roomCode}
                                onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                                maxLength={6}
                                className="text-center text-2xl font-bold tracking-wider"
                                required
                                autoFocus
                            />
                            <p className="text-sm text-gray-500 text-center">
                                Enter the 6-character code
                            </p>
                        </div>

                        <Button
                            type="submit"
                            className="w-full bg-gradient-to-r from-blue-600 to-cyan-600"
                            disabled={isLoading || roomCode.length !== 6}
                        >
                            {isLoading ? 'Joining...' : 'Join Room'}
                        </Button>
                    </form>
                </Card>
            </motion.div>
        </div>
    );
}

export default JoinRoomPage;