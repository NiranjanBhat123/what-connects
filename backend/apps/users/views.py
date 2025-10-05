"""
Users app views.
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Player
from .serializers import PlayerSerializer
import logging

logger = logging.getLogger(__name__)


class PlayerCreateView(generics.CreateAPIView):
    """Create a new player (no auth required)."""
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """Create a new player with proper validation and session handling."""
        username = request.data.get('username', '').strip()

        if not username:
            return Response(
                {'error': 'Username is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get session key if available
        session_key = request.session.session_key
        if not session_key:
            # Create session if it doesn't exist
            request.session.create()
            session_key = request.session.session_key

        try:
            # Use custom manager to create player with validation
            player = Player.objects.create_player(
                username=username,
                session_key=session_key
            )

            # Store player_id in session for future reference
            request.session['player_id'] = str(player.id)
            request.session.modified = True

            logger.info(f"Created player: {player.username} ({player.id})")

            return Response({
                'id': str(player.id),
                'username': player.username,
                'created_at': player.created_at.isoformat(),
                'session_key': session_key
            }, status=status.HTTP_201_CREATED)

        except DjangoValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating player: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to create player'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PlayerDetailView(generics.RetrieveAPIView):
    """Get player details."""
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [AllowAny]

    def retrieve(self, request, *args, **kwargs):
        """Get player details and update activity."""
        instance = self.get_object()

        # Update last_active timestamp
        instance.update_activity()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class PlayerValidateView(APIView):
    """Validate if a player exists and is active."""
    permission_classes = [AllowAny]

    def get(self, request, player_id):
        """Check if player exists and is valid for joining games."""
        try:
            player = Player.objects.get(id=player_id)

            # Update activity
            player.update_activity()

            return Response({
                'valid': True,
                'player_id': str(player.id),
                'username': player.username,
                'is_active': player.is_active
            })
        except Player.DoesNotExist:
            return Response(
                {'valid': False, 'error': 'Player not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class PlayerCleanupView(APIView):
    """
    Admin endpoint to manually trigger player cleanup.
    Should also be run as a periodic task.
    """
    permission_classes = [AllowAny]  # Should be admin-only in production

    def post(self, request):
        """Clean up old inactive players."""
        days = request.data.get('days', 7)

        try:
            count = Player.objects.cleanup_old_players(days=days)
            logger.info(f"Cleaned up {count} old players")

            return Response({
                'success': True,
                'deleted_count': count,
                'message': f'Deleted {count} inactive players older than {days} days'
            })
        except Exception as e:
            logger.error(f"Error during player cleanup: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Cleanup failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )