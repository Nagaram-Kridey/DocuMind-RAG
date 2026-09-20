"""Persistence model for auditable question-answering requests."""

from django.conf import settings
from django.db import models


class QueryLog(models.Model):
    """Store inputs, retrieval evidence, and generation metadata per query."""

    class RetrievalMode(models.TextChoices):
        """Retrieval modes defined by the locked architecture."""

        VECTOR = "vector", "Vector"
        HYBRID = "hybrid", "Hybrid"
        HYBRID_RERANK = "hybrid_rerank", "Hybrid rerank"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documind_query_logs",
    )
    question = models.CharField(max_length=500)
    mode = models.CharField(max_length=20, choices=RetrievalMode.choices)
    retrieved = models.JSONField(default=list)
    answer = models.TextField(blank=True)
    citations = models.JSONField(default=list)
    refused = models.BooleanField(default=False)
    latency_ms = models.JSONField(default=dict)
    model = models.CharField(max_length=255, blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        """Return a concise administrative representation."""
        return f"QueryLog {self.pk}: {self.mode}"
