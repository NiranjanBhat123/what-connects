"""
Admin configuration for users app.
"""
from django.contrib import admin
from .models import Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    """Admin interface for Player model."""
    list_display = ['username', 'created_at']
    search_fields = ['username']
    list_filter = ['created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
