"""
Room views - FIXED VERSION with better error handling
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
    """Create a new game room with IMMEDIATE question generation."""
    queryset = Room.objects.all()
    serializer_class = RoomCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """Create room and IMMEDIATELY generate questions."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            host = Player.objects.get(id=serializer.validated_data['host_id'])
        except Player.DoesNotExist:
            return Response(
                {'error': 'Player not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        room = None
        try:
            # Create room and add host (atomic)
            with transaction.atomic():
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

            # ====== IMMEDIATELY PRE-GENERATE GAME AND QUESTIONS ======
            from ..games.models import Game, GameScore
            from ..games.services import GameService

            try:
                with transaction.atomic():
                    # Create game in 'pending' status (started_at will be None)
                    game = Game.objects.create(
                        room=room,
                        status='pending',
                        current_question_index=0
                        # started_at and completed_at will be None for pending games
                    )

                    # Generate questions IMMEDIATELY
                    num_questions = getattr(settings, 'QUESTIONS_PER_GAME', 10)
                    game_service = GameService()

                    logger.info(f"Starting question generation for room {room.code}...")

                    # Call the service to generate questions
                    try:
                        game_service.start_game(game, num_questions)
                    except AttributeError as ae:
                        logger.error(f"GameService method error: {str(ae)}")
                        raise QuestionGenerationException(
                            detail='Game service not properly configured. Please contact support.'
                        )
                    except Exception as gen_error:
                        logger.error(f"Question generation failed: {str(gen_error)}", exc_info=True)
                        raise QuestionGenerationException(
                            detail=f'Failed to generate questions: {str(gen_error)}'
                        )

                    # Refresh to verify questions were created
                    game.refresh_from_db()

                    if game.total_questions == 0:
                        raise QuestionGenerationException('No questions were generated')

                    logger.info(f"✅ Successfully pre-generated {game.total_questions} questions for room {room.code}")

                    # Link game to room
                    room.current_game = game
                    room.save()

            except QuestionGenerationException:
                # Clean up room if question generation fails
                if room:
                    logger.error(f"Deleting room {room.code} due to question generation failure")
                    room.delete()
                raise
            except Exception as e:
                logger.error(f"❌ Failed to pre-generate questions: {str(e)}", exc_info=True)
                # Delete the room if question generation fails
                if room:
                    room.delete()
                return Response(
                    {'error': f'Failed to generate questions: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Refresh room to get latest data
            room.refresh_from_db()
            response_serializer = RoomSerializer(room)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except QuestionGenerationException as qge:
            logger.error(f"Question generation exception: {str(qge)}")
            return Response(
                {'error': str(qge.detail) if hasattr(qge, 'detail') else 'Failed to generate questions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except IntegrityError as e:
            logger.error(f"Database integrity error: {str(e)}")
            if room:
                room.delete()
            return Response(
                {'error': 'Failed to create room due to database error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error creating room: {str(e)}", exc_info=True)
            if room:
                try:
                    room.delete()
                except Exception:
                    pass
            return Response(
                {'error': f'An unexpected error occurred: {str(e)}'},
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
            from ..games.models import Game
            games = Game.objects.filter(room=room)
            count = games.count()
            games.delete()
            logger.info(f"Deleted {count} games for room {room.code}")
        except Exception as e:
            logger.error(f"Error cleaning up games for room {room.code}: {str(e)}")


class RoomStartGameView(APIView):
    """Start the game - Questions ALREADY pre-generated."""
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

        from ..games.models import Game, GameScore

        try:
            # Use the pre-generated game
            game = room.current_game

            if not game or game.status != 'pending':
                raise QuestionGenerationException(
                    detail='No pre-generated game found. Please create a new room.'
                )

            if game.total_questions == 0:
                raise QuestionGenerationException(
                    detail='No questions available. Please create a new room.'
                )

            logger.info(f"Using pre-generated game with {game.total_questions} questions")

            # Activate the game and set started_at
            from django.utils import timezone
            game.status = 'active'
            game.started_at = timezone.now()
            game.save()

            # Create game scores for all players
            for room_player in room.players.all():
                GameScore.objects.get_or_create(
                    game=game,
                    player=room_player.player,
                    defaults={'total_score': 0, 'correct_answers': 0, 'wrong_answers': 0}
                )

            # Update room status
            room.status = 'in_progress'
            room.save()

            logger.info(f"✅ Game started successfully with {game.total_questions} questions")

            # Get first question for broadcasting
            first_question = game.current_question

            # Broadcast game start via WebSocket
            channel_layer = get_channel_layer()
            if channel_layer and first_question:
                game_started_data = {
                    'type': 'game_started',
                    'question': {
                        'id': str(first_question.id),
                        'order': first_question.order,
                        'items': first_question.items,
                        'options': first_question.options,
                        'hint': first_question.hint if first_question.hint else '',
                        'time_limit': first_question.time_limit if first_question.time_limit else 30
                    },
                    'question_number': 1,
                    'total_questions': game.total_questions,
                    'timestamp': game.created_at.isoformat() + 'Z'
                }

                logger.info(f"Broadcasting game_started event for room {room.code}")

                async_to_sync(channel_layer.group_send)(
                    f'game_room_{room.code}',
                    game_started_data
                )

            response_serializer = RoomSerializer(room)
            return Response(response_serializer.data)

        except QuestionGenerationException as e:
            logger.error(f"Game start failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error starting game: {str(e)}", exc_info=True)
            return Response(
                {'error': {'code': 'game_start_failed', 'message': 'Failed to start game'}},
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