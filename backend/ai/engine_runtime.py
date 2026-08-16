"""
In-process engine runtime — replaces the retired HTTP transport.

Phase 2 wires the vendored engine in-process: instead of POSTing tasks to the
external Pulse server over HTTP, Carbon calls this runtime directly.  It is
the in-process counterpart of Pulse's ``POST /instances/carbon/tasks`` and
``GET /instances/carbon/tasks/{id}`` endpoints.

Each task type will map to a concrete engine capability (KG query, turn
runner, LLM) in Phase 2b.  Until a task is wired, ``dispatch_task`` returns a
graceful ``pulse_unavailable`` result — fail-visible, never a fabricated
answer.
"""

from __future__ import annotations

import json
import logging
import math
import queue
import re
import threading
import time
import types
import uuid
from typing import Any

logger = logging.getLogger("carbon.ai.engine_runtime")

# Task types the engine advertises (mirrors the retired Pulse task API).
MODULES: list[str] = [
    "dq.validate",
    "dq.suggest",
    "dq.rule_test",
    "carbon.query.nl",
    "carbon.query.explain",
    "carbon.anomaly.detect",
    "carbon.anomaly.explain",
    "carbon.report.draft",
    "carbon.schema.analyze",
    "carbon.fix.suggest",
    "investigate",
    "chat",
]


def _new_task_id() -> str:
    return f"inproc-{uuid.uuid4().hex[:16]}"


def _run_async(coro):
    """Run an async coroutine from a sync context.

    ``dispatch_task`` is sync (the AIProvider ABC is sync).  The vendored
    engine is async, so we bridge with ``asyncio.run``.  If we are already
    inside a running loop (rare — e.g. a caller awaiting a sync wrapper),
    run the coroutine on a worker thread to avoid nesting loops.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _run_chat(
    instance_id: str, payload: dict[str, Any], task_id: str, *, stream_callback=None
) -> dict[str, Any]:
    """Run a single chat turn through the six-witness pipeline.

    This is the Phase 2b-1 proof path: the in-process engine's ``chat``
    task calls ``TurnPipelineRunner.run`` directly (no HTTP), writing
    durable ``TurnLedgerRow`` / ``LLMCallLog`` rows through the configured
    ``ai.store`` backend (DjangoStore in production).
    """
    from ai.engine.cognition.turn.runner import TurnPipelineRunner
    from ai.engine.core.database import get_session_factory

    message = payload.get("message") or ""
    conversation = payload.get("conversation_history") or {}
    conversation_id = (
        conversation.get("conversation_id")
        or f"conv-{uuid.uuid4().hex[:12]}"
    )
    history_messages = conversation.get("messages") or []

    factory = get_session_factory(instance_id)
    async with factory() as db:
        runner = TurnPipelineRunner(db=db)
        response, ledger = await runner.run(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=message,
            conversation_history=history_messages,
            stream_callback=stream_callback,
        )
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {
                "content": response.text,
                "follow_up_questions": list(response.follow_ups or []),
                "execution_ms": int(ledger.total_latency_ms or 0),
            },
        }


# ── Shared helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Timezone-aware ISO-8601 timestamp."""
    from django.utils.timezone import now

    return now().isoformat()


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


async def _llm_text(
    task: str,
    instance_id: str,
    conversation_id: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.3,
    response_format: dict[str, Any] | None = None,
) -> str | None:
    """Return trimmed LLM reply content, or ``None`` if the LLM is unavailable.

    LLM *unavailability* (no API key, provider error, empty reply) degrades to
    a deterministic answer — never a fabricated one.  Anything that is *not* an
    LLM failure propagates to ``dispatch_task``'s fail-visible handler.

    ``response_format`` (e.g. ``{"type": "json_object"}``) is forwarded to the
    LLM router for structured-output tasks such as ``dq.validate``/``dq.suggest``.
    """
    from ai.engine.llm.router import route_chat

    try:
        resp = await route_chat(
            task,
            instance_id,
            conversation_id,
            messages,
            temperature=temperature,
            response_format=response_format,
        )
    except Exception as exc:  # noqa: BLE001 - LLM outage → deterministic fallback
        logger.warning("LLM unavailable for %s: %s", task, exc)
        return None
    content = (resp or {}).get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def _extract_sql(text: str) -> str:
    """Pull the first SQL block (or leading SELECT/WITH line) out of LLM text."""
    if not text:
        return ""
    lowered = text.lower()
    for marker in ("```sql", "```"):
        idx = lowered.find(marker)
        if idx != -1:
            start = idx + len(marker)
            end = lowered.find("```", start)
            if end != -1:
                return text[start:end].strip()
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith(("SELECT", "WITH")):
            return s
    return ""


def _deterministic_sql(tables: list[str], max_rows: int) -> str:
    table = (tables or [""])[0]
    if not table:
        return ""
    return f"SELECT * FROM {table} LIMIT {max_rows}"


def _nl_prompt(question: str, tables: list[str], max_rows: int) -> str:
    table_list = ", ".join(tables) if tables else "(infer from question)"
    return (
        f"Write a single read-only SQL query to answer this question: {question}\n"
        f"Relevant tables: {table_list}\n"
        f"Limit results to {max_rows} rows. Return only the SQL inside a ```sql block."
    )


def _explain_prompt(
    question: str, sql: str, row_count: int, sample_rows: list[Any]
) -> str:
    sample = json.dumps(sample_rows[:5], default=str)[:800] if sample_rows else "none"
    return (
        f"Explain this SQL query in plain language.\n"
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Rows returned: {row_count}\n"
        f"Sample rows: {sample}\n"
        f"Explain what the query does, how to read the result, and any caveats."
    )


def _deterministic_explanation(
    question: str, sql: str, row_count: int, sample_rows: list[Any]
) -> dict[str, Any]:
    caveats: list[str] = []
    if sample_rows:
        caveats.append("Rows shown are a sample, not the complete result set.")
    if not sql:
        return {
            "explanation": (
                "No SQL was provided to explain. Supply a query to receive a "
                "step-by-step interpretation."
            ),
            "caveats": caveats or ["No SQL to analyze."],
        }
    explanation = (
        f"This query returns {row_count or 'an unknown number of'} row(s) "
        f"for the question: {question or '(no question provided)'}."
    )
    if row_count:
        caveats.append(f"Results reflect {row_count} row(s); verify against the full dataset.")
    return {"explanation": explanation, "caveats": caveats}


