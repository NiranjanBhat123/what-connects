"""
WebSocket middleware for authentication and connection handling.
"""
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
import logging

logger = logging.getLogger(__name__)


class TokenAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using player_id.
    Since we don't have traditional authentication, we use player_id from query params.
    """

    async def __call__(self, scope, receive, send):
        # Get player_id from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        player_id = query_params.get('player_id', [None])[0]

        # Add player_id to scope
        scope['player_id'] = player_id
        scope['user'] = AnonymousUser()  # We don't use Django's auth system

        return await super().__call__(scope, receive, send)


class RateLimitMiddleware(BaseMiddleware):
    """
    Simple rate limiting middleware to prevent WebSocket abuse.
    """

    def __init__(self, inner):
        super().__init__(inner)
        self.connections = {}  # IP -> count
        self.max_connections_per_ip = 10

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            # Get client IP
            client_ip = scope.get('client', ['unknown'])[0]

            # Check connection count
            current_count = self.connections.get(client_ip, 0)

            if current_count >= self.max_connections_per_ip:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                # Close connection
                await send({
                    'type': 'websocket.close',
                    'code': 1008  # Policy violation
                })
                return

            # Increment counter
            self.connections[client_ip] = current_count + 1

            try:
                result = await super().__call__(scope, receive, send)
                return result
            finally:
                # Decrement counter on disconnect
                self.connections[client_ip] = max(0, self.connections.get(client_ip, 1) - 1)
                if self.connections[client_ip] == 0:
                    del self.connections[client_ip]

        return await super().__call__(scope, receive, send)