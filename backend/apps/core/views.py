"""
Core views for health checks and monitoring.
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.db import connection
from django.core.cache import cache

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Health check endpoint to verify service status.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Check the health of the application and its dependencies.
        """
        health_status = {
            'status': 'healthy',
            'services': {}
        }

        # Check database connection
        try:
            connection.ensure_connection()
            health_status['services']['database'] = 'healthy'
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}", exc_info=True)
            health_status['services']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'

        # Check Redis connection
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                health_status['services']['redis'] = 'healthy'
            else:
                raise Exception("Cache read verification failed")
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}", exc_info=True)
            health_status['services']['redis'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'

        status_code = status.HTTP_200_OK if health_status['status'] == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(health_status, status=status_code)