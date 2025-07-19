# File: backend/config/settings.py

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load default .env, then override with .env.production if needed
load_dotenv(os.path.join(BASE_DIR, ".env"))
if os.getenv("DJANGO_ENV") == "production":
    load_dotenv(os.path.join(BASE_DIR, ".env.production"), override=True)

# Environment
DJANGO_ENV = os.getenv("DJANGO_ENV", "development").lower()

def get_env(name, default=None, required=False):
    v = os.getenv(name, default)
    if required and v is None:
        raise Exception(f"Environment variable {name} is required!")
    return v

# Key settings
SECRET_KEY = get_env("SECRET_KEY", required=True)
DEBUG = get_env("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = get_env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
FORCE_SCRIPT_NAME = get_env('FORCE_SCRIPT_NAME', None)

print("FORCE_SCRIPT_NAME =", FORCE_SCRIPT_NAME)

CSRF_TRUSTED_ORIGINS = [x.strip() for x in get_env("CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]

print("CSRF_TRUSTED_ORIGINS =", repr(CSRF_TRUSTED_ORIGINS))

print("DEBUG =", repr(DEBUG))


# Path for API (configurable, e.g. /api/v1/, /carbon/api/)
API_PREFIX = get_env("DJANGO_API_PREFIX", "/api/v1/")

# File upload path for dataschema files
DATASCHEMA_UPLOAD_PATH = get_env("DATASCHEMA_UPLOAD_PATH", "dataschema_uploads/")

# Application definition
INSTALLED_APPS = [
    'accounts',
    'core',
    'dataschema',
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

if DJANGO_ENV == "development":
    INSTALLED_APPS += ['debug_toolbar']

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DJANGO_ENV == "development":
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# CORS
if DJANGO_ENV == "development":
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
]
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

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
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
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
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": get_env("ROOT_LOG_LEVEL", "WARNING"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": get_env("DJANGO_LOG_LEVEL", "DEBUG" if DJANGO_ENV == "development" else "INFO"),
            "propagate": True,
        },
        "rest_framework": {
            "handlers": ["console"],
            "level": get_env("REST_FRAMEWORK_LOG_LEVEL", "DEBUG" if DJANGO_ENV == "development" else "INFO"),
            "propagate": False,
        },
    },
}

# Debug Toolbar
if DJANGO_ENV == "development":
    INTERNAL_IPS = ["127.0.0.1"]

# Custom API prefix (used in urls.py)
API_PREFIX = API_PREFIX