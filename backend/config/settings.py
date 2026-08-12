# File: backend/config/settings.py

import os
import logging
import sys
import warnings
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

# Detect when running under pytest / Django test runner so dev-only profilers
# (silk) can be excluded from the test request pipeline.
RUNNING_TESTS = bool("pytest" in sys.modules or "test" in sys.argv)

# Suppress ONNX Runtime GPU warnings (harmless - we don't need GPU)
warnings.filterwarnings('ignore', category=UserWarning, module='onnxruntime')
os.environ['ORT_LOGGING_LEVEL'] = '3'  # Error level only

BASE_DIR = Path(__file__).resolve().parent.parent

# Load default .env, then override with .env.production if needed
load_dotenv(os.path.join(BASE_DIR, ".env"))
if os.getenv("DJANGO_ENV") == "production":
    load_dotenv(os.path.join(BASE_DIR, ".env.production"), override=True)

# Environment
DJANGO_ENV = os.getenv("DJANGO_ENV", "development").lower()

# Single predicate for all development-only surface (debug toolbars, silk,
# swagger, CORS). URLs and settings gate on this — never on DEBUG directly,
# so DEBUG=True in a production env cannot enable dev tooling by accident.
IS_DEVELOPMENT = DJANGO_ENV == "development"

def get_env(name, default=None, required=False):
    v = os.getenv(name, default)
    if required and v is None:
        raise Exception(f"Environment variable {name} is required!")
    return v

# Key settings
SECRET_KEY = get_env("SECRET_KEY", required=True)
DEBUG = get_env("DJANGO_DEBUG", get_env("DEBUG", "False")).lower() == "true"
ALLOWED_HOSTS = get_env(
    "DJANGO_ALLOWED_HOSTS",
    get_env(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost,testserver,72.60.83.189,clearturn.tech,gigacast.clearturn.tech",
    ),
).split(",")
CSRF_TRUSTED_ORIGINS = [x.strip() for x in get_env("CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]

logger.debug("CSRF_TRUSTED_ORIGINS = %s", repr(CSRF_TRUSTED_ORIGINS))

logger.debug("DEBUG = %s", repr(DEBUG))


# Path for API (configurable, e.g. /api/v1/, /carbon/api/)
API_PREFIX = get_env("DJANGO_API_PREFIX", "/api/v1/")

# File upload path for dataschema files
DATASCHEMA_UPLOAD_PATH = get_env("DATASCHEMA_UPLOAD_PATH", "dataschema_uploads/")

# ── Platform App Registry (bootstrap_platform syncs these to DB) ──
# Mirrors frontend manifests in carbon-frontend/src/apps/*/manifest.js
# Used by AppManifestService.load_manifests() for runtime resolution.
APP_REGISTRY = [
    {
        "id": "carbon",
        "name": "Carbon Footprint",
        "version": "1.0.0",
        "description": "GHG emissions tracking, reporting, and analysis",
        "roles": [
            {"key": "carbon:data_owner", "label": "Data Owner", "scoped": True,
             "description": "CRUD on assigned org-unit data"},
            {"key": "carbon:analyst", "label": "Analyst", "scoped": False,
             "description": "Read-only, cross-org visibility"},
            {"key": "carbon:admin", "label": "Carbon Admin", "scoped": False,
             "description": "Manage factors, rules, periods"},
        ],
    },
    {
        "id": "catalog",
        "name": "Data Catalog",
        "version": "1.0.0",
        "description": "Data product catalog, metadata, governance policies",
        "roles": [
            {"key": "catalog:admin", "label": "Catalog Admin", "scoped": True,
             "description": "Manage data products and metadata"},
        ],
    },
    {
        "id": "mdm",
        "name": "Master Data Management",
        "version": "1.0.0",
        "description": "Org units, reference data, hierarchy management",
        "roles": [],
    },
    {
        "id": "dq",
        "name": "Data Quality",
        "version": "1.0.0",
        "description": "Data quality rules, profiling, dashboards",
        "roles": [
            {"key": "dq:admin", "label": "DQ Admin", "scoped": True,
             "description": "Create and manage DQ rules"},
        ],
    },
    {
        "id": "connections",
        "name": "Connections",
        "version": "1.0.0",
        "description": "External data sources and connection management",
        "roles": [],
    },
    {
        "id": "importexport",
        "name": "Import / Export",
        "version": "1.0.0",
        "description": "Data import and export job management",
        "roles": [],
    },
    {
        "id": "dataschema",
        "name": "Data Schema",
        "version": "1.0.0",
        "description": "Data table and field schema management",
        "roles": [],
    },
]

# Application definition
INSTALLED_APPS = [
    'accounts',
    'ai',
    'core',
    'dataschema',
    'emissions',
    'catalog',
    'mdm',
    'dq',
    'connections',
    'importexport',
    'evidence',
    'rest_framework_simplejwt.token_blacklist',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'drf_yasg',
]

# Phase 1.1 — Dynamic email config from DB (defaults to console)
# See accounts/email_config.py for runtime override from EmailConfig model.
INSTALLED_APPS.insert(0, 'anymail')

if IS_DEVELOPMENT:
    INSTALLED_APPS += ['debug_toolbar', 'silk', 'simulation']

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.RequestLoggingMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if IS_DEVELOPMENT:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
# Silk records every request (incl. DB writes) — keep it out of test runs so
# CaptureQueriesContext assertions stay deterministic.
if IS_DEVELOPMENT and not RUNNING_TESTS:
    MIDDLEWARE.insert(0, 'silk.middleware.SilkyMiddleware')

# CORS
if IS_DEVELOPMENT:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [x.strip() for x in get_env("CORS_ALLOWED_ORIGINS", "").split(",") if x.strip()]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-correlation-id",
]
CORS_EXPOSE_HEADERS = ["Content-Disposition", "X-Correlation-ID"]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Phase 1.5: Inject DJANGO_ENV into all admin templates
                'config.context_processors.django_env',
                # Phase 1.9: Inject health status into admin templates
                'config.admin_health.health_context_processor',
            ],
        },
    },
]

