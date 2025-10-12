"""
Enhanced admin configuration for rooms app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse
from ..core.admin import TimeStampedAdmin
from .models import Room, RoomPlayer


class RoomPlayerInline(admin.TabularInline):
    """Inline display of players in a room."""
    model = RoomPlayer
    extra = 0
    readonly_fields = ['player', 'is_ready', 'score', 'joined_at']
    fields = ['player', 'is_ready', 'score', 'joined_at']

    def joined_at(self, obj):
        """Show when player joined."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    joined_at.short_description = 'Joined At'


@admin.register(Room)
class RoomAdmin(TimeStampedAdmin):
    """Enhanced admin for Room model."""
    list_display = ['code_display', 'name', 'host_display', 'status_display', 'player_stats', 'game_info', 'created_at']
    list_filter = ['status', 'created_at', 'max_players']
    search_fields = ['code', 'name', 'host__username']
    readonly_fields = ['code', 'room_details', 'player_list', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [RoomPlayerInline]

    fieldsets = (
        ('Room Info', {
            'fields': ('code', 'name', 'host', 'status')
        }),
        ('Settings', {
            'fields': ('max_players', 'current_game')
        }),
        ('Details', {
            'fields': ('room_details', 'player_list'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def code_display(self, obj):
        """Display room code with styling."""
        return format_html(
            '<span style="font-family: monospace; font-size: 16px; font-weight: bold; background: #e3f2fd; padding: 4px 8px; border-radius: 4px;">{}</span>',
            obj.code
        )
    code_display.short_description = 'Room Code'

    def host_display(self, obj):
        """Display host with crown icon."""
        return format_html(
            '👑 <a href="{}">{}</a>',
            reverse('admin:users_player_change', args=[obj.host.id]),
            obj.host.username
        )
    host_display.short_description = 'Host'

    def status_display(self, obj):
        """Display status with color coding."""
        status_config = {
            'waiting': ('🕐', 'orange', 'Waiting'),
            'in_progress': ('🎮', 'blue', 'In Progress'),
            'completed': ('✅', 'gray', 'Completed'),
        }

        icon, color, label = status_config.get(obj.status, ('', 'gray', obj.status))

        return format_html(
            '{} <span style="color: {}; font-weight: bold;">{}</span>',
            icon, color, label
        )
    status_display.short_description = 'Status'

    def player_stats(self, obj):
        """Display player count with progress bar."""
        current = obj.player_count
        max_players = obj.max_players
        percentage = (current / max_players) * 100 if max_players > 0 else 0

        color = '#4CAF50' if current >= max_players else '#2196F3'

        return format_html(
            '<div style="width: 120px;">'
            '<div style="margin-bottom: 4px;"><strong>{}/{}</strong> players</div>'
            '<div style="background: #f0f0f0; border-radius: 3px; height: 8px;">'
            '<div style="width: {}%; background: {}; height: 8px; border-radius: 3px;"></div>'
            '</div>'
            '</div>',
            current, max_players, percentage, color
        )
    player_stats.short_description = 'Players'

    def game_info(self, obj):
        """Display current game information."""
        if obj.current_game:
            return format_html(
                '🎯 <a href="{}">Game Active</a><br/>'
                '<small>Q{}/{}</small>',
                reverse('admin:games_game_change', args=[obj.current_game.id]),
                obj.current_game.current_question_index + 1,
                obj.current_game.total_questions
            )
        elif obj.status == 'completed':
            game_count = obj.games.count()
            return format_html('✅ {} game(s) completed', game_count)
        return '⏳ No active game'
    game_info.short_description = 'Game Status'

    def room_details(self, obj):
        """Display comprehensive room details."""
        games_played = obj.games.count()
        total_answers = 0

        if obj.current_game:
            from ..games.models import Answer
            total_answers = Answer.objects.filter(
                question__game__room=obj
            ).count()

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Room Statistics</h3>'
            '<table style="width: 100%; border-collapse: collapse;">'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Room Code:</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Current Players:</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{}/{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Games Played:</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{}</td></tr>'
            '<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Total Answers:</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{}</td></tr>'
            '<tr><td style="padding: 8px;"><strong>Can Start:</strong></td><td style="padding: 8px;">{}</td></tr>'
            '</table>'
            '</div>',
            obj.code,
            obj.player_count, obj.max_players,
            games_played,
            total_answers,
            'Yes' if obj.can_start else 'No'
        )
    room_details.short_description = 'Details'

    def player_list(self, obj):
        """Display list of players in room."""
        players = obj.players.select_related('player').all()

        if not players.exists():
            return format_html('<p>No players in room</p>')

        rows = ''.join([
            f'<tr>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6;">'
            f'{"👑 " if player.player.id == obj.host.id else ""}'
            f'<a href="{reverse("admin:users_player_change", args=[player.player.id])}">{player.player.username}</a>'
            f'</td>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: center;">{"✅" if player.is_ready else "⏳"}</td>'
            f'<td style="padding: 8px; border-bottom: 1px solid #dee2e6; text-align: center;">{player.score}</td>'
            f'</tr>'
            for player in players
        ])

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Players in Room</h3>'
            '<table style="width: 100%; border-collapse: collapse;">'
            '<tr style="background: #e9ecef;">'
            '<th style="padding: 8px; text-align: left;">Player</th>'
            '<th style="padding: 8px; text-align: center;">Ready</th>'
            '<th style="padding: 8px; text-align: center;">Score</th>'
            '</tr>'
            '{}'
            '</table>'
            '</div>',
            rows
        )
    player_list.short_description = 'Players'


@admin.register(RoomPlayer)
class RoomPlayerAdmin(TimeStampedAdmin):
    """Enhanced admin for RoomPlayer model."""
    list_display = ['player_display', 'room_display', 'ready_status', 'score_display', 'joined_time', 'created_at']
    list_filter = ['is_ready', 'created_at', 'room__status']
    search_fields = ['player__username', 'room__code', 'room__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Player & Room', {
            'fields': ('player', 'room')
        }),
        ('Status', {
            'fields': ('is_ready', 'score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def player_display(self, obj):
        """Display player with link."""
        return format_html(
            '<a href="{}"><strong>{}</strong></a>',
            reverse('admin:users_player_change', args=[obj.player.id]),
            obj.player.username
        )
    player_display.short_description = 'Player'

    def room_display(self, obj):
        """Display room with code."""
        return format_html(
            '<a href="{}"><span style="font-family: monospace; font-weight: bold;">{}</span></a><br/>'
            '<small>{}</small>',
            reverse('admin:rooms_room_change', args=[obj.room.id]),
            obj.room.code,
            obj.room.name
        )
    room_display.short_description = 'Room'

    def ready_status(self, obj):
        """Display ready status with icon."""
        if obj.is_ready:
            return format_html('<span style="color: green; font-size: 18px;">✓</span> Ready')
        return format_html('<span style="color: orange;">⏳</span> Not Ready')
    ready_status.short_description = 'Status'

    def score_display(self, obj):
        """Display score with styling."""
        if obj.score > 0:
            return format_html(
                '<span style="font-weight: bold; color: #4CAF50;">{}</span> pts',
                obj.score
            )
        return '0 pts'
    score_display.short_description = 'Score'

    def joined_time(self, obj):
        """Show how long ago player joined."""
        from django.utils.timezone import now
        delta = now() - obj.created_at

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        return "Just now"
    joined_time.short_description = 'Joined'