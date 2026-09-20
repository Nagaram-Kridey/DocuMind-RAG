"""Root URL configuration."""

from django.urls import include, path

urlpatterns = [path("api/", include("apps.qa.urls"))]
