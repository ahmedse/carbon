"""
Phase 2b-3a smoke script — proves dq.validate + dq.suggest complete.

Run from ``backend/``::

    /home/ahmed/aast/carbon/.venv/bin/python smoke_dq_wiring.py

Uses the in-memory Store (no DB required) and a stubbed LLM client (dev has no
``LLM_API_KEY``).  The durable-write path (DjangoStore -> PostgreSQL) is covered
by ``ai/tests/test_dq_wiring.py``.
"""

from __future__ import annotations

import json
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
    """One JSON object covering both result contracts (validate + suggest)."""
    content = json.dumps(
        {
            "results": [
                {"index": 0, "passed": True, "explanation": "ok"},
                {"index": 1, "passed": False, "explanation": "negative co2e"},
            ],
            "suggestions": [
                {
                    "prompt": "co2e_kg must be non-negative",
                    "rule_type": "nl_check",
                    "rationale": "emissions cannot be negative",
                    "suggested_severity": "error",
                    "confidence": 0.95,
                }
            ],
        }
    )

    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content=content, tool_calls=None),
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
    get_settings.cache_clear()
    reset_store()  # in-memory backend (default)

    cases = [
        (
            "dq.validate",
            {
                "rules": [
                    {
                        "id": "r1",
                        "prompt": "co2e_kg must be non-negative",
                        "fields": ["co2e_kg"],
                        "severity": "error",
                    }
                ],
                "rows": [{"co2e_kg": 10.5}, {"co2e_kg": -3.2}],
                "context": {"table_name": "emissions", "row_count_hint": 2},
            },
        ),
        (
            "dq.suggest",
            {
                "table": {
                    "name": "emissions",
                    "description": "facility emissions records",
                    "columns": [{"name": "co2e_kg", "type": "float"}],
                    "row_count": 1200,
                },
            },
        ),
    ]

    failures = []
    with patch(
        "ai.engine.llm.provider.get_llm_client",
        return_value=_fake_llm_client(),
    ):
        for task_type, payload in cases:
            data = dispatch_task(task_type, payload, instance_id="carbon")
            status = data.get("status")
            print(f"{task_type:14s} -> {status}")
            if status != "completed":
                failures.append((task_type, data))

    if failures:
        print("SMOKE FAILED:", failures)
        return 1

    print("SMOKE PASSED: dq.validate + dq.suggest -> status='completed'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
