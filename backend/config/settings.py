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

# Enable audit logging for mutating requests (disabled during pytest to avoid N+1 assertions)
CORE_REQUEST_AUDIT_ENABLED = not RUNNING_TESTS

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

# ── TurnKey Bridge (Phase P2) ─────────────────────────────────
# Never hardcode these — they come from the environment (.env / .env.production).
# FERNET_KEY: 44-char Fernet key for encrypting TurnKey API keys at rest.
#   Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# TURNKEY_CALLBACK_SECRET: 64-char hex shared secret used to HMAC-SHA256 sign
#   TurnKey → Carbon callbacks (verified before processing).
#   Generate: python -c "import secrets; print(secrets.token_hex(32))"
FERNET_KEY = get_env("FERNET_KEY", required=True)
TURNKEY_CALLBACK_SECRET = get_env("TURNKEY_CALLBACK_SECRET", required=True)

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
    {
        "id": "stub",
        "name": "Isolation Stub",
        "version": "0.0.1",
        "description": "Placeholder app proving per-instance app isolation (disabled by default)",
        "roles": [],
    },
    {
        "id": "people",
        "name": "People & Payroll",
        "version": "0.1.0",
        "description": "HRMS wedge: employee master, payroll, leave, EOSI, GOSI, WPS (Nibras)",
        "roles": [],
    },
    {
        "id": "healthy",
        "name": "Healthy Foods Factory",
        "version": "1.0.0",
        "description": "Legacy ERP analytics: rep health, load-out demand, AR aging",
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
    'integrations.turnkey',
    'appregistry',
    'connections',
    'importexport',
    'evidence',
    'healthy',
    'people',
    'rest_framework_simplejwt.token_blacklist',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
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
    'core.middleware.AuditMiddleware',
    'core.middleware.ApiVersionMiddleware',
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
    # EPH-5C (ADR 0003): drf-spectacular schema generator (was drf-yasg).
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # EPH-5A: structured handler wraps catalog's data_trust_exception_handler
    # and adds a taxonomy error_code — see core/exception_handler.py.
    'EXCEPTION_HANDLER': 'core.exception_handler.structured_exception_handler',
    # EPH-5B: per-minute complements + per-endpoint scoped throttles (core/throttling.py)
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'core.throttling.UserMinuteRateThrottle',
        'core.throttling.AnonMinuteRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'user_minute': '1000/min',
        'anon_minute': '60/min',
        'ai': '60/min',
        'heavy': '10/min',
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

# drf-spectacular OpenAPI config (ADR 0003 — migrated from drf-yasg)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Carbon Data Trust Platform API',
    'DESCRIPTION': (
        "**Data Trust Core Platform APIs**\n\n"
        "Provides catalog, master data management (MDM), and data quality (DQ) services.\n\n"
        "### Key Modules\n"
        "- **Catalog** (`/catalog/`): Asset profiling, governance events, glossary terms, data domains\n"
        "- **MDM** (`/mdm/`): Reference sets (temporal + lifecycle), org-unit hierarchy, field binding\n"
        "- **DQ** (`/dq/`): Data profiling, rule execution, quality metrics, execution history\n\n"
        "### Authentication\n"
        "All endpoints require JWT. Obtain a token via `POST /carbon-api/token/`.\n\n"
        "### Soft-Delete Policy\n"
        "Hard DELETE is rejected with HTTP 405 on catalog and DQ resources. "
        "Use `PATCH {\"is_active\": false}` or the dedicated `archive-bulk` actions instead."
    ),
    'VERSION': '1.0.0',
    # Strip the API mount prefix from generated paths so operation paths read
    # like `/mdm/reference-sets/{id}/values/` (matching the pre-EPH-5C docs).
    'SCHEMA_PATH_PREFIX': f'/{API_PREFIX.strip("/")}',
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'SERVE_INCLUDE_SCHEMA': False,
}

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

