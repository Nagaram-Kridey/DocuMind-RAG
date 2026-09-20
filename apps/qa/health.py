"""Dependency health checks for the public API."""

from typing import Literal

from django.conf import settings
from django.db import connections
from redis import Redis

HealthStatus = Literal["connected", "disconnected"]


def check_database() -> HealthStatus:
    """Return the PostgreSQL connectivity status."""
    try:
        connections["default"].ensure_connection()
    except Exception:  # pragma: no cover
        return "disconnected"
    return "connected"


def check_redis() -> HealthStatus:
    """Return the Redis connectivity status."""
    try:
        Redis.from_url(settings.REDIS_URL).ping()
    except Exception:  # pragma: no cover
        return "disconnected"
    return "connected"
