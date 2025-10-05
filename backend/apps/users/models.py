"""
User models for WhatConnects.
Simple session-based players without persistent stats.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta
from ..core.models import TimeStampedModel, UUIDModel


class PlayerManager(models.Manager):
    """Custom manager for Player model."""

    def create_player(self, username, session_key=None):
        """Create a new player with validation."""
        # Clean username
        username = username.strip()

        # Check for recent duplicate usernames (within last 24 hours)
        recent_cutoff = timezone.now() - timedelta(hours=24)
        if self.filter(
                username__iexact=username,
                created_at__gte=recent_cutoff
        ).exists():
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Username '{username}' was recently used. Please choose another.")

        return self.create(username=username, session_key=session_key)

    def cleanup_old_players(self, days=7):
        """
        Clean up players older than specified days.
        Should be run as a periodic task.
        """
        cutoff_date = timezone.now() - timedelta(days=days)

        # Only delete players not in any active rooms
        from ..rooms.models import RoomPlayer

        old_players = self.filter(created_at__lt=cutoff_date)

        # Exclude players currently in active rooms
        active_player_ids = RoomPlayer.objects.filter(
            is_active=True,
            room__status__in=['waiting', 'active']
        ).values_list('player_id', flat=True)

        players_to_delete = old_players.exclude(id__in=active_player_ids)
        count = players_to_delete.count()
        players_to_delete.delete()

        return count


class Player(UUIDModel, TimeStampedModel):
    """
    Temporary player model for game sessions.
    No stats stored - just username for identification during gameplay.
    Players are automatically cleaned up after 7 days if not in active rooms.
    """
    username = models.CharField(max_length=50, db_index=True)
    session_key = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Django session key for tracking"
    )
    last_active = models.DateTimeField(auto_now=True)

    objects = PlayerManager()

    class Meta:
        db_table = 'players'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['username', '-created_at']),
        ]

    def __str__(self):
        return f"{self.username} ({self.id})"

    def update_activity(self):
        """Update last_active timestamp."""
        self.last_active = timezone.now()
        self.save(update_fields=['last_active'])

    @property
    def is_active(self):
        """Check if player has been active recently (within 1 hour)."""
        if not self.last_active:
            return False
        return timezone.now() - self.last_active < timedelta(hours=1)

    def clean(self):
        """Validate player data."""
        from django.core.exceptions import ValidationError

        if not self.username or len(self.username.strip()) < 3:
            raise ValidationError("Username must be at least 3 characters long.")

        if len(self.username) > 50:
            raise ValidationError("Username must be less than 50 characters.")

        # Clean whitespace
        self.username = self.username.strip()