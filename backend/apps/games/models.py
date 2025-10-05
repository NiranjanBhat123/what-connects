"""
Game models for WhatConnects.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from ..core.models import TimeStampedModel, UUIDModel


class GameManager(models.Manager):
    """Custom manager for Game model."""

    def active(self):
        """Get active games."""
        return self.filter(status='active')

    def completed(self):
        """Get completed games."""
        return self.filter(status='completed')


class Game(UUIDModel, TimeStampedModel):
    """Game model."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]

    room = models.ForeignKey('rooms.Room', on_delete=models.CASCADE, related_name='games')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    current_question_index = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = GameManager()

    class Meta:
        db_table = 'games'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['room', '-created_at']),
        ]

    def __str__(self):
        return f"Game {self.id} - {self.room.code}"

    @property
    def total_questions(self):
        """Get total number of questions."""
        return self.questions.count()

    @property
    def current_question(self):
        """Get current question."""
        questions = self.questions.order_by('order')
        if self.current_question_index < questions.count():
            return questions[self.current_question_index]
        return None

    @property
    def is_active(self):
        """Check if game is active."""
        return self.status == 'active'

    @property
    def is_completed(self):
        """Check if game is completed."""
        return self.status == 'completed'

    def next_question(self):
        """
        Move to next question.
        Returns the new current question or None if game is complete.
        """
        self.current_question_index += 1
        if self.current_question_index >= self.total_questions:
            self.complete_game()
            return None
        self.save(update_fields=['current_question_index', 'updated_at'])
        return self.current_question

    def complete_game(self):
        """Mark game as completed and update room status."""
        if self.status == 'completed':
            return  # Already completed

        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

        # Update room status
        self.room.status = 'completed'
        self.room.save(update_fields=['status', 'updated_at'])

    def get_player_answers(self, player):
        """Get all answers from a specific player in this game."""
        return Answer.objects.filter(
            question__game=self,
            player=player
        ).select_related('question').order_by('question__order')

    def get_leaderboard(self):
        """Get ordered leaderboard for this game."""
        return self.scores.select_related('player').order_by('-total_score', 'created_at')


class Question(UUIDModel, TimeStampedModel):
    """Question model."""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='questions')
    order = models.IntegerField(db_index=True)
    text = models.TextField()
    items = models.JSONField()  # List of 4 items to connect
    correct_answer = models.CharField(max_length=500)
    hint = models.TextField(blank=True)
    time_limit = models.IntegerField(default=30)  # seconds

    class Meta:
        db_table = 'questions'
        ordering = ['order']
        unique_together = ['game', 'order']
        indexes = [
            models.Index(fields=['game', 'order']),
        ]

    def __str__(self):
        return f"Question {self.order + 1} - Game {self.game.id}"

    def clean(self):
        """Validate question data."""
        from django.core.exceptions import ValidationError

        if not isinstance(self.items, list):
            raise ValidationError({'items': 'Items must be a list'})

        if len(self.items) != 4:
            raise ValidationError({'items': 'Must have exactly 4 items'})

        if not self.correct_answer.strip():
            raise ValidationError({'correct_answer': 'Answer cannot be empty'})

    def check_answer(self, answer_text):
        """
        Check if an answer is correct.
        Case-insensitive comparison with whitespace trimming.
        """
        return answer_text.strip().lower() == self.correct_answer.strip().lower()

    @property
    def answer_count(self):
        """Get number of answers submitted for this question."""
        return self.answers.count()

    @property
    def correct_answer_count(self):
        """Get number of correct answers for this question."""
        return self.answers.filter(is_correct=True).count()


class Answer(UUIDModel, TimeStampedModel):
    """Answer submission model."""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    player = models.ForeignKey('users.Player', on_delete=models.CASCADE, related_name='answers')
    answer_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False, db_index=True)
    used_hint = models.BooleanField(default=False, db_index=True)
    time_taken = models.IntegerField()  # seconds
    points_earned = models.IntegerField(default=0)

    class Meta:
        db_table = 'answers'
        unique_together = ['question', 'player']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['question', 'player']),
            models.Index(fields=['player', '-created_at']),
            models.Index(fields=['is_correct', '-created_at']),
        ]

    def __str__(self):
        return f"{self.player.username} - Q{self.question.order + 1}"

    def calculate_points(self):
        """
        Calculate points for this answer based on game settings.
        Returns the points earned.
        """
        # Default game settings if not configured
        default_settings = {
            'CORRECT_ANSWER_POINTS': 100,
            'CORRECT_ANSWER_WITH_HINT_POINTS': 50,
            'WRONG_ANSWER_POINTS': 0,
            'WRONG_ANSWER_WITH_HINT_POINTS': -10,
        }

        game_settings = getattr(settings, 'GAME_SETTINGS', default_settings)

        if self.is_correct:
            if self.used_hint:
                self.points_earned = game_settings.get(
                    'CORRECT_ANSWER_WITH_HINT_POINTS',
                    default_settings['CORRECT_ANSWER_WITH_HINT_POINTS']
                )
            else:
                self.points_earned = game_settings.get(
                    'CORRECT_ANSWER_POINTS',
                    default_settings['CORRECT_ANSWER_POINTS']
                )
        else:
            if self.used_hint:
                self.points_earned = game_settings.get(
                    'WRONG_ANSWER_WITH_HINT_POINTS',
                    default_settings['WRONG_ANSWER_WITH_HINT_POINTS']
                )
            else:
                self.points_earned = game_settings.get(
                    'WRONG_ANSWER_POINTS',
                    default_settings['WRONG_ANSWER_POINTS']
                )

        self.save(update_fields=['points_earned', 'updated_at'])
        return self.points_earned


class GameScoreManager(models.Manager):
    """Custom manager for GameScore model."""

    def get_ranked_scores(self, game):
        """Get scores with rankings for a game."""
        return self.filter(game=game).order_by('-total_score', 'created_at')

    def top_players(self, game, limit=10):
        """Get top N players for a game."""
        return self.get_ranked_scores(game)[:limit]


class GameScore(UUIDModel, TimeStampedModel):
    """Player scores for a game."""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='scores')
    player = models.ForeignKey('users.Player', on_delete=models.CASCADE, related_name='game_scores')
    total_score = models.IntegerField(default=0, db_index=True)
    correct_answers = models.IntegerField(default=0)
    wrong_answers = models.IntegerField(default=0)
    rank = models.IntegerField(null=True, blank=True, db_index=True)

    objects = GameScoreManager()

    class Meta:
        db_table = 'game_scores'
        unique_together = ['game', 'player']
        ordering = ['-total_score', 'created_at']
        indexes = [
            models.Index(fields=['game', '-total_score']),
            models.Index(fields=['player', '-total_score']),
        ]

    def __str__(self):
        return f"{self.player.username} - Game {self.game.id}: {self.total_score} pts"

    @property
    def accuracy(self):
        """Calculate accuracy percentage."""
        total_answers = self.correct_answers + self.wrong_answers
        if total_answers == 0:
            return 0
        return round((self.correct_answers / total_answers) * 100, 2)

    def update_score(self, answer):
        """
        Update score based on answer.

        Args:
            answer: Answer instance
        """
        self.total_score += answer.points_earned
        if answer.is_correct:
            self.correct_answers += 1
        else:
            self.wrong_answers += 1
        self.save(update_fields=['total_score', 'correct_answers', 'wrong_answers', 'updated_at'])

    def reset_score(self):
        """Reset score to zero (useful for game restarts)."""
        self.total_score = 0
        self.correct_answers = 0
        self.wrong_answers = 0
        self.rank = None
        self.save()