# Phase 1.5: Environment flags
DJANGO_ENV = get_env("DJANGO_ENV", "development")
DJANGO_ENV_LABEL = {
    'development': 'DEV',
    'staging': 'STAGING',
    'production': 'PRODUCTION',
}.get(DJANGO_ENV, DJANGO_ENV.upper())
STAGING = DJANGO_ENV == 'staging'
PRODUCTION = DJANGO_ENV == 'production'

WSGI_APPLICATION = 'config.wsgi.application'
APPEND_SLASH = False

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': get_env("DB_NAME", required=True),
        'USER': get_env("DB_USER", required=True),
        'PASSWORD': get_env("DB_PASSWORD", required=True),
        'HOST': get_env("DB_HOST", "localhost"),
        'PORT': get_env("DB_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
        'TEST': {
            'NAME': 'test_carbon_dev',
        },
    }
}

# Cache — Redis when available, local-memory fallback
_redis_url = os.getenv('REDIS_URL', '')
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
        },
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    }

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # 'EXCEPTION_HANDLER': 'catalog.exceptions.data_trust_exception_handler',  # Temporarily disabled to see full errors
    'EXCEPTION_HANDLER': 'catalog.exceptions.data_trust_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        # Development: allow rapid logins for E2E testing
        'login': '1000/minute' if IS_DEVELOPMENT else '5/minute',
    },
    # Phase 1.4: Default API pagination (overridable via APIConfig model)
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.CarbonPageNumberPagination',
    'PAGE_SIZE': 50,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'accounts.validators.PasswordComplexityValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = get_env("DJANGO_STATIC_ROOT", BASE_DIR / 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = get_env("DJANGO_MEDIA_ROOT", BASE_DIR / 'mediafiles')

# drf-yasg compat (ADR 0003: migrate to drf-spectacular)
SWAGGER_USE_COMPAT_RENDERERS = False

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Emissions module settings ─────────────────────────────────────────────

# When True, saving a DataRow triggers automatic recalculation of linked
# CalculationRules where auto_calculate=True (E3-4).
# Default: False — manual calculation remains the safe default.
EMISSIONS_AUTO_CALC = get_env("EMISSIONS_AUTO_CALC", "False").lower() == "true"

# SSL and Security settings (controlled by the environment)
SECURE_SSL_REDIRECT = get_env(
    "DJANGO_SECURE_SSL_REDIRECT",
    "True" if DJANGO_ENV == "production" else "False"
).lower() == "true"

SESSION_COOKIE_SECURE = get_env(
    "DJANGO_SESSION_COOKIE_SECURE",
    str(SECURE_SSL_REDIRECT)
).lower() == "true"

CSRF_COOKIE_SECURE = get_env(
    "DJANGO_CSRF_COOKIE_SECURE",
    str(SECURE_SSL_REDIRECT)
).lower() == "true"

if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Trust the X-Forwarded-Proto header from nginx (SSL terminated at reverse proxy)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── Phase 1.1: Email defaults (overridden at runtime by EmailConfig model) ─
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'Carbon Data Trust <noreply@carbon.clearturn.tech>'
EMAIL_SUBJECT_PREFIX = '[Carbon] '
ANYMAIL = {}

# Password reset — token expiry read from PasswordPolicy at runtime
PASSWORD_RESET_TIMEOUT = 86400  # 24 hours (overridden by PasswordPolicy.load())

# ── Logging ────────────────────────────────────────────────────────────────
from pythonjsonlogger import jsonlogger

# Ensure logs directory exists
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if os.getenv("LOG_FORMAT", "json") == "json" else "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_DIR, "carbon.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": get_env("ROOT_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "catalog": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "mdm": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "dq": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Debug Toolbar
if DJANGO_ENV == "development":
    INTERNAL_IPS = ["127.0.0.1"]

# Custom API prefix (used in urls.py)
API_PREFIX = API_PREFIX

# ── AI Store (Phase 2 — in-process engine persistence seam) ─────────────
# The AI engine is wired in-process; the HTTP provider transport is retired.
# Select the persistence backend for the vendored engine
# (``inmemory`` or ``django``).
AI_STORE_BACKEND = os.environ.get("AI_STORE_BACKEND", "inmemory")

# ── AI Intelligence ─────────────────────────────────────────────────────
AI_CACHE_TTL_SECONDS = int(os.environ.get("AI_CACHE_TTL_SECONDS", 300))
AI_MAX_CHAT_HISTORY = int(os.environ.get("AI_MAX_CHAT_HISTORY", 50))
AI_RATE_LIMIT_PER_MINUTE = int(os.environ.get("AI_RATE_LIMIT_PER_MINUTE", 30))