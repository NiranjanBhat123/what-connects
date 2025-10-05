"""
Admin configuration for games app.
"""
from django.contrib import admin
from ..core.admin import TimeStampedAdmin
from .models import Game, Question, Answer, GameScore


class QuestionInline(admin.TabularInline):
    """Inline admin for questions."""
    model = Question
    extra = 0
    readonly_fields = ['id', 'created_at', 'updated_at']
    fields = ['order', 'text', 'items', 'correct_answer', 'hint', 'time_limit']


class GameScoreInline(admin.TabularInline):
    """Inline admin for game scores."""
    model = GameScore
    extra = 0
    readonly_fields = ['id', 'total_score', 'correct_answers', 'wrong_answers', 'rank', 'created_at', 'updated_at']
    fields = ['player', 'total_score', 'correct_answers', 'wrong_answers', 'rank']


@admin.register(Game)
class GameAdmin(TimeStampedAdmin):
    """Admin interface for Game model."""
    list_display = ['id', 'room', 'status', 'current_question_index', 'total_questions', 'started_at']
    search_fields = ['room__code', 'room__name']
    list_filter = ['status', 'started_at', 'created_at']
    readonly_fields = ['id', 'started_at', 'completed_at', 'created_at', 'updated_at']
    inlines = [QuestionInline, GameScoreInline]

    fieldsets = (
        ('Game Info', {
            'fields': ('id', 'room', 'status')
        }),
        ('Progress', {
            'fields': ('current_question_index', 'started_at', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Question)
class QuestionAdmin(TimeStampedAdmin):
    """Admin interface for Question model."""
    list_display = ['order', 'game', 'text_preview', 'correct_answer', 'time_limit', 'created_at']
    search_fields = ['text', 'correct_answer', 'game__room__code']
    list_filter = ['game__status', 'time_limit', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['game', 'order']

    fieldsets = (
        ('Question Info', {
            'fields': ('id', 'game', 'order', 'text')
        }),
        ('Items & Answer', {
            'fields': ('items', 'correct_answer', 'hint')
        }),
        ('Settings', {
            'fields': ('time_limit',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def text_preview(self, obj):
        """Show preview of question text."""
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Question Text'


@admin.register(Answer)
class AnswerAdmin(TimeStampedAdmin):
    """Admin interface for Answer model."""
    list_display = ['player', 'question_order', 'game', 'is_correct', 'used_hint', 'points_earned', 'time_taken', 'created_at']
    search_fields = ['player__username', 'answer_text', 'question__game__room__code']
    list_filter = ['is_correct', 'used_hint', 'created_at']
    readonly_fields = ['id', 'points_earned', 'created_at', 'updated_at']

    fieldsets = (
        ('Answer Info', {
            'fields': ('id', 'player', 'question', 'answer_text', 'is_correct')
        }),
        ('Performance', {
            'fields': ('time_taken', 'used_hint', 'points_earned')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def question_order(self, obj):
        """Show question order."""
        return f"Q{obj.question.order + 1}"
    question_order.short_description = 'Question'

    def game(self, obj):
        """Show game."""
        return obj.question.game.room.code
    game.short_description = 'Game'


@admin.register(GameScore)
class GameScoreAdmin(TimeStampedAdmin):
    """Admin interface for GameScore model."""
    list_display = ['player', 'game_code', 'total_score', 'correct_answers', 'wrong_answers', 'rank', 'created_at']
    search_fields = ['player__username', 'game__room__code']
    list_filter = ['rank', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['game', '-total_score']

    fieldsets = (
        ('Player Info', {
            'fields': ('id', 'player', 'game')
        }),
        ('Score Details', {
            'fields': ('total_score', 'correct_answers', 'wrong_answers', 'rank')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def game_code(self, obj):
        """Show game room code."""
        return obj.game.room.code
    game_code.short_description = 'Room Code'