import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Plus, ArrowLeft, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { toast } from 'sonner';
import { useGameStore } from '@/store/gameStore';
import { roomAPI } from '@/services/api';

export default function CreateRoomPage() {
    const navigate = useNavigate();
    const { player, setRoom } = useGameStore();
    const [roomName, setRoomName] = useState('');
    const [maxPlayers, setMaxPlayers] = useState(6);
    const [isLoading, setIsLoading] = useState(false);

    const handleCreateRoom = async (e) => {
        e.preventDefault();

        if (!player) {
            toast.error('Please create a username first');
            navigate('/');
            return;
        }

        if (!roomName.trim()) {
            toast.error('Room name is required');
            return;
        }

        setIsLoading(true);
        try {
            const response = await roomAPI.create({
                name: roomName.trim(),
                max_players: maxPlayers,
                host_id: player.id,
            });

            setRoom(response.data);
            toast.success('Room created successfully!');
            navigate(`/room/${response.data.code}`);
        } catch (error) {
            const errorMsg = error.response?.data?.error || 'Failed to create room';
            toast.error(errorMsg);
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
                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 mb-4">
                            <Plus className="w-8 h-8 text-white" />
                        </div>
                        <h1 className="text-3xl font-bold mb-2">Create Room</h1>
                        <p className="text-gray-600">Set up a new game room</p>
                    </div>

                    <form onSubmit={handleCreateRoom} className="space-y-6">
                        <div className="space-y-2">
                            <Label htmlFor="roomName">Room Name</Label>
                            <Input
                                id="roomName"
                                placeholder="My Awesome Game Room"
                                value={roomName}
                                onChange={(e) => setRoomName(e.target.value)}
                                maxLength={100}
                                required
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="maxPlayers">Maximum Players</Label>
                            <div className="flex gap-2">
                                {[2, 4, 6, 8, 10].map((num) => (
                                    <Button
                                        key={num}
                                        type="button"
                                        variant={maxPlayers === num ? 'default' : 'outline'}
                                        onClick={() => setMaxPlayers(num)}
                                        className="flex-1"
                                    >
                                        {num}
                                    </Button>
                                ))}
                            </div>
                            <p className="text-sm text-gray-500">
                                <Users className="w-3 h-3 inline mr-1" />
                                {maxPlayers} players maximum
                            </p>
                        </div>

                        <Button
                            type="submit"
                            className="w-full bg-gradient-to-r from-purple-600 to-pink-600"
                            disabled={isLoading}
                        >
                            {isLoading ? 'Creating...' : 'Create Room'}
                        </Button>
                    </form>
                </Card>
            </motion.div>
        </div>
    );
}