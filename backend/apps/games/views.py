"""
Game views - FIXED VERSION
Fixed final standings endpoint
"""
import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Game, Question, Answer, GameScore
from .serializers import (
    GameSerializer,
    GameDetailSerializer,
    QuestionSerializer,
    QuestionWithoutAnswerSerializer,
    SubmitAnswerSerializer,
    GameScoreSerializer,
    AnswerSerializer,
)
from ..users.models import Player
from ..core.exceptions import GameException

logger = logging.getLogger(__name__)


class GameDetailView(generics.RetrieveAPIView):
    """Get game details."""
    queryset = Game.objects.select_related('room').prefetch_related('scores__player', 'questions')
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        """Use detailed serializer for completed games."""
        game = self.get_object()
        if game.status == 'completed':
            return GameDetailSerializer
        return GameSerializer


class QuestionDetailView(generics.RetrieveAPIView):
    """Get question details."""
    queryset = Question.objects.select_related('game')
    permission_classes = [AllowAny]
    lookup_url_kwarg = 'question_id'

    def get_serializer_class(self):
        """Hide correct answer for active games."""
        question = self.get_object()
        if question.game.status == 'completed':
            return QuestionSerializer
        return QuestionWithoutAnswerSerializer


class SubmitAnswerView(APIView):
    """Submit an answer to a question."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, game_id):
        """Submit an answer with atomic transaction."""
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            game = get_object_or_404(Game.objects.select_for_update(), id=game_id)
            player = get_object_or_404(Player, id=serializer.validated_data['player_id'])
            question = get_object_or_404(
                Question.objects.select_related('game'),
                id=serializer.validated_data['question_id'],
                game=game
            )

            # Validate game is active
            if game.status not in ['active', 'pending']:
                raise GameException(
                    detail='Cannot submit answers for completed games.',
                    code='game_completed'
                )

            # Validate player is in the game
            if not game.room.players.filter(player=player).exists():
                raise GameException(
                    detail='Player is not part of this game.',
                    code='player_not_in_game'
                )

            # Validate this is the current question
            if question.order != game.current_question_index:
                raise GameException(
                    detail='This is not the current question.',
                    code='invalid_question'
                )

            # Check if answer already exists
            existing_answer = Answer.objects.select_for_update().filter(
                question=question,
                player=player
            ).first()

            if existing_answer:
                return Response(
                    {
                        'error': {
                            'code': 'answer_already_submitted',
                            'message': 'Answer already submitted for this question.'
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate time taken
            time_taken = serializer.validated_data['time_taken']
            if time_taken > question.time_limit:
                return Response(
                    {
                        'error': {
                            'code': 'time_limit_exceeded',
                            'message': f'Time limit of {question.time_limit} seconds exceeded.'
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if time_taken < 0:
                raise GameException(
                    detail='Invalid time taken value.',
                    code='invalid_time_taken'
                )

            # Check if answer is correct
            answer_text = serializer.validated_data['answer_text'].strip().lower()
            correct_answer = question.correct_answer.strip().lower()
            is_correct = answer_text == correct_answer

            # Create answer with calculated points
            answer = Answer.objects.create(
                question=question,
                player=player,
                answer_text=serializer.validated_data['answer_text'],
                is_correct=is_correct,
                used_hint=serializer.validated_data['used_hint'],
                time_taken=time_taken
            )

            # Calculate and save points
            points = answer.calculate_points()
            answer.points_earned = points
            answer.save(update_fields=['points_earned'])

            # Update game score
            game_score, created = GameScore.objects.select_for_update().get_or_create(
                game=game,
                player=player,
                defaults={'total_score': 0, 'correct_answers': 0, 'wrong_answers': 0}
            )
            game_score.update_score(answer)

            logger.info(
                f"Answer submitted: Player={player.username}, "
                f"Question={question.order}, Correct={is_correct}, Points={points}"
            )

            response_data = {
                'is_correct': is_correct,
                'points_earned': points,
                'total_score': game_score.total_score,
                'answer': AnswerSerializer(answer).data
            }

            if not is_correct:
                response_data['correct_answer'] = question.correct_answer

            return Response(response_data, status=status.HTTP_201_CREATED)

        except GameException:
            raise
        except Exception as e:
            logger.error(f"Error submitting answer: {str(e)}", exc_info=True)
            raise GameException(
                detail=f'Failed to submit answer: {str(e)}',
                code='answer_submission_failed'
            )


class GameLeaderboardView(APIView):
    """Get game leaderboard."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def get(self, request, pk):
        """Get leaderboard with rankings."""
        game = get_object_or_404(
            Game.objects.prefetch_related('scores__player'),
            id=pk
        )

        # Get all scores
        scores = GameScore.objects.select_for_update().filter(game=game).select_related('player').order_by(
            '-total_score', 'created_at'
        )

        # Assign ranks
        current_rank = 1
        previous_score = None
        rank_counter = 1
        scores_to_update = []

        for score in scores:
            # Handle ties
            if previous_score is not None and score.total_score < previous_score:
                current_rank = rank_counter

            if score.rank != current_rank:
                score.rank = current_rank
                scores_to_update.append(score)

            previous_score = score.total_score
            rank_counter += 1

        # Bulk update ranks
        if scores_to_update:
            GameScore.objects.bulk_update(scores_to_update, ['rank'])

        serializer = GameScoreSerializer(scores, many=True)

        return Response({
            'game_id': str(game.id),
            'game_status': game.status,
            'leaderboard': serializer.data
        })


