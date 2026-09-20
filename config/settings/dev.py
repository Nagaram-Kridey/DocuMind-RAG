"""Development settings for DocuMind."""

import os

from .base import *  # noqa: F403

DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
