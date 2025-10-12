"""
Game serializers.
"""
from rest_framework import serializers
from ..core.serializers import TimeStampedSerializer
from .models import Game, Question, Answer, GameScore
from ..users.serializers import PlayerSerializer


class QuestionSerializer(TimeStampedSerializer):
    """Serializer for Question model."""

    class Meta:
        model = Question
        fields = ['id', 'order', 'items', 'options', 'correct_answer', 'hint', 'time_limit', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuestionWithoutAnswerSerializer(TimeStampedSerializer):
    """Serializer for Question model without correct answer (for active gameplay)."""

    class Meta:
        model = Question
        fields = ['id', 'order', 'items', 'options', 'hint', 'time_limit', 'created_at']
        read_only_fields = ['id', 'created_at']


class AnswerSerializer(TimeStampedSerializer):
    """Serializer for Answer model."""
    player = PlayerSerializer(read_only=True)
    player_username = serializers.CharField(source='player.username', read_only=True)

    class Meta:
        model = Answer
        fields = [
            'id', 'player', 'player_username', 'answer_text', 'is_correct',
            'used_hint', 'time_taken', 'points_earned', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_correct', 'points_earned', 'created_at', 'updated_at']


class GameScoreSerializer(TimeStampedSerializer):
    """Serializer for GameScore model."""
    player = PlayerSerializer(read_only=True)
    player_username = serializers.CharField(source='player.username', read_only=True)
    accuracy = serializers.SerializerMethodField()

    class Meta:
        model = GameScore
        fields = [
            'id', 'player', 'player_username', 'total_score', 'correct_answers',
            'wrong_answers', 'hints_used', 'accuracy', 'rank', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_accuracy(self, obj):
        return obj.accuracy


class GameSerializer(TimeStampedSerializer):
    """Serializer for Game model."""
    current_question = QuestionWithoutAnswerSerializer(read_only=True)
    scores = GameScoreSerializer(many=True, read_only=True)
    room_code = serializers.CharField(source='room.code', read_only=True)

    class Meta:
        model = Game
        fields = [
            'id', 'room_code', 'status', 'current_question_index', 'total_questions',
            'current_question', 'scores', 'started_at', 'completed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'current_question_index', 'started_at',
            'completed_at', 'created_at', 'updated_at'
        ]


class GameDetailSerializer(TimeStampedSerializer):
    """Detailed serializer for Game with all questions (for completed games)."""
    questions = QuestionSerializer(many=True, read_only=True)
    scores = GameScoreSerializer(many=True, read_only=True)
    room_code = serializers.CharField(source='room.code', read_only=True)

    class Meta:
        model = Game
        fields = [
            'id', 'room_code', 'status', 'current_question_index', 'total_questions',
            'questions', 'scores', 'started_at', 'completed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'current_question_index', 'started_at',
            'completed_at', 'created_at', 'updated_at'
        ]


class SubmitAnswerSerializer(serializers.Serializer):
    """Serializer for submitting an answer."""
    player_id = serializers.UUIDField()
    question_id = serializers.UUIDField()
    answer_text = serializers.CharField(max_length=200, allow_blank=False)
    used_hint = serializers.BooleanField(default=False)
    time_taken = serializers.IntegerField(min_value=0)

    def validate_answer_text(self, value):
        """Validate answer text is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Answer cannot be empty.")
        return value.strip()