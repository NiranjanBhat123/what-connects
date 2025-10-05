"""
Admin configuration for rooms app.
"""
from django.contrib import admin
from .models import Room, RoomPlayer


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    """Admin for Room model."""
    list_display = ['code', 'name', 'host', 'status', 'player_count', 'max_players', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['code', 'name', 'host__username']
    readonly_fields = ['code', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def player_count(self, obj):
        return obj.player_count
    player_count.short_description = 'Players'


@admin.register(RoomPlayer)
class RoomPlayerAdmin(admin.ModelAdmin):
    """Admin for RoomPlayer model."""
    list_display = ['player', 'room', 'is_ready', 'score', 'created_at']
    list_filter = ['is_ready', 'created_at']
    search_fields = ['player__username', 'room__code']
    ordering = ['-created_at']