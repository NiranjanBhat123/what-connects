"""
Users app URL configuration.
"""
from django.urls import path
from .views import (
    PlayerCreateView,
    PlayerDetailView,
    PlayerValidateView,
    PlayerCleanupView
)

app_name = 'users'

urlpatterns = [
    path('create/', PlayerCreateView.as_view(), name='player-create'),
    path('<uuid:pk>/', PlayerDetailView.as_view(), name='player-detail'),
    path('<uuid:player_id>/validate/', PlayerValidateView.as_view(), name='player-validate'),
    path('cleanup/', PlayerCleanupView.as_view(), name='player-cleanup'),
]