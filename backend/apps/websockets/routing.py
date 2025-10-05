"""
WebSocket URL routing.
"""
from django.urls import re_path, path
from . import consumers

websocket_urlpatterns = [
    # Main game room WebSocket
    # ws://localhost:8000/ws/room/<room_code>/?player_id=<player_id>
    re_path(
        r'ws/room/(?P<room_code>[A-Z0-9]{6})/$',
        consumers.GameRoomConsumer.as_asgi()
    ),
]