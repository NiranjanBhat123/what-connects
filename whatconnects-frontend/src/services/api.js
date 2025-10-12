import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Player API
export const playerAPI = {
    create: (username) => api.post('/users/create/', { username }),
    get: (playerId) => api.get(`/users/${playerId}/`),
    validate: (playerId) => api.get(`/users/${playerId}/validate/`),
};

// Room API
export const roomAPI = {
    create: (data) => api.post('/rooms/create/', data),
    get: (code) => api.get(`/rooms/${code}/`),
    join: (code, playerId) => api.post(`/rooms/${code}/join/`, { player_id: playerId }),
    leave: (code, playerId) => api.post(`/rooms/${code}/leave/`, { player_id: playerId }),
    start: (code, playerId) => api.post(`/rooms/${code}/start/`, { player_id: playerId }),
    toggleReady: (code, playerId) => api.post(`/rooms/${code}/ready/`, { player_id: playerId }),
};

// Game API
export const gameAPI = {
    get: (gameId) => api.get(`/games/${gameId}/`),
    getCurrentQuestion: (gameId) => api.get(`/games/${gameId}/current-question/`),
    submitAnswer: (gameId, data) => api.post(`/games/${gameId}/answer/`, data),
    nextQuestion: (gameId, playerId) => api.post(`/games/${gameId}/next-question/`, { player_id: playerId }),
    getLeaderboard: (gameId) => api.get(`/games/${gameId}/leaderboard/`),
    getQuestions: (gameId) => api.get(`/games/${gameId}/questions/`),
};

// Health check
export const healthCheck = () => api.get('/health/');

export default api;