"""
Django app configuration for the AI Copilot module.

Provides AI-powered conversation workspace, data quality
validation, and intelligent suggestions via the Pulse provider.
"""

from django.apps import AppConfig


class AIConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    label = "ai"
    verbose_name = "AI Copilot"
