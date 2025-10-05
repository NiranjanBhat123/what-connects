"""
Custom exceptions for the WhatConnects application.
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status


class GameException(APIException):
    """Base exception for game-related errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A game error occurred.'
    default_code = 'game_error'


class RoomFullException(GameException):
    """Exception raised when trying to join a full room."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Room is full. Maximum players reached.'
    default_code = 'room_full'


class RoomNotFoundException(GameException):
    """Exception raised when room is not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Room not found.'
    default_code = 'room_not_found'


class GameAlreadyStartedException(GameException):
    """Exception raised when trying to join a game that has already started."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Game has already started.'
    default_code = 'game_already_started'


class NotHostException(GameException):
    """Exception raised when non-host tries to perform host-only actions."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Only the host can perform this action.'
    default_code = 'not_host'


class InsufficientPlayersException(GameException):
    """Exception raised when trying to start game with insufficient players."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Not enough players to start the game.'
    default_code = 'insufficient_players'


class QuestionGenerationException(GameException):
    """Exception raised when question generation fails."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Failed to generate questions.'
    default_code = 'question_generation_failed'


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Handle both dict and list response data
        if isinstance(response.data, dict):
            detail = response.data.get('detail', str(exc))
        elif isinstance(response.data, list):
            detail = response.data[0] if response.data else str(exc)
        else:
            detail = str(exc)

        custom_response_data = {
            'error': {
                'code': getattr(exc, 'default_code', 'error'),
                'message': detail,
                'status_code': response.status_code,
            }
        }

        # Add field-specific errors if present
        if isinstance(response.data, dict):
            field_errors = {k: v for k, v in response.data.items() if k != 'detail'}
            if field_errors:
                custom_response_data['error']['fields'] = field_errors

        response.data = custom_response_data

    return response