"""
Room models for WhatConnects.
"""
import random
import string
from django.db import models
from django.conf import settings
from ..core.models import TimeStampedModel, UUIDModel
from ..users.models import Player


def generate_room_code():
    """Generate a unique 6-character room code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


class RoomManager(models.Manager):
    """Custom manager for Room model."""

    def active(self):
        """Get active rooms (waiting or in progress)."""
        return self.filter(status__in=['waiting', 'in_progress'])

    def waiting(self):
        """Get rooms waiting for players."""
        return self.filter(status='waiting')

    def in_progress(self):
        """Get rooms with games in progress."""
        return self.filter(status='in_progress')


class Room(UUIDModel, TimeStampedModel):
    """Game room model."""

    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    code = models.CharField(max_length=6, unique=True, default=generate_room_code, db_index=True)
    name = models.CharField(max_length=100)
    host = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='hosted_rooms')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting', db_index=True)
    max_players = models.IntegerField(default=6)
    # Use string reference to avoid circular import
    current_game = models.OneToOneField(
        'games.Game',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_room'
    )

    objects = RoomManager()

    class Meta:
        db_table = 'rooms'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['code', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def player_count(self):
        """Get current number of players in room."""
        return self.players.count()

    @property
    def is_full(self):
        """Check if room is full."""
        return self.player_count >= self.max_players

    @property
    def can_start(self):
        """Check if game can be started."""
        min_players = settings.GAME_SETTINGS.get('MIN_PLAYERS', 2)
        return self.player_count >= min_players and self.status == 'waiting'

    @property
    def is_waiting(self):
        """Check if room is in waiting status."""
        return self.status == 'waiting'

    @property
    def is_in_progress(self):
        """Check if room has game in progress."""
        return self.status == 'in_progress'

    @property
    def is_completed(self):
        """Check if room is completed."""
        return self.status == 'completed'


class RoomPlayer(TimeStampedModel):
    """Junction table for room players."""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='players')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='rooms')
    is_ready = models.BooleanField(default=False, db_index=True)
    score = models.IntegerField(default=0)

    class Meta:
        db_table = 'room_players'
        unique_together = ['room', 'player']
        ordering = ['-score', 'created_at']
        indexes = [
            models.Index(fields=['room', 'player']),
            models.Index(fields=['room', '-score']),
        ]

    def __str__(self):
        return f"{self.player.username} in {self.room.code}"