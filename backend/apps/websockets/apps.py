"""
Websockets app configuration.
"""
from django.apps import AppConfig


class WebsocketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.websockets'
    verbose_name = 'WebSockets'

    def ready(self):
        """Import signals when app is ready."""
        import apps.websockets.signals  # noqa