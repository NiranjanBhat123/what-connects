import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export const useGameStore = create(
    persist(
        (set, get) => ({
            // Player state
            player: null,
            setPlayer: (player) => {
                console.log('Setting player:', player);
                set({ player });
            },
            clearPlayer: () => {
                console.log('Clearing player');
                set({ player: null });
            },

            // Room state
            room: null,
            roomCode: null,
            players: [],
            isHost: false,
            setRoom: (room) => {
                if (!room) {
                    console.warn('Attempted to set null/undefined room');
                    return;
                }

                // Handle both room object and room_state from WebSocket
                const roomCode = room.code || room.room_code;
                const roomPlayers = room.players || [];

                if (!roomCode) {
                    console.error('Room object missing code:', room);
                    return;
                }

                const currentPlayer = get().player;
                const hostId = room.host?.id || room.host_id;
                const isHost = currentPlayer && hostId === currentPlayer.id;

                console.log('Setting room:', roomCode, 'isHost:', isHost);
                set({
                    room,
                    roomCode,
                    players: roomPlayers,
                    isHost,
                });
            },
            updatePlayers: (players) => set({ players }),
            clearRoom: () => {
                console.log('Clearing room');
                set({
                    room: null,
                    roomCode: null,
                    players: [],
                    isHost: false,
                });
            },

            // Game state
            game: null,
            gameStatus: 'waiting', // waiting | active | completed
            currentQuestion: null,
            currentQuestionIndex: 0,
            totalQuestions: 0,
            timeRemaining: 30,
            usedHint: false,

            setGame: (game) => set({
                game,
                gameStatus: game.status,
                totalQuestions: game.total_questions || 0,
            }),

            setCurrentQuestion: (question, index) => set({
                currentQuestion: question,
                currentQuestionIndex: index,
                timeRemaining: question?.time_limit || 30,
                usedHint: false,
            }),

            decrementTime: () => {
                const timeRemaining = get().timeRemaining;
                if (timeRemaining > 0) {
                    set({ timeRemaining: timeRemaining - 1 });
                }
            },

            setUsedHint: (used) => set({ usedHint: used }),

            resetTimer: (timeLimit = 30) => set({ timeRemaining: timeLimit }),

            // Answer state
            currentAnswer: '',
            hasAnswered: false,
            answerResult: null,

            setCurrentAnswer: (answer) => set({ currentAnswer: answer }),

            setAnswerResult: (result) => set({
                hasAnswered: true,
                answerResult: result,
            }),

            clearAnswer: () => set({
                currentAnswer: '',
                hasAnswered: false,
                answerResult: null,
            }),

            // Leaderboard
            leaderboard: [],
            setLeaderboard: (leaderboard) => set({ leaderboard }),

            // UI state
            showHint: false,
            toggleHint: () => set((state) => ({ showHint: !state.showHint })),
            setShowHint: (show) => set({ showHint: show }),

            // Chat messages
            chatMessages: [],
            addChatMessage: (message) => set((state) => ({
                chatMessages: [...state.chatMessages, message],
            })),
            clearChatMessages: () => set({ chatMessages: [] }),

            // Reset everything
            resetGame: () => set({
                game: null,
                gameStatus: 'waiting',
                currentQuestion: null,
                currentQuestionIndex: 0,
                totalQuestions: 0,
                timeRemaining: 30,
                usedHint: false,
                currentAnswer: '',
                hasAnswered: false,
                answerResult: null,
                leaderboard: [],
                showHint: false,
                chatMessages: [],
            }),
        }),
        {
            name: 'whatconnects-storage',
            storage: createJSONStorage(() => localStorage),
            partialize: (state) => ({
                // Only persist player and room info
                player: state.player,
                roomCode: state.roomCode,
                room: state.room,
            }),
            // Add version for migrations
            version: 1,
            // Merge function to handle rehydration
            merge: (persistedState, currentState) => {
                console.log('Rehydrating state:', persistedState);
                return {
                    ...currentState,
                    ...persistedState,
                };
            },
        }
    )
);

// Debug: Log state changes
if (typeof window !== 'undefined') {
    useGameStore.subscribe((state) => {
        console.log('Store updated:', {
            player: state.player,
            roomCode: state.roomCode,
        });
    });
}

export default useGameStore;