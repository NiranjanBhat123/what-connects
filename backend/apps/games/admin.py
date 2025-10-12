"""
Enhanced admin configuration for games app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.urls import reverse
from ..core.admin import TimeStampedAdmin
from .models import Game, Question, Answer, GameScore


class QuestionInline(admin.TabularInline):
    """Inline admin for questions with better display."""
    model = Question
    extra = 0
    readonly_fields = ['id', 'answer_count', 'correct_rate', 'created_at']
    fields = ['order', 'items_display', 'options_display', 'correct_answer', 'hint_display', 'time_limit', 'answer_count', 'correct_rate']

    def items_display(self, obj):
        """Display items as comma-separated list."""
        if obj.items:
            return ', '.join(str(item) for item in obj.items)
        return '-'
    items_display.short_description = 'Items'

    def options_display(self, obj):
        """Display MCQ options."""
        if obj.options:
            return ', '.join(str(opt) for opt in obj.options)
        return '-'
    options_display.short_description = 'Options'

    def hint_display(self, obj):
        """Show hint preview."""
        if obj.hint:
            return obj.hint[:30] + '...' if len(obj.hint) > 30 else obj.hint
        return 'No hint'
    hint_display.short_description = 'Hint'

    def answer_count(self, obj):
        """Show number of answers."""
        if obj.id:
            return obj.answers.count()
        return 0
    answer_count.short_description = 'Answers'

    def correct_rate(self, obj):
        """Show percentage of correct answers."""
        if obj.id:
            total = obj.answers.count()
            if total > 0:
                correct = obj.answers.filter(is_correct=True).count()
                percentage = (correct / total) * 100
                color = 'green' if percentage >= 50 else 'orange' if percentage >= 25 else 'red'
                return format_html(
                    '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                    color, percentage
                )
        return '-'
    correct_rate.short_description = 'Correct %'


class GameScoreInline(admin.TabularInline):
    """Inline admin for game scores with rankings."""
    model = GameScore
    extra = 0
    readonly_fields = ['id', 'total_score', 'correct_answers', 'wrong_answers', 'hints_used', 'accuracy_display', 'rank_display', 'created_at']
    fields = ['player', 'total_score', 'correct_answers', 'wrong_answers', 'hints_used', 'accuracy_display', 'rank_display']

    def accuracy_display(self, obj):
        """Display accuracy with color coding."""
        accuracy = obj.accuracy
        if accuracy >= 75:
            color = 'green'
        elif accuracy >= 50:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, accuracy
        )
    accuracy_display.short_description = 'Accuracy'

    def rank_display(self, obj):
        """Display rank with medal emoji."""
        if obj.rank == 1:
            return format_html('<span style="font-size: 18px;">🥇 #{}</span>', obj.rank)
        elif obj.rank == 2:
            return format_html('<span style="font-size: 18px;">🥈 #{}</span>', obj.rank)
        elif obj.rank == 3:
            return format_html('<span style="font-size: 18px;">🥉 #{}</span>', obj.rank)
        return f'#{obj.rank}' if obj.rank else '-'
    rank_display.short_description = 'Rank'


@admin.register(Game)
class GameAdmin(TimeStampedAdmin):
    """Enhanced admin interface for Game model."""
    list_display = ['game_id_short', 'room_display', 'status_display', 'progress_display', 'player_count', 'duration', 'started_at']
    search_fields = ['room__code', 'room__name', 'id']
    list_filter = ['status', 'started_at', 'created_at']
    readonly_fields = ['id', 'game_stats', 'started_at', 'completed_at', 'created_at', 'updated_at']
    inlines = [QuestionInline, GameScoreInline]
    date_hierarchy = 'started_at'

    fieldsets = (
        ('Game Info', {
            'fields': ('id', 'room', 'status')
        }),
        ('Progress', {
            'fields': ('current_question_index', 'game_stats')
        }),
        ('Timeline', {
            'fields': ('started_at', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def game_id_short(self, obj):
        """Display shortened game ID."""
        return str(obj.id)[:8]
    game_id_short.short_description = 'Game ID'

    def room_display(self, obj):
        """Display room with code and name."""
        return format_html(
            '<a href="{}"><strong>{}</strong></a><br/><small>{}</small>',
            reverse('admin:rooms_room_change', args=[obj.room.id]),
            obj.room.code,
            obj.room.name
        )
    room_display.short_description = 'Room'

    def status_display(self, obj):
        """Display status with color."""
        colors = {
            'active': 'orange',
            'completed': 'green',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'), obj.status.upper()
        )
    status_display.short_description = 'Status'

    def progress_display(self, obj):
        """Display progress bar."""
        total = obj.total_questions
        current = obj.current_question_index + 1
        if total > 0:
            percentage = (current / total) * 100
            return format_html(
                '<div style="width: 100px; background: #f0f0f0; border-radius: 3px;">'
                '<div style="width: {}%; background: #4CAF50; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 11px; line-height: 20px;">'
                '{}/{}'
                '</div></div>',
                percentage, current, total
            )
        return '-'
    progress_display.short_description = 'Progress'

    def player_count(self, obj):
        """Show number of players."""
        count = obj.scores.count()
        return format_html('<strong>{}</strong> players', count)
    player_count.short_description = 'Players'

    def duration(self, obj):
        """Calculate game duration."""
        if obj.completed_at and obj.started_at:
            delta = obj.completed_at - obj.started_at
            minutes = delta.total_seconds() / 60
            return f"{minutes:.1f} min"
        elif obj.started_at:
            return "In progress"
        return "-"
    duration.short_description = 'Duration'

    def game_stats(self, obj):
        """Display comprehensive game statistics."""
        if not obj.id:
            return '-'

        stats = obj.scores.aggregate(
            total_players=Count('id'),
            avg_score=Avg('total_score')
        )

        total_answers = Answer.objects.filter(question__game=obj).count()

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<p><strong>Players:</strong> {}</p>'
            '<p><strong>Avg Score:</strong> {:.1f} points</p>'
            '<p><strong>Total Answers:</strong> {}</p>'
            '<p><strong>Questions:</strong> {}</p>'
            '</div>',
            stats['total_players'] or 0,
            stats['avg_score'] or 0,
            total_answers,
            obj.total_questions
        )
    game_stats.short_description = 'Statistics'


@admin.register(Question)
class QuestionAdmin(TimeStampedAdmin):
    """Enhanced admin interface for Question model."""
    list_display = ['question_number', 'game_code', 'items_preview', 'options_count', 'has_hint', 'time_limit', 'answer_stats', 'created_at']
    search_fields = ['correct_answer', 'game__room__code', 'hint']
    list_filter = ['game__status', 'time_limit', 'created_at']
    readonly_fields = ['id', 'answer_statistics', 'created_at', 'updated_at']
    ordering = ['game', 'order']

    fieldsets = (
        ('Question Info', {
            'fields': ('id', 'game', 'order')
        }),
        ('Items & MCQ Options', {
            'fields': ('items', 'options', 'correct_answer', 'hint'),
            'description': 'Items should be a list of 4 related things. Options should be 4 MCQ choices.'
        }),
        ('Settings', {
            'fields': ('time_limit',)
        }),
        ('Statistics', {
            'fields': ('answer_statistics',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def question_number(self, obj):
        """Display question number."""
        return format_html('<strong>Q{}</strong>', obj.order + 1)
    question_number.short_description = '#'

    def game_code(self, obj):
        """Display game room code."""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:games_game_change', args=[obj.game.id]),
            obj.game.room.code
        )
    game_code.short_description = 'Game'

    def items_preview(self, obj):
        """Show preview of items."""
        if obj.items:
            preview = ', '.join(str(item)[:15] for item in obj.items[:2])
            if len(obj.items) > 2:
                preview += '...'
            return preview
        return '-'
    items_preview.short_description = 'Items'

    def options_count(self, obj):
        """Display MCQ options as badges."""
        if obj.options:
            items_html = ''.join([
                f'<span style="background: {"#c8e6c9" if opt == obj.correct_answer else "#e3f2fd"}; padding: 2px 8px; margin: 2px; border-radius: 3px; display: inline-block; font-size: 11px;">{str(opt)[:15]}</span>'
                for opt in obj.options[:4]
            ])
            return format_html(items_html)
        return '-'
    options_count.short_description = 'MCQ Options'

    def has_hint(self, obj):
        """Show if hint exists."""
        if obj.hint:
            return format_html('✅ <small>{}</small>', obj.hint[:30] + '...' if len(obj.hint) > 30 else obj.hint)
        return '❌'
    has_hint.short_description = 'Hint'

    def answer_stats(self, obj):
        """Show answer statistics."""
        total = obj.answers.count()
        if total > 0:
            correct = obj.answers.filter(is_correct=True).count()
            percentage = (correct / total) * 100
            color = 'green' if percentage >= 50 else 'orange' if percentage >= 25 else 'red'
            return format_html(
                '<span style="color: {};">{}/{}</span> <small>({:.0f}%)</small>',
                color, correct, total, percentage
            )
        return '-'
    answer_stats.short_description = 'Answers (Correct/Total)'

    def answer_statistics(self, obj):
        """Detailed answer statistics."""
        if not obj.id:
            return '-'

        answers = obj.answers.all()
        total = answers.count()

        if total == 0:
            return 'No answers yet'

        correct = answers.filter(is_correct=True).count()
        with_hint = answers.filter(used_hint=True).count()
        avg_time = answers.aggregate(Avg('time_taken'))['time_taken__avg'] or 0

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<p><strong>Total Answers:</strong> {}</p>'
            '<p><strong>Correct:</strong> {} ({:.1f}%)</p>'
            '<p><strong>Used Hint:</strong> {} ({:.1f}%)</p>'
            '<p><strong>Avg Time:</strong> {:.1f}s</p>'
            '</div>',
            total,
            correct, (correct/total)*100,
            with_hint, (with_hint/total)*100 if total > 0 else 0,
            avg_time
        )
    answer_statistics.short_description = 'Answer Statistics'


@admin.register(Answer)
class AnswerAdmin(TimeStampedAdmin):
    """Enhanced admin interface for Answer model."""
    list_display = ['player_name', 'question_display', 'answer_preview', 'result_display', 'hint_used', 'points_display', 'time_display', 'created_at']
    search_fields = ['player__username', 'answer_text', 'question__game__room__code']
    list_filter = ['is_correct', 'used_hint', 'created_at', 'question__game__status']
    readonly_fields = ['id', 'points_earned', 'correctness_display', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Answer Info', {
            'fields': ('id', 'player', 'question', 'answer_text', 'correctness_display')
        }),
        ('Performance', {
            'fields': ('time_taken', 'used_hint', 'points_earned')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def player_name(self, obj):
        """Display player name with link."""
        return format_html(
            '<a href="{}"><strong>{}</strong></a>',
            reverse('admin:users_player_change', args=[obj.player.id]),
            obj.player.username
        )
    player_name.short_description = 'Player'

    def question_display(self, obj):
        """Display question info."""
        return format_html(
            'Q{} - <a href="{}">{}</a>',
            obj.question.order + 1,
            reverse('admin:games_question_change', args=[obj.question.id]),
            obj.question.game.room.code
        )
    question_display.short_description = 'Question'

    def answer_preview(self, obj):
        """Show answer with truncation."""
        max_len = 40
        answer = obj.answer_text[:max_len] + '...' if len(obj.answer_text) > max_len else obj.answer_text
        return format_html('<code>{}</code>', answer)
    answer_preview.short_description = 'Answer'

    def result_display(self, obj):
        """Display correctness with icon."""
        if obj.is_correct:
            return format_html('<span style="color: green; font-size: 18px;">✓</span> Correct')
        else:
            return format_html('<span style="color: red; font-size: 18px;">✗</span> Wrong<br/><small>Correct: {}</small>', obj.question.correct_answer)
    result_display.short_description = 'Result'

    def hint_used(self, obj):
        """Show if hint was used."""
        return '💡' if obj.used_hint else '-'
    hint_used.short_description = 'Hint'

    def points_display(self, obj):
        """Display points with color."""
        color = 'green' if obj.points_earned > 0 else 'red' if obj.points_earned < 0 else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:+d}</span>',
            color, obj.points_earned
        )
    points_display.short_description = 'Points'

    def time_display(self, obj):
        """Display time taken with color coding."""
        color = 'green' if obj.time_taken < 15 else 'orange' if obj.time_taken < 25 else 'red'
        return format_html(
            '<span style="color: {};">{}</span>s',
            color, obj.time_taken
        )
    time_display.short_description = 'Time'

    def correctness_display(self, obj):
        """Display correctness with more detail."""
        if obj.is_correct:
            return format_html(
                '<div style="background: #d4edda; padding: 10px; border-radius: 5px; color: #155724;">'
                '<strong>✓ Correct Answer</strong>'
                '</div>'
            )
        else:
            return format_html(
                '<div style="background: #f8d7da; padding: 10px; border-radius: 5px; color: #721c24;">'
                '<strong>✗ Wrong Answer</strong><br/>'
                '<small>Player answered: <code>{}</code></small><br/>'
                '<small>Correct answer: <code>{}</code></small>'
                '</div>',
                obj.answer_text, obj.question.correct_answer
            )
    correctness_display.short_description = 'Correctness'


@admin.register(GameScore)
class GameScoreAdmin(TimeStampedAdmin):
    """Enhanced admin interface for GameScore model."""
    list_display = ['rank_display', 'player_name', 'game_code', 'score_display', 'answers_display', 'hints_display', 'accuracy_display', 'created_at']
    search_fields = ['player__username', 'game__room__code']
    list_filter = ['rank', 'created_at', 'game__status']
    readonly_fields = ['id', 'score_breakdown', 'created_at', 'updated_at']
    ordering = ['game', '-total_score']

    fieldsets = (
        ('Player & Game', {
            'fields': ('id', 'player', 'game')
        }),
        ('Score Details', {
            'fields': ('total_score', 'correct_answers', 'wrong_answers', 'hints_used', 'rank', 'score_breakdown')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def rank_display(self, obj):
        """Display rank with medal."""
        if obj.rank == 1:
            return format_html('<span style="font-size: 24px;">🥇</span>')
        elif obj.rank == 2:
            return format_html('<span style="font-size: 24px;">🥈</span>')
        elif obj.rank == 3:
            return format_html('<span style="font-size: 24px;">🥉</span>')
        return f'#{obj.rank}' if obj.rank else '-'
    rank_display.short_description = 'Rank'

    def player_name(self, obj):
        """Display player name."""
        return format_html(
            '<a href="{}"><strong>{}</strong></a>',
            reverse('admin:users_player_change', args=[obj.player.id]),
            obj.player.username
        )
    player_name.short_description = 'Player'

    def game_code(self, obj):
        """Display game room code."""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:games_game_change', args=[obj.game.id]),
            obj.game.room.code
        )
    game_code.short_description = 'Game'

    def score_display(self, obj):
        """Display score with styling."""
        return format_html(
            '<span style="font-size: 18px; font-weight: bold; color: #4CAF50;">{}</span> pts',
            obj.total_score
        )
    score_display.short_description = 'Score'

    def answers_display(self, obj):
        """Display answer breakdown."""
        return format_html(
            '<span style="color: green;">✓ {}</span> / <span style="color: red;">✗ {}</span>',
            obj.correct_answers, obj.wrong_answers
        )
    answers_display.short_description = 'Answers'

    def hints_display(self, obj):
        """Display hints used."""
        return format_html('💡 {}', obj.hints_used)
    hints_display.short_description = 'Hints'

    def accuracy_display(self, obj):
        """Display accuracy with progress bar."""
        accuracy = obj.accuracy
        color = '#4CAF50' if accuracy >= 75 else '#FF9800' if accuracy >= 50 else '#F44336'
        return format_html(
            '<div style="width: 100px; background: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background: {}; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 11px; line-height: 20px;">'
            '{:.0f}%'
            '</div></div>',
            accuracy, color, accuracy
        )
    accuracy_display.short_description = 'Accuracy'

    def score_breakdown(self, obj):
        """Detailed score breakdown."""
        if not obj.id:
            return '-'

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Score Breakdown</h3>'
            '<table style="width: 100%; border-collapse: collapse;">'
            '<tr style="background: #e9ecef;"><th style="padding: 8px; text-align: left;">Metric</th><th style="padding: 8px; text-align: right;">Value</th></tr>'
            '<tr><td style="padding: 8px;">Total Score</td><td style="padding: 8px; text-align: right; font-weight: bold; color: #4CAF50;">{}</td></tr>'
            '<tr style="background: #f8f9fa;"><td style="padding: 8px;">Correct Answers</td><td style="padding: 8px; text-align: right; color: green;">{}</td></tr>'
            '<tr><td style="padding: 8px;">Wrong Answers</td><td style="padding: 8px; text-align: right; color: red;">{}</td></tr>'
            '<tr style="background: #f8f9fa;"><td style="padding: 8px;">Hints Used</td><td style="padding: 8px; text-align: right;">💡 {}</td></tr>'
            '<tr><td style="padding: 8px;">Accuracy</td><td style="padding: 8px; text-align: right; font-weight: bold;">{:.1f}%</td></tr>'
            '<tr style="background: #f8f9fa;"><td style="padding: 8px;">Rank</td><td style="padding: 8px; text-align: right; font-weight: bold;">#{}</td></tr>'
            '</table>'
            '</div>',
            obj.total_score,
            obj.correct_answers,
            obj.wrong_answers,
            obj.hints_used,
            obj.accuracy,
            obj.rank or '-'
        )
    score_breakdown.short_description = 'Breakdown'