"""
Phase 2b-1 smoke script — proves ``dispatch_task("chat", ...)`` completes.

Run from ``backend/``::

    /home/ahmed/aast/carbon/.venv/bin/python smoke_chat_wiring.py

Uses the in-memory Store (no DB required) and a stubbed LLM client (dev has no
``LLM_API_KEY``).  The durable-write path (DjangoStore -> PostgreSQL) is covered
by ``ai/tests/test_chat_wiring.py``.
"""

from __future__ import annotations

import os
import types
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from ai.engine.core.config import get_settings  # noqa: E402
from ai.engine_runtime import dispatch_task  # noqa: E402
from ai.store import reset_store  # noqa: E402


def _fake_llm_client() -> types.SimpleNamespace:
    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content="This is a stubbed chat reply.",
                        tool_calls=None,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10, completion_tokens=4, total_tokens=14
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))
    )


def main() -> int:
    # Force the single-pass six-witness spine (fan-out / multi-step are 2b-2/3).
    os.environ["AGENT_ORCHESTRATOR_ENABLED"] = "false"
    os.environ["KG_MULTI_STEP_ENABLED"] = "false"
    get_settings.cache_clear()

    reset_store()  # in-memory backend (default)

    payload = {
        "message": "What is our carbon footprint this quarter?",
        "conversation_history": {
            "conversation_id": "conv-smoke-1",
            "messages": [{"role": "user", "content": "hello"}],
        },
    }

    with patch("ai.engine.llm.provider.get_llm_client", return_value=_fake_llm_client()):
        data = dispatch_task("chat", payload, instance_id="carbon")

    print("status =", data.get("status"))
    print("result =", data.get("result"))

    if data.get("status") != "completed":
        print("SMOKE FAILED:", data)
        return 1
    if not (data.get("result") or {}).get("content"):
        print("SMOKE FAILED: empty content")
        return 1

    print("SMOKE PASSED: dispatch_task('chat', ...) -> status='completed'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
