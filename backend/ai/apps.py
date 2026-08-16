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

        # Register built-in domain apps so the manifest API and per-domain
        # prompt injection work in production (the domain modules are otherwise
        # never imported outside the test suite). Idempotent by identifier.
        from ai.domain import register_builtin_domains

        register_builtin_domains()
