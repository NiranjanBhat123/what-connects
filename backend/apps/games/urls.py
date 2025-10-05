"""
Games app URL configuration.
"""
from django.urls import path
from .views import (
    GameDetailView,
    QuestionDetailView,
    SubmitAnswerView,
    GameLeaderboardView,
    GameQuestionsView,
    NextQuestionView,
    CurrentQuestionView,
)

app_name = 'games'

urlpatterns = [
    # Game endpoints
    path('<uuid:pk>/', GameDetailView.as_view(), name='game-detail'),
    path('<uuid:pk>/questions/', GameQuestionsView.as_view(), name='game-questions'),
    path('<uuid:pk>/leaderboard/', GameLeaderboardView.as_view(), name='game-leaderboard'),

    # NEW: Current question and navigation
    path('<uuid:game_id>/current-question/', CurrentQuestionView.as_view(), name='current-question'),
    path('<uuid:game_id>/next-question/', NextQuestionView.as_view(), name='next-question'),

    # Question endpoints
    path('<uuid:game_id>/questions/<uuid:question_id>/', QuestionDetailView.as_view(), name='question-detail'),

    # Answer endpoints
    path('<uuid:game_id>/answer/', SubmitAnswerView.as_view(), name='submit-answer'),
]