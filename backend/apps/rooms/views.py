"""
Room views.
FIXED VERSION with WebSocket game start broadcasting.
"""
import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Room, RoomPlayer
from .serializers import (
    RoomSerializer,
    RoomCreateSerializer,
    RoomJoinSerializer,
)
from ..users.models import Player
from ..core.exceptions import (
    RoomFullException,
    GameAlreadyStartedException,
    NotHostException,
    InsufficientPlayersException,
    QuestionGenerationException,
)

logger = logging.getLogger(__name__)


class RoomCreateView(generics.CreateAPIView):
    """Create a new game room."""
    queryset = Room.objects.all()
    serializer_class = RoomCreateSerializer
    permission_classes = [AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get host player
        host = get_object_or_404(Player, id=serializer.validated_data['host_id'])

        try:
            # Create room with retry logic for unique code
            room = Room.objects.create(
                name=serializer.validated_data['name'],
                max_players=serializer.validated_data['max_players'],
                host=host
            )

            # Add host as first player
            RoomPlayer.objects.create(
                room=room,
                player=host
            )

            logger.info(f"Room {room.code} created by {host.username}")

            response_serializer = RoomSerializer(room)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except IntegrityError as e:
            logger.error(f"Failed to create room: {str(e)}")
            return Response(
                {'error': 'Failed to create room. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RoomDetailView(generics.RetrieveAPIView):
    """Get room details by code."""
    queryset = Room.objects.prefetch_related('players__player').select_related('current_game')
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    lookup_field = 'code'

    def get_object(self):
        code = self.kwargs.get('code')
        room = get_object_or_404(
            Room.objects.prefetch_related('players__player').select_related('current_game'),
            code=code
        )
        return room


class RoomJoinView(APIView):
    """Join a game room."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, code):
        room = get_object_or_404(
            Room.objects.select_for_update().prefetch_related('players__player'),
            code=code
        )

        serializer = RoomJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        player = get_object_or_404(Player, id=serializer.validated_data['player_id'])

        # Check if game already started
        if room.status != 'waiting':
            raise GameAlreadyStartedException()

        # Check if room is full
        if room.is_full:
            raise RoomFullException()

        # Use get_or_create to prevent race condition
        room_player, created = RoomPlayer.objects.get_or_create(
            room=room,
            player=player,
            defaults={'is_ready': False, 'score': 0}
        )

        if not created:
            logger.info(f"Player {player.username} already in room {room.code}")
        else:
            logger.info(f"Player {player.username} joined room {room.code}")

        response_serializer = RoomSerializer(room)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class RoomLeaveView(APIView):
    """Leave a game room."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, code):
        room = get_object_or_404(
            Room.objects.select_for_update().prefetch_related('players__player'),
            code=code
        )

        player_id = request.data.get('player_id')
        if not player_id:
            return Response(
                {'error': {'code': 'player_id_required', 'message': 'player_id is required'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            player = Player.objects.get(id=player_id)
        except Player.DoesNotExist:
            return Response(
                {'error': {'code': 'player_not_found', 'message': 'Player not found'}},
                status=status.HTTP_404_NOT_FOUND
            )

        # Remove player from room
        try:
            room_player = RoomPlayer.objects.get(room=room, player=player)
            room_player.delete()
            logger.info(f"Player {player.username} left room {room.code}")

        except RoomPlayer.DoesNotExist:
            return Response(
                {'error': {'code': 'player_not_in_room', 'message': 'Player not in this room'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If host left and room has other players, assign new host
        if room.host == player:
            remaining_players = room.players.all()
            if remaining_players.exists():
                new_host_player = remaining_players.first().player
                room.host = new_host_player
                room.save()
                logger.info(f"New host {new_host_player.username} for room {room.code}")
            else:
                # Clean up associated games before deleting room
                self._cleanup_room_games(room)
                logger.info(f"Room {room.code} deleted (no players remaining)")
                room.delete()
                return Response({'message': 'Room deleted'}, status=status.HTTP_200_OK)

        response_serializer = RoomSerializer(room)
        return Response(response_serializer.data)

    def _cleanup_room_games(self, room):
        """Clean up games associated with room before deletion."""
        try:
            # Import here to avoid circular import
            from ..games.models import Game
            games = Game.objects.filter(room=room)
            count = games.count()
            games.delete()
            logger.info(f"Deleted {count} games for room {room.code}")
        except Exception as e:
            logger.error(f"Error cleaning up games for room {room.code}: {str(e)}")


class RoomStartGameView(APIView):
    """Start the game in a room."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, code):
        room = get_object_or_404(
            Room.objects.select_for_update().prefetch_related('players__player'),
            code=code
        )

        player_id = request.data.get('player_id')
        if not player_id:
            return Response(
                {'error': {'code': 'player_id_required', 'message': 'player_id is required'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        player = get_object_or_404(Player, id=player_id)

        # Check if player is host
        if room.host != player:
            raise NotHostException()

        # Check if room can start
        if not room.can_start:
            min_players = getattr(settings, 'MIN_PLAYERS_TO_START', 2)
            raise InsufficientPlayersException(
                detail=f'Need at least {min_players} players to start'
            )

        # Check if game already in progress
        if room.status == 'in_progress':
            raise GameAlreadyStartedException()

        logger.info(f"Starting game in room {room.code}")

        # Import here to avoid circular imports
        from ..games.models import Game, GameScore
        from ..games.services import GameService

        try:
            # Create game
            game = Game.objects.create(
                room=room,
                status='active',
                current_question_index=0
            )

            # Create game scores for all players in room
            for room_player in room.players.all():
                GameScore.objects.create(
                    game=game,
                    player=room_player.player,
                    total_score=0,
                    correct_answers=0,
                    wrong_answers=0
                )

            # Generate questions - if this fails, rollback everything
            num_questions = getattr(settings, 'QUESTIONS_PER_GAME', 10)
            game_service = GameService()
            game_service.start_game(game, num_questions)

            # Refresh game to get questions
            game.refresh_from_db()

            if game.total_questions == 0:
                raise QuestionGenerationException(
                    detail='Failed to generate questions for the game'
                )

            # Update room status only after successful question generation
            room.status = 'in_progress'
            room.current_game = game
            room.save()

            logger.info(f"Generated {game.total_questions} questions for game {game.id}")

            # Get first question for broadcasting
            first_question = game.current_question

            # Broadcast game start via WebSocket - CRITICAL - FIXED
            channel_layer = get_channel_layer()
            if channel_layer and first_question:
                from asgiref.sync import async_to_sync

                game_started_data = {
                    'type': 'game_started',
                    'question': {
                        'id': str(first_question.id),
                        'order': first_question.order,
                        # FIXED: Use 'items' and 'options' instead of 'text'
                        'items': first_question.items,
                        'options': first_question.options,
                        'hint': first_question.hint if first_question.hint else '',
                        'time_limit': first_question.time_limit if first_question.time_limit else 30
                    },
                    'question_number': 1,
                    'total_questions': game.total_questions,
                    'timestamp': game.created_at.isoformat() + 'Z'
                }

                logger.info(f"Broadcasting game_started event for room {room.code}: {game_started_data}")

                async_to_sync(channel_layer.group_send)(
                    f'game_room_{room.code}',
                    game_started_data
                )
                logger.info(f"Successfully broadcasted game_started event for room {room.code}")

            response_serializer = RoomSerializer(room)
            return Response(response_serializer.data)

        except QuestionGenerationException as e:
            logger.error(f"Question generation failed for room {room.code}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error starting game in room {room.code}: {str(e)}", exc_info=True)
            return Response(
                {'error': {'code': 'game_start_failed', 'message': 'Failed to start game. Please try again.'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RoomReadyToggleView(APIView):
    """Toggle player ready status."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, code):
        room = get_object_or_404(Room.objects.select_for_update(), code=code)

        player_id = request.data.get('player_id')
        if not player_id:
            return Response(
                {'error': {'code': 'player_id_required', 'message': 'player_id is required'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        player = get_object_or_404(Player, id=player_id)
        room_player = get_object_or_404(RoomPlayer, room=room, player=player)

        # Toggle ready status
        room_player.is_ready = not room_player.is_ready
        room_player.save(update_fields=['is_ready'])

        logger.info(
            f"Player {player.username} ready status: {room_player.is_ready} in room {room.code}"
        )

        return Response(RoomSerializer(room).data)