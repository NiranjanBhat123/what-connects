"""
Utility functions for WebSocket operations.
"""
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)


def send_to_room(room_code, message_type, data):
    """
    Send a message to all connections in a room.

    Args:
        room_code: The room code
        message_type: Type of message (must match a handler method in consumer)
        data: Dictionary of data to send
    """
    channel_layer = get_channel_layer()
    room_group_name = f'game_room_{room_code}'

    try:
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': message_type,
                **data
            }
        )
        logger.info(f"Sent {message_type} to room {room_code}")
    except Exception as e:
        logger.error(f"Failed to send message to room {room_code}: {str(e)}")


def broadcast_game_update(room_code, game_state):
    """
    Broadcast game state update to all players in a room.

    Args:
        room_code: The room code
        game_state: Dictionary containing game state information
    """
    from datetime import datetime

    send_to_room(
        room_code,
        'game_state_update',
        {
            'state': game_state,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    )


def notify_room_update(room_code, update_type, data):
    """
    Send a notification about room changes.

    Args:
        room_code: The room code
        update_type: Type of update (e.g., 'player_joined', 'settings_changed')
        data: Update data
    """
    from datetime import datetime

    send_to_room(
        room_code,
        update_type,
        {
            **data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    )


class WebSocketConnectionManager:
    """
    Manager class to track active WebSocket connections.
    Useful for debugging and monitoring.
    """

    def __init__(self):
        self.active_connections = {}  # room_code -> set of channel_names

    def connect(self, room_code, channel_name):
        """Register a new connection."""
        if room_code not in self.active_connections:
            self.active_connections[room_code] = set()
        self.active_connections[room_code].add(channel_name)
        logger.info(f"Connection added to room {room_code}. Total: {len(self.active_connections[room_code])}")

    def disconnect(self, room_code, channel_name):
        """Remove a connection."""
        if room_code in self.active_connections:
            self.active_connections[room_code].discard(channel_name)
            if not self.active_connections[room_code]:
                del self.active_connections[room_code]
            logger.info(f"Connection removed from room {room_code}")

    def get_room_connections(self, room_code):
        """Get number of active connections for a room."""
        return len(self.active_connections.get(room_code, set()))

    def get_all_rooms(self):
        """Get all rooms with active connections."""
        return list(self.active_connections.keys())


# Global connection manager instance
connection_manager = WebSocketConnectionManager()