"""Production settings for DocuMind."""

import os

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(",")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
