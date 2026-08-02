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

# Application definition
INSTALLED_APPS = [
    'accounts',
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

if IS_DEVELOPMENT:
    INSTALLED_APPS += ['debug_toolbar', 'silk']

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
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

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
        'login': '5/minute',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
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

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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

# Logging
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