def _analyze_schema_change(change: dict[str, Any]) -> dict[str, Any]:
    raw = (change.get("change") or "").lower()
    table_name = change.get("table_name") or "table"
    field_name = change.get("field_name") or ""
    if any(k in raw for k in ("drop", "remove", "delete")):
        impact = (
            f"Removing {field_name or 'an object'} from {table_name} may break "
            "queries, reports, and downstream pipelines that reference it."
        )
        severity = "high"
        action = (
            "Audit all consumers before removal; stage a deprecation window and "
            "a compatibility view where feasible."
        )
    elif "rename" in raw:
        impact = (
            f"Renaming {field_name or 'an object'} in {table_name} breaks "
            "references unless aliases are preserved."
        )
        severity = "high"
        action = "Introduce a compatibility alias and update referencing queries before cutover."
    elif any(k in raw for k in ("type", "cast", "alter", "modify")):
        impact = (
            f"Changing the type of {field_name or 'a column'} in {table_name} "
            "can truncate data or alter comparison semantics."
        )
        severity = "medium"
        action = "Validate coercion on a copy of the data and update consumers of the changed type."
    elif any(k in raw for k in ("add", "create", "new")):
        impact = (
            f"Adding {field_name or 'a column or table'} to {table_name} is "
            "backward compatible but must be documented."
        )
        severity = "low"
        action = "Update the data catalog and schema documentation."
    else:
        impact = (
            f"Schema change '{change.get('change') or '(unknown)'}' on "
            f"{table_name} needs review."
        )
        severity = "medium"
        action = "Review the change against the data catalog and downstream consumers."
    return {
        "change": change.get("change") or "",
        "impact": impact,
        "severity": severity,
        "suggested_action": action,
    }


def _deterministic_anomaly_explanation(
    table_name: str, anomaly: dict[str, Any]
) -> dict[str, Any]:
    metric = anomaly.get("metric") or f"{table_name}.unknown"
    z = anomaly.get("z_score")
    z_text = f" ({z}σ)" if isinstance(z, (int, float)) else ""
    explanation = (
        f"Anomaly detected in metric '{metric}'{z_text}. Compare the observed "
        "value against the historical range and trace recent data loads or "
        "process changes that could explain the deviation."
    )
    return {
        "explanation": explanation,
        "investigation_steps": [
            "Compare the affected period against previous periods.",
            "Check source ingestion jobs for partial or duplicate loads.",
            "Verify unit-of-measure and sensor/feed configuration.",
        ],
    }


def _deterministic_report_summary(
    report_type: str, period_start: str, period_end: str
) -> str:
    window = ""
    if period_start and period_end:
        window = f" for {period_start} through {period_end}"
    elif period_start:
        window = f" starting {period_start}"
    return (
        f"{report_type.replace('_', ' ').title()} report{window}. "
        "Figures below should be verified against source systems before "
        "external release."
    )


def _deterministic_fix_suggestions(
    issue_type: str, table_name: str, affected_rows: int
) -> list[dict[str, Any]]:
    t = (issue_type or "").lower()
    base = {
        "estimated_affected_rows": affected_rows,
    }
    if any(k in t for k in ("null", "missing", "empty")):
        return [
            {
                **base,
                "description": (
                    f"Fill or flag null/missing values in {table_name} using "
                    "domain defaults or imputation."
                ),
                "confidence": 0.8,
                "suggested_action_type": "impute",
            },
            {
                **base,
                "description": f"Exclude rows missing required fields from analysis.",
                "confidence": 0.7,
                "suggested_action_type": "filter",
            },
        ]
    if any(k in t for k in ("duplicate", "dup")):
        return [
            {
                **base,
                "description": (
                    f"Deduplicate {table_name} on its natural key, keeping the "
                    "most recent row."
                ),
                "confidence": 0.85,
                "suggested_action_type": "deduplicate",
            }
        ]
    if any(k in t for k in ("outlier", "anomaly", "spike")):
        return [
            {
                **base,
                "description": (
                    f"Review and quarantine outlier rows in {table_name} before "
                    "aggregation."
                ),
                "confidence": 0.75,
                "suggested_action_type": "review",
            }
        ]
    if any(k in t for k in ("type", "format", "cast", "invalid")):
        return [
            {
                **base,
                "description": (
                    f"Coerce invalid values in {table_name} to the declared type, "
                    "logging rejected values."
                ),
                "confidence": 0.8,
                "suggested_action_type": "coerce",
            }
        ]
    return [
        {
            **base,
            "description": (
                f"Investigate {table_name} ({issue_type or 'unknown issue'}) and "
                "apply a targeted corrective update."
            ),
            "confidence": 0.6,
            "suggested_action_type": "investigate",
        }
    ]


async def _write_query_feedback(
    instance_id: str,
    task_id: str,
    question: str,
    sql: str,
    outcome: Any,
) -> None:
    from ai.engine.core.config import get_settings

    if not get_settings().KG_FEEDBACK_ENABLED:
        return

    from ai.engine.core.database import get_session_factory
    from ai.models.knowledge_graph import KgQueryFeedback

    factory = get_session_factory(instance_id)
    async with factory() as db:
        db.add(
            KgQueryFeedback(
                instance_id=instance_id,
                question=(question or "")[:500],
                sql_final=(sql or "")[:2000],
                succeeded=bool(outcome.success),
                retry_count=0,
                error_category=(outcome.error.category.value if outcome.error else ""),
                duration_ms=int(outcome.duration_ms or 0),
                row_count=int(outcome.row_count or 0),
                shape="",
            )
        )
        await db.commit()


# ── Task handlers ─────────────────────────────────────────────────────────────


async def _run_query_nl(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    from ai.engine.core.config import get_settings
    from ai.engine.knowledge_graph.engine import ExecutionEngine

    settings = get_settings()
    question = payload.get("question") or ""
    tables = [str(t) for t in (payload.get("tables") or [])]
    max_rows = int(payload.get("max_rows") or settings.TASK_NL_QUERY_MAX_ROWS)

    llm_text = await _llm_text(
        task="query_nl",
        instance_id=instance_id,
        conversation_id=f"nl-{task_id}",
        messages=[{"role": "user", "content": _nl_prompt(question, tables, max_rows)}],
        temperature=0.1,
    )
    sql = _extract_sql(llm_text) if llm_text else ""
    if not sql:
        sql = _deterministic_sql(tables, max_rows)

    if not sql:
        # No tables supplied and LLM unavailable -> cannot generate SQL.
        return {
            "status": "pulse_unavailable",
            "task_id": task_id,
            "error": {
                "code": "engine_error",
                "message": (
                    "Unable to generate SQL: no tables supplied and the LLM "
                    "is unavailable."
                ),
            },
        }

    engine = ExecutionEngine(instance_id)
    outcome = await engine.execute(sql)

    await _write_query_feedback(instance_id, task_id, question, sql, outcome)

    # Fail-visible: a failed execution (table_not_found, syntax, permission,
    # timeout) must NOT be reported as a completed query with empty rows.
    if not outcome.success:
        err = outcome.error
        return {
            "status": "pulse_unavailable",
            "task_id": task_id,
            "error": {
                "code": "engine_error",
                "message": err.message if err else "SQL execution failed.",
            },
        }

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "sql": outcome.sql_executed or sql,
            "rows": outcome.rows,
            "row_count": outcome.row_count,
            "execution_ms": outcome.duration_ms,
            "recovery_applied": False,
        },
    }


async def _run_query_explain(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    question = payload.get("question") or ""
    sql = payload.get("sql") or ""
    row_count = int(payload.get("row_count") or 0)
    sample_rows = payload.get("sample_rows") or []

    deterministic = _deterministic_explanation(question, sql, row_count, sample_rows)
    llm_text = await _llm_text(
        task="query_explain",
        instance_id=instance_id,
        conversation_id=f"explain-{task_id}",
        messages=[
            {
                "role": "user",
                "content": _explain_prompt(question, sql, row_count, sample_rows),
            }
        ],
    )
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "explanation": llm_text or deterministic["explanation"],
            "caveats": deterministic["caveats"],
            "execution_ms": 0,
        },
    }


