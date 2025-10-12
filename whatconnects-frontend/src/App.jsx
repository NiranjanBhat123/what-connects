import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

// Pages
import HomePage from './pages/HomePage';
import CreateRoomPage from './pages/CreateRoomPage';
import JoinRoomPage from './pages/JoinRoomPage';
import RoomLobbyPage from './pages/RoomLobbyPage';
import GamePlayPage from './pages/GamePlayPage';
import GameResultsPage from './pages/GameResultsPage';

// Create Query Client
const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 5 * 60 * 1000, // 5 minutes
        },
    },
});

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <BrowserRouter>
                <div className="min-h-screen bg-gradient-to-br from-purple-100 via-pink-100 to-blue-100">
                    <Routes>
                        {/* All Routes */}
                        <Route path="/" element={<HomePage />} />
                        <Route path="/create" element={<CreateRoomPage />} />
                        <Route path="/join" element={<JoinRoomPage />} />
                        <Route path="/room/:code" element={<RoomLobbyPage />} />
                        <Route path="/game/:code" element={<GamePlayPage />} />
                        <Route path="/results/:code" element={<GameResultsPage />} />

                        {/* Fallback */}
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>

                    {/* Toast Notifications */}
                    <Toaster
                        position="top-center"
                        richColors
                        closeButton
                        duration={3000}
                    />
                </div>
            </BrowserRouter>
        </QueryClientProvider>
    );
}

export default App;