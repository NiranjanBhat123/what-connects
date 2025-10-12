"""
WebSocket consumers for real-time game functionality.
FIXED VERSION with proper room state including code field.
"""
import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from ..users.models import Player
from ..rooms.models import Room, RoomPlayer
from ..games.models import Game, Question, Answer, GameScore
from .utils import connection_manager

logger = logging.getLogger(__name__)


class GameRoomConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for game room real-time communication.
    Handles player connections, game state updates, and answer submissions.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        self.room_code = self.scope['url_route']['kwargs']['room_code']

        # Get player_id from query string
        query_string = self.scope.get('query_string', b'').decode()
        from urllib.parse import parse_qs
        query_params = parse_qs(query_string)
        self.player_id = query_params.get('player_id', [None])[0]

        if not self.player_id:
            logger.error("No player_id provided in connection")
            await self.close(code=4001)
            return

        self.room_group_name = f'game_room_{self.room_code}'

        # Verify room exists and player is valid
        room_valid = await self.verify_room_and_player()
        if not room_valid:
            logger.warning(f"Invalid room/player: {self.room_code}/{self.player_id}")
            await self.close(code=4004)
            return

        # Join room group BEFORE accepting connection
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Track connection
        connection_manager.connect(self.room_code, self.channel_name)

        # Get player info
        player_info = await self.get_player_info()

        # Broadcast to ALL players in room (including the one who just joined)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'player_joined',
                'player_id': str(self.player_id),
                'player_name': player_info['username'],
                'timestamp': self._get_timestamp()
            }
        )

        # Send current room state to the newly connected player
        room_state = await self.get_room_state()
        await self.send(text_data=json.dumps({
            'type': 'room_state_update',
            'state': room_state,
            'timestamp': self._get_timestamp()
        }))

        # Send game state if game is active
        game_state = await self.get_game_state()
        if game_state.get('game_status'):
            await self.send(text_data=json.dumps({
                'type': 'initial_state',
                'state': game_state,
                'timestamp': self._get_timestamp()
            }))

        logger.info(f"Player {self.player_id} connected to room {self.room_code}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'room_group_name'):
            # Untrack connection
            if hasattr(self, 'room_code'):
                connection_manager.disconnect(self.room_code, self.channel_name)

            # Get player info before leaving
            try:
                player_info = await self.get_player_info()
                player_name = player_info['username']
            except Exception:
                player_name = 'Unknown'

            # Notify room of player leaving
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_left',
                    'player_id': str(self.player_id),
                    'player_name': player_name,
                    'timestamp': self._get_timestamp()
                }
            )

            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

            logger.info(f"Player {self.player_id} disconnected from room {self.room_code} (code: {close_code})")

    async def receive(self, text_data):
        """Receive message from WebSocket."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            # Route message based on type
            handlers = {
                'submit_answer': self.handle_submit_answer,
                'next_question': self.handle_next_question,
                'start_game': self.handle_start_game,
                'chat_message': self.handle_chat_message,
                'request_hint': self.handle_request_hint,
                'ping': self.handle_ping
            }

            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_error("Unknown message type")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self.send_error("Invalid message format")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            await self.send_error("Error processing message")

    async def handle_submit_answer(self, data):
        """Handle answer submission with race condition protection."""
        answer = data.get('answer', '').strip()
        question_id = data.get('question_id')
        time_taken = data.get('time_taken', 0)
        used_hint = data.get('used_hint', False)

        if not answer:
            await self.send_error("Answer cannot be empty")
            return

        if not question_id:
            await self.send_error("Question ID is required")
            return

        # Check answer and update game state
        result = await self.check_answer(answer, question_id, time_taken, used_hint)

        if result.get('error'):
            await self.send_error(result['error'])
            return

        # Don't broadcast if already answered
        if result.get('already_answered'):
            await self.send(text_data=json.dumps({
                'type': 'answer_result',
                'is_correct': result['is_correct'],
                'message': 'You already answered this question',
                'timestamp': self._get_timestamp()
            }))
            return

        # Broadcast answer submission to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'answer_submitted',
                'player_id': str(self.player_id),
                'player_name': result['player_name'],
                'is_correct': result['is_correct'],
                'correct_answer': result.get('correct_answer'),
                'question_id': question_id,
                'points_earned': result.get('points_earned', 0),
                'total_score': result.get('total_score', 0),
                'timestamp': self._get_timestamp()
            }
        )

    async def handle_start_game(self, data):
        """Handle game start request (host only)."""
        is_host = await self.verify_host()
        if not is_host:
            await self.send_error("Only the host can start the game")
            return

        result = await self.start_game()

        if result.get('error'):
            await self.send_error(result['error'])
            return

        # Broadcast game start to all players
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_started',
                'question': result['question'],
                'question_number': 1,
                'total_questions': result['total_questions'],
                'timestamp': self._get_timestamp()
            }
        )

    async def handle_next_question(self, data):
        """Handle next question request (host only)."""
        is_host = await self.verify_host()
        if not is_host:
            await self.send_error("Only the host can advance questions")
            return

        question_data = await self.get_next_question()

        if question_data.get('error'):
            await self.send_error(question_data['error'])
            return

        # Check if game is complete
        if question_data.get('game_complete'):
            results = await self.get_final_results()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_complete',
                    'results': results,
                    'timestamp': self._get_timestamp()
                }
            )
        else:
            # Broadcast next question to all players
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'next_question',
                    'question': question_data['question'],
                    'question_number': question_data['question_number'],
                    'total_questions': question_data['total_questions'],
                    'timestamp': self._get_timestamp()
                }
            )

    async def handle_chat_message(self, data):
        """Handle chat messages."""
        message = data.get('message', '').strip()
        if not message or len(message) > 500:
            return

        player_info = await self.get_player_info()

        # Broadcast chat message to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'player_id': str(self.player_id),
                'player_name': player_info['username'],
                'message': message,
                'timestamp': self._get_timestamp()
            }
        )

    async def handle_request_hint(self, data):
        """Handle hint request."""
        question_id = data.get('question_id')

        if not question_id:
            await self.send_error("Question ID is required")
            return

        hint = await self.get_hint(question_id)

        if hint:
            await self.send(text_data=json.dumps({
                'type': 'hint',
                'hint': hint,
                'question_id': question_id,
                'timestamp': self._get_timestamp()
            }))
        else:
            await self.send_error("No hint available")

    async def handle_ping(self, data):
        """Handle ping to keep connection alive."""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': self._get_timestamp()
        }))

    # Event handlers for group messages
    async def player_joined(self, event):
        """Send player joined message to WebSocket."""
        # Also send updated room state
        room_state = await self.get_room_state()

        await self.send(text_data=json.dumps({
            'type': 'player_joined',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'room_state': room_state,  # Include updated state
            'timestamp': event['timestamp']
        }))

    async def player_left(self, event):
        """Send player left message to WebSocket."""
        # Also send updated room state
        room_state = await self.get_room_state()

        await self.send(text_data=json.dumps({
            'type': 'player_left',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'room_state': room_state,  # Include updated state
            'timestamp': event['timestamp']
        }))

    async def answer_submitted(self, event):
        """Send answer submitted notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'answer_submitted',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'is_correct': event['is_correct'],
            'correct_answer': event.get('correct_answer'),
            'question_id': event['question_id'],
            'points_earned': event.get('points_earned', 0),
            'total_score': event.get('total_score', 0),
            'timestamp': event['timestamp']
        }))

    async def game_started(self, event):
        """Send game started message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'game_started',
            'question': event['question'],
            'question_number': event['question_number'],
            'total_questions': event['total_questions'],
            'timestamp': event['timestamp']
        }))

    async def next_question(self, event):
        """Send next question to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'next_question',
            'question': event['question'],
            'question_number': event['question_number'],
            'total_questions': event['total_questions'],
            'timestamp': event['timestamp']
        }))

    async def game_complete(self, event):
        """Send game complete message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'game_complete',
            'results': event['results'],
            'timestamp': event['timestamp']
        }))

    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }))

    async def game_state_update(self, event):
        """Send game state update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'game_state_update',
            'state': event.get('state', {}),
            'timestamp': event.get('timestamp', self._get_timestamp())
        }))

    async def room_state_update(self, event):
        """Send room state update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'room_state_update',
            'state': event['state'],
            'timestamp': event['timestamp']
        }))

    # Database operations
    @database_sync_to_async
    def verify_room_and_player(self):
        """Verify room exists and player is valid."""
        try:
            room = Room.objects.get(code=self.room_code)
            if self.player_id:
                player = Player.objects.get(id=self.player_id)
                # Check if player is in the room
                return RoomPlayer.objects.filter(
                    room=room,
                    player=player
                ).exists()
            return True
        except (ObjectDoesNotExist, ValueError):
            return False

    @database_sync_to_async
    def get_player_info(self):
        """Get player information."""
        try:
            player = Player.objects.get(id=self.player_id)
            return {
                'id': str(player.id),
                'username': player.username
            }
        except ObjectDoesNotExist:
            return {'id': None, 'username': 'Unknown'}

    @database_sync_to_async
    def verify_host(self):
        """Verify if current player is the room host."""
        try:
            room = Room.objects.get(code=self.room_code)
            return str(room.host.id) == str(self.player_id)
        except ObjectDoesNotExist:
            return False

    @database_sync_to_async
    def get_room_state(self):
        """Get current room state with all players - FIXED to include code."""
        try:
            room = Room.objects.prefetch_related('players__player').get(code=self.room_code)

            return {
                'id': str(room.id),
                'code': room.code,  # CRITICAL: Must include code
                'room_code': room.code,
                'name': room.name,
                'room_name': room.name,
                'room_status': room.status,
                'status': room.status,  # For compatibility
                'max_players': room.max_players,
                'can_start': room.can_start,
                'host_id': str(room.host.id),
                'host': {
                    'id': str(room.host.id),
                    'username': room.host.username
                },
                'players': [
                    {
                        'id': str(rp.player.id),
                        'player_id': str(rp.player.id),  # For compatibility
                        'username': rp.player.username,
                        'player_name': rp.player.username,  # For compatibility
                        'score': rp.score,
                        'is_ready': rp.is_ready,
                        'is_host': str(rp.player.id) == str(room.host.id)
                    }
                    for rp in room.players.all()
                ],
                'player_count': room.players.count()
            }
        except ObjectDoesNotExist:
            return {'error': 'Room not found'}

    @database_sync_to_async
    def get_game_state(self):
        """Get current game state."""
        try:
            room = Room.objects.prefetch_related('players__player').get(code=self.room_code)

            # Get active game
            try:
                game = Game.objects.filter(
                    room=room,
                    status='active'
                ).latest('created_at')

                current_question = game.current_question
                question_data = None
                if current_question:
                    question_data = {
                        'id': str(current_question.id),
                        'order': current_question.order,
                        'text': current_question.text,
                        'items': current_question.items,
                        'hint': current_question.hint if hasattr(current_question, 'hint') else None,
                        'time_limit': current_question.time_limit if hasattr(current_question, 'time_limit') else 30
                    }

                return {
                    'room_code': room.code,
                    'room_status': room.status,
                    'game_status': game.status,
                    'current_question_index': game.current_question_index,
                    'total_questions': game.total_questions,
                    'current_question': question_data,
                    'players': [
                        {
                            'id': str(rp.player.id),
                            'username': rp.player.username,
                            'score': rp.score,
                            'is_host': str(rp.player.id) == str(room.host.id)
                        }
                        for rp in room.players.all()
                    ]
                }
            except Game.DoesNotExist:
                return {
                    'room_code': room.code,
                    'room_status': room.status,
                    'game_status': None,
                    'players': [
                        {
                            'id': str(rp.player.id),
                            'username': rp.player.username,
                            'score': rp.score,
                            'is_host': str(rp.player.id) == str(room.host.id)
                        }
                        for rp in room.players.all()
                    ]
                }

        except ObjectDoesNotExist:
            return {'error': 'Room not found'}

    @database_sync_to_async
    def start_game(self):
        """Start the game."""
        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().get(code=self.room_code)

                # Check if game already exists
                if Game.objects.filter(room=room, status='active').exists():
                    return {'error': 'Game already in progress'}

                # Create new game
                game = Game.objects.create(
                    room=room,
                    status='active',
                    current_question_index=0
                )

                # Get first question
                first_question = game.current_question
                if not first_question:
                    return {'error': 'No questions available'}

                return {
                    'question': {
                        'id': str(first_question.id),
                        'order': first_question.order,
                        'text': first_question.text,
                        'items': first_question.items,
                        'time_limit': getattr(first_question, 'time_limit', 30)
                    },
                    'total_questions': game.total_questions
                }

        except ObjectDoesNotExist:
            return {'error': 'Room not found'}
        except Exception as e:
            logger.error(f"Error starting game: {str(e)}", exc_info=True)
            return {'error': 'Failed to start game'}

    @database_sync_to_async
    def check_answer(self, answer, question_id, time_taken=0, used_hint=False):
        """Check if answer is correct and update score."""
        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().get(code=self.room_code)
                game = Game.objects.select_for_update().get(room=room, status='active')
                player = Player.objects.get(id=self.player_id)
                question = Question.objects.select_for_update().get(id=question_id, game=game)

                # Check if already answered
                existing_answer = Answer.objects.select_for_update().filter(
                    question=question,
                    player=player
                ).first()

                if existing_answer:
                    return {
                        'player_name': player.username,
                        'is_correct': existing_answer.is_correct,
                        'correct_answer': question.correct_answer if not existing_answer.is_correct else None,
                        'points_earned': existing_answer.points_earned,
                        'total_score': GameScore.objects.get(game=game, player=player).total_score,
                        'already_answered': True
                    }

                # Check answer
                is_correct = question.check_answer(answer)

                # Create answer
                answer_obj = Answer.objects.create(
                    question=question,
                    player=player,
                    answer_text=answer,
                    is_correct=is_correct,
                    used_hint=used_hint,
                    time_taken=max(0, int(time_taken))
                )

                # Calculate points
                points = answer_obj.calculate_points()

                # Update game score
                game_score, created = GameScore.objects.get_or_create(
                    game=game,
                    player=player,
                    defaults={'total_score': 0, 'correct_answers': 0, 'wrong_answers': 0}
                )
                game_score.update_score(answer_obj)

                # Update RoomPlayer score
                room_player = RoomPlayer.objects.get(room=room, player=player)
                room_player.score = game_score.total_score
                room_player.save()

                return {
                    'player_name': player.username,
                    'is_correct': is_correct,
                    'correct_answer': question.correct_answer if not is_correct else None,
                    'points_earned': points,
                    'total_score': game_score.total_score,
                    'already_answered': False
                }

        except ObjectDoesNotExist as e:
            logger.error(f"Object not found: {str(e)}")
            return {'error': 'Game, player, or question not found', 'player_name': 'Unknown', 'is_correct': False}
        except Exception as e:
            logger.error(f"Error checking answer: {str(e)}", exc_info=True)
            return {'error': 'Failed to check answer', 'player_name': 'Unknown', 'is_correct': False}

    @database_sync_to_async
    def get_next_question(self):
        """Get the next question."""
        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().get(code=self.room_code)
                game = Game.objects.select_for_update().get(room=room, status='active')

                # Move to next question
                next_q = game.next_question()

                if next_q is None:
                    # Game complete
                    game.status = 'completed'
                    game.save()
                    return {'game_complete': True}

                return {
                    'question': {
                        'id': str(next_q.id),
                        'order': next_q.order,
                        'text': next_q.text,
                        'items': next_q.items,
                        'hint': getattr(next_q, 'hint', None),
                        'time_limit': getattr(next_q, 'time_limit', 30),
                        'correct_answer': next_q.correct_answer
                    },
                    'question_number': game.current_question_index + 1,
                    'total_questions': game.total_questions
                }

        except ObjectDoesNotExist:
            return {'error': 'Game not found'}
        except Exception as e:
            logger.error(f"Error getting next question: {str(e)}", exc_info=True)
            return {'error': 'Failed to get next question'}

    @database_sync_to_async
    def get_hint(self, question_id):
        """Get hint for current question."""
        try:
            question = Question.objects.get(id=question_id)
            return getattr(question, 'hint', None)
        except ObjectDoesNotExist:
            return None

    async def all_players_answered(self, event):
        """Send notification that all players have answered."""
        await self.send(text_data=json.dumps({
            'type': 'all_players_answered',
            'state': event.get('state', {}),
            'timestamp': event.get('timestamp', self._get_timestamp())
        }))

    @database_sync_to_async
    def get_final_results(self):
        """Calculate final game results."""
        try:
            room = Room.objects.get(code=self.room_code)
            game = Game.objects.get(room=room)

            results = GameScore.objects.filter(
                game=game
            ).select_related('player').order_by('-total_score', 'created_at')

            return [
                {
                    'player_id': str(score.player.id),
                    'player_name': score.player.username,
                    'total_score': score.total_score,
                    'correct_answers': score.correct_answers,
                    'wrong_answers': score.wrong_answers,
                    'accuracy': score.accuracy
                }
                for score in results
            ]
        except ObjectDoesNotExist:
            return []

    async def send_error(self, message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': self._get_timestamp()
        }))

    @staticmethod
    def _get_timestamp():
        """Get current timestamp."""
        return datetime.utcnow().isoformat() + 'Z'