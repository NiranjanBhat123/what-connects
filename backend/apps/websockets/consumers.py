"""
WebSocket consumers - FIXED VERSION with Delayed Answer Reveal
✅ Answer locked immediately, result shown only after timer expires
✅ All players see results together
✅ Auto-advance working properly
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

# Timer tracking
question_timers = {}


class GameRoomConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for game room real-time communication."""

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

        # Broadcast to ALL players in room
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

            logger.info(f"Player {self.player_id} disconnected from room {self.room_code}")

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
        """Handle answer submission - LOCK answer, don't reveal result yet."""
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

        # Save answer but DON'T reveal if correct
        result = await self.check_answer(answer, question_id, time_taken, used_hint)

        if result.get('error'):
            await self.send_error(result['error'])
            return

        # Already answered
        if result.get('already_answered'):
            await self.send(text_data=json.dumps({
                'type': 'answer_locked',
                'message': 'You already answered this question',
                'timestamp': self._get_timestamp()
            }))
            return

        # Broadcast that player submitted (NO correctness info)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'answer_submitted',
                'player_id': str(self.player_id),
                'player_name': result['player_name'],
                'question_id': question_id,
                'timestamp': self._get_timestamp()
            }
        )

        # Send ONLY confirmation to this player (NO correctness)
        await self.send(text_data=json.dumps({
            'type': 'answer_locked',
            'message': 'Answer locked! Waiting for timer...',
            'timestamp': self._get_timestamp()
        }))

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

        # Start timer for automatic reveal after time expires
        question_id = result['question']['id']
        time_limit = result['question'].get('time_limit', 30)
        await self.start_question_timer(question_id, time_limit)

    async def handle_next_question(self, data):
        """Handle next question request - DEPRECATED (game auto-advances now)."""
        logger.warning("Manual next_question called - game should auto-advance")
        await self.send_error("Game advances automatically after each question")

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

        logger.info(f"💡 Hint requested by player {self.player_id} for question {question_id}")

        hint = await self.get_hint(question_id)

        if hint and hint.strip():
            logger.info(f"✅ Sending hint: {hint}")
            await self.send(text_data=json.dumps({
                'type': 'hint',
                'hint': hint,
                'question_id': question_id,
                'timestamp': self._get_timestamp()
            }))
        else:
            logger.warning(f"❌ No hint available for question {question_id}")
            await self.send_error("No hint available")

    async def handle_ping(self, data):
        """Handle ping to keep connection alive."""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': self._get_timestamp()
        }))

    async def reveal_all_answers(self, question_id):
        """Reveal all answers AFTER timer expires."""
        logger.info(f"🔓 Revealing answers for question {question_id}")

        # Get all answers for this question
        answers_data = await self.get_question_answers(question_id)

        # Broadcast reveal to all players
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'answers_revealed',
                'question_id': question_id,
                'answers': answers_data,
                'timestamp': self._get_timestamp()
            }
        )

    async def broadcast_leaderboard_update(self):
        """Broadcast leaderboard update AFTER answers revealed."""
        import asyncio

        # Wait 2 seconds for answer reveal animation
        await asyncio.sleep(2)

        logger.info(f"📊 Broadcasting leaderboard update for room {self.room_code}")
        leaderboard = await self.get_current_leaderboard()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'leaderboard_update',
                'leaderboard': leaderboard,
                'timestamp': self._get_timestamp()
            }
        )

        # Auto-advance to next question after showing leaderboard
        await asyncio.sleep(5)  # Wait 5 seconds for leaderboard display
        await self.auto_advance_question()

    async def auto_advance_question(self):
        """Automatically advance to next question or end game."""
        logger.info(f"➡️ Auto-advancing to next question for room {self.room_code}")

        question_data = await self.get_next_question()

        if question_data.get('error'):
            logger.error(f"Error auto-advancing: {question_data['error']}")
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

            # Start timer for next question
            question_id = question_data['question']['id']
            time_limit = question_data['question'].get('time_limit', 30)
            await self.start_question_timer(question_id, time_limit)

    async def start_question_timer(self, question_id, duration):
        """Start timer - reveals answers ONLY after time expires."""
        import asyncio

        timer_key = f"{self.room_code}_{question_id}"

        # Cancel existing timer if any
        if timer_key in question_timers:
            question_timers[timer_key].cancel()

        async def timer_task():
            try:
                logger.info(f"⏰ Starting {duration}s timer for question {question_id}")
                await asyncio.sleep(duration)
                logger.info(f"✅ Timer expired for {timer_key} - revealing answers")

                # Step 1: Reveal all answers
                await self.reveal_all_answers(question_id)

                # Step 2: Show leaderboard (with delay, then auto-advance)
                await self.broadcast_leaderboard_update()

            except asyncio.CancelledError:
                logger.info(f"❌ Timer cancelled for {timer_key}")
            finally:
                if timer_key in question_timers:
                    del question_timers[timer_key]

        question_timers[timer_key] = asyncio.create_task(timer_task())

    # Event handlers
    async def player_joined(self, event):
        """Send player joined message."""
        room_state = await self.get_room_state()
        await self.send(text_data=json.dumps({
            'type': 'player_joined',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'room_state': room_state,
            'timestamp': event['timestamp']
        }))

    async def player_left(self, event):
        """Send player left message."""
        room_state = await self.get_room_state()
        await self.send(text_data=json.dumps({
            'type': 'player_left',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'room_state': room_state,
            'timestamp': event['timestamp']
        }))

    async def answer_submitted(self, event):
        """Send answer submitted notification (NO correctness info)."""
        await self.send(text_data=json.dumps({
            'type': 'answer_submitted',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'question_id': event['question_id'],
            'timestamp': event['timestamp']
        }))

    async def answers_revealed(self, event):
        """Send answer reveal to ALL players at once."""
        await self.send(text_data=json.dumps({
            'type': 'answers_revealed',
            'question_id': event['question_id'],
            'answers': event['answers'],
            'timestamp': event['timestamp']
        }))

    async def game_started(self, event):
        """Send game started message."""
        await self.send(text_data=json.dumps({
            'type': 'game_started',
            'question': event['question'],
            'question_number': event['question_number'],
            'total_questions': event['total_questions'],
            'timestamp': event['timestamp']
        }))

    async def next_question(self, event):
        """Send next question."""
        await self.send(text_data=json.dumps({
            'type': 'next_question',
            'question': event['question'],
            'question_number': event['question_number'],
            'total_questions': event['total_questions'],
            'timestamp': event['timestamp']
        }))

    async def game_complete(self, event):
        """Send game complete message."""
        await self.send(text_data=json.dumps({
            'type': 'game_complete',
            'results': event['results'],
            'timestamp': event['timestamp']
        }))

    async def chat_message(self, event):
        """Send chat message."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'player_id': event['player_id'],
            'player_name': event['player_name'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }))

    async def game_state_update(self, event):
        """Send game state update."""
        await self.send(text_data=json.dumps({
            'type': 'game_state_update',
            'state': event.get('state', {}),
            'timestamp': event.get('timestamp', self._get_timestamp())
        }))

    async def room_state_update(self, event):
        """Send room state update."""
        await self.send(text_data=json.dumps({
            'type': 'room_state_update',
            'state': event['state'],
            'timestamp': event['timestamp']
        }))

    async def leaderboard_update(self, event):
        """Send leaderboard update."""
        await self.send(text_data=json.dumps({
            'type': 'leaderboard_update',
            'leaderboard': event['leaderboard'],
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
                return RoomPlayer.objects.filter(room=room, player=player).exists()
            return True
        except (ObjectDoesNotExist, ValueError):
            return False

    @database_sync_to_async
    def get_player_info(self):
        """Get player information."""
        try:
            player = Player.objects.get(id=self.player_id)
            return {'id': str(player.id), 'username': player.username}
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
        """Get current room state."""
        try:
            room = Room.objects.prefetch_related('players__player').get(code=self.room_code)
            return {
                'id': str(room.id),
                'code': room.code,
                'name': room.name,
                'status': room.status,
                'max_players': room.max_players,
                'host_id': str(room.host.id),
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
    def get_game_state(self):
        """Get current game state."""
        try:
            room = Room.objects.get(code=self.room_code)
            try:
                game = Game.objects.filter(room=room, status='active').latest('created_at')
                current_question = game.current_question
                question_data = None
                if current_question:
                    question_data = {
                        'id': str(current_question.id),
                        'order': current_question.order,
                        'items': current_question.items,
                        'options': current_question.options,
                        'hint': current_question.hint or '',
                        'time_limit': current_question.time_limit or 30
                    }
                return {
                    'room_code': room.code,
                    'game_status': game.status,
                    'current_question': question_data
                }
            except Game.DoesNotExist:
                return {'room_code': room.code, 'game_status': None}
        except ObjectDoesNotExist:
            return {'error': 'Room not found'}

    @database_sync_to_async
    def start_game(self):
        """Start the game."""
        try:
            room = Room.objects.get(code=self.room_code)
            game = room.current_game

            if not game or game.status != 'pending':
                return {'error': 'No pre-generated game available'}

            game.status = 'active'
            game.save()

            first_question = game.current_question
            if not first_question:
                return {'error': 'No questions available'}

            return {
                'question': {
                    'id': str(first_question.id),
                    'order': first_question.order,
                    'items': first_question.items,
                    'options': first_question.options,
                    'hint': first_question.hint or '',
                    'time_limit': first_question.time_limit or 30
                },
                'total_questions': game.total_questions
            }
        except Exception as e:
            logger.error(f"Error starting game: {str(e)}", exc_info=True)
            return {'error': 'Failed to start game'}

    @database_sync_to_async
    def check_answer(self, answer, question_id, time_taken=0, used_hint=False):
        """Save answer but DON'T return if correct yet."""
        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().get(code=self.room_code)
                game = Game.objects.select_for_update().get(room=room, status='active')
                player = Player.objects.get(id=self.player_id)
                question = Question.objects.select_for_update().get(id=question_id, game=game)

                existing_answer = Answer.objects.filter(question=question, player=player).first()
                if existing_answer:
                    return {
                        'player_name': player.username,
                        'already_answered': True
                    }

                is_correct = question.check_answer(answer)

                answer_obj = Answer.objects.create(
                    question=question,
                    player=player,
                    answer_text=answer,
                    is_correct=is_correct,
                    used_hint=used_hint,
                    time_taken=max(0, int(time_taken))
                )

                points = answer_obj.calculate_points()

                game_score, _ = GameScore.objects.get_or_create(
                    game=game, player=player,
                    defaults={'total_score': 0, 'correct_answers': 0, 'wrong_answers': 0}
                )
                game_score.update_score(answer_obj)

                room_player = RoomPlayer.objects.get(room=room, player=player)
                room_player.score = game_score.total_score
                room_player.save()

                return {
                    'player_name': player.username,
                    'already_answered': False
                }
        except Exception as e:
            logger.error(f"Error checking answer: {str(e)}", exc_info=True)
            return {'error': 'Failed to check answer'}

    @database_sync_to_async
    def get_question_answers(self, question_id):
        """Get all player answers for a question."""
        try:
            question = Question.objects.get(id=question_id)
            answers = Answer.objects.filter(question=question).select_related('player')

            return {
                'correct_answer': question.correct_answer,
                'player_results': [
                    {
                        'player_id': str(ans.player.id),
                        'player_name': ans.player.username,
                        'is_correct': ans.is_correct,
                        'points_earned': ans.points_earned,
                        'answer_text': ans.answer_text,
                        'used_hint': ans.used_hint
                    }
                    for ans in answers
                ]
            }
        except ObjectDoesNotExist:
            return {'correct_answer': None, 'player_results': []}

    @database_sync_to_async
    def get_current_leaderboard(self):
        """Get current leaderboard."""
        try:
            room = Room.objects.get(code=self.room_code)
            game = Game.objects.get(room=room, status='active')
            scores = GameScore.objects.filter(game=game).select_related('player').order_by(
                '-total_score', 'created_at'
            )
            return [
                {
                    'player_id': str(score.player.id),
                    'player_name': score.player.username,
                    'total_score': score.total_score,
                    'correct_answers': score.correct_answers,
                    'wrong_answers': score.wrong_answers
                }
                for score in scores
            ]
        except ObjectDoesNotExist:
            return []

    @database_sync_to_async
    def get_next_question(self):
        """Get the next question."""
        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().get(code=self.room_code)
                game = Game.objects.select_for_update().get(room=room, status='active')
                next_q = game.next_question()

                if next_q is None:
                    game.status = 'completed'
                    game.save()
                    return {'game_complete': True}

                return {
                    'question': {
                        'id': str(next_q.id),
                        'order': next_q.order,
                        'items': next_q.items,
                        'options': next_q.options,
                        'hint': next_q.hint or '',
                        'time_limit': next_q.time_limit or 30
                    },
                    'question_number': game.current_question_index + 1,
                    'total_questions': game.total_questions
                }
        except Exception as e:
            logger.error(f"Error getting next question: {str(e)}", exc_info=True)
            return {'error': 'Failed to get next question'}

    @database_sync_to_async
    def get_hint(self, question_id):
        """Get hint for question."""
        try:
            question = Question.objects.get(id=question_id)
            hint = question.hint or ''
            logger.info(f"Retrieved hint for question {question_id}: {hint}")
            return hint
        except ObjectDoesNotExist:
            logger.error(f"Question {question_id} not found")
            return None

    @database_sync_to_async
    def get_final_results(self):
        """Calculate final results."""
        try:
            room = Room.objects.get(code=self.room_code)
            game = Game.objects.get(room=room)
            results = GameScore.objects.filter(game=game).select_related('player').order_by(
                '-total_score', 'created_at'
            )
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
        """Send error message."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': self._get_timestamp()
        }))

    @staticmethod
    def _get_timestamp():
        """Get current timestamp."""
        return datetime.utcnow().isoformat() + 'Z'