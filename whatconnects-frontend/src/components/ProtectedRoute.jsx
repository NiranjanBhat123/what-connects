import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useGameStore } from '@/store/gameStore';

/**
 * ProtectedRoute component that checks if user has a player session
 * If not, redirects to home page
 */
export default function ProtectedRoute({ children }) {
    const { player } = useGameStore();
    const location = useLocation();

    // Debug log
    console.log('ProtectedRoute check:', {
        hasPlayer: !!player,
        player: player,
        path: location.pathname
    });

    if (!player) {
        console.warn('No player found, redirecting to home from:', location.pathname);
        // Redirect to home page if no player exists
        return <Navigate to="/" replace state={{ from: location }} />;
    }

    // Render children if player exists
    return children;
}