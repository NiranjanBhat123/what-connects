"""
Signals for WebSocket-related events.
FIXED VERSION - Disabled auto-broadcasting to prevent conflicts
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from ..rooms.models import Room, RoomPlayer
from ..games.models import Game, Answer
from .utils import send_to_room, broadcast_game_update
import logging

logger = logging.getLogger(__name__)


# DISABLED: This signal causes issues during game start
# The views.py already handles broadcasting via channel_layer
# @receiver(post_save, sender=RoomPlayer)
# @receiver(post_delete, sender=RoomPlayer)
# def room_player_changed(sender, instance, **kwargs):
#     """Notify room when players join or leave."""
#     pass


# DISABLED: This signal conflicts with manual broadcasting in views
# @receiver(post_save, sender=Game)
# def game_updated(sender, instance, created, **kwargs):
#     """Notify room when game is created or updated."""
#     pass


@receiver(post_save, sender=Answer)
def answer_submitted(sender, instance, created, **kwargs):
    """Notify room when a player submits an answer."""
    if created:
        try:
            # Check if all players have answered current question
            question = instance.question
            game = question.game
            room = game.room

            # Count answers for this question
            answers_count = Answer.objects.filter(
                question=question
            ).count()

            # Count active players in room
            total_players = room.players.count()

            # If all players answered, notify room
            if answers_count >= total_players:
                send_to_room(
                    room.code,
                    'all_players_answered',
                    {
                        'state': {
                            'all_answered': True,
                            'question_id': str(question.id),
                            'question_number': question.order + 1
                        }
                    }
                )
                logger.info(f"All players answered question {question.order + 1} in room {room.code}")

        except Exception as e:
            logger.error(f"Failed to process answer signal: {str(e)}")