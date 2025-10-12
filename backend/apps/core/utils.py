import random
import string


def generate_code(length=6, uppercase=True):
    """Generate a random alphanumeric code."""
    chars = string.ascii_uppercase + string.digits if uppercase else string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

"""
Utility to handle question timers and automatic leaderboard updates.
Add this to core/utils.py or websockets/timer_utils.py
"""
import asyncio
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class QuestionTimerManager:
    """Manages timers for questions to automatically update leaderboards."""

    def __init__(self):
        self.timers = {}  # room_code -> asyncio.Task

    async def start_question_timer(self, room_code, question_id, duration=30):
        """
        Start a timer for a question. After duration, broadcast leaderboard update.

        Args:
            room_code: Room code
            question_id: Question ID
            duration: Timer duration in seconds (default 30)
        """
        # Cancel existing timer if any
        if room_code in self.timers:
            self.timers[room_code].cancel()

        # Create new timer
        task = asyncio.create_task(
            self._question_timer_task(room_code, question_id, duration)
        )
        self.timers[room_code] = task

    async def _question_timer_task(self, room_code, question_id, duration):
        """Timer task that runs for the question duration."""
        try:
            logger.info(f"Started {duration}s timer for question {question_id} in room {room_code}")

            # Wait for the duration
            await asyncio.sleep(duration)

            logger.info(f"Timer expired for question {question_id} in room {room_code}")

            # Get leaderboard and broadcast
            from ..games.models import Game, GameScore
            from ..rooms.models import Room

            try:
                room = await self._get_room(room_code)
                game = await self._get_active_game(room)
                leaderboard = await self._get_leaderboard(game)

                # Broadcast leaderboard update
                channel_layer = get_channel_layer()
                if channel_layer:
                    await channel_layer.group_send(
                        f'game_room_{room_code}',
                        {
                            'type': 'leaderboard_update',
                            'leaderboard': leaderboard,
                            'timestamp': self._get_timestamp()
                        }
                    )
                    logger.info(f"Broadcasted leaderboard update for room {room_code}")

            except Exception as e:
                logger.error(f"Error broadcasting leaderboard for room {room_code}: {str(e)}")

        except asyncio.CancelledError:
            logger.info(f"Timer cancelled for room {room_code}")
        except Exception as e:
            logger.error(f"Error in question timer for room {room_code}: {str(e)}", exc_info=True)
        finally:
            # Clean up
            if room_code in self.timers:
                del self.timers[room_code]

    def cancel_timer(self, room_code):
        """Cancel timer for a room."""
        if room_code in self.timers:
            self.timers[room_code].cancel()
            del self.timers[room_code]
            logger.info(f"Cancelled timer for room {room_code}")

    @staticmethod
    async def _get_room(room_code):
        """Get room from database (async)."""
        from channels.db import database_sync_to_async
        from ..rooms.models import Room

        @database_sync_to_async
        def get_room():
            return Room.objects.get(code=room_code)

        return await get_room()

    @staticmethod
    async def _get_active_game(room):
        """Get active game for room (async)."""
        from channels.db import database_sync_to_async
        from ..games.models import Game

        @database_sync_to_async
        def get_game():
            return Game.objects.filter(room=room, status='active').latest('created_at')

        return await get_game()

    @staticmethod
    async def _get_leaderboard(game):
        """Get leaderboard for game (async)."""
        from channels.db import database_sync_to_async
        from ..games.models import GameScore

        @database_sync_to_async
        def get_leaderboard():
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

        return await get_leaderboard()

    @staticmethod
    def _get_timestamp():
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'


# Singleton instance
timer_manager = QuestionTimerManager()