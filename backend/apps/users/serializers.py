"""
User serializers.
"""
from rest_framework import serializers
from .models import Player


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['id', 'username', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


    def validate_username(self, value):
        """Validate username."""
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long.")
        if len(value) > 50:
            raise serializers.ValidationError("Username must be less than 50 characters.")
        return value