def _iter_schema_tables(payload: dict[str, Any]) -> list[tuple[str, list[dict]]]:
    """Yield (table_name, columns) pairs from ``schema`` / ``schema_changes``.

    Tolerates list-of-dicts, dict-of-lists, and bare-name entries.
    Returns [] when the payload carries no schema information (the
    deterministic fallback path).
    """
    tables: list[tuple[str, list[dict]]] = []

    schema = payload.get("schema")
    if isinstance(schema, dict):
        for tname, cols in schema.items():
            if isinstance(cols, list):
                tables.append(
                    (str(tname), [c for c in cols if isinstance(c, dict)])
                )
    elif isinstance(schema, list):
        for item in schema:
            if isinstance(item, dict):
                tname = item.get("table_name") or item.get("name") or ""
                cols = item.get("columns") or item.get("fields") or []
                if tname:
                    tables.append(
                        (str(tname), [c for c in cols if isinstance(c, dict)])
                    )
            elif isinstance(item, str):
                tables.append((item, []))

    for c in payload.get("schema_changes") or []:
        if isinstance(c, dict) and c.get("table_name"):
            tables.append((str(c["table_name"]), []))

    # Dedupe by table name, keeping the first (richest) column list.
    seen: set[str] = set()
    unique: list[tuple[str, list[dict]]] = []
    for tname, cols in tables:
        if tname not in seen:
            seen.add(tname)
            unique.append((tname, cols))
    return unique


async def _bootstrap_schema_graph(
    store: Any, instance_id: str, payload: dict[str, Any]
) -> dict[str, int]:
    """Upsert ENTITY/ATTRIBUTE nodes + HAS_ATTRIBUTE edges from the payload.

    Idempotent (exact-name upsert).  Returns creation counts.  Never raises:
    per-table failures are logged and skipped.
    """
    counts = {"entities": 0, "attributes": 0, "edges": 0}
    tables = _iter_schema_tables(payload)
    if not tables:
        return counts

    for tname, columns in tables:
        try:
            entity = await store.upsert_node(
                name=tname,
                instance_id=instance_id,
                node_type="ENTITY",
                properties={
                    "schema_json": json.dumps(columns, default=str),
                    "columns": columns,
                },
            )
            counts["entities"] += 1
        except Exception as exc:
            logger.debug("schema bootstrap ENTITY %s failed: %s", tname, exc)
            continue

        for col in columns:
            cname = col.get("column_name") or col.get("name") or ""
            if not cname:
                continue
            props = dict(col)
            if "column_name" not in props and "name" in props:
                props["column_name"] = props.pop("name")
            try:
                attr = await store.upsert_node(
                    name=f"{tname}.{cname}",
                    instance_id=instance_id,
                    node_type="ATTRIBUTE",
                    properties=props,
                )
                counts["attributes"] += 1
                try:
                    await store.add_edge(
                        {
                            "instance_id": instance_id,
                            "source_node_id": entity.id,
                            "target_node_id": attr.id,
                            "relationship": "HAS_ATTRIBUTE",
                            "properties": {"schema": True},
                            "confidence": 0.9,
                            "source": "SCHEMA",
                        }
                    )
                    counts["edges"] += 1
                except ValueError:
                    logger.debug(
                        "HAS_ATTRIBUTE edge skipped (duplicate): %s → %s",
                        tname, cname,
                    )
            except Exception as exc:
                logger.debug("schema bootstrap ATTRIBUTE %s failed: %s", cname, exc)

    return counts


async def _run_schema_analyze(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """
    Run the real KG schema-analysis pipeline (``run_schema_analysis``).

    When the payload carries schema information (``schema`` /
    ``schema_changes``), the KG is bootstrapped (ENTITY/ATTRIBUTE nodes +
    HAS_ATTRIBUTE edges) and ``run_schema_analysis(force=True)`` runs.
    Per-change deterministic analysis is always included (backward
    compatible).  Any failure — or a payload with no schema — degrades
    gracefully to the deterministic result only.
    """
    from ai.engine.core.database import get_session_factory
    from ai.engine.knowledge_graph.schema_analyzer import run_schema_analysis
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

    t0 = time.perf_counter()

    schema_changes = payload.get("schema_changes") or []
    analysis = [
        _analyze_schema_change(c) for c in schema_changes if isinstance(c, dict)
    ]

    kg_analysis: dict[str, Any] = {}
    if _iter_schema_tables(payload):
        try:
            factory = get_session_factory(instance_id)
            async with factory() as db:
                store = KnowledgeGraphStore(db)
                bootstrap = await _bootstrap_schema_graph(store, instance_id, payload)
                kg_analysis = await run_schema_analysis(
                    instance_id, force=True, session=db
                )
                kg_analysis["bootstrap"] = bootstrap
        except Exception as exc:
            logger.warning(
                "schema.analyze KG analysis failed for %s: %s", instance_id, exc
            )
            kg_analysis = {"error": str(exc), "degraded": True}

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "analysis": analysis,
            "kg_analysis": kg_analysis,
            "execution_ms": int((time.perf_counter() - t0) * 1000),
        },
    }


