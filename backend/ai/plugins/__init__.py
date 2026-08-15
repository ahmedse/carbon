"""Built-in AI tool/workflow plugins (Sprint 12 — ARCH_AI_EXTENSIBILITY).

A plugin is a well-defined, specific host process exposed to the agent as one
named tool.  Growth = add a class + one ``register_plugin()`` call; no edit to
``tools.py``'s static lists.

``register_builtin_plugins()`` is invoked once at app startup
(``ai.apps.AIConfig.ready``) and is idempotent (registration is first-wins by
name), so it is safe to call from ``ready()``, management commands, and tests.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("carbon.ai.plugins")


def register_builtin_plugins() -> None:
    """Import + register every built-in plugin (idempotent by name)."""
    from ai.engine.agent.plugins import register_plugin

    from .create_dq_rule import CreateDQRule

    register_plugin(CreateDQRule())
