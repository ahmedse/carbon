# File: backend/config/settings.py
# Purpose: Django project settings for the 'backend' project.

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

print("Loaded SECRET_KEY:", os.getenv("SECRET_KEY"))
print("Loaded ALLOWED_HOSTS:", os.getenv("DJANGO_ALLOWED_HOSTS"))

# Determine the environment: 'development' or 'production'
DJANGO_ENV = os.getenv("DJANGO_ENV", "development").lower()

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    'django-insecure-9(mkyr(v_!gbmxt+kb(1z)a=l7vp(g(q4ocn^mo_0k#y_$!!v9'
)

# DEBUG/ALLOWED_HOSTS per environment
if DJANGO_ENV == "development":
    DEBUG = True
    ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "91.108.121.172,127.0.0.1,localhost").split(",")
else:
    DEBUG = False
    ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")

print("DJANGO_ENV is set to:", DJANGO_ENV)
print("DEBUG is set to:", DEBUG)

# File upload path for dataschema files
DATASCHEMA_UPLOAD_PATH = os.getenv("DATASCHEMA_UPLOAD_PATH", "dataschema_uploads/")

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
    'corsheaders',
    'drf_yasg',
]

# Development-only apps
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

# CORS configuration
if DJANGO_ENV == "development":
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False

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
        'NAME': os.getenv("DB_NAME"),
        'USER': os.getenv("DB_USER"),
        'PASSWORD': os.getenv("DB_PASSWORD"),
        'HOST': os.getenv("DB_HOST", "localhost"),
        'PORT': os.getenv("DB_PORT", "5433"),
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

STATIC_URL = 'static/'
STATIC_ROOT = os.getenv("DJANGO_STATIC_ROOT", BASE_DIR / 'staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Production-specific secure settings
if DJANGO_ENV == "production":
    # Secure settings
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Logging configuration
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {"class": "logging.StreamHandler"},
        },
        "root": {
            "handlers": ["console"],
            "level": os.getenv("ROOT_LOG_LEVEL", "WARNING"),
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
                "propagate": True,
            },
            "rest_framework": {
                "handlers": ["console"],
                "level": os.getenv("REST_FRAMEWORK_LOG_LEVEL", "INFO"),
                "propagate": False,
            },
        },
    }
else:
    # Development logging (more verbose)
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {"class": "logging.StreamHandler"},
        },
        "root": {
            "handlers": ["console"],
            "level": os.getenv("ROOT_LOG_LEVEL", "WARNING"),
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": os.getenv("DJANGO_LOG_LEVEL", "DEBUG"),
                "propagate": True,
            },
            "rest_framework": {
                "handlers": ["console"],
                "level": os.getenv("REST_FRAMEWORK_LOG_LEVEL", "DEBUG"),
                "propagate": False,
            },
        },
    }

# Internal IPs for debug toolbar
if DJANGO_ENV == "development":
    INTERNAL_IPS = ["127.0.0.1"]