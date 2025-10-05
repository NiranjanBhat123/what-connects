"""
Signals for WebSocket-related events.
These handle automatic notifications when models change.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from ..rooms.models import Room, RoomPlayer
from ..games.models import Game, Answer
from .utils import send_to_room, broadcast_game_update
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=RoomPlayer)
@receiver(post_delete, sender=RoomPlayer)
def room_player_changed(sender, instance, **kwargs):
    """Notify room when players join or leave."""
    try:
        room = instance.room
        players_data = [
            {
                'id': str(rp.player.id),
                'username': rp.player.username,
                'score': rp.score
            }
            for rp in room.players.all()
        ]

        send_to_room(
            room.code,
            'game_state_update',
            {
                'state': {
                    'room_code': room.code,
                    'players': players_data,
                    'player_count': len(players_data)
                }
            }
        )
        logger.info(f"Notified room {room.code} of player change")
    except Exception as e:
        logger.error(f"Failed to notify room of player change: {str(e)}")


@receiver(post_save, sender=Game)
def game_updated(sender, instance, created, **kwargs):
    """Notify room when game is created or updated."""
    if not created and instance.status in ['active', 'completed']:
        try:
            # Get current game state
            game_state = {
                'status': instance.status,
                'current_question_index': instance.current_question_index,
                'total_questions': instance.total_questions
            }

            if instance.status == 'completed':
                # Include final results
                from ..games.models import GameScore
                from django.db.models import Q

                results = GameScore.objects.filter(
                    game=instance
                ).select_related('player').order_by('-total_score', 'created_at')

                game_state['results'] = [
                    {
                        'player_id': str(score.player.id),
                        'player_name': score.player.username,
                        'total_score': score.total_score,
                        'correct_answers': score.correct_answers,
                        'accuracy': score.accuracy
                    }
                    for score in results
                ]

            broadcast_game_update(instance.room.code, game_state)
            logger.info(f"Broadcasted game update for room {instance.room.code}")

        except Exception as e:
            logger.error(f"Failed to broadcast game update: {str(e)}")


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
            total_players = room.players.filter(is_active=True).count()

            # If all players answered, notify room
            if answers_count >= total_players:
                send_to_room(
                    room.code,
                    'game_state_update',
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