async def _run_anomaly_detect(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    from ai.engine.core.config import get_settings

    table_name = payload.get("table_name") or "table"
    history = payload.get("profile_history") or []
    sensitivity = float(payload.get("sensitivity") or 2.0)
    volume_threshold_pct = float(payload.get("volume_threshold_pct") or 30.0)

    history_snapshots = len(history)
    anomalies: list[dict[str, Any]] = []

    if history_snapshots >= 2:
        baseline = history[:-1]
        latest = history[-1]

        # Volume anomaly on row_count.
        past = [
            float(s["row_count"])
            for s in baseline
            if isinstance(s.get("row_count"), (int, float))
        ]
        current = latest.get("row_count")
        if past and isinstance(current, (int, float)):
            mean = _mean(past)
            std = _std(past)
            z = (current - mean) / std if std > 0 else 0.0
            pct = abs(current - mean) / mean * 100 if mean else 0.0
            if (std > 0 and abs(z) >= sensitivity) or pct >= volume_threshold_pct:
                anomalies.append(
                    {
                        "metric": f"{table_name}.row_count",
                        "expected_range": {
                            "low": round(mean - sensitivity * std, 2),
                            "high": round(mean + sensitivity * std, 2),
                        },
                        "observed": float(current),
                        "z_score": round(z, 2),
                        "severity": "error" if abs(z) >= sensitivity + 1 else "warning",
                        "explanation": (
                            f"row_count is {z:.2f}σ "
                            f"{'above' if z >= 0 else 'below'} the historical "
                            f"mean of {mean:.0f}."
                        ),
                    }
                )

        # Completeness anomaly (drop is bad).
        past_c = [
            float(s["completeness_pct"])
            for s in baseline
            if isinstance(s.get("completeness_pct"), (int, float))
        ]
        current_c = latest.get("completeness_pct")
        if past_c and isinstance(current_c, (int, float)):
            mean_c = _mean(past_c)
            std_c = _std(past_c)
            z_c = (current_c - mean_c) / std_c if std_c > 0 else 0.0
            if std_c > 0 and z_c <= -sensitivity:
                anomalies.append(
                    {
                        "metric": f"{table_name}.completeness",
                        "expected_range": {
                            "low": round(mean_c - sensitivity * std_c, 2),
                            "high": round(mean_c + sensitivity * std_c, 2),
                        },
                        "observed": float(current_c),
                        "z_score": round(z_c, 2),
                        "severity": "error" if z_c <= -(sensitivity + 1) else "warning",
                        "explanation": (
                            f"completeness dropped {abs(z_c):.2f}σ below the "
                            f"historical mean of {mean_c:.1f}%."
                        ),
                    }
                )

    # Real KG path: live profile of the table when a host DB is configured.
    # Best-effort — any failure degrades gracefully to the heuristic above.
    real_profile: dict[str, Any] = {}
    try:
        from ai.engine.knowledge_graph.engine import _default_host_db_url

        # Prefer an explicit HOST_DB_URL, but fall back to Django's default
        # database (Carbon's own PostgreSQL) so live profiling works without
        # any manual connection-string config — mirroring ExecutionEngine.
        host_db_url = get_settings().HOST_DB_URL or _default_host_db_url()
        if host_db_url:
            from ai.engine.knowledge_graph.data_profiler import DataProfiler

            profile = await DataProfiler(
                host_db_url=host_db_url,
                schema=get_settings().HOST_DB_SCHEMA,
            ).profile_table(
                table_name=table_name,
                columns=payload.get("columns") or [],
                sample_size=get_settings().KG_PROFILE_SAMPLE_SIZE,
                max_cardinality=get_settings().KG_PROFILE_MAX_CARDINALITY,
            )
            real_profile = {
                "table_name": profile.table_name,
                "row_count": profile.row_count,
                "columns": len(profile.columns),
                "profiled_at": profile.profiled_at,
            }
            # If the live count deviates from the latest snapshot, flag it.
            if history:
                latest = history[-1]
                live = profile.row_count
                last_count = latest.get("row_count")
                # ``row_count == 0`` is ambiguous (empty table vs. missing
                # table), so only flag a live deviation when the profiler
                # actually found rows in the host database.
                if (
                    live > 0
                    and isinstance(last_count, (int, float))
                    and isinstance(live, int)
                ):
                    delta_pct = (
                        abs(live - last_count) / last_count * 100
                        if last_count
                        else 0.0
                    )
                    if delta_pct >= volume_threshold_pct:
                        anomalies.append(
                            {
                                "metric": f"{table_name}.row_count.live",
                                "expected_range": {
                                    "low": float(last_count),
                                    "high": float(last_count),
                                },
                                "observed": float(live),
                                "z_score": None,
                                "severity": "warning",
                                "explanation": (
                                    f"Live row count {live} differs from the most "
                                    f"recent snapshot by {delta_pct:.1f}%."
                                ),
                            }
                        )
    except Exception as exc:
        logger.warning(
            "anomaly.detect live profile failed for %s: %s", table_name, exc
        )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "anomalies": anomalies,
            "history_snapshots": history_snapshots,
            "live_profile": real_profile,
        },
    }


async def _run_anomaly_explain(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    table_name = payload.get("table_name") or "table"
    anomaly = payload.get("anomaly") or {}
    deterministic = _deterministic_anomaly_explanation(table_name, anomaly)
    llm_text = await _llm_text(
        task="anomaly_explain",
        instance_id=instance_id,
        conversation_id=f"anomaly-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Explain the likely cause of this anomaly on {table_name}: "
                    f"{json.dumps(anomaly, default=str)}."
                ),
            }
        ],
    )
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "explanation": llm_text or deterministic["explanation"],
            "investigation_steps": deterministic["investigation_steps"],
            "execution_ms": 0,
        },
    }


async def _run_report_draft(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    report_type = payload.get("report_type") or "summary"
    period_start = payload.get("period_start") or ""
    period_end = payload.get("period_end") or ""

    title = f"{report_type.replace('_', ' ').title()} Report"
    summary = _deterministic_report_summary(report_type, period_start, period_end)

    # Real KG context: report only what the store actually holds — never
    # invent figures.  Best-effort; failure degrades to no context.
    kg_context: dict[str, Any] = {}
    try:
        from ai.engine.core.database import get_session_factory
        from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode

        factory = get_session_factory(instance_id)
        async with factory() as db:
            entities = await db.select(
                KnowledgeNode,
                ("instance_id", instance_id),
                ("node_type", "ENTITY"),
            )
            attributes = await db.select(
                KnowledgeNode,
                ("instance_id", instance_id),
                ("node_type", "ATTRIBUTE"),
            )
            edges = await db.select(KnowledgeEdge, ("instance_id", instance_id))
        kg_context = {
            "entities": len(entities),
            "attributes": len(attributes),
            "edges": len(edges),
        }
    except Exception as exc:
        logger.warning(
            "report.draft KG context failed for %s: %s", instance_id, exc
        )
        kg_context = {"error": str(exc)}

    # Real host-DB grounding: pull live table volume from the host database
    # so the report references actual data present in the platform, never
    # invented figures.  Best-effort — failure degrades to no live metrics.
    host_metrics: dict[str, Any] = {}
    try:
        from ai.engine.knowledge_graph.engine import ExecutionEngine

        engine = ExecutionEngine(instance_id)
        outcome = await engine.execute(
            "SELECT relname AS table_name, n_live_tup AS row_count "
            "FROM pg_stat_user_tables "
            "WHERE schemaname = 'public' AND n_live_tup > 0 "
            "ORDER BY n_live_tup DESC LIMIT 25"
        )
        if outcome.success:
            host_metrics = {
                "tables": outcome.rows,
                "total_tables": len(outcome.rows),
            }
        else:
            host_metrics = {"error": "host query failed"}
    except Exception as exc:
        logger.warning(
            "report.draft host metrics failed for %s: %s", instance_id, exc
        )
        host_metrics = {"error": str(exc)}

    llm_text = await _llm_text(
        task="report_draft",
        instance_id=instance_id,
        conversation_id=f"report-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Draft a {report_type} report summary for "
                    f"{period_start} → {period_end}."
                    f"\n\nKnowledge-graph context: {json.dumps(kg_context, default=str)}"
                    f"\nLive host-data volume: {json.dumps(host_metrics, default=str)}"
                    "\n\nGround the narrative in these figures; do not invent numbers."
                ),
            }
        ],
    )
    if llm_text:
        summary = llm_text

    caveats = [
        "Verify figures against source systems before release.",
    ]
    if kg_context.get("error") or not kg_context:
        caveats.append(
            "Knowledge-graph context unavailable; figures are not sourced "
            "from the live graph."
        )
    if host_metrics.get("error") or not host_metrics.get("tables"):
        caveats.append(
            "Live host-data volume unavailable; table figures are not "
            "sourced from the live database."
        )

    sections = [
        {
            "title": "Summary",
            "narrative": summary,
            "sql": None,
            "data_table": kg_context or None,
            "caveats": caveats,
        },
        {
            "title": "Data Volume (Live)",
            "narrative": (
                "Live row counts for the largest platform tables "
                "(pg_stat_user_tables)."
            ),
            "sql": None,
            "data_table": host_metrics or None,
            "caveats": [],
        },
    ]
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "title": title,
            "summary": summary,
            "report_type": report_type,
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": _now_iso(),
            "kg_context": kg_context,
            "host_metrics": host_metrics,
            "sections": sections,
        },
    }


