"""Request and response serializers for the question-answering API."""

from rest_framework import serializers

from apps.retrieval.service import IMPLEMENTED_MODES, SUPPORTED_MODES

MAX_QUESTION_LENGTH = 500
MIN_TOP_K = 1
MAX_TOP_K = 10


class AskRequestSerializer(serializers.Serializer[dict[str, object]]):
    """Validate the ``/api/ask/`` request body."""

    question = serializers.CharField(max_length=MAX_QUESTION_LENGTH, trim_whitespace=True)
    mode = serializers.ChoiceField(choices=SUPPORTED_MODES, default=IMPLEMENTED_MODES[0])
    top_k = serializers.IntegerField(
        required=False, min_value=MIN_TOP_K, max_value=MAX_TOP_K, default=5
    )


class CitationSerializer(serializers.Serializer[dict[str, object]]):
    """Describe a single citation returned with an answer."""

    chunk_id = serializers.IntegerField()
    title = serializers.CharField()
    heading_path = serializers.CharField()
    url = serializers.CharField()
    score = serializers.FloatField()


class AskResponseSerializer(serializers.Serializer[dict[str, object]]):
    """Describe the successful ``/api/ask/`` response."""

    answer = serializers.CharField()
    refused = serializers.BooleanField()
    citations = CitationSerializer(many=True)
    mode = serializers.CharField()
    latency_ms = serializers.DictField(child=serializers.IntegerField())