from django.apps import AppConfig


class QaConfig(AppConfig):
    """Configure the question-answering application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.qa"
