"""P0-07 — L1 replay/golden fixture loader (QA-FRAMEWORK deliverable #1).

This module is deliberately **pure**: it imports no Django models, opens no DB
connection, and performs no network/LLM calls.  It can be reused by the offline
replay runner (``ai.eval.replay``), by ``pytest``, and by any tooling that just
wants the canonical fixtures.

Two on-disk fixture files back the L1 replay layer:

* ``ai/tests/fixtures/replay/conversations.json`` — 30 real user messages
  (phrasing sourced from ``eval_pulse_behavior.py`` ``SCENARIOS`` and
  ``ai/eval/golden.py`` ``GOLDEN_QUERIES``) with the **expected** salience
  classification.
* ``ai/tests/fixtures/replay/mutations.json`` — 10 mutation attempts
  (indirect phrasing, cross-tenant, self-approval, role-escalation,
  prompt-injection) each carrying an unconfirmed non-GET tool call.

The loader is **fail-closed**: any schema violation — missing/invalid field,
bad enum, empty message, duplicate id, wrong vector — raises ``ValueError``.
It never silently skips an entry.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Locations ──────────────────────────────────────────────────────────────

REPLAY_FIXTURES_DIR: Path = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "replay"
)
CONVERSATIONS_FILE: Path = REPLAY_FIXTURES_DIR / "conversations.json"
MUTATIONS_FILE: Path = REPLAY_FIXTURES_DIR / "mutations.json"

# ── Enums (mirrored from the deterministic spine surfaces) ───────────────────
#
# salience.py / witnesses.SalienceResult — "operational" is part of the
# documented domain enum even though the current regex classifier only emits
# data / conversational / identity / general.
SALIENCE_DOMAINS: frozenset[str] = frozenset(
    {"data", "operational", "conversational", "identity", "general"}
)
# witnesses.SalienceResult.route
SALIENCE_ROUTES: frozenset[str] = frozenset({"fast", "full", "deep"})

# witnesses.CriticVerdict.verdict
CRITIC_VERDICTS: frozenset[str] = frozenset(
    {"pass", "pass_with_flag", "rewrite", "veto", "knowledge_gap"}
)
# critic.py rules-tier flags (documented + emitted by review/_rules_only_verdict)
CRITIC_FLAGS: frozenset[str] = frozenset(
    {
        "ungrounded_claim",
        "cross_tenancy",
        "unconfirmed_mutation",
        "mutation_not_confirmed",
        "dry_run_preview",
        "knowledge_gap",
    }
)

# Neutral mutation vectors the fixture set must cover.
MUTATION_VECTORS: frozenset[str] = frozenset(
    {
        "indirect_phrasing",
        "cross_tenant",
        "self_approval",
        "role_escalation",
        "prompt_injection",
    }
)

# Fixture group labels (eval_pulse_behavior.py groups, MEMORY folds MULTI_TURN).
FIXTURE_GROUPS: frozenset[str] = frozenset(
    {"GROUNDING", "DOMAIN", "TOOL_USE", "MEMORY", "SAFETY", "EDGE"}
)

# HTTP methods a tool call may carry.  ``GET`` is read-only; anything else is a
# state change and must be confirmed (critic.py hard-vetoes the unconfirmed).
HTTP_METHODS: frozenset[str] = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
NON_GET_METHODS: frozenset[str] = HTTP_METHODS - {"GET"}


# ── Validation helpers ──────────────────────────────────────────────────────


def _fail(where: str, message: str) -> None:
    raise ValueError(f"replay fixture schema violation at {where}: {message}")


def _require_non_empty_str(container: dict, key: str, where: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(where, f"'{key}' must be a non-empty string")
    return value


def _require_enum(value: Any, allowed: frozenset[str], field: str, where: str) -> str:
    if value not in allowed:
        _fail(
            where,
            f"'{field}' must be one of {sorted(allowed)} (got {value!r})",
        )
    return value


def _validate_tool_call(tc: Any, where: str) -> None:
    if not isinstance(tc, dict):
        _fail(where, "'draft_tool_calls' entries must be objects")
    method = tc.get("method")
    if not isinstance(method, str) or method.upper() not in HTTP_METHODS:
        _fail(where, f"tool call 'method' must be one of {sorted(HTTP_METHODS)} (got {method!r})")
    if "confirmed" not in tc or not isinstance(tc["confirmed"], bool):
        _fail(where, "tool call must carry a boolean 'confirmed'")
    function = tc.get("function")
    if not isinstance(function, dict):
        _fail(where, "tool call must carry a 'function' object")
    name = function.get("name")
    if not isinstance(name, str) or not name.strip():
        _fail(where, "tool call 'function.name' must be a non-empty string")


def _validate_conversation(entry: Any, where: str, seen_ids: set[str]) -> None:
    if not isinstance(entry, dict):
        _fail(where, "conversation entry must be an object")
    fixture_id = _require_non_empty_str(entry, "id", where)
    if fixture_id in seen_ids:
        _fail(where, f"duplicate fixture id '{fixture_id}'")
    seen_ids.add(fixture_id)

    group = _require_non_empty_str(entry, "group", where)
    _require_enum(group, FIXTURE_GROUPS, "group", where)

    _require_non_empty_str(entry, "instance_id", where)
    _require_non_empty_str(entry, "user_message", where)

    expected = entry.get("expected")
    if not isinstance(expected, dict):
        _fail(where, "'expected' must be an object")
    _require_enum(
        expected.get("salience_domain"), SALIENCE_DOMAINS, "expected.salience_domain", where
    )
    _require_enum(
        expected.get("salience_route"), SALIENCE_ROUTES, "expected.salience_route", where
    )

    if "tool_hint" in expected and expected["tool_hint"] is not None:
        if not isinstance(expected["tool_hint"], str) or not expected["tool_hint"].strip():
            _fail(where, "'expected.tool_hint' must be null or a non-empty string")
    if "outcome" in expected:
        _require_non_empty_str(expected, "outcome", where)


def _validate_mutation(entry: Any, where: str, seen_ids: set[str]) -> None:
    if not isinstance(entry, dict):
        _fail(where, "mutation entry must be an object")
    fixture_id = _require_non_empty_str(entry, "id", where)
    if fixture_id in seen_ids:
        _fail(where, f"duplicate fixture id '{fixture_id}'")
    seen_ids.add(fixture_id)

    group = _require_non_empty_str(entry, "group", where)
    _require_enum(group, FIXTURE_GROUPS, "group", where)

    _require_non_empty_str(entry, "user_message", where)
    _require_enum(entry.get("vector"), MUTATION_VECTORS, "vector", where)

    tool_calls = entry.get("draft_tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        _fail(where, "'draft_tool_calls' must be a non-empty list")
    for index, tool_call in enumerate(tool_calls):
        _validate_tool_call(tool_call, f"{where}.draft_tool_calls[{index}]")

    # Fail-closed: a mutation fixture is only valid if it actually exercises the
    # hard-veto path (≥1 unconfirmed non-GET call).
    has_unconfirmed_non_get = any(
        str(tc["method"]).upper() in NON_GET_METHODS and tc["confirmed"] is False
        for tc in tool_calls
    )
    if not has_unconfirmed_non_get:
        _fail(
            where,
            "mutation must carry at least one non-GET tool call with confirmed=false "
            "(otherwise the rules-tier veto is never exercised)",
        )

    expected = entry.get("expected")
    if not isinstance(expected, dict):
        _fail(where, "'expected' must be an object")
    _require_enum(expected.get("verdict"), CRITIC_VERDICTS, "expected.verdict", where)
    _require_enum(expected.get("flag"), CRITIC_FLAGS, "expected.flag", where)


def validate_replay_fixtures(data: Any) -> dict:
    """Validate an in-memory ``{"conversations": [...], "mutations": [...]}`` payload.

    Pure (no filesystem).  Raises ``ValueError`` on any schema violation.
    Returns a shallow-normalized dict with both lists (never ``None``).
    """
    if not isinstance(data, dict):
        _fail("<root>", "fixture payload must be an object")
    conversations = data.get("conversations")
    mutations = data.get("mutations")
    if not isinstance(conversations, list):
        _fail("<root>", "'conversations' must be a list")
    if not isinstance(mutations, list):
        _fail("<root>", "'mutations' must be a list")

    seen_ids: set[str] = set()
    for index, entry in enumerate(conversations):
        _validate_conversation(entry, f"conversations[{index}]", seen_ids)
    for index, entry in enumerate(mutations):
        _validate_mutation(entry, f"mutations[{index}]", seen_ids)

    return {"conversations": conversations, "mutations": mutations}


# ── Public loader ────────────────────────────────────────────────────────────


def load_replay_fixtures() -> dict:
    """Load + validate the L1 replay fixtures.

    Returns ``{"conversations": [...], "mutations": [...]}``.

    Raises ``ValueError`` on ANY schema violation (missing/invalid field, bad
    enum, empty message, duplicate id, wrong vector).  Never silently skips an
    entry.  Imports no Django models.
    """
    try:
        conversations = json.loads(CONVERSATIONS_FILE.read_text(encoding="utf-8"))
        mutations = json.loads(MUTATIONS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # fail-closed: missing fixtures are an error
        raise ValueError(f"replay fixture files not found: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"replay fixture file is not valid JSON: {exc}") from exc

    return validate_replay_fixtures(
        {"conversations": conversations, "mutations": mutations}
    )
