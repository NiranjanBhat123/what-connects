"""
Rooms app URL configuration.
"""
from django.urls import path
from .views import (
    RoomCreateView,
    RoomDetailView,
    RoomJoinView,
    RoomLeaveView,
    RoomStartGameView,
    RoomReadyToggleView,
)

app_name = 'rooms'

urlpatterns = [
    path('create/', RoomCreateView.as_view(), name='room-create'),
    path('<str:code>/', RoomDetailView.as_view(), name='room-detail'),
    path('<str:code>/join/', RoomJoinView.as_view(), name='room-join'),
    path('<str:code>/leave/', RoomLeaveView.as_view(), name='room-leave'),
    path('<str:code>/start/', RoomStartGameView.as_view(), name='room-start'),
    path('<str:code>/ready/', RoomReadyToggleView.as_view(), name='room-ready'),
]