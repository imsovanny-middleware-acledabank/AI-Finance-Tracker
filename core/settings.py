import os
import socket
import logging
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-production"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = (
    os.environ.get("ALLOWED_HOSTS", "").split(",")
    if os.environ.get("ALLOWED_HOSTS")
    else []
)

RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = (
    os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if os.environ.get("CSRF_TRUSTED_ORIGINS")
    else []
)
CSRF_TRUSTED_ORIGINS += ["https://*.ngrok-free.dev"]


# Application definition

INSTALLED_APPS = [
    "tracker",  # must come before django.contrib.admin to override admin templates
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases


def _sqlite_db_config():
    return {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


def _db_host_resolvable(database_url: str) -> bool:
    """Best-effort DNS check for DB host in DATABASE_URL."""
    try:
        parsed = urlparse(database_url)
        host = parsed.hostname
        if not host or parsed.scheme.startswith("sqlite"):
            return True
        port = parsed.port or 5432
        socket.getaddrinfo(host, port)
        return True
    except Exception as exc:
        logger.error("[DB CONFIG] Database host DNS resolution failed: %s", exc)
        return False


# Use DATABASE_URL if set, otherwise default to local SQLite for dev
DATABASE_URL = os.environ.get("DATABASE_URL")
DB_FALLBACK_TO_SQLITE = os.environ.get("DB_FALLBACK_TO_SQLITE", "false").lower() in (
    "true",
    "1",
    "yes",
)

if DATABASE_URL:
    if DB_FALLBACK_TO_SQLITE and not _db_host_resolvable(DATABASE_URL):
        logger.warning(
            "[DB CONFIG] DB_FALLBACK_TO_SQLITE=true and DATABASE_URL host is not resolvable. "
            "Falling back to SQLite to keep service available."
        )
        DATABASES = _sqlite_db_config()
    else:
        DATABASES = {
            "default": dj_database_url.config(
                default=DATABASE_URL,
                conn_max_age=600,
                ssl_require=not DATABASE_URL.startswith("sqlite")
            )
        }
else:
    DATABASES = _sqlite_db_config()

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Phnom_Penh"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
