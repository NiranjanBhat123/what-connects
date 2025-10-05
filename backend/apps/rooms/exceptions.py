"""
Custom exceptions for WhatConnects application.
"""
from rest_framework.exceptions import APIException
from rest_framework import status


class BaseGameException(APIException):
    """Base exception for game-related errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A game error occurred.'
    default_code = 'game_error'


class GameException(BaseGameException):
    """General game exception."""
    def __init__(self, detail=None, code=None):
        if detail is not None:
            self.detail = detail
        if code is not None:
            self.default_code = code
        super().__init__(detail, code)


class QuestionGenerationException(BaseGameException):
    """Exception raised when question generation fails."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Failed to generate questions.'
    default_code = 'question_generation_failed'


class RoomNotFoundException(BaseGameException):
    """Exception raised when room is not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Room not found.'
    default_code = 'room_not_found'


class RoomFullException(BaseGameException):
    """Exception raised when room is full."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Room is full.'
    default_code = 'room_full'


class GameAlreadyStartedException(BaseGameException):
    """Exception raised when trying to join a game that already started."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Game has already started.'
    default_code = 'game_already_started'


class NotHostException(BaseGameException):
    """Exception raised when non-host tries to perform host action."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Only the room host can perform this action.'
    default_code = 'not_host'


class InsufficientPlayersException(BaseGameException):
    """Exception raised when there are not enough players to start."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Not enough players to start the game.'
    default_code = 'insufficient_players'


class PlayerNotFoundException(BaseGameException):
    """Exception raised when player is not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Player not found.'
    default_code = 'player_not_found'


class PlayerAlreadyExistsException(BaseGameException):
    """Exception raised when player username already exists."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Player with this username already exists.'
    default_code = 'player_already_exists'