async def _run_fix_suggest(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    issue_type = payload.get("issue_type") or ""
    table_name = payload.get("table_name") or "table"
    affected_rows = int(payload.get("affected_rows") or 0)

    suggestions = _deterministic_fix_suggestions(issue_type, table_name, affected_rows)
    llm_text = await _llm_text(
        task="fix_suggest",
        instance_id=instance_id,
        conversation_id=f"fix-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Suggest fixes for issue '{issue_type}' on table {table_name} "
                    f"({affected_rows} affected rows)."
                ),
            }
        ],
    )
    if llm_text:
        suggestions[0]["description"] = llm_text

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "issue_type": issue_type,
            "table_name": table_name,
            "suggestions": suggestions,
        },
    }


# ── DQ handlers (Phase 2b-3a) ────────────────────────────────────────────────
#
# ``dq.validate`` / ``dq.suggest`` are LLM-only task types: arbitrary
# natural-language DQ rules have no deterministic evaluator, so an LLM outage
# returns ``pulse_unavailable`` (fail-visible) — never a fabricated verdict.
# ``backend/dq/engine.py`` is the *caller* (via PulseProvider), not a
# dependency: these handlers use the engine LLM only.


def _dq_validate_prompt(
    rule: dict[str, Any], rows: list[Any], context: dict[str, Any]
) -> str:
    """Build the evaluator message for one rule against all rows.

    Requires a JSON object with one ``{index, passed, explanation}`` entry per
    row; ``index`` must match the row's 0-based position in ``rows``.
    """
    ctx = context or {}
    table_name = ctx.get("table_name") or "table"
    row_count_hint = ctx.get("row_count_hint") or len(rows)
    fields = ", ".join(str(f) for f in (rule.get("fields") or [])) or "(all columns)"
    row_json = json.dumps(rows, default=str)
    return (
        "You are a data-quality rule evaluator. Evaluate the business rule "
        "against EVERY data row and return a single JSON object:\n"
        '{"results": [{"index": int, "passed": bool, "explanation": str}, ...]}\n'
        "with exactly one entry per row. \"index\" must match the row's 0-based "
        "position in the provided list; \"passed\" is true if the row satisfies "
        "the rule, false otherwise; \"explanation\" is a short reason.\n"
        f"Rule id: {rule.get('id') or '(none)'}\n"
        f"Rule: {rule.get('prompt') or '(no prompt)'}\n"
        f"Relevant fields: {fields}\n"
        f"Severity: {rule.get('severity') or 'unknown'}\n"
        f"Table: {table_name} (row count hint: {row_count_hint})\n"
        f"Rows: {row_json}\n"
        "Return only the JSON object, nothing else."
    )


def _dq_suggest_prompt(table: dict[str, Any]) -> str:
    """Build the suggestion message for a table's metadata.

    Requires a JSON object of proposed natural-language DQ business rules
    (completeness, cross-field consistency, temporal plausibility,
    range/outlier plausibility).
    """
    columns = table.get("columns") or []
    col_json = json.dumps(columns, default=str)[:2000]
    return (
        "You are a data-quality analyst. Propose natural-language data-quality "
        "business rules for the table below — consider completeness, "
        "cross-field consistency, temporal plausibility, and range/outlier "
        "plausibility — and return a single JSON object:\n"
        '{"suggestions": [{"prompt": str, "rule_type": "nl_check", '
        '"rationale": str, "suggested_severity": "info"|"warn"|"error", '
        '"confidence": float}, ...]}\n'
        f"Table name: {table.get('name') or '(unknown)'}\n"
        f"Description: {table.get('description') or '(none)'}\n"
        f"Columns: {col_json}\n"
        f"Row count: {table.get('row_count') or 'unknown'}\n"
        "Return only the JSON object, nothing else."
    )


def _coerce_confidence(value: Any) -> float:
    """Coerce an LLM-provided confidence to a float clamped to [0.0, 1.0].

    Missing/uncoercible values default to a neutral 0.5.
    """
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.5
    return max(0.0, min(1.0, confidence))


def _llm_unavailable(task_id: str, message: str) -> dict[str, Any]:
    """Fail-visible result for an LLM outage (never fabricate a verdict)."""
    return {
        "status": "pulse_unavailable",
        "task_id": task_id,
        "error": {
            "code": "llm_unavailable",
            "message": message,
        },
    }


