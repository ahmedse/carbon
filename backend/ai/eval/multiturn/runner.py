"""Multi-turn coherence runner — offline evaluation with scripted stub LLM.

Drives real dispatch_task("chat", ...) calls with:
1. A scripted stub LLM (returns stub_reply per turn)
2. Single-pass spine (AGENT_ORCHESTRATOR_ENABLED=false, KG_MULTI_STEP_ENABLED=false)
3. Accumulated conversation history fed to each turn
4. Per-turn expectation validation (decision, slots, language, coherence)

**Design notes:**
- Django setup happens in `main()` only, not at import time (allows clean reuse).
- The CLI never touches the configured dev database: `main()` creates an
  isolated throwaway test database (Django `setup_databases`, dedicated name
  `test_<DB_NAME>_multiturn`, schema synced from models like pytest
  `--nomigrations`) and tears it down in a `finally` (`--keepdb` keeps it).
- For pytest integration: use @pytest.mark.django_db(transaction=True) on tests
  that call run_script/run_bank.

**Offline limitations (PV2-0B baseline):**
- Fan-out agents + multi-step planning disabled in the engine ``Settings`` via
  ``engine_single_pass()`` (env + ``get_settings.cache_clear()``; PV2-1C —
  before that, ``override_settings`` left both ON)
- Live tools not supported (stub stub_tool_calls only)
- Unauthenticated runs (host_user_id=None; persona for context only), so
  `call_host_api` fails with "requires an authenticated session" in ESS scripts

**Exit codes:**
- 0: All scripts ran without engine error (report-only; expectation failures OK)
- 2: Malformed script (YAML load error, schema violation) or no scripts matched
- 3: At least one script recorded an engine error during turn dispatch, or
  the isolated test database could not be set up / torn down
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch
from uuid import uuid4

import yaml


_SINGLE_PASS_ENV = {
    "AGENT_ORCHESTRATOR_ENABLED": "false",
    "KG_MULTI_STEP_ENABLED": "false",
}


@contextlib.contextmanager
def engine_single_pass():
    """Force the engine's single-pass spine for the duration of a run.

    The engine reads flags from its own pydantic ``Settings`` (env-driven,
    ``get_settings()`` is ``lru_cache``d), which Django ``override_settings``
    never reaches. Set the env vars, drop the cache, and restore both after.
    """
    from ai.engine.core.config import get_settings

    saved = {key: os.environ.get(key) for key in _SINGLE_PASS_ENV}
    os.environ.update(_SINGLE_PASS_ENV)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


# ── Stub LLM fixture ─────────────────────────────────────────────────────


def _make_stub_llm_factory(turns: list[Turn]):
    """Factory that returns a stub LLM client.
    
    Each call returns the next turn's stub_reply.
    """
    turn_index = [0]  # closure mutable counter
    
    def _fake_completion(*args, **kwargs) -> types.SimpleNamespace:
        """Return a deterministic OpenAI-shaped chat completion."""
        
        async def _create(**kw):
            idx = turn_index[0]
            turn_index[0] += 1
            
            if idx < len(turns):
                content = turns[idx].stub_reply
                tool_calls = turns[idx].stub_tool_calls or None
            else:
                content = "End of script."
                tool_calls = None
            
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(
                            content=content,
                            tool_calls=tool_calls,
                        ),
                        finish_reason="stop",
                    )
                ],
                usage=types.SimpleNamespace(
                    prompt_tokens=10,
                    completion_tokens=len(content.split()),
                    total_tokens=10 + len(content.split()),
                ),
            )
        
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=_create)
            )
        )
    
    return _fake_completion


# ── Turn result ──────────────────────────────────────────────────────────


@dataclass
class TurnResult:
    """Result of evaluating one turn."""
    
    user_input: str
    stub_reply: str
    expect: Optional["ExpectationBlock"] = None  # the expectation this turn was validated against
    decision: Optional[str] = None
    llm_calls: Optional[int] = None  # None = unmeasured (before PV2-0A); int = measured
    llm_calls_background: Optional[int] = None  # PV2-2C — auto_memory etc.
    language_detected: str = "en"
    language_ok: bool = True
    reask_violations: list[str] = field(default_factory=list)
    mentions_ok: bool = True
    mentions_missing: list[str] = field(default_factory=list)
    mentions_unwanted: list[str] = field(default_factory=list)
    decision_ok: bool = True
    llm_calls_ok: bool = True
    passed: bool = False
    error: Optional[str] = None
    fail_reasons: list[str] = field(default_factory=list)


# ── Script result ────────────────────────────────────────────────────────


@dataclass
class ScriptResult:
    """Result of evaluating an entire script."""
    
    script_id: str
    turns: list[TurnResult] = field(default_factory=list)
    passed: bool = False
    error: Optional[str] = None
    
    def summary(self) -> dict:
        """Return a summary dict for metrics."""
        return {
            "script_id": self.script_id,
            "turns": len(self.turns),
            "turns_passed": sum(1 for t in self.turns if t.passed),
            "language_failures": sum(1 for t in self.turns if not t.language_ok),
            "reask_violations": sum(len(t.reask_violations) for t in self.turns),
            "decision_failures": sum(1 for t in self.turns if not t.decision_ok),
            "llm_budget_failures": sum(1 for t in self.turns if not t.llm_calls_ok),
            "passed": self.passed,
        }


# ── Bank report ──────────────────────────────────────────────────────────


@dataclass
class BankReport:
    """Aggregated results from running a bank of scripts."""
    
    scripts_run: int = 0
    scripts_passed: int = 0
    total_turns: int = 0
    turns_passed: int = 0
    
    focus_retention: float = 0.0  # turns with mentions_any satisfied ÷ applicable
    slot_carry_over: float = 0.0  # 1 − reask violations ÷ applicable
    language_fidelity: float = 0.0  # language_ok ÷ applicable
    router_agreement: float = 0.0  # decision_ok ÷ applicable
    
    llm_calls_p50: float = 0.0
    llm_calls_max: int = 0
    turns_over_budget: int = 0
    
    per_objective_pass: dict[str, float] = field(default_factory=dict)
    
    scripts: list[ScriptResult] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)  # [{script_id, error}]


# ── Main runner ──────────────────────────────────────────────────────────


def run_script(
    script: "Script",
    *,
    instance_id: str = "nibras",
    stub_llm_turns: Optional[list["Turn"]] = None,
    live: bool = False,
    host_user_id: Optional[int] = None,
) -> ScriptResult:
    """Run a single script: dispatch each turn and validate.
    
    Exceptions from dispatch_task are NOT caught here — they propagate to
    run_bank() for proper error recording and re-raising.
    
    Args:
        script: The Script to run
        instance_id: Instance ID for dispatch (default: nibras)
        stub_llm_turns: Turns for the stub LLM (default: script.turns)
    
    Returns:
        ScriptResult with per-turn evaluations (raises on engine error)
    """
    from ai.context_assembler import render_history_content
    from ai.engine_runtime import dispatch_task
    from django.test import override_settings
    from ai.eval.multiturn.bank import ExpectationBlock, detect_language, reasks_slot
    from ai.store import reset_store
    
    if stub_llm_turns is None:
        stub_llm_turns = script.turns
    
    result = ScriptResult(script_id=script.id)
    conversation_history = {
        "conversation_id": f"conv-{uuid4().hex[:12]}",
        "messages": [],
    }
    
    stub_factory = _make_stub_llm_factory(stub_llm_turns)

    # PV2-0C live tier: real provider (LLM_API_KEY from .env), no stub patch.
    if live:
        llm_ctx = contextlib.nullcontext()
    else:
        llm_ctx = patch("ai.engine.llm.provider.get_llm_client")
    
    with override_settings(AI_STORE_BACKEND="django"), engine_single_pass():
        reset_store()
        
        with llm_ctx as mock_client:
            if mock_client is not None:
                mock_client.return_value = stub_factory()
            
            for turn_idx, turn in enumerate(script.turns):
                # Dispatch the chat turn — do NOT catch exceptions
                dispatch_response = dispatch_task(
                    "chat",
                    {
                        "message": turn.user,
                        "conversation_history": conversation_history,
                        "host_user_id": host_user_id,
                    },
                    instance_id=instance_id,
                )
                
                # Extract the inner result (phase 0A adds turn_decision, llm_calls)
                if dispatch_response.get("status") != "completed":
                    raise ValueError(
                        f"dispatch_task failed: {dispatch_response.get('error', {}).get('message', 'unknown error')}"
                    )
                
                response = dispatch_response.get("result", {})
                
                # Extract result keys (with .get() for 0A optional fields; None = unmeasured)
                reply_content = response.get("content", "")
                turn_decision = response.get("turn_decision") or "unknown"
                llm_calls = response.get("llm_calls")  # None if not measured (pre-PV2-0A)
                llm_calls_background = response.get("llm_calls_background")
                
                # Build turn result
                turn_result = TurnResult(
                    user_input=turn.user,
                    stub_reply=reply_content,
                    expect=turn.expect,
                    decision=turn_decision,
                    llm_calls=llm_calls,
                    llm_calls_background=llm_calls_background,
                    language_detected=detect_language(reply_content),
                )
                
                # Validate against expectations if present
                if turn.expect:
                    exp = turn.expect
                    
                    # Decision check
                    turn_result.decision_ok = turn_decision in exp.decision_in
                    
                    # Language check
                    turn_result.language_ok = (
                        turn_result.language_detected == exp.language or
                        (exp.language == "mixed" and turn_result.language_detected in ["ar", "en", "mixed"])
                    )
                    
                    # Slot re-ask check
                    for slot in exp.must_not_reask_slots:
                        if reasks_slot(reply_content, slot):
                            turn_result.reask_violations.append(slot)
                    
                    # Mentions check
                    mentions_match = False
                    if exp.mentions_any:
                        for mention in exp.mentions_any:
                            if mention.lower() in reply_content.lower():
                                mentions_match = True
                                break
                        turn_result.mentions_ok = mentions_match
                        if not mentions_match:
                            turn_result.mentions_missing = exp.mentions_any
                    
                    if exp.mentions_none:
                        for mention in exp.mentions_none:
                            if mention.lower() in reply_content.lower():
                                turn_result.mentions_unwanted.append(mention)
                        turn_result.mentions_ok = (
                            turn_result.mentions_ok and not turn_result.mentions_unwanted
                        )
                    
                    # LLM budget check (only if llm_calls was measured)
                    if llm_calls is not None:
                        turn_result.llm_calls_ok = llm_calls <= exp.max_llm_calls
                    # else: llm_calls_ok remains True (unmeasured, not counted as over-budget)
                    
                    reasons = turn_result.fail_reasons
                    if not turn_result.decision_ok:
                        reasons.append(f"decision={turn_decision} not in {exp.decision_in}")
                    if not turn_result.language_ok:
                        reasons.append(f"lang={turn_result.language_detected} expected {exp.language}")
                    if turn_result.reask_violations:
                        reasons.append(f"reask={turn_result.reask_violations}")
                    if turn_result.mentions_missing:
                        reasons.append(f"mentions_any missing {turn_result.mentions_missing}")
                    if turn_result.mentions_unwanted:
                        reasons.append(f"mentions_none hit {turn_result.mentions_unwanted}")
                    if not turn_result.llm_calls_ok:
                        reasons.append(f"llm_calls={llm_calls} > {exp.max_llm_calls}")

                    # Overall turn pass
                    turn_result.passed = (
                        turn_result.decision_ok and
                        turn_result.language_ok and
                        len(turn_result.reask_violations) == 0 and
                        turn_result.mentions_ok and
                        turn_result.llm_calls_ok
                    )
                else:
                    # No expectations given; just record the turn
                    turn_result.passed = True
                
                result.turns.append(turn_result)
                
                # Add the assistant reply to history for next turn
                conversation_history["messages"].append(
                    {"role": "user", "content": turn.user}
                )
                # Same history rendering as the host (tool digest replay).
                conversation_history["messages"].append(
                    {
                        "role": "assistant",
                        "content": render_history_content({
                            "role": "assistant",
                            "content": reply_content,
                            "metadata_json": {
                                "tool_digest": response.get("tool_digest") or "",
                            },
                        }),
                    }
                )

        reset_store()
    
    result.passed = all(t.passed for t in result.turns)
    return result


def run_bank(
    scripts: list["Script"],
    strict: bool = False,
    *,
    live: bool = False,
    host_user_id: Optional[int] = None,
) -> BankReport:
    """Run all scripts and aggregate metrics.
    
    Args:
        scripts: List of Script objects to evaluate
        strict: If True, raise exceptions from run_script; if False, record and continue
        live: PV2-0C live tier — real LLM provider instead of the stub
        host_user_id: Django user PK to dispatch as (None = unauthenticated)
    
    Returns:
        BankReport with aggregated metrics
    
    Raises:
        ValueError: If strict=True and any script raises during dispatch
    """
    report = BankReport(scripts_run=len(scripts))
    
    llm_calls_all = []
    
    for script in scripts:
        try:
            script_result = run_script(script, live=live, host_user_id=host_user_id)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            script_result = ScriptResult(script_id=script.id, error=error)
            report.errors.append({"script_id": script.id, "error": error})
            if strict:
                report.scripts.append(script_result)
                raise
        
        report.scripts.append(script_result)
        
        if script_result.error:
            # Script had an engine error; no turns to count
            continue
        
        if script_result.passed:
            report.scripts_passed += 1
        
        report.total_turns += len(script_result.turns)
        report.turns_passed += sum(1 for t in script_result.turns if t.passed)
        
        # Collect LLM calls for percentiles (only measured values, skip None)
        for turn in script_result.turns:
            if turn.llm_calls is not None:
                llm_calls_all.append(turn.llm_calls)
                if turn.llm_calls > report.llm_calls_max:
                    report.llm_calls_max = turn.llm_calls
        
        # Track over-budget turns (only count if llm_calls was measured)
        for turn in script_result.turns:
            if turn.expect and turn.llm_calls is not None and not turn.llm_calls_ok:
                report.turns_over_budget += 1
    
    # Calculate percentiles and aggregates
    if llm_calls_all:
        llm_calls_all.sort()
        report.llm_calls_p50 = llm_calls_all[len(llm_calls_all) // 2]
    
    # Language fidelity (turns with expect + language check)
    language_checks = sum(
        1 for s in report.scripts
        for t in s.turns
        if t.expect and t.expect.language  # has a language expectation
    )
    if language_checks:
        language_ok = sum(
            1 for s in report.scripts
            for t in s.turns
            if t.expect and t.expect.language and t.language_ok
        )
        report.language_fidelity = language_ok / language_checks
    
    # Slot carry-over (1 − reask violations ÷ applicable)
    reask_total = sum(
        len(t.reask_violations) for s in report.scripts
        for t in s.turns
        if t.expect and t.expect.must_not_reask_slots
    )
    reask_applicable = sum(
        1 for s in report.scripts
        for t in s.turns
        if t.expect and t.expect.must_not_reask_slots
    )
    if reask_applicable:
        report.slot_carry_over = 1.0 - (reask_total / reask_applicable)
    
    # Router agreement
    decision_ok = sum(
        1 for s in report.scripts
        for t in s.turns
        if t.expect and t.decision_ok
    )
    decision_applicable = sum(
        1 for s in report.scripts
        for t in s.turns
        if t.expect
    )
    if decision_applicable:
        report.router_agreement = decision_ok / decision_applicable
    
    # Focus retention (turns with mentions_any in expect)
    focus_ok = sum(
        1 for s in report.scripts
        for t in s.turns
        if t.expect and t.expect.mentions_any and t.mentions_ok
    )
    focus_applicable = sum(
        1 for s in report.scripts
        for t in s.turns
        if t.expect and t.expect.mentions_any
    )
    if focus_applicable:
        report.focus_retention = focus_ok / focus_applicable
    
    # Per-objective pass ratios
    objective_counts = {}  # {obj_id: (pass_count, total_count)}
    for script in scripts:
        script_result = next(
            (s for s in report.scripts if s.script_id == script.id), None
        )
        if script_result and not script_result.error:
            obj_pass = sum(1 for t in script_result.turns if t.passed)
            obj_total = len(script_result.turns)
            for obj_id in script.objective_ids:
                if obj_id not in objective_counts:
                    objective_counts[obj_id] = [0, 0]
                objective_counts[obj_id][0] += obj_pass
                objective_counts[obj_id][1] += obj_total
    
    for obj_id, (passed, total) in objective_counts.items():
        if total > 0:
            report.per_objective_pass[obj_id] = passed / total
    
    return report


def metrics_to_json(report: BankReport) -> dict:
    """Convert BankReport to JSON-serializable dict."""
    return {
        "scripts_run": report.scripts_run,
        "scripts_passed": report.scripts_passed,
        "total_turns": report.total_turns,
        "turns_passed": report.turns_passed,
        "focus_retention": round(report.focus_retention, 3),
        "slot_carry_over": round(report.slot_carry_over, 3),
        "language_fidelity": round(report.language_fidelity, 3),
        "router_agreement": round(report.router_agreement, 3),
        "llm_calls_p50": report.llm_calls_p50,
        "llm_calls_max": report.llm_calls_max,
        "turns_over_budget": report.turns_over_budget,
        "per_objective_pass": {
            k: round(v, 3) for k, v in report.per_objective_pass.items()
        },
    }


TIER = "offline_stub"

CAVEATS = [
    "Tier offline_stub: every LLM call returns canned stub_reply text from the "
    "script YAML, so reply-text metrics mostly measure the stub, not the engine.",
    "Engine-attributable in this tier: router_agreement (turn_decision), "
    "llm_calls_p50 / llm_calls_max / turns_over_budget (LLM call counting), and "
    "slot_carry_over only where the engine itself re-asks deterministically "
    "(e.g. a clarify template) instead of passing the stub text through.",
    "Stub-dominated in this tier: focus_retention (mentions_any), mentions_none, "
    "language_fidelity, and per_objective_pass for text-based objectives; treat "
    "them as harness plumbing checks until the live tier (PV2-0C).",
    "KNOWN DEFECT (not fixed in PV2-0B rev3): the stub client advances one "
    "stub_reply per LLM call, not per turn. Turns that make 2-4 LLM calls "
    "consume later turns' stub text, so replies drift out of alignment and, "
    "once the script's stubs are exhausted (often by turn 3), the reply is the "
    "literal fallback 'End of script.'. See turns_detail[].reply.",
    "host_user_id=None: call_host_api fails with 'requires an authenticated "
    "session' in ESS scripts; the live tier (PV2-0C) will pass a real user.",
    "Fan-out agents and multi-step planning are disabled in the engine "
    "Settings (AGENT_ORCHESTRATOR_ENABLED=false, KG_MULTI_STEP_ENABLED=false "
    "set via os.environ + get_settings.cache_clear() since PV2-1C). Django "
    "override_settings does not reach the engine Settings, so the PV2-0B/0C "
    "baselines ran WITH fan-out on (the extra 'fanout' LLM call per turn).",
]


TIER_LIVE = "live_dev"

CAVEATS_LIVE = [
    "Tier live_dev: real LLM provider (LLM_API_KEY) and the configured dev DB, "
    "dispatched as an authenticated employee. Reply-text metrics are "
    "engine-attributable but non-deterministic across runs (LLM variance).",
    "Chat mode only (ADR-0046): host writes are never committed from these "
    "turns; process dials may create Plan/Run rows awaiting consent in the dev DB.",
    "Fan-out agents and multi-step planning are disabled in the engine "
    "Settings (os.environ + get_settings.cache_clear() since PV2-1C). The "
    "PV2-0C live baseline ran WITH fan-out on (override_settings does not "
    "reach the engine Settings) — compare llm_calls against it accordingly.",
]


def report_to_json(
    report: BankReport,
    *,
    database: Optional[str] = None,
    live: bool = False,
    host_user: Optional[str] = None,
) -> dict:
    """Full JSON report: metrics + tier/caveats + errors + per-turn detail."""
    return {
        "tier": TIER_LIVE if live else TIER,
        "caveats": list(CAVEATS_LIVE if live else CAVEATS),
        "host_user": host_user,
        "database": database,
        "errors": list(report.errors),
        **metrics_to_json(report),
        "scripts": [
            {
                **sr.summary(),
                "error": sr.error,
                "turns_detail": [
                    {
                        "turn": i + 1,
                        "decision": t.decision,
                        "llm_calls": t.llm_calls,
                        "llm_calls_background": t.llm_calls_background,
                        "language": t.language_detected,
                        "passed": t.passed,
                        "fail_reasons": t.fail_reasons,
                        "reply": t.stub_reply[:160],
                    }
                    for i, t in enumerate(sr.turns)
                ],
            }
            for sr in report.scripts
        ],
    }


def format_turn_line(script_id: str, turn_no: int, t: TurnResult) -> str:
    status = "pass" if t.passed else "FAIL"
    reasons = f" [{'; '.join(t.fail_reasons)}]" if t.fail_reasons else ""
    return (
        f"    {script_id} turn{turn_no} decision={t.decision} "
        f"llm_calls={t.llm_calls} lang={t.language_detected} {status}{reasons}"
    )


def exit_code_for(report: BankReport) -> int:
    return 3 if report.errors else 0


# ── CLI entry point ──────────────────────────────────────────────────────


class _DisableMigrations:
    """MIGRATION_MODULES value that syncs every app from models (pytest --nomigrations)."""

    def __contains__(self, item: str) -> bool:
        return True

    def __getitem__(self, item: str) -> None:
        return None


@contextlib.contextmanager
def isolated_test_db(*, keepdb: bool = False):
    """Run the body against a throwaway test DB, never the configured dev DB.

    Uses a dedicated TEST NAME so it cannot collide with pytest's reused
    ``test_<DB_NAME>`` database. When ``TEST_DB_NAME`` is set (parallel
    workers), the name is ``<TEST_DB_NAME>_multiturn`` so concurrent runners
    never share (and drop) one database. Yields the test database name.
    """
    from django.conf import settings
    from django.db import connections
    from django.test.utils import (
        setup_databases,
        setup_test_environment,
        teardown_databases,
        teardown_test_environment,
    )

    default = connections["default"].settings_dict
    default.setdefault("TEST", {})
    worker_db = (os.environ.get("TEST_DB_NAME") or "").strip()
    default["TEST"]["NAME"] = (
        f"{worker_db}_multiturn" if worker_db else f"test_{default['NAME']}_multiturn"
    )
    settings.MIGRATION_MODULES = _DisableMigrations()

    setup_test_environment()
    old_config = None
    try:
        old_config = setup_databases(verbosity=0, interactive=False, keepdb=keepdb)
        yield connections["default"].settings_dict["NAME"]
    finally:
        if old_config is not None:
            if not keepdb:
                _terminate_other_sessions()
            teardown_databases(old_config, verbosity=0, keepdb=keepdb)
        teardown_test_environment()


def _terminate_other_sessions() -> None:
    """Drop connections held by engine worker threads so DROP DATABASE succeeds.

    Thread-pool connections (sync_to_async) are not reachable via
    ``connections.close_all()`` from the main thread.
    """
    from django.db import connections

    conn = connections["default"]
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid()"
        )
    connections.close_all()


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point: python -m ai.eval.multiturn.runner --report /tmp/out.json

    Returns the process exit code:
    - 0: all scripts ran without engine error (expectation failures are report-only)
    - 2: malformed script (YAML/schema error) or no scripts matched
    - 3: at least one script recorded an engine error, or the isolated test
      database could not be created / torn down
    """
    import argparse
    from ai.eval.multiturn.bank import load_scripts_from_glob

    parser = argparse.ArgumentParser(
        description="Multi-turn coherence offline runner (PV2-0B)"
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to write metrics JSON",
    )
    parser.add_argument(
        "--scripts",
        default="scripts/*.yaml",
        help="Glob pattern for scripts (relative to backend/ai/eval/multiturn)",
    )
    parser.add_argument(
        "--keepdb",
        action="store_true",
        help="Keep the isolated test database between runs",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print one line per turn: script turn# decision llm_calls lang pass/FAIL [reasons]",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="PV2-0C live tier: call the real LLM provider (LLM_API_KEY) instead of the stub",
    )
    parser.add_argument(
        "--host-user",
        default=None,
        metavar="USERNAME",
        help="Dispatch as this Django user (e.g. emp_1067). Requires --no-isolated-db "
        "because the isolated test DB has no users.",
    )
    parser.add_argument(
        "--no-isolated-db",
        action="store_true",
        help="Run against the configured dev DB instead of a throwaway test DB "
        "(live tier only; writes conversations/ledger rows into the dev DB)",
    )
    args = parser.parse_args(argv)
    if args.host_user and not args.no_isolated_db:
        parser.error("--host-user requires --no-isolated-db (test DB has no users)")

    # Setup Django ONLY in main() — not at import time
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

    base_dir = Path(__file__).parent
    try:
        scripts = load_scripts_from_glob(args.scripts, base_dir)
    except ValueError as e:
        print(f"Malformed script: {e}", file=sys.stderr)
        return 2

    if not scripts:
        print(f"No scripts found matching {args.scripts}", file=sys.stderr)
        return 2

    print(f"Running {len(scripts)} scripts...")

    host_user_id: Optional[int] = None
    if args.host_user:
        from django.contrib.auth import get_user_model

        try:
            host_user_id = get_user_model().objects.get(username=args.host_user).pk
        except Exception as e:  # noqa: BLE001 - surface, never silently run anon
            print(f"Unknown --host-user {args.host_user!r}: {e}", file=sys.stderr)
            return 2

    try:
        if args.no_isolated_db:
            from django.db import connections

            database = connections["default"].settings_dict["NAME"]
            report = run_bank(
                scripts, strict=False, live=args.live, host_user_id=host_user_id,
            )
        else:
            with isolated_test_db(keepdb=args.keepdb) as database:
                report = run_bank(
                    scripts, strict=False, live=args.live, host_user_id=host_user_id,
                )
    except Exception as e:
        print(f"Engine/database error: {type(e).__name__}: {e}", file=sys.stderr)
        return 3

    print()
    print("Script Results:")
    print("-" * 80)
    for sr in report.scripts:
        if sr.error:
            print(f"  ERROR  {sr.script_id}: {sr.error}")
        else:
            status = "PASS" if sr.passed else "FAIL"
            print(f"  {status}  {sr.script_id}")
        if args.verbose:
            for i, t in enumerate(sr.turns):
                print(format_turn_line(sr.script_id, i + 1, t))

    print()
    print("Metrics:")
    print("-" * 80)
    metrics = metrics_to_json(report)
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    report_path = Path(args.report)
    with open(report_path, "w") as f:
        json.dump(
            report_to_json(
                report, database=database, live=args.live, host_user=args.host_user,
            ),
            f, indent=2, ensure_ascii=False,
        )

    print()
    print(f"Metrics written to {report_path}")
    print()

    code = exit_code_for(report)
    if code:
        print(
            f"{len(report.errors)} script(s) recorded engine errors -> exit {code}",
            file=sys.stderr,
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
