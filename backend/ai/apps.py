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

    def ready(self):
        # Sprint 12 (ARCH_AI_EXTENSIBILITY): register built-in tool/workflow
        # plugins once at startup. Idempotent by name, so safe for ready(),
        # management commands, and the test suite alike.
        from ai.plugins import register_builtin_plugins

        register_builtin_plugins()
