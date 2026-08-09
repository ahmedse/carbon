# File: config/context_processors.py
# Phase 1.5 — Inject DJANGO_ENV into template context

from django.conf import settings


def django_env(request):
    """Makes DJANGO_ENV available in all templates (for env badge)."""
    return {
        'DJANGO_ENV': getattr(settings, 'DJANGO_ENV', 'development'),
        'DJANGO_ENV_LABEL': getattr(settings, 'DJANGO_ENV_LABEL', 'DEV'),
    }