async def _run_dq_validate(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Evaluate each DQ rule against all rows in ONE LLM call per rule.

    Per-rule verdict JSON: ``{"results": [{"index", "passed", "explanation"}]}``.
    An LLM outage → ``pulse_unavailable``/``llm_unavailable``; an unparseable
    verdict degrades that rule to ``skipped_unavailable`` (never a fabricated
    pass/fail).  ``details`` is positionally indexed by row.
    """
    rules = [r for r in (payload.get("rules") or []) if isinstance(r, dict)]
    rows = payload.get("rows") or []
    context = payload.get("context") or {}

    if not rules or not rows:
        # The consumer treats "no rules / no rows" as a local no-op.
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {"results": []},
        }

    results: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = str(rule.get("id") or "")
        llm_text = await _llm_text(
            task="eval",
            instance_id=instance_id,
            conversation_id=f"dq-validate-{task_id}",
            messages=[
                {"role": "user", "content": _dq_validate_prompt(rule, rows, context)}
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        if not llm_text:
            return _llm_unavailable(
                task_id, f"LLM unavailable while evaluating rule {rule_id!r}."
            )

        try:
            verdicts = json.loads(llm_text).get("results")
        except (json.JSONDecodeError, TypeError, AttributeError):
            verdicts = None
        if not isinstance(verdicts, list):
            # Unparseable/empty verdict → fail-visible skip, never a pass.
            results.append(
                {"rule_id": rule_id, "status": "skipped_unavailable", "details": []}
            )
            continue

        by_index: dict[int, dict[str, Any]] = {}
        for verdict in verdicts:
            if not isinstance(verdict, dict):
                continue
            try:
                idx = int(verdict.get("index"))
            except (TypeError, ValueError):
                continue
            by_index[idx] = verdict

        details = [
            {
                "passed": bool(by_index.get(i, {}).get("passed", False)),
                "explanation": str(by_index.get(i, {}).get("explanation") or ""),
            }
            for i in range(len(rows))
        ]
        status = "pass" if all(d["passed"] for d in details) else "fail"
        results.append({"rule_id": rule_id, "status": status, "details": details})

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {"results": results},
    }


async def _run_dq_suggest(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Propose natural-language DQ rules for a table via the LLM.

    Verdict JSON: ``{"suggestions": [{"prompt", "rule_type", "rationale",
    "suggested_severity", "confidence"}]}``.  No deterministic fallback — an
    LLM outage or unparseable verdict returns ``pulse_unavailable``.
    """
    table = payload.get("table") or {}
    llm_text = await _llm_text(
        task="cognition",
        instance_id=instance_id,
        conversation_id=f"dq-suggest-{task_id}",
        messages=[{"role": "user", "content": _dq_suggest_prompt(table)}],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    if not llm_text:
        return _llm_unavailable(
            task_id, "LLM unavailable while suggesting data-quality rules."
        )

    try:
        raw = json.loads(llm_text).get("suggestions")
    except (json.JSONDecodeError, TypeError, AttributeError):
        raw = None
    if not isinstance(raw, list):
        # Unparseable payload — fabricating rules is worse than saying no.
        return _llm_unavailable(
            task_id, "LLM returned an unparseable suggestion payload."
        )

    suggestions: list[dict[str, Any]] = []
    for suggestion in raw:
        if not isinstance(suggestion, dict):
            continue
        severity = str(suggestion.get("suggested_severity") or "warn").lower()
        if severity not in ("info", "warn", "error"):
            severity = "warn"
        suggestions.append(
            {
                "prompt": str(suggestion.get("prompt") or ""),
                "rule_type": str(suggestion.get("rule_type") or "nl_check"),
                "rationale": str(suggestion.get("rationale") or ""),
                "suggested_severity": severity,
                "confidence": _coerce_confidence(suggestion.get("confidence")),
            }
        )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {"suggestions": suggestions},
    }


# Deterministic v1 rule types that ``dq.engine.evaluate`` can dry-run without
# an NL-check round-trip.  The LLM is constrained to emit only these; anything
# else is fail-visible (never a fabricated pass/fail).
_DETERMINISTIC_RULE_TYPES = {
    "not_null",
    "unique",
    "allowed_values",
    "range",
    "regex",
    "reference_integrity",
    "threshold",
}


def _nl_rule_test_prompt(
    nl: str, schema: list[dict[str, Any]], table_name: str
) -> str:
    """Build the parse message that turns NL into a v1 rule definition.

    Requires a JSON object using ``type`` + ``params`` keys (NOT
    ``rule_type``) so the output matches ``dq.engine.evaluate`` directly.
    """
    schema_json = json.dumps(schema, default=str)[:2000]
    return (
        "You are a data-quality engineer. Convert the natural-language rule "
        "below into a single JSON object describing a deterministic v1 DQ "
        "rule definition:\n"
        '{"type": str, "params": object, "severity": "info"|"warn"|"error", '
        '"confidence": float, "field": str}\n'
        '"type" must be one of: not_null, unique, allowed_values, range, '
        'regex, reference_integrity, threshold.\n'
        '"params" hold the parameters for that type: range -> {"min","max"}; '
        'threshold -> {"operator","value"}; regex -> {"pattern"}; '
        'allowed_values -> {"values":[...]}; unique -> {}; not_null -> {}; '
        'reference_integrity -> {"reference_set_id": int}.\n'
        '"field" is the column name the rule applies to (use one of the '
        'columns below).\n'
        f"Table name: {table_name}\n"
        f"Columns: {schema_json}\n"
        f"Natural-language rule: {nl}\n"
        "Return only the JSON object, nothing else."
    )


def _is_empty_value(v: Any) -> bool:
    """Mirror dq.engine's emptiness rule (None/''/[] are empty)."""
    return v is None or v == "" or v == []


def _rule_test_rows(
    rule_type: str,
    params: dict[str, Any],
    rows: list[Any],
    field_name: str | None,
) -> list[dict[str, Any]]:
    """Per-row detail for the Phase 8-B threshold slider re-score.

    One entry per *applicable* row carrying ``{row_id, actual, expected,
    passed}`` so the frontend can re-score client-side with no server
    round-trip.  Mirrors dq.engine.evaluate's deterministic branches; pure
    and read-only.
    """
    out: list[dict[str, Any]] = []

    # Pre-compute uniqueness counts (the 'unique' verdict depends on the set).
    unique_counts: dict[str, int] = {}
    if rule_type == "unique":
        for r in rows:
            v = r.values.get(field_name)
            if _is_empty_value(v):
                continue
            unique_counts[str(v)] = unique_counts.get(str(v), 0) + 1

    # Pre-compute allowed values for reference-set-backed rules (read-only).
    allowed: set[str] | None = None
    if rule_type == "allowed_values":
        from mdm.models import ReferenceValue

        rs_id = params.get("reference_set")
        if rs_id:
            allowed = {
                str(c)
                for c in ReferenceValue.objects.filter(
                    reference_set_id=rs_id, is_active=True
                ).values_list("code", flat=True)
            }
        else:
            allowed = {str(a) for a in (params.get("values") or [])}
    elif rule_type == "reference_integrity":
        rs_id = params.get("reference_set_id")
        if rs_id:
            from mdm.models import ReferenceSet

            try:
                ref_set = ReferenceSet.objects.get(id=rs_id)
                allowed = {
                    str(c)
                    for c in ref_set.get_current_values().values_list("code", flat=True)
                }
            except ReferenceSet.DoesNotExist:
                allowed = set()
        else:
            allowed = set()

    for r in rows:
        v = r.values.get(field_name)
        row_id = r.id

        if rule_type == "not_null":
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": "non-empty",
                    "passed": not _is_empty_value(v),
                }
            )
            continue

        if _is_empty_value(v):
            continue  # not applicable for every other deterministic type

        if rule_type == "unique":
            passed = unique_counts.get(str(v), 0) <= 1
            out.append(
                {"row_id": row_id, "actual": v, "expected": "unique", "passed": passed}
            )
        elif rule_type == "allowed_values":
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": sorted(allowed) if allowed is not None else [],
                    "passed": str(v) in (allowed or set()),
                }
            )
        elif rule_type == "range":
            lo = params.get("min")
            hi = params.get("max")
            try:
                fv = float(v)
                passed = (lo is None or fv >= lo) and (hi is None or fv <= hi)
            except (TypeError, ValueError):
                passed = False
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": {"min": lo, "max": hi},
                    "passed": passed,
                }
            )
        elif rule_type == "regex":
            pat = params.get("pattern", "")
            try:
                rx = re.compile(pat) if pat else None
            except re.error:
                rx = None
            passed = rx is None or rx.search(str(v)) is not None
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": pat,
                    "passed": passed,
                }
            )
        elif rule_type == "threshold":
            op = params.get("operator", "gte")
            tv = params.get("value")
            try:
                fv = float(v)
                t = float(tv) if tv is not None else None
                if t is None:
                    passed = False
                elif op == "gte":
                    passed = fv >= t
                elif op == "gt":
                    passed = fv > t
                elif op == "lte":
                    passed = fv <= t
                elif op == "lt":
                    passed = fv < t
                elif op == "eq":
                    passed = fv == t
                elif op == "neq":
                    passed = fv != t
                else:
                    passed = True  # unknown operator → no-op (matches evaluate)
            except (TypeError, ValueError):
                passed = False
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": {"operator": op, "value": tv},
                    "passed": passed,
                }
            )
        elif rule_type == "reference_integrity":
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": params.get("reference_set_id"),
                    "passed": str(v) in (allowed or set()),
                }
            )

    return out