class GameQuestionsView(generics.ListAPIView):
    """Get all questions for a game (only for completed games)."""
    permission_classes = [AllowAny]
    serializer_class = QuestionSerializer

    def get_queryset(self):
        """Get questions only for completed games."""
        game_id = self.kwargs.get('pk')
        game = get_object_or_404(Game, id=game_id)

        if game.status != 'completed':
            raise GameException(
                detail='Questions are only available for completed games.',
                code='game_not_completed'
            )

        return Question.objects.filter(game=game).order_by('order')


class NextQuestionView(APIView):
    """Advance to next question (host only)."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, game_id):
        """Move to next question."""
        try:
            game = get_object_or_404(
                Game.objects.select_for_update().select_related('room'),
                id=game_id
            )

            # Validate game is active
            if game.status != 'active':
                raise GameException(
                    detail='Game is not active.',
                    code='game_not_active'
                )

            # Validate host
            player_id = request.data.get('player_id')
            if not player_id:
                raise GameException(
                    detail='player_id is required.',
                    code='missing_player_id'
                )

            player = get_object_or_404(Player, id=player_id)

            if game.room.host_id != player.id:
                from ..core.exceptions import NotHostException
                raise NotHostException()

            # Move to next question
            next_q = game.next_question()

            if next_q is None:
                # Game completed
                return Response({
                    'status': 'completed',
                    'message': 'Game has been completed.',
                    'game': GameSerializer(game).data
                }, status=status.HTTP_200_OK)

            return Response({
                'status': 'success',
                'message': 'Moved to next question.',
                'current_question_index': game.current_question_index,
                'current_question': QuestionWithoutAnswerSerializer(next_q).data,
                'total_questions': game.total_questions
            }, status=status.HTTP_200_OK)

        except (GameException, NotHostException):
            raise
        except Exception as e:
            logger.error(f"Error advancing to next question: {str(e)}", exc_info=True)
            raise GameException(
                detail=f'Failed to advance to next question: {str(e)}',
                code='next_question_failed'
            )


class CurrentQuestionView(APIView):
    """Get the current question for an active game."""
    permission_classes = [AllowAny]

    def get(self, request, game_id):
        """Get current question."""
        game = get_object_or_404(
            Game.objects.select_related('room').prefetch_related('questions'),
            id=game_id
        )

        if game.status not in ['active', 'pending']:
            raise GameException(
                detail='Game is not active.',
                code='game_not_active'
            )

        current_question = game.current_question

        if not current_question:
            return Response({
                'message': 'No current question available.',
                'game_status': game.status
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = QuestionWithoutAnswerSerializer(current_question)

        return Response({
            'current_question': serializer.data,
            'current_question_index': game.current_question_index,
            'total_questions': game.total_questions,
            'progress_percentage': round((game.current_question_index / game.total_questions) * 100, 2) if game.total_questions > 0 else 0
        })


class RoomGamesListView(APIView):
    """Get all games for a room (for results page)."""
    permission_classes = [AllowAny]

    def get(self, request, room_code):
        """Get games for a room."""
        from ..rooms.models import Room

        room = get_object_or_404(Room, code=room_code)

        # Get all games for this room, ordered by most recent first
        games = Game.objects.filter(room=room).order_by('-created_at')

        games_data = []
        for game in games:
            games_data.append({
                'id': str(game.id),
                'status': game.status,
                'started_at': game.started_at,
                'completed_at': game.completed_at,
                'total_questions': game.total_questions,
                'current_question_index': game.current_question_index
            })

        return Response({
            'room_code': room_code,
            'games': games_data
        })