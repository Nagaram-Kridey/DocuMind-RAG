"""URL routes for the question-answering API."""

from django.urls import path

from .views import AskView, HealthCheckView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("ask/", AskView.as_view(), name="ask"),
]
