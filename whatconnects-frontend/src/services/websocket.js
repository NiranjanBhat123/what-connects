/**
 * WebSocket Manager for real-time communication
 * Fixed for React StrictMode compatibility
 */

class WebSocketManager {
    constructor() {
        this.socket = null;
        this.roomCode = null;
        this.playerId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.listeners = new Map();
        this.isConnecting = false;
        this.isIntentionalDisconnect = false;
        this.connectionPromise = null;
    }

    /**
     * Connect to WebSocket
     */
    connect(roomCode, playerId) {
        // If already connected to the same room, don't reconnect
        if (this.socket &&
            this.socket.readyState === WebSocket.OPEN &&
            this.roomCode === roomCode &&
            this.playerId === playerId) {
            console.log('Already connected to this room');
            return Promise.resolve();
        }

        // If connecting, return existing promise
        if (this.isConnecting && this.connectionPromise) {
            console.log('Connection already in progress...');
            return this.connectionPromise;
        }

        // Close existing connection if connecting to different room
        if (this.socket && (this.roomCode !== roomCode || this.playerId !== playerId)) {
            console.log('Closing existing connection to different room');
            this.isIntentionalDisconnect = true;
            this.socket.close();
            this.socket = null;
        }

        this.roomCode = roomCode;
        this.playerId = playerId;
        this.isConnecting = true;
        this.isIntentionalDisconnect = false;

        // Create connection promise
        this.connectionPromise = new Promise((resolve, reject) => {
            // Construct WebSocket URL
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.hostname;
            const port = import.meta.env.VITE_WS_PORT || '8000';

            const wsUrl = `${protocol}//${host}:${port}/ws/room/${roomCode}/?player_id=${playerId}`;

            console.log('Connecting to WebSocket:', wsUrl);

            try {
                this.socket = new WebSocket(wsUrl);
                this.setupEventHandlers(resolve, reject);
            } catch (error) {
                console.error('Failed to create WebSocket:', error);
                this.isConnecting = false;
                this.connectionPromise = null;
                reject(error);
                this.handleReconnect();
            }
        });

        return this.connectionPromise;
    }

    /**
     * Setup WebSocket event handlers
     */
    setupEventHandlers(resolveConnection, rejectConnection) {
        if (!this.socket) return;

        this.socket.onopen = () => {
            console.log('WebSocket connected successfully');
            this.isConnecting = false;
            this.reconnectAttempts = 0;
            this.connectionPromise = null;
            this.emit('connected', { roomCode: this.roomCode });
            resolveConnection();
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('WebSocket message received:', data);

                if (data.type) {
                    this.emit(data.type, data);
                }
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.isConnecting = false;
            this.connectionPromise = null;
            this.emit('error', { message: 'WebSocket connection error' });
            rejectConnection(error);
        };

        this.socket.onclose = (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
            this.isConnecting = false;
            this.connectionPromise = null;
            this.emit('disconnected', { code: event.code, reason: event.reason });

            // Only attempt reconnect if not intentional disconnect and not normal close
            if (!this.isIntentionalDisconnect && event.code !== 1000) {
                this.handleReconnect();
            }
        };
    }

    /**
     * Handle reconnection logic
     */
    handleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.emit('max_reconnect_attempts', {});
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * this.reconnectAttempts;

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            if (this.roomCode && this.playerId && !this.isIntentionalDisconnect) {
                console.log('Attempting to reconnect...');
                this.connect(this.roomCode, this.playerId);
            }
        }, delay);
    }

    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        this.isIntentionalDisconnect = true;

        if (this.socket) {
            if (this.socket.readyState === WebSocket.OPEN ||
                this.socket.readyState === WebSocket.CONNECTING) {
                console.log('Closing WebSocket connection');
                this.socket.close(1000, 'Client disconnect');
            }
            this.socket = null;
        }

        this.roomCode = null;
        this.playerId = null;
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.connectionPromise = null;
        // Don't clear listeners - they may be needed for reconnection
    }

    /**
     * Send message through WebSocket
     */
    send(type, data = {}) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected');
            return false;
        }

        try {
            const message = JSON.stringify({ type, ...data });
            this.socket.send(message);
            console.log('Sent message:', type, data);
            return true;
        } catch (error) {
            console.error('Failed to send message:', error);
            return false;
        }
    }

    /**
     * Register event listener
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }

    /**
     * Remove event listener
     */
    off(event, callback) {
        if (!this.listeners.has(event)) return;

        const callbacks = this.listeners.get(event);
        const index = callbacks.indexOf(callback);
        if (index > -1) {
            callbacks.splice(index, 1);
        }
    }

    /**
     * Remove all listeners for an event
     */
    removeAllListeners(event) {
        if (event) {
            this.listeners.delete(event);
        } else {
            this.listeners.clear();
        }
    }

    /**
     * Emit event to all listeners
     */
    emit(event, data) {
        if (!this.listeners.has(event)) return;

        const callbacks = this.listeners.get(event);
        callbacks.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error(`Error in ${event} listener:`, error);
            }
        });
    }

    /**
     * Submit answer
     */
    submitAnswer(questionId, answer, timeTaken, usedHint = false) {
        return this.send('submit_answer', {
            question_id: questionId,
            answer,
            time_taken: timeTaken,
            used_hint: usedHint,
        });
    }

    /**
     * Request next question (host only)
     */
    requestNextQuestion() {
        return this.send('next_question', {});
    }

    /**
     * Request hint
     */
    requestHint(questionId) {
        return this.send('request_hint', {
            question_id: questionId,
        });
    }

    /**
     * Send chat message
     */
    sendChatMessage(message) {
        return this.send('chat_message', {
            message,
        });
    }

    /**
     * Send ping to keep connection alive
     */
    ping() {
        return this.send('ping', {});
    }

    /**
     * Check if connected
     */
    isConnected() {
        return this.socket && this.socket.readyState === WebSocket.OPEN;
    }

    /**
     * Get connection state
     */
    getState() {
        if (!this.socket) return 'CLOSED';

        switch (this.socket.readyState) {
            case WebSocket.CONNECTING:
                return 'CONNECTING';
            case WebSocket.OPEN:
                return 'OPEN';
            case WebSocket.CLOSING:
                return 'CLOSING';
            case WebSocket.CLOSED:
                return 'CLOSED';
            default:
                return 'UNKNOWN';
        }
    }
}

// Export singleton instance
export const websocketManager = new WebSocketManager();

// Setup ping interval to keep connection alive
let pingInterval = null;

websocketManager.on('connected', () => {
    // Clear any existing interval
    if (pingInterval) {
        clearInterval(pingInterval);
    }

    // Send ping every 30 seconds
    pingInterval = setInterval(() => {
        if (websocketManager.isConnected()) {
            websocketManager.ping();
        }
    }, 30000);
});

websocketManager.on('disconnected', () => {
    if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
    }
});

export default websocketManager;