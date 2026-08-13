"""
Phase 2b-2 smoke script — proves all seven KG/analytics tasks complete.

Run from ``backend/``::

    /home/ahmed/aast/carbon/.venv/bin/python smoke_kg_wiring.py

Uses the in-memory Store (no DB required) and a stubbed LLM client (dev has no
``LLM_API_KEY``).  The durable-write path (DjangoStore -> PostgreSQL) is covered
by ``ai/tests/test_kg_wiring.py``.
"""

from __future__ import annotations

import os
import types
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from ai.engine.core.config import get_settings  # noqa: E402
from ai.engine.knowledge_graph.engine import ExecutionResult  # noqa: E402
from ai.engine_runtime import dispatch_task  # noqa: E402
from ai.store import reset_store  # noqa: E402


async def _fake_execute(self, sql):
    return ExecutionResult(success=True, rows=[], row_count=0,
                           duration_ms=1, sql_executed=sql)


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


def _snap(rc, comp):
    return {
        "at": "2026-01-01T00:00:00Z", "row_count": rc,
        "completeness_pct": comp, "null_counts": {},
    }


def main() -> int:
    get_settings.cache_clear()
    reset_store()  # in-memory backend (default)

    cases = [
        ("carbon.query.nl", {"question": "total co2e", "tables": ["emissions"]}),
        ("carbon.query.explain", {"sql": "SELECT * FROM emissions", "question": "?"}),
        ("carbon.schema.analyze", {"schema_changes": [
            {"change": "drop column co2e_kg", "table_name": "emissions",
             "field_name": "co2e_kg"}], "context": {}}),
        ("carbon.anomaly.detect", {"table_name": "emissions",
                                   "profile_history": [
                                       _snap(1000, 98.0), _snap(1050, 97.5),
                                       _snap(2100, 97.0)],
                                   "sensitivity": 2.0,
                                   "volume_threshold_pct": 30.0}),
        ("carbon.anomaly.explain", {"table_name": "emissions",
                                    "anomaly": {"metric": "row_count"}}),
        ("carbon.report.draft", {"report_type": "emissions_summary",
                                 "period_start": "2026-01-01",
                                 "period_end": "2026-06-30", "metrics": {}}),
        ("carbon.fix.suggest", {"issue_type": "null_values",
                                "table_name": "emissions",
                                "affected_rows": 42}),
    ]

    failures = []
    with patch("ai.engine.llm.provider.get_llm_client", return_value=_fake_llm_client()), \
            patch("ai.engine.knowledge_graph.engine.ExecutionEngine.execute",
                  new=_fake_execute):
        for task_type, payload in cases:
            data = dispatch_task(task_type, payload, instance_id="carbon")
            status = data.get("status")
            print(f"{task_type:26s} -> {status}")
            if status != "completed":
                failures.append((task_type, data))

    if failures:
        print("SMOKE FAILED:", failures)
        return 1

    print("SMOKE PASSED: all 7 KG/analytics tasks -> status='completed'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
