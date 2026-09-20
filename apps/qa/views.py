"""Public API views."""

from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .health import check_database, check_redis


class HealthCheckView(APIView):
    """Report the status of DocuMind and its required dependencies."""

    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []

    def get(self, request: Request) -> Response:
        """Return health state and use 503 when a dependency is unavailable."""
        del request
        database = check_database()
        redis = check_redis()
        is_healthy = database == "connected" and redis == "connected"
        payload = {
            "status": "healthy" if is_healthy else "unhealthy",
            "database": database,
            "redis": redis,
            "version": settings.APP_VERSION,
        }
        response_status = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=response_status)
