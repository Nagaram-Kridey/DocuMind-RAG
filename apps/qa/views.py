"""Public API views."""

from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.retrieval.service import UnsupportedModeError

from .generation import answer_question
from .health import check_database, check_redis
from .llm_client import LLMConfigurationError
from .serializers import AskRequestSerializer


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


class AskView(APIView):
    """Answer a question with citation metadata from the retrieval pipeline."""

    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []

    def post(self, request: Request) -> Response:
        """Validate input, run retrieval plus generation, and return the answer."""
        serializer = AskRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question: str = serializer.validated_data["question"]
        mode: str = serializer.validated_data["mode"]
        top_k: int = serializer.validated_data["top_k"]

        try:
            result = answer_question(question, mode=mode, top_k=top_k)
        except UnsupportedModeError as error:
            return Response(
                {"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST
            )
        except LLMConfigurationError as error:
            return Response(
                {"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(result.as_response(), status=status.HTTP_200_OK)