# CB-09: a Prometheus scraper does not follow 301 redirects, so the metrics
# endpoints must stay reachable over plain HTTP on the loopback — exempt them
# from the HTTPS redirect.
SECURE_REDIRECT_EXEMPT = [
    rf'^/{API_PREFIX.strip("/")}/health/(metrics/|prometheus/)',
]

# Trust the X-Forwarded-Proto header from nginx (SSL terminated at reverse proxy)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── Branding (multi-entity reuse) ─────────────────────────────────────────
# Mirrors the frontend VITE_* branding. Drive from the backend env so emails,
# PDFs, and API docs use the same identity as the UI.
PLATFORM_NAME = get_env("DJANGO_PLATFORM_NAME", "Data Trust Platform")
PLATFORM_SHORT = get_env("DJANGO_PLATFORM_SHORT", "Data Trust")
INSTANCE_NAME = get_env("DJANGO_INSTANCE_NAME", "AASTMT")
PLATFORM_TITLE = f"{INSTANCE_NAME} · {PLATFORM_NAME}" if INSTANCE_NAME else PLATFORM_NAME

# ── Brand switch (one var drives app-enablement preset + identity) ──────────
# Frontend counterpart: VITE_BRAND → src/brands/*.js. Keep ids in sync.
DJANGO_BRAND = get_env("DJANGO_BRAND", "aastmt")

# Per-brand domain-app enablement preset. Applied by
# accounts/management/commands/bootstrap_platform.py when seeding
# PlatformAppConfig. Core apps (catalog/mdm/dq/connections/importexport/
# dataschema) stay enabled in every instance — they are platform capabilities
# gated separately by RBAC. The enabled set is intentionally OPEN: add future
# app ids per brand as they land (e.g. tectona grows beyond 'healthy').
BRAND_APP_PRESETS = {
    "aastmt": {
        "carbon": True,
        "people": False,
        "healthy": False,
        "stub": False,
    },
    "nibras": {
        "carbon": False,
        "people": True,
        "healthy": False,
        "stub": False,
    },
    "medos": {
        "carbon": False,
        "people": False,
        "healthy": False,
        "stub": False,
    },
    "tectona": {
        "carbon": False,
        "people": False,
        "healthy": True,   # + future first-party AI apps (open set)
        "stub": False,
    },
}

# ── Phase 1.1: Email defaults (overridden at runtime by EmailConfig model) ─
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = get_env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    f"{PLATFORM_TITLE} <noreply@carbon.clearturn.tech>",
)
EMAIL_SUBJECT_PREFIX = get_env("DJANGO_EMAIL_SUBJECT_PREFIX", f"[{PLATFORM_SHORT}] ")
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
    "filters": {
        "correlation_id": {
            "()": "core.log_filters.CorrelationIdFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d %(correlation_id)s",
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
            "filters": ["correlation_id"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_DIR, "carbon.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "formatter": "json",
            "filters": ["correlation_id"],
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

# Phase 21-A — per-user monthly token quota (soft warning at 80%, hard stop at 100%).
AI_DEFAULT_MONTHLY_TOKEN_LIMIT = int(
    os.environ.get("AI_DEFAULT_MONTHLY_TOKEN_LIMIT", 1_000_000)
)
AI_QUOTA_SOFT_WARNING_PCT = int(
    os.environ.get("AI_QUOTA_SOFT_WARNING_PCT", 80)
)

# ── OpenTelemetry (EPH-6A / P1-11) ────────────────────────────────────────
# Auto-instruments Django only when an OTLP collector endpoint is configured.
# Default: disabled — no span pipeline is started, zero overhead.
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

if OTEL_EXPORTER_OTLP_ENDPOINT:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _otel_resource = Resource.create({SERVICE_NAME: "carbon-backend"})
    _otel_provider = TracerProvider(resource=_otel_resource)
    _otel_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT))
    )
    trace.set_tracer_provider(_otel_provider)
    DjangoInstrumentor().instrument()