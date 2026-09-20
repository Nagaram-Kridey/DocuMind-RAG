"""Smoke tests for the health endpoint."""

from unittest.mock import patch

from rest_framework.test import APIClient


@patch("apps.qa.views.check_redis", return_value="connected")
@patch("apps.qa.views.check_database", return_value="connected")
def test_health_endpoint_reports_healthy(*_: object) -> None:
    """The public health endpoint reports all dependencies as connected."""
    response = APIClient().get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
        "version": "0.1.0",
    }
