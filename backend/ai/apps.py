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
        # ── P2-03: store + adapter DI bootstrap ──────────────────────────
        # The vendored engine must never import ``ai.store`` / ``ai.adapters``
        # directly. We inject the host's concrete backends here — the single,
        # earliest bootstrap point (runs for the web process, management
        # commands like ``run_cognition_loop``, and the pytest suite alike).
        from ai.engine.core.database import set_store_provider
        from ai.store import get_store as _host_get_store

        set_store_provider(_host_get_store)

        from ai.adapters.cognition import DjangoSweepRunAdapter
        from ai.adapters.evidence import DjangoEvidenceAdapter
        from ai.adapters.knowledge import DjangoKnowledgeEntityAdapter
        from ai.adapters.preferences import DjangoUserPreferenceAdapter
        from ai.adapters.watches import DjangoWatchAdapter

        from ai.engine.cognition.loop import set_sweep_store_factory
        from ai.engine.cognition.turn.execute import set_evidence_store_provider
        from ai.engine.knowledge.store import set_knowledge_entity_store_provider
        from ai.engine.learning.preferences import set_user_preference_store_provider
        from ai.engine.proactive.user_watches import set_user_watch_store_factory

        set_sweep_store_factory(DjangoSweepRunAdapter)
        set_evidence_store_provider(DjangoEvidenceAdapter)
        set_knowledge_entity_store_provider(DjangoKnowledgeEntityAdapter)
        set_user_preference_store_provider(DjangoUserPreferenceAdapter)
        set_user_watch_store_factory(DjangoWatchAdapter)

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