async def _run_nl_rule_test(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Parse an NL rule into a v1 definition and dry-run it (read-only).

    Never writes a DQRule/DQResult: the LLM parse and the
    ``dq.engine.evaluate`` call are both pure.  An LLM outage, an unparseable
    definition, or an unsupported rule type returns ``pulse_unavailable`` —
    never a fabricated pass/fail.
    """
    nl = str(payload.get("nl") or "").strip()
    table_name = str(payload.get("table_name") or "table")
    schema = payload.get("schema") or []
    rows = payload.get("rows") or []
    field_name = payload.get("field_name")

    if not nl:
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {
                "rule_preview": None,
                "test_summary": {
                    "total_rows": len(rows),
                    "applicable_rows": 0,
                    "passed": 0,
                    "failed": 0,
                    "pass_rate": 0.0,
                },
                "violations": [],
                "rows": [],
                "recommendation": "No natural-language rule was provided.",
            },
        }

    llm_text = await _llm_text(
        task="cognition",
        instance_id=instance_id,
        conversation_id=f"nl-rule-test-{task_id}",
        messages=[
            {"role": "user", "content": _nl_rule_test_prompt(nl, schema, table_name)}
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    if not llm_text:
        return _llm_unavailable(
            task_id, "LLM unavailable while parsing the natural-language rule."
        )

    try:
        parsed = json.loads(llm_text)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if not isinstance(parsed, dict):
        return _llm_unavailable(
            task_id, "LLM returned an unparseable rule definition."
        )

    rule_type = str(parsed.get("type") or "")
    if rule_type not in _DETERMINISTIC_RULE_TYPES:
        return _llm_unavailable(
            task_id, f"LLM returned an unsupported rule type {rule_type!r}."
        )

    params = parsed.get("params")
    if not isinstance(params, dict):
        params = {}
    severity = str(parsed.get("severity") or "warn").lower()
    if severity not in ("info", "warn", "error"):
        severity = "warn"
    confidence = _coerce_confidence(parsed.get("confidence"))
    resolved_field = parsed.get("field") or field_name

    rule_def = {
        "type": rule_type,
        "params": params,
        "severity": severity,
    }

    # ``dq.engine.evaluate`` only needs ``field.name`` (and, for
    # reference_integrity, ``field.reference_set_id``) — pass a lightweight
    # namespace rather than importing dataschema models into the engine.
    field_obj = (
        types.SimpleNamespace(name=resolved_field, reference_set_id=None)
        if resolved_field
        else None
    )

    from dq.engine import evaluate as engine_evaluate

    _passed, checked, failed, sample_failures, _score = engine_evaluate(
        rule_def, rows, field=field_obj
    )

    passed_count = checked - failed
    pass_rate = round(passed_count / checked, 4) if checked else 0.0

    # Per-applicable-row detail (actual vs expected) so the Phase 8-B
    # threshold slider can re-score client-side with no server round-trip.
    detail_rows = _rule_test_rows(rule_type, params, rows, resolved_field)

    if failed == 0:
        recommendation = "All applicable rows pass — this rule can be saved as-is."
    else:
        recommendation = (
            f"{failed} of {checked} applicable row(s) fail. Review the "
            "violations before saving the rule."
        )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "rule_preview": {
                "type": rule_type,
                "params": params,
                "severity": severity,
                "confidence": confidence,
                "field": resolved_field,
            },
            "test_summary": {
                "total_rows": len(rows),
                "applicable_rows": checked,
                "passed": passed_count,
                "failed": failed,
                "pass_rate": pass_rate,
            },
            "violations": sample_failures,
            "rows": detail_rows,
            "recommendation": recommendation,
        },
    }


# Severity mapping for investigate findings (DQ + anomaly → high|medium|low).
_INVESTIGATE_SEVERITY_MAP = {
    "error": "high",
    "warn": "medium",
    "warning": "medium",
    "info": "low",
}


def _investigate_severity(value: str) -> str:
    """Map a DQ/anomaly severity string to high|medium|low."""
    return _INVESTIGATE_SEVERITY_MAP.get(str(value or "").lower(), "medium")


async def _run_investigate(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Read-only investigation pipeline (Phase 9-A).

    Consumes a pre-loaded payload (assembled by the intelligence layer) and
    produces ``plan_steps`` + ``findings`` + ``summary``.  Never writes to DQ:
    the DQ step calls the pure ``dq.engine.evaluate`` loop (RULE_21), the
    anomaly step reuses the already-registered ``_run_anomaly_detect``, and
    the KG step reports entities retrieved upstream (retrieval needs
    ``scope``, which only the intelligence layer holds).

    An LLM outage only degrades the narrative ``summary`` — deterministic
    findings are still returned, and the synthesis step is marked
    ``llm_unavailable`` (never ``pulse_unavailable``).
    """
    from dq.engine import evaluate as engine_evaluate

    table_id = payload.get("table_id")
    table_name = str(payload.get("table_name") or "table")
    schema = payload.get("schema") or []
    rows = payload.get("rows") or []
    profile_summary = payload.get("profile_summary") or {}
    rule_defs = [r for r in (payload.get("rule_defs") or []) if isinstance(r, dict)]
    anomaly_payload = payload.get("anomaly_payload")
    kg_entries = payload.get("kg_entries") or []

    field_type_by_name = {
        str(f.get("name")): f.get("type")
        for f in schema
        if isinstance(f, dict) and f.get("name")
    }

    plan_steps: list[dict[str, Any]] = []

    # Step 1 — Profile (read-only, from the latest TableProfile summary).
    row_count = profile_summary.get("row_count", len(rows))
    field_count = profile_summary.get("field_count", len(schema))
    plan_steps.append(
        {
            "step": 1,
            "label": "Profile table",
            "status": "done",
            "detail": f"{row_count} rows · {field_count} fields",
        }
    )

    # Step 2 — DQ rules (pure evaluate loop mirroring run_dq's selection, but
    # with no persistence).
    findings: list[dict[str, Any]] = []
    rules_run = 0
    rules_failed = 0
    for rule_def in rule_defs:
        field_name = rule_def.get("field_name")
        field = (
            types.SimpleNamespace(
                name=field_name,
                data_type=field_type_by_name.get(field_name),
                reference_set_id=rule_def.get("reference_set_id"),
            )
            if field_name
            else None
        )
        try:
            _passed, checked, failed, _sample, _score = engine_evaluate(
                rule_def, rows, field=field
            )
        except Exception as exc:  # noqa: BLE001 - a bad rule def must not kill the turn
            logger.warning(
                "investigate DQ eval failed for rule %s: %s",
                rule_def.get("name"),
                exc,
            )
            continue
        rules_run += 1
        if failed > 0:
            rules_failed += 1
            label = rule_def.get("name") or rule_def.get("id")
            findings.append(
                {
                    "severity": _investigate_severity(rule_def.get("severity")),
                    "title": f"DQ rule '{label}' failed",
                    "detail": f"{failed} of {checked} applicable row(s) violated rule '{label}'.",
                    "recommended_action": "Review the failing rows and correct or quarantine them.",
                    "entity_ref": field_name,
                }
            )
    plan_steps.append(
        {
            "step": 2,
            "label": "Evaluate DQ rules",
            "status": "done",
            "detail": f"{rules_run} rules run · {rules_failed} failed",
        }
    )

    # Step 3 — Anomalies (reuse the already-registered _run_anomaly_detect).
    anomalies: list[dict[str, Any]] = []
    if anomaly_payload:
        anomaly_result = await _run_anomaly_detect(instance_id, anomaly_payload, task_id)
        anomalies = (anomaly_result.get("result") or {}).get("anomalies") or []
        for anomaly in anomalies:
            if not isinstance(anomaly, dict):
                continue
            findings.append(
                {
                    "severity": _investigate_severity(anomaly.get("severity")),
                    "title": f"Anomaly: {anomaly.get('metric', table_name)}",
                    "detail": str(anomaly.get("explanation") or "Detected an anomalous value."),
                    "recommended_action": "Investigate this anomaly before it propagates downstream.",
                    "entity_ref": anomaly.get("metric") or table_name,
                }
            )
        detail = f"{len(anomalies)} anomalies" if anomalies else "0 anomalies"
    else:
        detail = "insufficient history"
    plan_steps.append(
        {
            "step": 3,
            "label": "Detect anomalies",
            "status": "done",
            "detail": detail,
        }
    )

    # Step 4 — Knowledge graph (retrieved upstream in the intelligence layer).
    plan_steps.append(
        {
            "step": 4,
            "label": "Retrieve knowledge graph",
            "status": "done",
            "detail": f"{len(kg_entries)} entities",
        }
    )

    counts = {
        "rules_run": rules_run,
        "rules_failed": rules_failed,
        "anomalies": len(anomalies),
        "kg_entities": len(kg_entries),
    }

    # Step 5 — Synthesis (best-effort LLM narrative; deterministic fallback).
    llm_text = await _llm_text(
        task="investigate",
        instance_id=instance_id,
        conversation_id=f"investigate-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize the data-quality investigation of table "
                    f"{table_name!r}. Return a JSON object: "
                    '{"summary": str}.\n'
                    f"Findings: {json.dumps(findings, default=str)}"
                ),
            }
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    summary = None
    if llm_text:
        try:
            parsed_summary = json.loads(llm_text)
            if isinstance(parsed_summary, dict):
                summary = str(parsed_summary.get("summary") or "").strip()
        except (json.JSONDecodeError, TypeError):
            summary = None

    if summary:
        synthesis_status = "done"
        synthesis_detail = summary
    else:
        summary = (
            f"{rules_failed} of {rules_run} rule(s) failed, "
            f"{len(anomalies)} anomaly(s) detected."
        )
        synthesis_status = "llm_unavailable"
        synthesis_detail = "LLM unavailable — deterministic summary used."
    plan_steps.append(
        {
            "step": 5,
            "label": "Synthesize findings",
            "status": synthesis_status,
            "detail": synthesis_detail,
        }
    )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "table_id": table_id,
            "table_name": table_name,
            "plan_steps": plan_steps,
            "findings": findings,
            "summary": summary,
            "counts": counts,
        },
    }


