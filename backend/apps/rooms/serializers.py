"""
Room serializers - UPDATED VERSION
"""
from rest_framework import serializers
from ..core.serializers import TimeStampedSerializer
from .models import Room, RoomPlayer
from ..users.serializers import PlayerSerializer


class RoomPlayerSerializer(serializers.ModelSerializer):
    """Serializer for room players."""
    player = PlayerSerializer(read_only=True)
    username = serializers.CharField(source='player.username', read_only=True)

    class Meta:
        model = RoomPlayer
        fields = ['player', 'username', 'is_ready', 'score', 'created_at']
        read_only_fields = ['created_at']


class CurrentGameSerializer(serializers.Serializer):
    """Minimal serializer for current game reference."""
    id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    current_question_index = serializers.IntegerField(read_only=True)
    total_questions = serializers.IntegerField(read_only=True)


class RoomSerializer(TimeStampedSerializer):
    """Serializer for Room model."""
    host = PlayerSerializer(read_only=True)
    players = RoomPlayerSerializer(many=True, read_only=True)
    player_count = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()
    current_game = CurrentGameSerializer(read_only=True)

    class Meta:
        model = Room
        fields = [
            'id', 'code', 'name', 'host', 'status', 'max_players',
            'player_count', 'is_full', 'can_start', 'players',
            'current_game', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'code', 'status', 'created_at', 'updated_at']

    def get_player_count(self, obj):
        """Get current player count."""
        return obj.player_count

    def get_is_full(self, obj):
        """Check if room is full."""
        return obj.is_full

    def get_can_start(self, obj):
        """Check if game can start."""
        return obj.can_start


class RoomCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a room."""
    host_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Room
        fields = ['name', 'max_players', 'host_id']

    def validate_max_players(self, value):
        """Validate max players."""
        min_val = 2
        max_val = 10
        if value < min_val or value > max_val:
            raise serializers.ValidationError(f"Max players must be between {min_val} and {max_val}.")
        return value

    def validate_name(self, value):
        """Validate room name."""
        if not value.strip():
            raise serializers.ValidationError("Room name cannot be empty.")
        if len(value) > 100:
            raise serializers.ValidationError("Room name cannot exceed 100 characters.")
        return value.strip()


class RoomJoinSerializer(serializers.Serializer):
    """Serializer for joining a room."""
    player_id = serializers.UUIDField()

    def validate_player_id(self, value):
        """Validate player_id is provided."""
        if not value:
            raise serializers.ValidationError("Player ID is required.")
        return value


class RoomLeaveSerializer(serializers.Serializer):
    """Serializer for leaving a room."""
    player_id = serializers.UUIDField()

    def validate_player_id(self, value):
        """Validate player_id is provided."""
        if not value:
            raise serializers.ValidationError("Player ID is required.")
        return value


class RoomStartGameSerializer(serializers.Serializer):
    """Serializer for starting a game."""
    player_id = serializers.UUIDField()

    def validate_player_id(self, value):
        """Validate player_id is provided."""
        if not value:
            raise serializers.ValidationError("Player ID is required.")
        return value