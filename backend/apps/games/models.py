"""
Fixed Game model - started_at should be nullable for pending games
"""
from django.db import models
from django.conf import settings
from ..core.models import TimeStampedModel, UUIDModel


class GameManager(models.Manager):
    """Custom manager for Game model."""

    def active(self):
        """Get active games."""
        return self.filter(status='active')

    def pending(self):
        """Get pending games."""
        return self.filter(status='pending')

    def completed(self):
        """Get completed games."""
        return self.filter(status='completed')


class Game(UUIDModel, TimeStampedModel):
    """Game model - represents a trivia game session."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),      # Questions generated, waiting to start
        ('active', 'Active'),         # Game in progress
        ('completed', 'Completed'),   # Game finished
    ]

    room = models.ForeignKey(
        'rooms.Room',
        on_delete=models.CASCADE,
        related_name='games'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    current_question_index = models.IntegerField(default=0)

    # FIXED: Make these nullable for pending games
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = GameManager()

    class Meta:
        db_table = 'games'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Game {self.id} - {self.room.code} ({self.status})"

    @property
    def total_questions(self):
        """Get total number of questions in this game."""
        return self.questions.count()

    @property
    def current_question(self):
        """Get the current question based on current_question_index."""
        try:
            return self.questions.get(order=self.current_question_index)
        except models.ObjectDoesNotExist:
            return None

    def next_question(self):
        """Move to next question and return it."""
        self.current_question_index += 1
        self.save(update_fields=['current_question_index'])
        return self.current_question

    def start(self):
        """Start the game - set started_at timestamp."""
        from django.utils import timezone
        if not self.started_at:
            self.started_at = timezone.now()
            self.status = 'active'
            self.save(update_fields=['started_at', 'status'])

    def complete(self):
        """Complete the game."""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def save(self, *args, **kwargs):
        """Override save to handle status transitions."""
        # Only set started_at when game becomes active
        if self.status == 'active' and not self.started_at:
            from django.utils import timezone
            self.started_at = timezone.now()

        super().save(*args, **kwargs)


class Question(UUIDModel, TimeStampedModel):
    """Question model for trivia questions."""

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    order = models.IntegerField(db_index=True)
    items = models.JSONField(help_text="List of 4 items to find connection")
    correct_answer = models.CharField(max_length=500)
    options = models.JSONField(help_text="List of 4 multiple choice options")
    hint = models.TextField(blank=True, null=True)
    time_limit = models.IntegerField(default=30, help_text="Time limit in seconds")

    class Meta:
        db_table = 'questions'
        ordering = ['game', 'order']
        unique_together = ['game', 'order']
        indexes = [
            models.Index(fields=['game', 'order']),
        ]

    def __str__(self):
        return f"Question {self.order} - {self.game.room.code}"

    def check_answer(self, answer):
        """Check if the provided answer is correct (case-insensitive)."""
        return answer.strip().lower() == self.correct_answer.strip().lower()


class Answer(UUIDModel, TimeStampedModel):
    """Answer model - records player answers."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    player = models.ForeignKey(
        'users.Player',
        on_delete=models.CASCADE,
        related_name='answers'
    )
    answer_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False, db_index=True)
    time_taken = models.IntegerField(help_text="Time taken in seconds")
    used_hint = models.BooleanField(default=False)
    points_earned = models.IntegerField(default=0)

    class Meta:
        db_table = 'answers'
        ordering = ['created_at']
        unique_together = ['question', 'player']
        indexes = [
            models.Index(fields=['question', 'player']),
            models.Index(fields=['player', 'is_correct']),
        ]

    def __str__(self):
        return f"{self.player.username} - Q{self.question.order}"

    def calculate_points(self):
        """Calculate points earned for this answer."""
        if self.is_correct:
            # Correct answer: +10 without hint, +5 with hint
            return 5 if self.used_hint else 10
        else:
            # Wrong answer: -5 with hint, 0 without hint
            return -5 if self.used_hint else 0


class GameScore(UUIDModel, TimeStampedModel):
    """Game score model - tracks player scores per game."""

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='scores'
    )
    player = models.ForeignKey(
        'users.Player',
        on_delete=models.CASCADE,
        related_name='game_scores'
    )
    total_score = models.IntegerField(default=0, db_index=True)
    correct_answers = models.IntegerField(default=0)
    wrong_answers = models.IntegerField(default=0)
    hints_used = models.IntegerField(default=0)
    rank = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'game_scores'
        ordering = ['-total_score', 'created_at']
        unique_together = ['game', 'player']
        indexes = [
            models.Index(fields=['game', '-total_score']),
            models.Index(fields=['player', '-total_score']),
        ]

    def __str__(self):
        return f"{self.player.username} - {self.total_score} pts"

    @property
    def accuracy(self):
        """Calculate accuracy percentage."""
        total = self.correct_answers + self.wrong_answers
        if total == 0:
            return 0
        return round((self.correct_answers / total) * 100, 2)

    def update_score(self, answer):
        """Update score based on an answer."""
        points = answer.calculate_points()
        self.total_score += points

        if answer.is_correct:
            self.correct_answers += 1
        else:
            self.wrong_answers += 1

        if answer.used_hint:
            self.hints_used += 1

        self.save(update_fields=['total_score', 'correct_answers', 'wrong_answers', 'hints_used'])