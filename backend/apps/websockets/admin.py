"""
Admin configuration for websockets app.
Mainly for monitoring and debugging WebSocket connections.
"""
from django.contrib import admin
from django.utils.html import format_html
from .utils import connection_manager


class WebSocketConnectionAdmin:
    """
    Custom admin view to monitor active WebSocket connections.
    Not a model admin, but a custom view.
    """

    def get_active_rooms(self):
        """Get list of rooms with active connections."""
        rooms = connection_manager.get_all_rooms()
        return [
            {
                'room_code': room,
                'connections': connection_manager.get_room_connections(room)
            }
            for room in rooms
        ]

    def get_total_connections(self):
        """Get total number of active connections."""
        return sum(
            connection_manager.get_room_connections(room)
            for room in connection_manager.get_all_rooms()
        )


# You can register this in your main admin.py to add a monitoring dashboard
# For now, it's just a utility class