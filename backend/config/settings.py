import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
TESTING = "test" in sys.argv
if not TESTING:
    load_dotenv(BASE_DIR.parent / ".env")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not (DEBUG or TESTING):
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set")
    SECRET_KEY = "insecure-development-only-key-not-for-deployment"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "channels",
    "accounts",
    "automation",
]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "autoapply"),
            "USER": os.environ.get("POSTGRES_USER", "autoapply"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        }
    }
else:
    # The default. Set POSTGRES_HOST in .env to use a PostgreSQL server instead.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "dev.sqlite3",
            "OPTIONS": {"timeout": 20},
            "TEST": {"NAME": BASE_DIR / "test.sqlite3"},
        }
    }

# A single Daphne process serves every socket, so no external broker is needed.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

BOSS_KEY = os.environ.get("BOSS_KEY", "")
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
TOKEN_MAX_AGE_SECONDS = 7 * 24 * 3600
RESUME_DIR = Path(os.environ.get("RESUME_DIR", BASE_DIR / "DB"))
MAX_RESUME_BYTES = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_RESUME_BYTES + 1024 * 1024

SLM_BASE_URL = os.environ.get("SLM_BASE_URL", "http://localhost:11434")
SLM_MODEL = os.environ.get("SLM_MODEL", "qwen2.5:7b")
SLM_TIMEOUT_SECONDS = float(os.environ.get("SLM_TIMEOUT_SECONDS", "180"))
# Ollama defaults to 4096 tokens and silently truncates anything longer.
SLM_NUM_CTX = int(os.environ.get("SLM_NUM_CTX", "8192"))
TAILOR_RESUME = os.environ.get("TAILOR_RESUME", "true").lower() == "true"
# Off by default: a filled form is left on the page for a person to review and submit.
AUTO_CLICK_SUBMIT = os.environ.get("AUTO_CLICK_SUBMIT", "false").lower() == "true"