# Handler registry: task type → async handler.
_TASK_HANDLERS: dict[str, Any] = {
    "dq.validate": _run_dq_validate,
    "dq.suggest": _run_dq_suggest,
    "dq.rule_test": _run_nl_rule_test,
    "carbon.query.nl": _run_query_nl,
    "carbon.query.explain": _run_query_explain,
    "carbon.schema.analyze": _run_schema_analyze,
    "carbon.anomaly.detect": _run_anomaly_detect,
    "carbon.anomaly.explain": _run_anomaly_explain,
    "carbon.report.draft": _run_report_draft,
    "carbon.fix.suggest": _run_fix_suggest,
    "investigate": _run_investigate,
}


def list_modules(instance_id: str = "carbon") -> dict[str, Any]:
    """Return the modules the in-process engine advertises."""
    return {"modules": [{"type": m} for m in MODULES]}


def dispatch_task(
    task_type: str,
    payload: dict[str, Any],
    *,
    instance_id: str = "carbon",
    timeout: int | None = None,
) -> dict[str, Any]:
    """Dispatch a task in-process.

    Returns a Pulse-shaped result dict::

        {"status": "completed"|"pending"|"failed"|"pulse_unavailable",
         "task_id": str,
         "result": {...} | "error": {"code": str, "message": str}}
    """
    if task_type not in MODULES:
        return {
            "status": "pulse_unavailable",
            "task_id": "",
            "error": {
                "code": "unknown_task",
                "message": f"Unknown task type: {task_type!r}",
            },
        }

    # Phase 2b-1: ``chat`` is wired end-to-end through the turn runner.
    # Fail-visible: any error returns ``pulse_unavailable`` — never a fake
    # answer.
    if task_type == "chat":
        task_id = _new_task_id()
        try:
            return _run_async(_run_chat(instance_id, payload, task_id))
        except Exception as exc:  # noqa: BLE001 - fail-visible contract
            logger.exception("chat dispatch failed for instance=%s", instance_id)
            return {
                "status": "pulse_unavailable",
                "task_id": task_id,
                "error": {
                    "code": "engine_error",
                    "message": f"chat failed: {exc}",
                },
            }

    # Phase 2b-2/2b-3: the KG/analytics and DQ task types are wired
    # in-process.  Every entry in MODULES is covered by ``chat`` above and
    # ``_TASK_HANDLERS`` below, so no ``not_wired`` path remains — a missing
    # handler is a programming error and surfaces fail-visible via
    # ``engine_error``.
    handler = _TASK_HANDLERS.get(task_type)
    task_id = _new_task_id()
    try:
        if handler is None:
            raise LookupError(f"no in-process handler for {task_type!r}")
        return _run_async(handler(instance_id, payload, task_id))
    except Exception as exc:  # noqa: BLE001 - fail-visible contract
        logger.exception("%s dispatch failed for instance=%s", task_type, instance_id)
        return {
            "status": "pulse_unavailable",
            "task_id": task_id,
            "error": {
                "code": "engine_error",
                "message": f"{task_type} failed: {exc}",
            },
        }


def dispatch_task_stream(task_type: str, payload: dict[str, Any], *, instance_id: str = "carbon"):
    """Stream a ``chat`` turn as ``(kind, value)`` tuples from a background thread.

    The engine's turn runner is async and yields text deltas through an async
    ``stream_callback``; this generator bridges that async stream to a sync
    iterator using a ``queue.Queue`` and a daemon thread so Django views can
    consume it inside a ``StreamingHttpResponse`` without blocking the event
    loop.

    Yields:
        ("chunk", delta)  — one text delta (may repeat)
        ("done", result)  — terminal success (same dict shape ``chat()`` reads)
        ("error", message) — terminal failure
    """
    if task_type != "chat":
        yield "error", f"streaming not supported for {task_type!r}"
        return

    q: queue.Queue = queue.Queue()

    async def _collect():
        async def cb(delta: str):
            q.put(("chunk", delta))

        try:
            result = await _run_chat(instance_id, payload, _new_task_id(), stream_callback=cb)
            q.put(("done", result))
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("chat stream failed for instance=%s", instance_id)
            q.put(("error", f"chat failed: {exc}"))
        finally:
            q.put(("eof", None))

    def _thread_target():
        _run_async(_collect())

    threading.Thread(target=_thread_target, daemon=True).start()

    while True:
        kind, value = q.get()
        if kind == "eof":
            break
        yield kind, value


def get_task(task_id: str, *, timeout: int | None = None) -> dict[str, Any]:
    """Retrieve an in-process task's status."""
    return {
        "status": "pulse_unavailable",
        "error": {
            "code": "not_found",
            "message": f"No in-process task with id {task_id!r}",
        },
    }


__all__ = ["MODULES", "list_modules", "dispatch_task", "dispatch_task_stream", "get_task"]
