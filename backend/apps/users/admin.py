"""
Enhanced admin configuration for users app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q
from django.urls import reverse
from ..core.admin import TimeStampedAdmin
from .models import Player


@admin.register(Player)
class PlayerAdmin(TimeStampedAdmin):
    """Enhanced admin interface for Player model."""
    list_display = ['username_display', 'activity_status', 'rooms_count', 'games_played', 'total_score', 'win_rate', 'last_active', 'created_at']
    search_fields = ['username', 'id', 'session_key']
    list_filter = ['created_at', 'last_active']
    readonly_fields = ['id', 'session_key', 'player_statistics', 'game_history', 'created_at', 'updated_at', 'last_active']
    ordering = ['-created_at']

    fieldsets = (
        ('Player Info', {
            'fields': ('id', 'username', 'session_key')
        }),
        ('Activity', {
            'fields': ('last_active',)
        }),
        ('Statistics', {
            'fields': ('player_statistics',),
            'classes': ('collapse',)
        }),
        ('Game History', {
            'fields': ('game_history',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def username_display(self, obj):
        """Display username with styling."""
        return format_html(
            '<strong style="font-size: 14px;">{}</strong><br/>'
            '<small style="color: gray;">{}</small>',
            obj.username,
            str(obj.id)[:8]
        )
    username_display.short_description = 'Player'

    def activity_status(self, obj):
        """Display activity status with indicator."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">● Active</span>'
            )
        return format_html(
            '<span style="color: gray;">○ Inactive</span>'
        )
    activity_status.short_description = 'Status'

    def rooms_count(self, obj):
        """Display number of rooms player is in."""
        count = obj.rooms.count()
        active_count = obj.rooms.filter(room__status__in=['waiting', 'in_progress']).count()

        if active_count > 0:
            return format_html(
                '<strong>{}</strong> total<br/>'
                '<small style="color: green;">{} active</small>',
                count, active_count
            )
        return format_html('{} total', count)
    rooms_count.short_description = 'Rooms'

    def games_played(self, obj):
        """Display number of games played."""
        from ..games.models import GameScore
        count = GameScore.objects.filter(player=obj).count()
        return format_html('<strong>{}</strong>', count)
    games_played.short_description = 'Games'

    def total_score(self, obj):
        """Display total points earned across all games."""
        from ..games.models import GameScore
        total = GameScore.objects.filter(player=obj).aggregate(
            total=Sum('total_score')
        )['total'] or 0

        return format_html(
            '<span style="font-weight: bold; color: #4CAF50;">{}</span> pts',
            total
        )
    total_score.short_description = 'Total Points'

    def win_rate(self, obj):
        """Calculate and display win rate."""
        from ..games.models import GameScore

        games = GameScore.objects.filter(player=obj)
        total_games = games.count()

        if total_games == 0:
            return '-'

        wins = games.filter(rank=1).count()
        win_percentage = (wins / total_games) * 100

        color = '#4CAF50' if win_percentage >= 30 else '#FF9800' if win_percentage >= 10 else '#F44336'

        return format_html(
            '<div style="width: 80px;">'
            '<div style="margin-bottom: 4px;"><strong>{}/{}</strong></div>'
            '<div style="background: #f0f0f0; border-radius: 3px; height: 8px;">'
            '<div style="width: {}%; background: {}; height: 8px; border-radius: 3px;"></div>'
            '</div>'
            '</div>',
            wins, total_games, win_percentage, color
        )
    win_rate.short_description = 'Win Rate'

    def player_statistics(self, obj):
        """Display comprehensive player statistics."""
        from ..games.models import GameScore, Answer

        # Game statistics
        game_scores = GameScore.objects.filter(player=obj)
        total_games = game_scores.count()

        if total_games == 0:
            return format_html('<p>No games played yet</p>')

        stats = game_scores.aggregate(
            total_score=Sum('total_score'),
            avg_score=Avg('total_score'),
            total_correct=Sum('correct_answers'),
            total_wrong=Sum('wrong_answers'),
            wins=Count('id', filter=Q(rank=1))
        )

        # Answer statistics
        answers = Answer.objects.filter(player=obj)
        answer_stats = answers.aggregate(
            total_answers=Count('id'),
            avg_time=Avg('time_taken'),
            hints_used=Count('id', filter=Q(used_hint=True))
        )

        # Calculate overall accuracy
        total_answers = (stats['total_correct'] or 0) + (stats['total_wrong'] or 0)
        accuracy = (stats['total_correct'] / total_answers * 100) if total_answers > 0 else 0

        # Win rate
        win_rate = (stats['wins'] / total_games * 100) if total_games > 0 else 0

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Player Statistics</h3>'

            '<h4 style="color: #495057; margin-bottom: 10px;">🎮 Game Performance</h4>'
            '<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Games Played</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Wins</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #4CAF50;">{} ({:.1f}%)</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Total Score</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Avg Score/Game</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{:.1f}</td></tr>'
            '</table>'

            '<h4 style="color: #495057; margin-bottom: 10px;">✏️ Answer Statistics</h4>'
            '<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Total Answers</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Correct Answers</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold; color: green;">{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Wrong Answers</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold; color: red;">{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Accuracy</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{:.1f}%</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Avg Time/Answer</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{:.1f}s</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">Hints Used</td><td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">{}</td></tr>'
            '</table>'
            '</div>',
            total_games,
            stats['wins'] or 0, win_rate,
            stats['total_score'] or 0,
            stats['avg_score'] or 0,
            answer_stats['total_answers'] or 0,
            stats['total_correct'] or 0,
            stats['total_wrong'] or 0,
            accuracy,
            answer_stats['avg_time'] or 0,
            answer_stats['hints_used'] or 0
        )
    player_statistics.short_description = 'Statistics'

    def game_history(self, obj):
        """Display recent game history."""
        from ..games.models import GameScore

        recent_games = GameScore.objects.filter(
            player=obj
        ).select_related('game__room').order_by('-created_at')[:10]

        if not recent_games.exists():
            return format_html('<p>No game history</p>')

        rows = ''.join([
            f'<tr>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6;">'
            f'<a href="{reverse("admin:games_game_change", args=[score.game.id])}">{score.game.room.code}</a>'
            f'</td>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: center;">'
            f'{"🥇" if score.rank == 1 else "🥈" if score.rank == 2 else "🥉" if score.rank == 3 else f"#{score.rank}"}'
            f'</td>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: center; font-weight: bold;">{score.total_score}</td>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: center;">{score.accuracy:.0f}%</td>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: center;"><small>{score.created_at.strftime("%Y-%m-%d %H:%M")}</small></td>'
            f'</tr>'
            for score in recent_games
        ])

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Recent Games</h3>'
            '<table style="width: 100%; border-collapse: collapse;">'
            '<tr style="background: #e9ecef;">'
            '<th style="padding: 8px; text-align: left;">Room</th>'
            '<th style="padding: 8px; text-align: center;">Rank</th>'
            '<th style="padding: 8px; text-align: center;">Score</th>'
            '<th style="padding: 8px; text-align: center;">Accuracy</th>'
            '<th style="padding: 8px; text-align: center;">Date</th>'
            '</tr>'
            '{}'
            '</table>'
            '</div>',
            rows
        )
    game_history.short_description = 'Game History'