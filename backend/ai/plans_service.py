"""
Agentic Task Orchestration — plan lifecycle service (Sprint 23 W3-A).

Wraps the already-built engine machinery (SkillAwarePlanner decompose →
ReActLoop execution → durable Run/RunStep ledger) behind a user-initiated,
reviewable task product:

    brief → pending_approval plan (reviewable) → approve → SSE streamed run
    → per-step consent (confirm/decline) → durable audit ledger.

Design contracts (TASKS.md W3-A — backend):

  * NO changes under ``backend/ai/engine/`` — this module only *calls* the
    engine's public seams (planner, ReActLoop, CarbonHostExecutor, store).
  * Reuses the existing ``Run`` / ``RunStep`` Django models
    (``ai.models.core``) — no new migrations
    (gate: ``makemigrations --check --dry-run`` stays clean).
  * The approved plan is the executed plan: ``run_plan`` rebuilds the ``Plan``
    from ``plan_json`` and drives ReActLoop with ``resume_run_id=plan_id`` so
    the engine reuses the plan's Run row and RunStep rows — never a
    duplicate ledger row.
  * Consent: plan-level approve (RULE_21) + step-level confirm/decline
    reusing ``CarbonHostExecutor.confirm_execution`` / ``.decline_execution``
    (the same seam as the workspace ``tool-executions/confirm|decline``
    endpoints).
  * Outcome copy only (RULE_23): frame types and statuses are product terms
    (``step_start`` / ``step_result`` / ``step_confirm`` / ``done`` …), never
    engine class names.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import queue
import re
import threading
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from ai.instance_registry import resolve_instance_id
from ai import run_machine
from ai import workflow
from ai.models.step_journal import (
    STEP_KIND_ACTIVITY,
    STEP_KIND_WORKFLOW,
    EVENT_STEP_CANCELLED,
    EVENT_STEP_PAUSED,
    EVENT_STEP_RESUMED,
    EVENT_STEP_SKIPPED,
)
from ai.step_journal import (
    StepJournal,
    canonical_step_id,
    EVENT_OUTCOME_UNKNOWN,
    EVENT_STEP_COMPLETED,
    EVENT_STEP_CONSENT_DECLINED,
    EVENT_STEP_CONSENT_GRANTED,
    EVENT_STEP_CONSENT_REQUESTED,
    EVENT_STEP_FAILED,
    EVENT_STEP_QUEUED,
    EVENT_STEP_RETRIED,
    EVENT_STEP_STARTED,
)

logger = logging.getLogger("carbon.ai.plans_service")

# Engine instance namespace (mirrors the chat/action paths).
PLAN_INSTANCE_ID = resolve_instance_id()


def _coerce_plan_json(raw) -> dict:
    """Normalize ``Run.plan_json`` to a dict for Django JSONField reads.

    The engine SQLAlchemy layer stores ``plan_json`` as a JSON *string*
    (``json.dumps(asdict(plan))``). Django's JSONField then surfaces that as
    a Python ``str``, which crashes list/get serialization. Accept dicts,
    JSON strings, and junk → always return a dict.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _plan_instance_config(host_user_id: str | None = None) -> dict:
    """Brand-resolved instance config for plan execution (not hard-coded carbon).

    Plan runs must load the active brand's YAML (e.g. nibras ``entities``) so
    ECF tools like ``resolve_entity`` see registered types. ``_carbon_instance_config``
    always loads carbon, which has no entities — that surfaces as
    ``Entity type 'employee' is not registered for this instance.``
    """
    from ai.engine_runtime import _instance_config

    return _instance_config(PLAN_INSTANCE_ID, host_user_id)


# Run statuses this service owns (superset of the engine's status set).
STATUS_DISCOVERING = "discovering"
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_COMPLETED_WITH_GAPS = "completed_with_gaps"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

# RunStep statuses (engine set: pending|running|awaiting_approval|
# completed|failed|skipped).
STEP_PENDING = "pending"
STEP_AWAITING_APPROVAL = "awaiting_approval"
STEP_RUNNING = "running"
STEP_COMPLETED = "completed"
STEP_FAILED = "failed"
STEP_SKIPPED = "skipped"
# W-7 per-step control: a running step held by ``pause_step``. Not an engine
# status — the host owns this transient state; ``resume_step`` returns the
# step to ``pending`` so the driver re-runs it.
STEP_PAUSED = "paused"

# Terminal step statuses — when every step is in this set the plan status
# must be completed (all success/skipped) or failed (any failed).
_STEP_TERMINAL = frozenset({STEP_COMPLETED, STEP_FAILED, STEP_SKIPPED})

# Run statuses that may be rewritten from step outcomes. Discovery /
# pending_approval / cancelled stay operator-owned and are never clobbered.
_RUN_STATUS_RECONCILEABLE = frozenset({
    STATUS_APPROVED,
    STATUS_RUNNING,
    STATUS_PAUSED,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_GAPS,
    STATUS_FAILED,
})


def _step_is_caught_failure(step) -> bool:
    """True when a failed step was routed through a catch (W-4/W-6)."""
    err = getattr(step, "error", None) or ""
    return isinstance(err, str) and err.startswith("[caught]")


def _derived_status_from_steps(steps):
    """Derive plan status from durable step rows when every step is terminal.

    Returns ``None`` when steps are empty or still in flight (so callers keep
    the stored run status). Any ``awaiting_approval`` → paused; mixed
    completed + caught failures → ``completed_with_gaps``; any uncaught
    ``failed`` → failed; otherwise completed.
    """
    if not steps:
        return None
    statuses = [getattr(s, "status", None) for s in steps]
    if any(st == STEP_AWAITING_APPROVAL for st in statuses):
        return STATUS_PAUSED
    if not all(st in _STEP_TERMINAL for st in statuses):
        return None
    failed = [s for s in steps if getattr(s, "status", None) == STEP_FAILED]
    completed = [s for s in steps if getattr(s, "status", None) == STEP_COMPLETED]
    if failed and completed and all(_step_is_caught_failure(s) for s in failed):
        return STATUS_COMPLETED_WITH_GAPS
    if failed:
        return STATUS_FAILED
    return STATUS_COMPLETED


def _reconcile_run_status_from_steps(run, steps) -> None:
    """Persist plan status from step outcomes when all steps have finished.

    Repairs stuck ``running`` / lagged ``failed`` rows after retries leave
    every step completed, and keeps list/get payloads honest for every plan.

    Also demotes a dishonest ``completed`` / ``completed_with_gaps`` when any
    step is still open (Pending under Completed — never leave that lie).
    """
    if run is None:
        return
    if run.status not in _RUN_STATUS_RECONCILEABLE:
        return
    derived = _derived_status_from_steps(steps)

    # Honesty demote: engine finalized completed while steps stayed pending.
    if (
        run.status in (STATUS_COMPLETED, STATUS_COMPLETED_WITH_GAPS)
        and derived is None
        and steps
    ):
        statuses = [getattr(s, "status", None) for s in steps]
        if any(st == STEP_AWAITING_APPROVAL for st in statuses):
            derived = STATUS_PAUSED
        elif any(st not in _STEP_TERMINAL for st in statuses):
            derived = STATUS_FAILED
            if not (run.final_response or "").strip():
                open_n = sum(1 for st in statuses if st not in _STEP_TERMINAL)
                run.final_response = (
                    "Run ended before steps finished "
                    f"({open_n} still open). Re-approve to retry."
                )[:2000]
                run.save(update_fields=["final_response", "updated_at"])

    if derived is None or derived == run.status:
        return
    fields = ["status", "updated_at"]
    run.status = derived
    if derived in (
        STATUS_COMPLETED, STATUS_COMPLETED_WITH_GAPS, STATUS_FAILED,
    ) and not run.completed_at:
        run.completed_at = timezone.now()
        fields.append("completed_at")
    run.save(update_fields=fields)
    logger.info(
        "reconciled plan status id=%s → %s from %d finished step(s)",
        run.id, derived, len(steps),
    )
    if derived in (
        STATUS_COMPLETED, STATUS_COMPLETED_WITH_GAPS, STATUS_FAILED,
    ):
        try:
            from ai.ops_canvas import sync_agent_job_map_from_run
            sync_agent_job_map_from_run(run)
        except Exception:  # noqa: BLE001
            logger.debug("ops_canvas reconcile sync failed", exc_info=True)


# Serialized step runnable-state enum (F-28) — the product-level lock/edit
# contract the frontend consumes. Derived from ``RunStep.status`` so the UI
# never has to guess from engine status strings.
RUNNABLE_COMPLETED = "completed"
RUNNABLE_IN_FLIGHT = "in_flight"
RUNNABLE_PENDING = "pending"

_RUNNABLE_STATE_BY_STATUS = {
    STEP_COMPLETED: RUNNABLE_COMPLETED,
    STEP_SKIPPED: RUNNABLE_COMPLETED,
    STEP_RUNNING: RUNNABLE_IN_FLIGHT,
    STEP_PAUSED: RUNNABLE_IN_FLIGHT,
    STEP_PENDING: RUNNABLE_PENDING,
    STEP_AWAITING_APPROVAL: RUNNABLE_PENDING,
}

# Cron day-of-week names, indexed 0-6 (Sunday-first; cron 7 == Sunday).
_CRON_WEEKDAY_NAMES = (
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
)

# Statuses from which a plan may (re)enter execution.
_RUNNABLE_STATUSES = {STATUS_APPROVED, STATUS_PAUSED}

# P3-11 — human-readable copy for the two run-lifecycle actions. These are the
# distinct outcome messages the frontend (P3-05c) surfaces: ``cancel`` stops
# work; ``compensate`` reverses prior effects and needs its own approval.
CANCEL_MESSAGE = "cancel stops the run; no further work will start"
COMPENSATE_MESSAGE = "compensate reverses prior effects and requires separate approval"


def _runnable_state(status: str) -> str:
    """Map a ``RunStep.status`` to the serialized ``runnable_state`` enum.

    Terminal non-success statuses (``failed``) and any unknown status fall
    back to ``completed`` (locked) — they are never editable in place and
    still carry their raw ``status`` for the UI chip / retry affordance.
    """
    return _RUNNABLE_STATE_BY_STATUS.get(status, RUNNABLE_COMPLETED)


def _step_execution_fields(step_phase, step_index, status):
    """Serialized execution-contract fields for one step (F-26 / F-28).

    ``strategy`` is the enclosing phase's strategy (propagated from the phase,
    default ``sequential``). ``parallel_group`` is a stable key shared by
    sibling steps in the same parallel phase; it is OMITTED for sequential
    steps (never emitted as ``null``) so the frontend keys on its presence.
    ``runnable_state`` is the product enum the UI locks/edits on, derived from
    the RunStep status.
    """
    strategy, phase_id = step_phase.get(step_index, ("sequential", None))
    fields = {
        "strategy": strategy,
        "runnable_state": _runnable_state(status),
    }
    if strategy == "parallel":
        fields["parallel_group"] = phase_id
    return fields


def _prior_run_receipt(run) -> dict | None:
    """Track D — Rerun receipt: prior Answer vs current (when both exist)."""
    notes = run.working_notes if isinstance(run.working_notes, dict) else {}
    prior = notes.get("prior_run")
    if not isinstance(prior, dict):
        return None
    prior_text = (prior.get("final_response") or "").strip()
    if not prior_text:
        return None
    current = (run.final_response or "").strip()
    receipt = {
        "prior_status": prior.get("status"),
        "prior_completed_at": prior.get("completed_at"),
        "prior_step_count": prior.get("step_count"),
        "prior_final_response": prior_text,
    }
    if not current:
        receipt["comparison"] = "pending"
        return receipt
    if current == prior_text:
        receipt["comparison"] = "unchanged"
    else:
        receipt["comparison"] = "changed"
    return receipt


def _display_timezone():
    """Resolve the admin-configurable display timezone for human-facing times.

    Reads ``accounts.GeneralConfig.timezone`` (default ``Africa/Cairo``) at
    call time so schedule previews and other render paths honor the value an
    admin sets in Django admin — without a redeploy. Falls back to Django's
    default timezone when the config or zone is unavailable.
    """
    try:
        from accounts.models import GeneralConfig
        return GeneralConfig.get_timezone()
    except Exception:  # noqa: BLE001 - pre-migration / import failure
        return timezone.get_default_timezone()

# Bounded, deterministic retry policy for transient tool failures (Gap #2).
# A failed step is re-queued (pending) and the loop re-entered with a fixed
# exponential backoff schedule — no jitter, so replays stay reproducible.
# Retries never bypass a consent gate: if any step is awaiting approval the
# run pauses for review instead of retrying (RULE_21).
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_MAX_DELAY_SECONDS = 8.0

# Lifecycle states whose transition is journaled as a step event (P3-07b).
# ``ready``/``planned``/``cancelled``/``awaiting_reconciliation`` are not
# journaled here: ``planned`` is emitted by ``begin_step`` (``step_queued``),
# ``cancelled`` by ``decline_step`` (``step_consent_declined``), and
# ``awaiting_reconciliation`` rides the ``outcome_unknown`` event emitted by
# ``reconcile_outcome``.
_ADVANCE_EVENT_BY_STATE = {
    run_machine.RUN_EXECUTING: EVENT_STEP_STARTED,
    run_machine.RUN_SUCCEEDED: EVENT_STEP_COMPLETED,
    run_machine.RUN_FAILED: EVENT_STEP_FAILED,
    run_machine.RUN_AWAITING_APPROVAL: EVENT_STEP_CONSENT_REQUESTED,
}


def _replay_result(action: str, recon: dict) -> dict:
    """Shape the replay decision response (RULE_23 outcome terms only)."""
    return {
        "action": action,
        "step_state": recon["step_state"],
        "status": recon["status"],
        "retry_count": recon["retry_count"],
        "outcome": recon["outcome"],
        "consent": recon["consent"],
        "committed": recon["committed"],
    }


def _restore_step_from_recon(step, recon: dict) -> None:
    """Realign a step row with its journal-reconstructed state (replay).

    Direct restoration, not a state-machine transition: replay is an explicit
    operator action that recovers a crashed/stale row from its append-only
    journal (the single source of truth).  Only fields that differ are
    written.
    """
    fields = ["updated_at"]
    if step.step_state != recon["step_state"]:
        step.step_state = recon["step_state"]
        fields.append("step_state")
    if step.status != recon["status"]:
        step.status = recon["status"]
        fields.append("status")
    if step.retry_count != recon["retry_count"]:
        step.retry_count = recon["retry_count"]
        fields.append("retry_count")
    if step.outcome != recon["outcome"]:
        step.outcome = recon["outcome"]
        fields.append("outcome")
    step.save(update_fields=fields)


def _retry_activity_step(run, step) -> None:
    """Retry a failed activity (bounded RETRY_*) and journal ``step_retried``."""
    step.retry_count = (step.retry_count or 0) + 1
    step.status = STEP_PENDING
    step.error = None
    step.save(update_fields=["status", "error", "retry_count", "updated_at"])
    StepJournal.append(
        run.id, canonical_step_id(step), EVENT_STEP_RETRIED,
        payload={"attempt": step.retry_count},
    )


class PlanNotAccessibleError(Exception):
    """Raised when the plan does not belong to the requesting user."""


class PlanForbiddenError(Exception):
    """Raised when the plan exists but belongs to a different user.

    Distinguishes an authenticated outsider (HTTP 403) from a missing plan
    (HTTP 404, ``PlanNotAccessibleError``) on the QoS/supervision endpoints
    (Phase 25-C, spec §4).
    """


class PlanNotRunnableError(Exception):
    """Raised when a plan cannot be executed in its current state."""


class PlanStepError(Exception):
    """Raised for step-level consent errors (missing/not pending/not owned)."""


def _run_async(coro):
    """Bridge an async engine call into the sync Django view context.

    Mirrors ``ai.engine_runtime._run_async`` — the engine is async, so we
    bridge with ``asyncio.run`` (or a worker thread when a loop is already
    running, e.g. inside pytest-asyncio).
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _parse_tool_output_json(tool_output_json):
    """Normalize a ``RunStep.tool_output_json`` value to a dict.

    The live engine path persists this field as a JSON string (the engine's
    SQLAlchemy ``RunStep`` maps it to a ``Text`` column), while the
    deterministic seam and Django ORM writes store a native dict. The consent
    endpoints must accept both shapes.
    """
    if not tool_output_json:
        return {}
    if isinstance(tool_output_json, dict):
        return tool_output_json
    if isinstance(tool_output_json, str):
        try:
            parsed = json.loads(tool_output_json)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _lifecycle_scope(user):
    """Build the host scope for a run-lifecycle action (P3-11).

    The caller is the authenticated owner; the boundary's ScopeGuard +
    AccessGuard still validate the scope shape, but ownership of the run is
    enforced separately by ``PlansService._get_owned_run`` (CBAC).
    """
    from ai.protocol import Scope

    return Scope(
        user_identifier=str(user.pk),
        org_unit_ids=["*"],
        module_ids=["*"],
        is_superuser=bool(getattr(user, "is_superuser", False)),
    )


def _lifecycle_command(user, run, action: str):
    """Build a fail-closed boundary ``Command`` for ``cancel``/``compensate``.

    The idempotency key binds the action to the exact run (``action:run_id``)
    so a ``cancel`` and a ``compensate`` can never alias the same effect slot.
    ``compensate`` carries ``requires_grant=True`` + its own capability; the
    human's explicit endpoint call is the confirmation token (there is no
    AI-initiated staged mutation to auto-confirm — RULE_21).
    """
    from ai.command_boundary import Command

    is_compensate = action == "compensate"
    return Command(
        principal=str(user.pk),
        scope=_lifecycle_scope(user),
        action=action,
        tool=action,
        objects=[str(run.id)],
        params={},
        requires_confirmation=is_compensate,
        confirmation_token=(
            f"human:{user.pk}:{run.id}" if is_compensate else None
        ),
        requires_grant=is_compensate,
        capability=("run.compensate" if is_compensate else "run.cancel"),
        object_id=str(run.id),
        object_type="plan",
        idempotency_key=f"{action}:{run.id}",
        autonomy="human_only",
    )


def _lifecycle_boundary(action: str, *, executor):
    """Assemble the command boundary for a run-lifecycle action (P3-11).

    Uses the real PDP (default-deny) and the real ``resolve_grant`` so the
    grant stage (stage 8) is exercised for ``compensate``. The catalog
    declaration mirrors ``command_boundary_factory``: ``compensate`` is the
    only entry that requires a grant.
    """
    from ai.command_boundary import CommandBoundary
    from ai.grant import resolve_grant
    from ai.pdp import PDP

    requires_grant = action == "compensate"
    capability = "run.compensate" if requires_grant else "run.cancel"
    return CommandBoundary(
        pdp=PDP(),
        executor=executor,
        tool_catalog={
            action: {
                "requires_grant": requires_grant,
                "required_capability": capability,
            }
        },
        grant_resolver=resolve_grant,
    )


# The plan Run id for the currently-executing step (set by the Django-side
# orchestrator before driving the engine, cleared after). The engine's frozen
# ``ToolContext`` does not carry ``run_id``, so export-style plugins read this
# thread-local to resolve the owning plan without touching ``backend/ai/engine/``.
_PLAN_RUN_CONTEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "plans_service_plan_run_id", default=None
)


def set_current_plan_run(run_id: str | None) -> None:
    _PLAN_RUN_CONTEXT.set(run_id)


def get_current_plan_run() -> str | None:
    return _PLAN_RUN_CONTEXT.get()


# The plan step index currently executing (set by ReActLoop around each step's
# tool dispatch, cleared after). export_document-style plugins read this via
# ``resolve_export_step_index`` so multi-step runs — including parallel waves —
# attribute artifacts to the step that ACTUALLY ran, not a heuristic.
_PLAN_STEP_CONTEXT: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "plans_service_plan_step_index", default=None
)


def set_current_step_index(step_index: int | None) -> None:
    _PLAN_STEP_CONTEXT.set(step_index)


def get_current_step_index() -> int | None:
    return _PLAN_STEP_CONTEXT.get()


def _artifact_download_url(run_id, artifact_id) -> str:
    """Public download URL for a stored plan artifact (W5-C).

    Uses the configured API prefix so the link matches the plans API mount.
    """
    prefix = getattr(settings, "API_PREFIX", "/api/v1/").rstrip("/")
    return f"{prefix}/ai/plans/{run_id}/artifacts/{artifact_id}/download/"


def _infer_output_type(tool_output_json):
    """Infer the renderer type for a step's tool output (W5-C B4).

    Outcome-shape driven so the frontend can pick a semantic renderer:
    ``text`` (prose), ``table`` (rows/columns), ``chart`` (series), ``artifact``
    (files), ``json`` (structured fallback). Returns ``None`` when there is no
    output yet.
    """
    data = _parse_tool_output_json(tool_output_json)
    if not data:
        return None
    # An explicit hint always wins (tool or service may already say the kind).
    hint = (
        data.get("_output_type")
        or data.get("output_type")
        or data.get("type")
        or data.get("render")
    )
    if hint in ("text", "table", "chart", "artifact", "json"):
        return hint
    # Artifact-shaped: any file/download marker in the payload.
    if any(
        k in data
        for k in (
            "artifact",
            "artifacts",
            "file",
            "files",
            "file_path",
            "download_url",
            "path",
            "filename",
        )
    ):
        return "artifact"

    # Prefer unwrapped sandbox / host payloads (stringified ``result``).
    result = data.get("result", data)
    if isinstance(result, str):
        stripped = result.strip()
        if stripped and stripped[0] in "{[":
            try:
                result = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                return "text"
        else:
            return "text"
    if isinstance(result, dict):
        if result.get("image_b64") or (
            isinstance(result.get("image"), dict) and result["image"].get("present")
        ):
            return "chart"
        if result.get("table_rows") or (
            isinstance(result.get("headers"), list) and isinstance(result.get("rows"), list)
        ):
            return "table"
        if any(k in result for k in ("series", "labels", "values", "x", "y")):
            return "chart"
        if any(k in result for k in ("columns", "headers", "rows", "breakdown")):
            return "table"
        return "json"
    if isinstance(result, list):
        if not result:
            return "json"
        if all(isinstance(r, dict) for r in result):
            return "table"
        if all(isinstance(r, (int, float)) for r in result):
            return "chart"
        return "json"
    return "json"


_BLOB_KEY_RE = re.compile(r"(_b64|base64|binary)$", re.IGNORECASE)
_MAX_UI_STRING = 240


def _looks_base64_blob(value: str) -> bool:
    if not isinstance(value, str) or len(value) < 120:
        return False
    sample = value[:200].replace("\n", "").replace(" ", "")
    if sample.startswith("data:image"):
        return True
    # Long mostly-base64 alphabet strings (PNG charts, etc.)
    import string as _string
    allowed = set(_string.ascii_letters + _string.digits + "+/=")
    if sum(1 for ch in sample if ch in allowed) / max(len(sample), 1) > 0.95:
        return True
    return False


def _sanitize_ui_value(value, *, key: str = ""):
    """Redact binary / huge strings for product-facing tool_output (RULE_23)."""
    if isinstance(value, str):
        if _BLOB_KEY_RE.search(key or "") or _looks_base64_blob(value):
            return {"present": True, "bytes_est": max(0, (len(value) * 3) // 4)}
        if len(value) > _MAX_UI_STRING:
            return value[:_MAX_UI_STRING - 1] + "…"
        return value
    if isinstance(value, list):
        # Cap list length for UI; keep first rows for tables.
        capped = value[:60]
        return [_sanitize_ui_value(v, key=key) for v in capped]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            sk = str(k)
            if sk in ("image_b64",) or _BLOB_KEY_RE.search(sk):
                if isinstance(v, str) and v:
                    out["image"] = {
                        "present": True,
                        "bytes_est": max(0, (len(v) * 3) // 4),
                    }
                elif isinstance(v, dict):
                    out[sk] = _sanitize_ui_value(v, key=sk)
                else:
                    out[sk] = {"present": bool(v)}
                continue
            out[sk] = _sanitize_ui_value(v, key=sk)
        return out
    return value


def _ui_tool_output(tool_output_json):
    """Product-facing tool_output: shaped + redacted (DB row stays raw).

    - Parses stringified ``result`` when it is sandbox/API JSON
    - Replaces ``image_b64`` with ``{present, bytes_est}``
    - Truncates huge strings
    - Sets ``_output_type`` for the FE renderer
    """
    data = _parse_tool_output_json(tool_output_json)
    if not data:
        return tool_output_json

    shaped = dict(data)
    raw_result = shaped.get("result")
    if isinstance(raw_result, str):
        stripped = raw_result.strip()
        if stripped and stripped[0] in "{[":
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, dict):
                # Promote sandbox keys for typed rendering; keep a short result note.
                for k in ("image_b64", "table_rows", "stdout", "error", "headers", "rows", "breakdown"):
                    if k in parsed and k not in shaped:
                        shaped[k] = parsed[k]
                summary = parsed.get("summary") or parsed.get("message")
                if isinstance(summary, str) and summary.strip():
                    shaped["result"] = summary.strip()[:_MAX_UI_STRING]
                else:
                    shaped.pop("result", None)
            elif isinstance(parsed, list):
                shaped["table_rows"] = parsed
                shaped.pop("result", None)
            else:
                shaped["result"] = _sanitize_ui_value(raw_result, key="result")
        else:
            shaped["result"] = _sanitize_ui_value(raw_result, key="result")

    shaped = _sanitize_ui_value(shaped)
    if isinstance(shaped, dict):
        shaped = dict(shaped)
        shaped["_output_type"] = _infer_output_type(shaped)
    return shaped


def _with_output_type(tool_output_json):
    """Return the UI-safe tool output with ``_output_type`` injected (W5-C B4).

    Prefer ``_ui_tool_output`` so product surfaces never receive raw base64.
    """
    return _ui_tool_output(tool_output_json)


def _step_tool_output_fields(tool_output_json):
    """Return ``(ui_tool_output, output_type)`` for plan/SSE step payloads."""
    ui = _with_output_type(tool_output_json)
    if isinstance(ui, dict):
        return ui, ui.get("_output_type") or _infer_output_type(ui)
    return ui, _infer_output_type(tool_output_json)

class PlansService:
    """Plan lifecycle: create → review → approve → run → consent → ledger."""

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _get_owned_run(user, plan_id):
        """Fetch a plan row scoped to the requesting user (CBAC)."""
        from ai.models.core import Run

        try:
            run = Run.objects.get(id=plan_id, host_user_id=str(user.pk))
        except Run.DoesNotExist:
            raise PlanNotAccessibleError(f"Plan {plan_id} not found.")
        return run

    @staticmethod
    def _resolve_plan_access(user, plan_id):
        """Fetch a plan distinguishing missing (404) from outsider (403).

        QoS/supervision endpoints must tell an authenticated outsider apart
        from a genuinely missing plan (spec §4): the plan row is resolved
        first (missing → ``PlanNotAccessibleError``), then ownership is
        checked (outsider → ``PlanForbiddenError``).
        """
        from ai.models.core import Run

        try:
            run = Run.objects.get(id=plan_id)
        except (Run.DoesNotExist, ValueError, TypeError):
            raise PlanNotAccessibleError(f"Plan {plan_id} not found.")
        if str(run.host_user_id) != str(user.pk):
            raise PlanForbiddenError(
                f"You do not have access to plan {plan_id}."
            )
        return run

    @staticmethod
    def _get_owned_step(run, step_id):
        from ai.models.core import RunStep

        try:
            step = RunStep.objects.get(
                run_id=run.id, step_index=int(step_id)
            )
        except (RunStep.DoesNotExist, ValueError, TypeError):
            raise PlanStepError(f"Step {step_id} not found on plan {run.id}.")
        return step

    # ── P3-07a durable run machine ───────────────────────────────────────

    @staticmethod
    def begin_step(
        run,
        step_id,
        *,
        step_index=None,
        intent="",
        tool_name=None,
        tool_args_json=None,
        depends_on_json=None,
        idempotency_key="",
    ):
        """Idempotently materialize a step row keyed on ``(run_id, step_id)``.

        The idempotency key is ``(instance, step)`` = ``(run.id, step_id)``:
        two calls with the same pair return the SAME row — no duplicate step,
        no effect re-run (P3-07a). New rows start in ``planned``.
        """
        from ai.models.core import RunStep

        if step_index is None:
            step_index = int(step_id) if str(step_id).isdigit() else 0
        step, created = RunStep.objects.get_or_create(
            run_id=run.id,
            step_id=str(step_id),
            defaults={
                "step_index": step_index,
                "intent": intent or "",
                "tool_name": tool_name or "",
                "tool_args_json": tool_args_json,
                "depends_on_json": depends_on_json,
                "status": STEP_PENDING,
                "step_state": run_machine.RUN_PLANNED,
                "idempotency_key": idempotency_key or "",
            },
        )
        if created:
            StepJournal.append(
                run.id,
                canonical_step_id(step),
                EVENT_STEP_QUEUED,
                payload={"step_index": step_index},
            )
        return step, created

    @staticmethod
    def advance_step(step, new_state, *, outcome="", error="", kind="step"):
        """Advance a step's durable state via the closed transition table.

        Rejects any edge not in ``STEP_TRANSITIONS`` (e.g. ``succeeded →
        executing``) with :class:`ai.run_machine.InvalidStateTransition`.
        """
        fields = ["step_state", "updated_at"]
        run_machine.transition(step, new_state, kind=kind, field="step_state")
        if outcome:
            step.outcome = outcome
            fields.append("outcome")
        if error:
            step.last_error = error
            fields.append("last_error")
        step.save(update_fields=fields)

        # Journal the lifecycle event (P3-07b).  Only transitions in the
        # closed map are journaled; ``step_queued`` is emitted by begin_step,
        # consent/cancel events by their own seams.
        event_type = _ADVANCE_EVENT_BY_STATE.get(new_state)
        if event_type:
            StepJournal.append(
                step.run_id,
                canonical_step_id(step),
                event_type,
                payload={"outcome": outcome} if outcome else {},
            )
        # ADR-0041 — keep Agent Job Map live_run in sync with execution.
        try:
            from ai.ops_canvas import sync_agent_job_map_from_run
            from ai.models.core import Run

            run = Run.objects.filter(id=step.run_id).first()
            if run is not None:
                sync_agent_job_map_from_run(run)
        except Exception:  # noqa: BLE001
            logger.debug("ops_canvas step sync failed", exc_info=True)
        return step

    @staticmethod
    def reconcile_outcome(step, op_id=""):
        """Route an inconclusive read-back to ``awaiting_reconciliation``.

        ``executing → outcome_unknown → awaiting_reconciliation`` (two legal
        edges). Idempotent: an already-reconciled or terminal step is a no-op.
        The reconciliation worker itself is P3-08 (separate).

        ``op_id`` is the downstream effect's **operation id**, persisted here at
        effect-dispatch time so the reconciliation worker can perform its
        authoritative read-back by operation id (P3-08).
        """
        # Persist the operation id at dispatch time regardless of the routing
        # branch — it is the reconciliation worker's only read-back key.
        if op_id:
            step.operation_id = str(op_id)

        if step.step_state in {
            run_machine.RUN_AWAITING_RECONCILIATION,
            run_machine.RUN_SUCCEEDED,
            run_machine.RUN_FAILED,
            run_machine.RUN_CANCELLED,
        }:
            step.save(update_fields=["operation_id", "updated_at"])
            return step
        if step.step_state != run_machine.RUN_OUTCOME_UNKNOWN:
            run_machine.transition(
                step, run_machine.RUN_OUTCOME_UNKNOWN, kind="step", field="step_state"
            )
            step.outcome = "outcome_unknown"
        run_machine.transition(
            step,
            run_machine.RUN_AWAITING_RECONCILIATION,
            kind="step",
            field="step_state",
        )
        StepJournal.append(
            step.run_id,
            canonical_step_id(step),
            EVENT_OUTCOME_UNKNOWN,
            payload={"operation_id": str(op_id)} if op_id else {},
        )
        step.save(
            update_fields=["step_state", "outcome", "operation_id", "updated_at"]
        )
        return step

    # ── P3-07b workflow/activity split + replay ─────────────────────────

    @staticmethod
    def is_activity(step) -> bool:
        """True when ``step`` is a side-effecting activity (LLM/host call).

        Workflow steps are pure deterministic orchestration (sequencing /
        phase / consent routing) and replay with no side effects.  The
        classification reads the explicit ``step_kind`` marker when present;
        otherwise it falls back to ``tool_name`` presence (a tool-bearing step
        is always an activity).  The default ``step_kind`` is ``activity``, so
        an unmarked step fails safe toward "retry, don't skip".
        """
        kind = getattr(step, "step_kind", "") or ""
        if kind == STEP_KIND_WORKFLOW:
            return False
        if kind == STEP_KIND_ACTIVITY:
            return True
        return bool(getattr(step, "tool_name", ""))

    @staticmethod
    def replay_step(run, step) -> dict:
        """Deterministically replay a step from its append-only journal.

        The journal — not ``RunStep.status`` — is the source of truth.  The
        pure fold in :class:`ai.step_journal.StepJournal` reconstructs exactly
        one state; the step row is restored to that state and a replay
        *decision* is returned (RULE_23 terms):

        * ``noop``    — terminal *committed* journal event
                        (``step_completed`` / ``step_consent_declined``); the
                        step must NEVER be re-executed (exactly-one-effect).
        * ``requeue`` — pure workflow step; deterministic, safe to re-run.
        * ``resume``  — interrupted activity; resume from the reconstructed
                        ``step_state``.

        Idempotent: restoring to the same state is a no-op write, so replaying
        twice yields the same decision and reconstructed state.
        """
        entries = StepJournal.for_step(run.id, canonical_step_id(step))
        if not entries:
            # No journal yet (legacy/materialized step): nothing committed.
            recon = {
                "step_state": step.step_state,
                "status": step.status,
                "retry_count": step.retry_count,
                "outcome": step.outcome,
                "consent": None,
                "committed": False,
            }
            action = "requeue" if not PlansService.is_activity(step) else "resume"
            return _replay_result(action, recon)

        recon = StepJournal.reconstruct(entries)
        _restore_step_from_recon(step, recon)

        if recon["committed"]:
            action = "noop"
        elif not PlansService.is_activity(step):
            action = "requeue"
        else:
            action = "resume"
        return _replay_result(action, recon)

    # ── P3-07b deterministic activity dispatch + restart-mid-run resume ────

    @staticmethod
    def _ensure_operation_id(run, step) -> str:
        """Return the activity's stable operation id, persisting it once.

        ``operation_id`` is the downstream effect's read-back key (P3-08) and
        MUST be stable across retries and restarts so re-dispatch is
        idempotent.  When absent it is derived deterministically from
        ``(run, step)`` (no randomness — replay-safe) and persisted on the
        ``RunStep`` row.
        """
        op = str(getattr(step, "operation_id", "") or "").strip()
        if not op:
            op = f"op-{run.id}-{canonical_step_id(step)}"
            step.operation_id = op
            step.save(update_fields=["operation_id", "updated_at"])
        return op

    @staticmethod
    def _invoke_effect(effect_fn, operation_id, attempt) -> dict:
        """Call the activity effect and normalize its result to a status dict.

        ``effect_fn(operation_id=..., attempt=...)`` may return a dict with a
        ``status`` key (``succeeded``/``failed``/``outcome_unknown``) plus
        optional ``result``/``error``; anything else is treated as success.
        A raised exception is a transient ``failed``.
        """
        try:
            result = effect_fn(operation_id=operation_id, attempt=attempt)
        except Exception as exc:  # noqa: BLE001 - transient failure is recoverable
            return {"status": workflow.STATUS_FAILED, "error": str(exc)}
        if isinstance(result, dict):
            return result
        return {"status": workflow.STATUS_SUCCEEDED, "result": result}

    def dispatch_activity(
        self,
        run,
        step,
        effect_fn,
        *,
        activity_kind=None,
        canonical_inputs=None,
        sleep=None,
    ):
        """Execute one activity (LLM/host call) with the bounded retry policy.

        This is the single place an *effect* is dispatched on the deterministic
        workflow path.  It writes a ``dispatched`` journal entry BEFORE the
        effect and a ``succeeded``/``failed``/``outcome_unknown`` entry AFTER,
        so the run journal is always replayable and a restart can resume
        mid-run.

        Retry policy (REUSED, not re-implemented):
          * a transient ``failed`` re-queues (``planned``) up to
            ``RETRY_MAX_ATTEMPTS`` total dispatches — ``_retry_backoff_delay``
            paces each retry, ``_mark_run_paused`` marks the run paused, and
            ``_append_retry_audit`` records durable provenance;
          * ``outcome_unknown`` is NEVER blind-retried — it routes to
            reconciliation via ``reconcile_outcome(op_id=...)`` (P3-08).

        ``sleep`` is injectable for tests (default ``time.sleep``).  Time does
        not affect the result — ordering is sequence-based, not time-based.
        """
        import time as _time

        sleep = sleep if sleep is not None else _time.sleep
        journal = workflow.RunJournal(str(run.id))

        # Consent gate — never auto-approve (RULE_21).
        if step.step_state == run_machine.RUN_AWAITING_APPROVAL:
            return workflow.STATUS_PLANNED

        # Idempotent: a committed activity is never re-dispatched.
        if step.step_state in {run_machine.RUN_SUCCEEDED, run_machine.RUN_CANCELLED}:
            return (
                workflow.STATUS_SUCCEEDED
                if step.step_state == run_machine.RUN_SUCCEEDED
                else workflow.STATUS_SKIPPED
            )
        if step.step_state == run_machine.RUN_AWAITING_RECONCILIATION:
            return workflow.STATUS_OUTCOME_UNKNOWN

        spec = workflow.ActivitySpec.from_step(step)
        if activity_kind is not None:
            spec = workflow.ActivitySpec(
                step_id=spec.step_id,
                step_index=spec.step_index,
                activity_kind=activity_kind,
                depends_on=spec.depends_on,
                tool_name=spec.tool_name,
            )

        operation_id = self._ensure_operation_id(run, step)

        # Advance the durable step to ``executing`` (planned → ready → executing).
        if step.step_state == run_machine.RUN_PLANNED:
            PlansService.advance_step(step, run_machine.RUN_READY)
            PlansService.advance_step(step, run_machine.RUN_EXECUTING)
        elif step.step_state == run_machine.RUN_READY:
            PlansService.advance_step(step, run_machine.RUN_EXECUTING)
        elif step.step_state == run_machine.RUN_FAILED:
            # A previous run exhausted the cap; a fresh dispatch starts over
            # from the re-queued (planned) state written by the resume path.
            step.step_state = run_machine.RUN_PLANNED
            step.status = STEP_PENDING
            step.save(update_fields=["step_state", "status", "updated_at"])
            PlansService.advance_step(step, run_machine.RUN_READY)
            PlansService.advance_step(step, run_machine.RUN_EXECUTING)
        # else: already executing — fine.

        step.status = STEP_RUNNING
        step.save(update_fields=["status", "updated_at"])

        last_error = ""

        for attempt in range(RETRY_MAX_ATTEMPTS):
            journal.append(
                spec,
                status=workflow.STATUS_DISPATCHED,
                operation_id=operation_id,
                canonical_inputs=canonical_inputs,
                attempt=attempt,
            )
            outcome = self._invoke_effect(effect_fn, operation_id, attempt)
            status = outcome.get("status")

            if status == workflow.STATUS_SUCCEEDED:
                journal.append(
                    spec,
                    status=workflow.STATUS_SUCCEEDED,
                    operation_id=operation_id,
                    result=outcome.get("result"),
                    attempt=attempt,
                )
                PlansService.advance_step(
                    step, run_machine.RUN_SUCCEEDED, outcome="succeeded"
                )
                step.status = STEP_COMPLETED
                step.save(update_fields=["status", "updated_at"])
                return workflow.STATUS_SUCCEEDED

            if status == workflow.STATUS_OUTCOME_UNKNOWN:
                journal.append(
                    spec,
                    status=workflow.STATUS_OUTCOME_UNKNOWN,
                    operation_id=operation_id,
                    error=outcome.get("error"),
                    attempt=attempt,
                )
                # Never blind-retry: route to reconciliation (P3-08).
                PlansService.reconcile_outcome(step, op_id=operation_id)
                return workflow.STATUS_OUTCOME_UNKNOWN

            # Transient failure.
            last_error = outcome.get("error") or "activity failed"
            journal.append(
                spec,
                status=workflow.STATUS_FAILED,
                operation_id=operation_id,
                error=last_error,
                attempt=attempt,
            )
            if attempt >= RETRY_MAX_ATTEMPTS - 1:
                break
            # Re-queue (append-only) for the next attempt.
            next_attempt = attempt + 1
            journal.append(
                spec,
                status=workflow.STATUS_PLANNED,
                operation_id=operation_id,
                attempt=next_attempt,
            )
            step.status = STEP_PENDING
            step.retry_count = (step.retry_count or 0) + 1
            step.save(update_fields=["status", "retry_count", "updated_at"])
            self._mark_run_paused(run)
            self._append_retry_audit(run, next_attempt, [int(spec.step_index)])
            sleep(self._retry_backoff_delay(next_attempt))

        # Retry cap exhausted → terminal failure.
        PlansService.advance_step(
            step, run_machine.RUN_FAILED, outcome="failed", error=last_error
        )
        step.status = STEP_FAILED
        step.save(update_fields=["status", "updated_at"])
        return workflow.STATUS_FAILED

    def resume_workflow(self, user, plan_id: str, *, now=None) -> dict:
        """Restart-mid-run: reconcile the journal, then re-enter the driver.

        Reuses ``resume_plan`` for the pre-flight gate (kills non-runnable
        statuses) and reads the append-only run journal (``RunJournalEntry``)
        — NOT the free-text ``RunStep.status`` — as the source of truth.
        In-flight entries are reconciled to a resumable state
        (``dispatched``/stale → re-queue, ``succeeded``/``skipped`` stay done,
        ``outcome_unknown`` stays for the reconciler, ``failed`` re-queues up
        to the retry cap), then the deterministic driver returns the first
        incomplete activity honoring dependency order.

        A step that is ``awaiting_approval`` stays gated — NEVER auto-approved
        (RULE_21) regardless of elapsed time.  ``now`` is recorded for the
        caller; it is deliberately NOT used to expire consent.
        """
        from ai.models.core import RunStep

        now = now or timezone.now()
        run = self._get_owned_run(user, plan_id)
        # Reuse the canonical pre-flight gate (blocks non-runnable statuses).
        self.resume_plan(user, plan_id)

        steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
        specs = [workflow.ActivitySpec.from_step(s) for s in steps]
        journal = workflow.RunJournal(str(run.id))

        decisions = workflow.reconcile_inflight(
            specs, journal.entries(), retry_max=RETRY_MAX_ATTEMPTS
        )
        for decision in decisions:
            journal.append(
                decision.spec,
                status=workflow.STATUS_PLANNED,
                attempt=decision.attempt,
            )

        nxt = workflow.next_activity(specs, journal.entries())
        next_step = None
        if nxt is not None:
            candidate = next(
                (s for s in steps if canonical_step_id(s) == nxt.step_id), None
            )
            if candidate is not None and candidate.step_state in {
                run_machine.RUN_AWAITING_APPROVAL,
                run_machine.RUN_AWAITING_RECONCILIATION,
            }:
                # Consent/reconciliation gate: block, never auto-advance.
                nxt = None
            else:
                next_step = candidate

        return {
            "status": "resumed",
            "plan_id": run.id,
            "next_activity": nxt,
            "next_step": next_step,
            "requeued": [d.as_dict() for d in decisions],
            "journal_count": journal.count(),
            "resumed_at": now.isoformat(),
        }

    def resume_and_run_next(self, user, plan_id: str, effect_fn, *, now=None, sleep=None) -> dict:
        """Resume from the journal and execute exactly the next activity.

        Never re-executes a committed activity (the driver skips
        ``succeeded``/``skipped`` entries), so a restart mid-run resumes at the
        first incomplete activity only.
        """
        resumed = self.resume_workflow(user, plan_id, now=now)
        next_step = resumed.get("next_step")
        if next_step is None:
            return {**resumed, "executed": None}
        run = self._get_owned_run(user, plan_id)
        final = self.dispatch_activity(run, next_step, effect_fn, sleep=sleep)
        return {
            **resumed,
            "executed": {
                "step_id": canonical_step_id(next_step),
                "step_index": next_step.step_index,
                "status": final,
            },
        }

    @staticmethod
    def preflight(run, step=None, *, action="run", objects=None, autonomy="human_only"):
        """Re-check authorization + kill switch before a new effect (P3-07a).

        (1) Kill switch — fail-closed, checked FIRST: a killed process blocks
            the effect regardless of policy and records ``kill_switched_at``.
        (2) PDP re-check — the current authorization is re-evaluated (the PDP
            persists its decision). ``REFUSE``/``ASK``/``DEFER`` block;
            ``ALLOW``/``ALLOW_WITH_CONFIRMATION`` permit (consent is handled
            by the existing confirm/decline seam, not here).

        Note (deferred): ProcessDefinition uses the 6-level ``VALID_AUTONOMY``
        dial while the PDP uses a 3-level runtime dial; full reconciliation is
        out of scope for P3-07a. The ``autonomy`` argument defaults to the
        conservative ``human_only``.
        """
        from ai import pdp
        from ai.engine.ports.policy import Decision
        from ai.registry_service import ProcessRegistry

        process_id = run.definition_id or ""
        objects = list(objects or [])
        if process_id and process_id not in objects:
            objects.insert(0, process_id)
        if step is not None and step.id and step.id not in objects:
            objects.append(step.id)

        # (1) Kill switch — fail-closed, before anything else.
        if process_id:
            try:
                killed = ProcessRegistry().is_killed(process_id)
            except Exception:  # noqa: BLE001 - unresolvable def → not killed
                logger.warning("Preflight: process %r not resolvable", process_id)
                killed = False
            if killed:
                run.kill_switched_at = timezone.now()
                run.save(update_fields=["kill_switched_at", "updated_at"])
                return {
                    "allowed": False,
                    "reason": "kill_switch",
                    "decision": "refuse",
                }

        # (2) PDP re-check — persisted by the PDP itself.
        decision = _run_async(
            pdp.decide(
                principal=str(run.host_user_id or ""),
                action=action,
                objects=objects,
                autonomy=autonomy,
            )
        )
        decision_value = decision["decision"]
        allowed = decision_value not in {
            Decision.REFUSE,
            Decision.ASK,
            Decision.DEFER,
        }
        return {
            "allowed": allowed,
            "reason": decision["reason"],
            "decision": decision_value.value,
        }

    @staticmethod
    def store_artifact(run_id, step_index, name, content_bytes, mime_type):
        """Persist a plan-step artifact and return its public metadata (W5-C).

        Durable artifact delivery: writes to ``MEDIA_ROOT/ai_artifacts/…`` and
        creates a ``RunArtifact`` row scoped to ``run_id``. Returns
        ``{artifact_id, name, size_bytes, download_url}`` so the caller (the
        ``export_document`` plugin) can surface a download link in its output.
        """
        from ai.models.core import Run, RunArtifact

        run = Run.objects.get(id=run_id)
        content_bytes = content_bytes or b""
        artifact = RunArtifact.objects.create(
            run_id=run.id,
            step_index=step_index,
            name=name or "artifact",
            mime_type=mime_type or "application/octet-stream",
            size_bytes=len(content_bytes),
        )
        artifact.file.save(name or "artifact", ContentFile(content_bytes), save=True)
        logger.info(
            "Stored plan artifact id=%s run=%s step=%s name=%s bytes=%d",
            artifact.id, run_id, step_index, name, len(content_bytes),
        )
        return {
            "artifact_id": artifact.id,
            "name": artifact.name,
            "size_bytes": artifact.size_bytes,
            "download_url": _artifact_download_url(run_id, artifact.id),
        }

    @staticmethod
    def resolve_export_step_index(run_id, step_index=None):
        """Map an export to a plan step index when the caller lacks one.

        The frozen engine ``ToolContext`` does not carry ``step_id``; the
        contextvar carries only ``run_id``. Best effort: honour an explicit
        ``step_index``, else attach to the most recent step that actually ran
        ``export_document``, else the most recent completed step, else ``None``
        (artifacts are still listed at plan level).
        """
        from ai.models.core import RunStep

        if step_index is not None:
            return int(step_index)
        # W6-D: the ReActLoop records the step it is dispatching in a
        # contextvar (copied onto the sync_to_async worker thread), so a
        # multi-step run attributes the artifact to the step that actually
        # ran — the heuristic below would otherwise label every export with
        # the highest-indexed export step.
        current = get_current_step_index()
        if current is not None:
            return int(current)
        steps = list(
            RunStep.objects.filter(run_id=run_id).order_by("-step_index")
        )
        for s in steps:
            if s.tool_name == "export_document":
                return s.step_index
        for s in steps:
            if s.status == STEP_COMPLETED:
                return s.step_index
        return steps[0].step_index if steps else None

    @staticmethod
    def _serialize_run(run, steps=None):
        """Product-facing plan payload (RULE_23 — outcome terms only)."""
        from ai.models.core import RunArtifact, RunStep

        plan_json = _coerce_plan_json(run.plan_json)
        # Service-owned per-step metadata (e.g. ``instructions`` from step
        # edits) rides in plan_json — engine fields stay untouched. Legacy
        # rows may carry string reprs, so guard with isinstance.
        step_meta = {
            s.get("step_id"): s
            for s in plan_json.get("steps", [])
            if isinstance(s, dict)
        }
        # F-26: map each step id to its enclosing phase so serialized steps
        # carry the phase strategy + a stable parallel group key.
        step_phase: dict = {}
        for i, phase in enumerate(plan_json.get("phases") or []):
            if not isinstance(phase, dict):
                continue
            strategy = phase.get("strategy", "sequential")
            phase_id = phase.get("phase_id", i)
            for sid in phase.get("step_ids") or []:
                try:
                    step_phase[int(sid)] = (strategy, phase_id)
                except (TypeError, ValueError):
                    continue
        if steps is None:
            steps = list(
                RunStep.objects.filter(run_id=run.id).order_by("step_index")
            )
        # When every step is terminal, keep the plan status aligned (list + get).
        _reconcile_run_status_from_steps(run, steps)
        # Artifacts grouped by step (W5-C): one query for the whole run.
        artifacts_by_step: dict = {}
        for a in RunArtifact.objects.filter(run_id=run.id):
            artifacts_by_step.setdefault(a.step_index, []).append(a)
        return {
            "id": run.id,
            "definition_id": run.definition_id,
            "status": run.status,
            "brief": run.user_message,
            "forked_from": (
                (run.working_notes or {}).get("forked_from")
                if run.working_notes else None
            ),
            "pattern": plan_json.get("pattern", "custom"),
            "source": plan_json.get("source", "single_step"),
            "skill_name": plan_json.get("skill_name"),
            "synthesis_instruction": plan_json.get("synthesis_instruction"),
            "phases": [
                {
                    "phase_id": p.get("phase_id", i),
                    "name": p.get("name", f"Phase {i + 1}"),
                    "goal": p.get("goal", ""),
                    "strategy": p.get("strategy", "sequential"),
                    "step_ids": p.get("step_ids") or [],
                }
                for i, p in enumerate(plan_json.get("phases") or [])
            ],
            "conversation_id": run.conversation_id,
            "discovery_turns": (
                plan_json.get("discovery_turns")
                if run.status == STATUS_DISCOVERING
                else None
            ),
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "final_response": run.final_response,
            "prior_run": _prior_run_receipt(run),
            "steps": [
                {
                    "step_id": s.step_index,
                    "intent": s.intent,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args_json or {},
                    "depends_on": s.depends_on_json or [],
                    **_step_execution_fields(step_phase, s.step_index, s.status),
                    "instructions": (
                        (step_meta.get(s.step_index) or {}).get("instructions")
                    ),
                    "agent_role": (
                        (step_meta.get(s.step_index) or {}).get(
                            "agent_role", "orchestrator"
                        )
                    ),
                    "status": s.status,
                    "draft_text": s.draft_text,
                    "critic_verdict": s.critic_verdict,
                    "consent_granted": bool(
                        isinstance(s.critic_flags_json, dict)
                        and s.critic_flags_json.get("consent_granted")
                    ),
                    "error": s.error,
                    "tool_output": _step_tool_output_fields(s.tool_output_json)[0],
                    "output_type": _step_tool_output_fields(s.tool_output_json)[1],
                    "artifacts": [
                        {
                            "id": a.id,
                            "name": a.name,
                            "mime_type": a.mime_type,
                            "size_bytes": a.size_bytes,
                            "download_url": _artifact_download_url(
                                run.id, a.id
                            ),
                        }
                        for a in artifacts_by_step.get(s.step_index, [])
                    ],
                }
                for s in steps
            ],
            "workflow_graph": (
                plan_json.get("workflow_graph")
                or PlansService._compile_workflow_graph_from_json(plan_json)
            ),
        }

    # ── W3-C: replan helpers ─────────────────────────────────────────────

    @staticmethod
    def _plan_to_dict(plan) -> dict:
        """Serialize an engine Plan into the service's plan_json shape.

        Steps become plain dicts (NOT dataclass reprs) so edit / replan /
        run all operate on structured data. ``instructions`` (service-owned
        review text from step edits) is an extra key the engine ignores.
        Phases + per-step agent roles ride along so the workflow shape and
        agent assignments survive persistence and round-trip through
        ``_rebuild_plan``.
        """
        return {
            "pattern": plan.pattern,
            "steps": [
                {
                    "step_id": s.step_id,
                    "intent": s.intent,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args or {},
                    "skill_name": s.skill_name,
                    "depends_on": s.depends_on or [],
                    "is_mutation": bool(s.is_mutation),
                    "dry_run_supported": bool(s.dry_run_supported),
                    "agent_role": s.agent_role or "orchestrator",
                }
                for s in plan.steps
            ],
            "phases": [
                {
                    "phase_id": p.phase_id,
                    "name": p.name,
                    "goal": p.goal,
                    "strategy": p.strategy,
                    "step_ids": p.step_ids or [],
                }
                for p in getattr(plan, "phases", []) or []
            ],
            "synthesis_instruction": plan.synthesis_instruction,
            "source": plan.source,
            "skill_name": plan.skill_name,
            "needs_confirmation": bool(plan.needs_confirmation),
            # ADR-0034 — typed graph compile (additive; UI/driver may ignore).
            "workflow_graph": PlansService._compile_workflow_graph(plan),
        }

    @staticmethod
    def _compile_workflow_graph(plan) -> dict | None:
        """Compile legacy Plan → WorkflowGraph dict (fail-soft)."""
        try:
            from ai.engine.workflow.graph import compile_plan_to_graph

            return compile_plan_to_graph(plan).to_dict()
        except Exception:  # noqa: BLE001 — never block plan persistence
            logger.exception("workflow_graph compile failed")
            return None

    @staticmethod
    def record_workflow_choice(run_id: str, node_id: str, context: dict | None = None) -> dict:
        """Journal guard evaluations + chosen edge for a choice node (ADR-0034).

        Fail-soft: returns ``{chosen, evaluations}`` even if journaling fails.
        """
        from ai.engine.workflow.driver import decide_choice
        from ai.engine.workflow.graph import WorkflowGraph
        from ai.models.core import Run
        from ai.models.step_journal import EVENT_EDGE_CHOSEN, EVENT_GUARD_EVAL
        from ai.step_journal import StepJournal

        run = Run.objects.filter(id=run_id).first()
        graph_raw = (
            _coerce_plan_json(run.plan_json).get("workflow_graph") if run else None
        )
        if not graph_raw:
            return {"chosen": None, "evaluations": []}
        graph = WorkflowGraph.from_dict(graph_raw)
        chosen, evaluations = decide_choice(graph, node_id, context or {})
        try:
            for ev in evaluations:
                StepJournal.append(
                    run_id,
                    node_id,
                    EVENT_GUARD_EVAL,
                    payload=ev,
                )
            if chosen is not None:
                StepJournal.append(
                    run_id,
                    node_id,
                    EVENT_EDGE_CHOSEN,
                    payload={
                        "source": chosen.source,
                        "target": chosen.target,
                        "guard": chosen.guard,
                        "is_default": chosen.is_default,
                    },
                )
        except Exception:  # noqa: BLE001 — journaling must never block routing
            logger.exception("workflow choice journal failed run=%s node=%s", run_id, node_id)
        return {
            "chosen": (
                {"source": chosen.source, "target": chosen.target, "guard": chosen.guard}
                if chosen else None
            ),
            "evaluations": evaluations,
        }

    @staticmethod
    def record_workflow_heal(
        run_id: str, observe_node_id: str, payload: dict | None = None,
    ) -> dict:
        """Journal an observe-node heal proposal (ADR-0034 / W-5)."""
        from ai.models.step_journal import EVENT_HEAL_PROPOSED
        from ai.step_journal import StepJournal

        body = dict(payload or {})
        body.setdefault("observe_node", observe_node_id)
        try:
            StepJournal.append(
                run_id,
                observe_node_id,
                EVENT_HEAL_PROPOSED,
                payload=body,
            )
        except Exception:  # noqa: BLE001 — journaling must never block heal
            logger.exception(
                "workflow heal journal failed run=%s node=%s", run_id, observe_node_id,
            )
        return body

    @staticmethod
    def record_workflow_compensation(
        run_id: str,
        failed_step_id: int,
        compensation_step_id: int,
        compensation_node: str,
    ) -> dict:
        """Journal a saga compensation enqueue (ADR-0034 / W-4)."""
        from ai.models.step_journal import EVENT_COMPENSATION_QUEUED
        from ai.step_journal import StepJournal

        body = {
            "failed_step_id": failed_step_id,
            "compensation_step_id": compensation_step_id,
            "compensation_node": compensation_node,
        }
        try:
            StepJournal.append(
                run_id,
                str(failed_step_id),
                EVENT_COMPENSATION_QUEUED,
                payload=body,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "workflow compensation journal failed run=%s", run_id,
            )
        return body

    @staticmethod
    def record_workflow_wait(
        run_id: str,
        node_id: str,
        *,
        duration_ms: int = 0,
        reason: str = "immediate",
        until_guard: str | None = None,
    ) -> dict:
        """Journal a wait node firing (ADR-0034 / W-3 timers)."""
        from ai.models.step_journal import EVENT_WAIT_FIRED
        from ai.step_journal import StepJournal

        body = {
            "node_id": node_id,
            "duration_ms": int(duration_ms or 0),
            "reason": reason,
            "until_guard": until_guard,
        }
        try:
            StepJournal.append(
                run_id,
                node_id,
                EVENT_WAIT_FIRED,
                payload=body,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "workflow wait journal failed run=%s node=%s", run_id, node_id,
            )
        return body

    @staticmethod
    def _compile_workflow_graph_from_json(plan_json: dict) -> dict | None:
        """Compile from persisted plan_json when workflow_graph was never stored."""
        if not plan_json or not plan_json.get("steps"):
            return None
        try:
            from types import SimpleNamespace

            from ai.engine.workflow.graph import compile_plan_to_graph

            steps = [
                SimpleNamespace(
                    step_id=s.get("step_id", i),
                    intent=s.get("intent", ""),
                    tool_name=s.get("tool_name"),
                    tool_args=s.get("tool_args") or {},
                    is_mutation=bool(s.get("is_mutation")),
                    depends_on=s.get("depends_on") or [],
                    agent_role=s.get("agent_role", "orchestrator"),
                )
                for i, s in enumerate(plan_json.get("steps") or [])
                if isinstance(s, dict)
            ]
            phases = [
                SimpleNamespace(
                    phase_id=p.get("phase_id", i),
                    name=p.get("name", ""),
                    strategy=p.get("strategy", "sequential"),
                    step_ids=p.get("step_ids") or [],
                )
                for i, p in enumerate(plan_json.get("phases") or [])
                if isinstance(p, dict)
            ]
            return compile_plan_to_graph(
                SimpleNamespace(steps=steps, phases=phases)
            ).to_dict()
        except Exception:  # noqa: BLE001
            logger.exception("workflow_graph compile-from-json failed")
            return None

    def _decompose(self, user, brief):
        """Run SkillAwarePlanner.decompose on a fresh engine session."""
        from ai.engine.core.config import get_settings
        from ai.engine.core.database import get_session_factory
        from ai.engine.cognition.plan.planner import SkillAwarePlanner
        from ai.engine.skills.registry import SkillRegistry

        settings = get_settings()
        user_pk = str(user.pk)

        async def _decompose():
            from ai.engine.llm.provider import get_llm_client

            factory = get_session_factory(PLAN_INSTANCE_ID)
            async with factory() as db:
                registry = SkillRegistry(db)
                planner = SkillAwarePlanner(
                    llm_client=get_llm_client(), model=settings.LLM_MODEL
                )
                return await planner.decompose(
                    utterance=brief,
                    skill_registry=registry,
                    instance_id=PLAN_INSTANCE_ID,
                    user_id=user_pk,
                    force_decompose=True,
                )

        return _run_async(_decompose())

    @staticmethod
    def _normalize_intent(intent) -> str:
        return (intent or "").strip().lower()

    @staticmethod
    def _intent_fingerprint(intent: str) -> str:
        """Coarse key for near-duplicate intents (ellipsis / truncated labels)."""
        text = PlansService._normalize_intent(intent)
        text = re.sub(r"[.…]+$", "", text)
        text = re.sub(r"\s+", " ", text)
        # First ~48 chars captures "analyze salary distribution by…" clones.
        return text[:48]

    @classmethod
    def _dedupe_plan_steps(cls, steps: list) -> list:
        """Drop near-duplicate intents that make Discuss→replan graphs regress."""
        out: list = []
        seen: set[str] = set()
        for s in steps:
            if not isinstance(s, dict):
                continue
            fp = cls._intent_fingerprint(s.get("intent") or "")
            if fp and fp in seen:
                continue
            if fp:
                seen.add(fp)
            out.append(dict(s))
        # Re-number step_id sequentially so the DAG stays contiguous.
        for i, s in enumerate(out):
            old_id = s.get("step_id", i)
            s["step_id"] = i
            deps = s.get("depends_on") or []
            if isinstance(deps, list) and deps:
                # Keep deps that still exist by remapping old→new when possible.
                id_map = {}
                # built below — first pass collect old ids
            s["_old_id"] = old_id
        id_map = {s.get("_old_id"): s["step_id"] for s in out}
        for s in out:
            deps = s.get("depends_on") or []
            if isinstance(deps, list):
                s["depends_on"] = [
                    id_map[d] for d in deps if d in id_map
                ]
            s.pop("_old_id", None)
        return out

    @staticmethod
    def _is_incremental_plan_feedback(old_brief: str, new_brief: str) -> bool:
        """True when the edit is a small additive ask (e.g. 'add a chart')."""
        new = (new_brief or "").strip()
        old = (old_brief or "").strip()
        if not new:
            return False
        lower = new.lower()
        # Short additive asks — never wipe the whole topology for these.
        if len(new) <= 320 and re.search(
            r"\b(add|include|embed|insert|also|with)\b.{0,40}\b"
            r"(chart|charts|graph|graphs|visual|visuals|plot|plots|"
            r"table|tables|export|docx|word|excel|xlsx)\b",
            lower,
        ):
            return True
        if old and len(new) <= len(old) + 500:
            # Feedback that still contains the prior spine.
            old_tokens = {t for t in re.findall(r"[a-z0-9]{4,}", old.lower())}
            new_tokens = {t for t in re.findall(r"[a-z0-9]{4,}", lower)}
            if old_tokens and len(old_tokens & new_tokens) / max(1, len(old_tokens)) >= 0.55:
                if re.search(
                    r"\b(add|include|embed|also|chart|graph|visual)\b", lower
                ):
                    return True
        return False

    @classmethod
    def _surgical_incremental_steps(cls, old_steps: list, feedback: str) -> list:
        """Keep existing steps; append chart/export work for additive feedback."""
        steps = [dict(s) for s in old_steps if isinstance(s, dict)]
        fl = (feedback or "").lower()
        wants_chart = bool(
            re.search(r"\b(chart|charts|graph|graphs|visual|plot)\b", fl)
        )
        has_chartish = any(
            re.search(
                r"\b(chart|graph|visual|plot)\b",
                f"{s.get('intent') or ''}".lower(),
            )
            for s in steps
        )
        has_export = any(
            (s.get("tool_name") or "") == "export_document"
            or re.search(r"\b(export|word|docx)\b", (s.get("intent") or "").lower())
            for s in steps
        )
        next_id = max((int(s.get("step_id", 0)) for s in steps), default=-1) + 1
        last_ids = [s.get("step_id") for s in steps[-2:]] if steps else []

        if wants_chart and not has_chartish:
            steps.append({
                "step_id": next_id,
                "intent": (
                    "Generate visually compelling charts for each salary "
                    "dimension (nationality, org unit, position)"
                ),
                "tool_name": "code_execute",
                "tool_args": {},
                "depends_on": [last_ids[-1]] if last_ids else [],
                "is_mutation": False,
                "dry_run_supported": False,
                "instructions": (
                    "Build bar/pie charts from prior analysis tables; "
                    "return image_b64 PNG figures for the Word pack."
                ),
            })
            next_id += 1
            has_chartish = True

        if wants_chart and has_export:
            # Point the last export at embedding visuals.
            for s in reversed(steps):
                if (s.get("tool_name") or "") == "export_document" or re.search(
                    r"\b(export|word|docx)\b", (s.get("intent") or "").lower()
                ):
                    intent = (s.get("intent") or "").rstrip(".")
                    if "chart" not in intent.lower() and "visual" not in intent.lower():
                        s["intent"] = f"{intent} with embedded charts"
                    break
        elif wants_chart and not has_export:
            chart_deps = [
                s.get("step_id") for s in steps
                if re.search(r"chart|visual|code_execute", f"{s.get('intent')}{s.get('tool_name')}".lower())
            ]
            steps.append({
                "step_id": next_id,
                "intent": "Export the Word report with embedded charts and tables",
                "tool_name": "export_document",
                "tool_args": {"format": "docx"},
                "depends_on": chart_deps or ([steps[-1]["step_id"]] if steps else []),
                "is_mutation": False,
                "dry_run_supported": False,
                "instructions": None,
            })

        return cls._dedupe_plan_steps(steps)

    @staticmethod
    def _step_key(step) -> tuple:
        """Canonical fingerprint for diffing two plan steps."""
        step = step if isinstance(step, dict) else {}
        return (
            (step.get("intent") or "").strip().lower(),
            step.get("tool_name") or "",
            json.dumps(step.get("tool_args") or {}, sort_keys=True, default=str),
            json.dumps(sorted(step.get("depends_on") or [])),
            (step.get("instructions") or "").strip(),
        )

    @classmethod
    def _plan_diff(cls, old_steps, new_steps, key="intent") -> dict:
        """Diff two step lists → ``{added, removed, changed}`` (RULE_23 terms).

        Steps are matched by ``key`` (``"intent"`` for replans where step ids
        are regenerated, ``"step_id"`` for in-place step edits where the id is
        stable). When lengths match on a replan, prefer **positional** pairing
        so the same slot with reworded intent shows as ``changed`` instead of
        remove+add. ``changed`` entries carry ``{"old": ..., "new": ...}``.
        """
        old_list = [s for s in old_steps if isinstance(s, dict)]
        new_list = [s for s in new_steps if isinstance(s, dict)]

        if key == "step_id":
            def _sid(s):
                return s.get("step_id")

            old = {_sid(s): s for s in old_list if _sid(s) is not None}
            new = {_sid(s): s for s in new_list if _sid(s) is not None}
            added = [s for k, s in new.items() if k not in old]
            removed = [s for k, s in old.items() if k not in new]
            changed = [
                {"old": old[k], "new": new[k]}
                for k in old.keys() & new.keys()
                if cls._step_key(old[k]) != cls._step_key(new[k])
            ]
            return {"added": added, "removed": removed, "changed": changed}

        # Same-length replan: pair by position (stable workflow spine).
        if len(old_list) == len(new_list) and old_list:
            changed = [
                {"old": o, "new": n}
                for o, n in zip(old_list, new_list)
                if cls._step_key(o) != cls._step_key(n)
            ]
            return {"added": [], "removed": [], "changed": changed}

        def _intent_key(s):
            return cls._normalize_intent(s.get("intent"))

        old = {_intent_key(s): s for s in old_list}
        new = {_intent_key(s): s for s in new_list}
        added = [s for k, s in new.items() if k not in old]
        removed = [s for k, s in old.items() if k not in new]
        changed = [
            {"old": old[k], "new": new[k]}
            for k in old.keys() & new.keys()
            if cls._step_key(old[k]) != cls._step_key(new[k])
        ]
        return {"added": added, "removed": removed, "changed": changed}

    _PRE_EDIT_SNAPSHOT = "pre_edit_snapshot"

    def _stash_pre_edit_snapshot(self, run) -> None:
        """Capture plan + step rows so discard-edit can restore after Cancel."""
        from ai.models.core import RunStep

        steps = list(
            RunStep.objects.filter(run_id=run.id).order_by("step_index")
        )
        notes = dict(run.working_notes or {})
        notes[self._PRE_EDIT_SNAPSHOT] = {
            "user_message": run.user_message,
            "plan_json": json.loads(json.dumps(_coerce_plan_json(run.plan_json))),
            "status": run.status,
            "final_response": run.final_response,
            "completed_at": (
                run.completed_at.isoformat() if run.completed_at else None
            ),
            "steps": [
                {
                    "step_index": s.step_index,
                    "intent": s.intent,
                    "tool_name": s.tool_name,
                    "tool_args_json": s.tool_args_json or {},
                    "depends_on_json": s.depends_on_json or [],
                    "status": s.status,
                    "error": s.error,
                    "last_error": getattr(s, "last_error", "") or "",
                    "critic_verdict": s.critic_verdict,
                    "critic_flags_json": (
                        s.critic_flags_json
                        if isinstance(s.critic_flags_json, dict)
                        else {}
                    ),
                    "draft_text": s.draft_text,
                    "tool_output_json": s.tool_output_json,
                    "latency_ms": s.latency_ms,
                    "retry_count": s.retry_count or 0,
                    "confirmation_token": s.confirmation_token,
                }
                for s in steps
            ],
        }
        run.working_notes = notes

    def _clear_pre_edit_snapshot(self, run) -> None:
        notes = dict(run.working_notes or {})
        if self._PRE_EDIT_SNAPSHOT not in notes:
            return
        notes.pop(self._PRE_EDIT_SNAPSHOT, None)
        run.working_notes = notes or None
        run.save(update_fields=["working_notes", "updated_at"])

    def confirm_plan_edit(self, user, plan_id: str) -> dict:
        """Keep the applied edit — drop the Cancel rollback snapshot."""
        run = self._get_owned_run(user, plan_id)
        self._clear_pre_edit_snapshot(run)
        return self.get_plan(user, plan_id)

    def discard_plan_edit(self, user, plan_id: str) -> dict:
        """Restore the pre-edit snapshot (diff-dialog Cancel). Idempotent."""
        from ai.models.core import RunStep
        from django.utils.dateparse import parse_datetime

        run = self._get_owned_run(user, plan_id)
        notes = dict(run.working_notes or {})
        snap = notes.get(self._PRE_EDIT_SNAPSHOT)
        if not snap:
            return self.get_plan(user, plan_id)

        run.user_message = snap.get("user_message") or run.user_message
        run.plan_json = snap.get("plan_json") or run.plan_json
        run.status = snap.get("status") or run.status
        run.final_response = snap.get("final_response")
        completed_raw = snap.get("completed_at")
        run.completed_at = parse_datetime(completed_raw) if completed_raw else None
        notes.pop(self._PRE_EDIT_SNAPSHOT, None)
        run.working_notes = notes or None
        run.save(
            update_fields=[
                "user_message",
                "plan_json",
                "status",
                "final_response",
                "completed_at",
                "working_notes",
                "updated_at",
            ]
        )

        RunStep.objects.filter(run_id=run.id).delete()
        for row in snap.get("steps") or []:
            if not isinstance(row, dict):
                continue
            RunStep.objects.create(
                run_id=run.id,
                step_index=int(row.get("step_index", 0)),
                intent=row.get("intent") or "",
                tool_name=row.get("tool_name"),
                tool_args_json=row.get("tool_args_json") or {},
                depends_on_json=row.get("depends_on_json") or [],
                status=row.get("status") or STEP_PENDING,
                error=row.get("error"),
                last_error=row.get("last_error") or "",
                critic_verdict=row.get("critic_verdict"),
                critic_flags_json=(
                    row.get("critic_flags_json")
                    if isinstance(row.get("critic_flags_json"), dict)
                    else {}
                ),
                draft_text=row.get("draft_text"),
                tool_output_json=row.get("tool_output_json"),
                latency_ms=row.get("latency_ms"),
                retry_count=int(row.get("retry_count") or 0),
                confirmation_token=row.get("confirmation_token"),
            )

        logger.info(
            "Plan edit discarded id=%s user=%s restored_status=%s",
            plan_id, str(user.pk), run.status,
        )
        return self.get_plan(user, plan_id)

    @staticmethod
    def _apply_step_deltas(steps, step_deltas) -> list:
        """Apply user-supplied step deltas on top of a fresh decomposition.

        Each delta::

            {"action": "remove", "step_id": N}
            {"action": "add", "intent": ..., "tool_name": ...,
             "tool_args": {...}, "depends_on": [...]}
            {"action": "update", "step_id": N, "intent"?: ...,
             "tool_name"?: ..., "tool_args"?: ..., "depends_on"?: ...}

        Deltas are applied in order; the returned step list feeds the diff so
        the outcome is always reviewable.
        """
        if not isinstance(step_deltas, list):
            raise ValueError("step_deltas must be a list.")
        steps = [dict(s) for s in steps if isinstance(s, dict)]
        next_id = max((s.get("step_id", 0) for s in steps), default=0) + 1
        for delta in step_deltas:
            if not isinstance(delta, dict):
                continue
            action = delta.get("action")
            if action == "remove":
                steps = [
                    s for s in steps
                    if s.get("step_id") != delta.get("step_id")
                ]
            elif action == "add":
                step = {
                    "step_id": delta.get("step_id", next_id),
                    "intent": delta.get("intent", ""),
                    "tool_name": delta.get("tool_name"),
                    "tool_args": delta.get("tool_args") or {},
                    "skill_name": delta.get("skill_name"),
                    "depends_on": delta.get("depends_on") or [],
                    "is_mutation": bool(delta.get("is_mutation", False)),
                    "dry_run_supported": bool(
                        delta.get("dry_run_supported", False)
                    ),
                    "instructions": delta.get("instructions"),
                }
                steps.append(step)
                next_id = max(next_id, int(step["step_id"]) + 1)
            elif action == "update":
                for s in steps:
                    if s.get("step_id") != delta.get("step_id"):
                        continue
                    for field in (
                        "intent", "tool_name", "tool_args", "depends_on",
                        "skill_name", "instructions",
                    ):
                        if field in delta:
                            s[field] = delta[field]
                    if "is_mutation" in delta:
                        s["is_mutation"] = bool(delta["is_mutation"])
        return steps

    @staticmethod
    def _replace_run_steps(run_id, steps):
        """Replace a plan's RunStep rows from a (possibly edited) step list."""
        from ai.models.core import RunStep

        RunStep.objects.filter(run_id=run_id).delete()
        for step in steps:
            if not isinstance(step, dict):
                continue
            RunStep.objects.create(
                run_id=run_id,
                step_index=int(step.get("step_id", 0)),
                intent=step.get("intent", ""),
                tool_name=step.get("tool_name"),
                tool_args_json=step.get("tool_args") or {},
                depends_on_json=step.get("depends_on") or [],
                status=STEP_PENDING,
            )

    @staticmethod
    def _rebuild_plan(run):
        """Rebuild the engine ``Plan`` dataclass from the persisted plan_json.

        The approved plan is the executed plan — no re-decomposition at run
        time (review contract).

        If ``plan_json.steps`` is empty but durable ``RunStep`` rows exist,
        rebuild from those rows so the loop never finalizes empty-success
        while the UI still shows pending steps.
        """
        from ai.engine.cognition.plan.planner import Plan, PlanPhase, PlanStep
        from ai.models.core import RunStep

        plan_json = _coerce_plan_json(run.plan_json)
        raw_steps = [
            s for s in (plan_json.get("steps") or []) if isinstance(s, dict)
        ]
        if not raw_steps:
            durable = list(
                RunStep.objects.filter(run_id=run.id).order_by("step_index")
            )
            if durable:
                logger.warning(
                    "plan_json.steps empty for run=%s — rebuilding %d steps "
                    "from durable RunStep rows",
                    run.id, len(durable),
                )
                raw_steps = [
                    {
                        "step_id": s.step_index,
                        "intent": s.intent or "",
                        "tool_name": s.tool_name,
                        "tool_args": s.tool_args_json or {},
                        "depends_on": s.depends_on_json or [],
                        "is_mutation": False,
                        "dry_run_supported": False,
                        "agent_role": "orchestrator",
                        "instructions": None,
                    }
                    for s in durable
                ]
        steps = [
            PlanStep(
                step_id=int(s.get("step_id", 0)),
                intent=s.get("intent", ""),
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args") or {},
                skill_name=s.get("skill_name"),
                depends_on=s.get("depends_on") or [],
                is_mutation=bool(s.get("is_mutation", False)),
                dry_run_supported=bool(s.get("dry_run_supported", False)),
                agent_role=s.get("agent_role", "orchestrator"),
                instructions=s.get("instructions"),
            )
            for s in raw_steps
        ]
        phases = [
            PlanPhase(
                phase_id=int(p.get("phase_id", i)),
                name=p.get("name", ""),
                goal=p.get("goal", ""),
                strategy=p.get("strategy", "sequential"),
                step_ids=[int(x) for x in (p.get("step_ids") or [])],
            )
            for i, p in enumerate(plan_json.get("phases") or [])
        ]
        return Plan(
            pattern=plan_json.get("pattern", "custom"),
            steps=steps,
            synthesis_instruction=plan_json.get("synthesis_instruction", ""),
            source=plan_json.get("source", "custom"),
            skill_name=plan_json.get("skill_name"),
            needs_confirmation=bool(plan_json.get("needs_confirmation", False)),
            phases=phases,
        )

    # ── Create / read ─────────────────────────────────────────────────────

    def create_plan(self, user, brief: str, conversation_id: str = "") -> dict:
        """Decompose a brief into a reviewable plan (pending_approval).

        Planning only — NO execution (RULE_21: review before mutation).
        The engine planner runs on its own store session via a worker thread;
        the resulting Plan is persisted as the Run row's ``plan_json`` plus
        one RunStep row per step.
        """
        from ai.models.core import Run, RunStep, generate_uuid

        brief = (brief or "").strip()
        if not brief:
            raise ValueError("brief is required.")
        if len(brief) > 4000:
            raise ValueError("brief is too long (max 4000 characters).")

        user_pk = str(user.pk)
        plan = self._decompose(user, brief)

        run_id = generate_uuid()
        run = Run(
            id=run_id,
            instance_id=PLAN_INSTANCE_ID,
            conversation_id=conversation_id or "",
            host_user_id=user_pk,
            user_message=brief,
            status=STATUS_PENDING_APPROVAL,
            plan_json=self._plan_to_dict(plan),
        )
        run.save()

        for step in plan.steps:
            RunStep.objects.create(
                run_id=run_id,
                step_index=step.step_id,
                intent=step.intent,
                tool_name=step.tool_name,
                tool_args_json=step.tool_args or {},
                depends_on_json=step.depends_on or [],
                status=STEP_PENDING,
            )

        logger.info(
            "Plan created id=%s user=%s steps=%d source=%s",
            run_id, user_pk, len(plan.steps), plan.source,
        )
        result = self.get_plan(user, run_id)

        # ADR-0041 Phase 2 — Agent Job Map on plan create.
        if conversation_id:
            try:
                from ai.ops_canvas import (
                    MODE_AGENT,
                    build_payload,
                    layers_from_plan,
                    upsert_job_map_artifact,
                )

                plan_dict = self._plan_to_dict(plan)
                layers = layers_from_plan(plan_dict)
                payload = build_payload(
                    mode=MODE_AGENT,
                    ask=brief,
                    layers=layers,
                    plan_id=run_id,
                    conversation_id=conversation_id,
                    title=(brief[:80] or "Agent Job Map"),
                )
                upsert_job_map_artifact(
                    user=user,
                    conversation_id=conversation_id,
                    title=(brief[:80] or "Agent Job Map"),
                    payload=payload,
                )
            except Exception:  # noqa: BLE001
                logger.debug("ops_canvas agent job map emit failed", exc_info=True)

        return result

    # ── W5-B: guided discovery conversation ───────────────────────────────

    DISCOVERY_MAX_TURNS = 5

    DISCOVERY_SYSTEM_PROMPT = (
        "You are Pulse, the planning assistant for the Carbon / EduOS platform. "
        "Before proposing a plan, you clarify the user's outcome "
        "with a short series of focused questions. Ask ONE concise question "
        "at a time. When you have enough information, respond with complete."
        "\n\n"
        "Scope rules (critical):\n"
        "- Only clarify outcomes Agent can plan: reports, board packs, data-quality "
        "rules, data workflows, exports.\n"
        "- Never map personal leave / vacation / إجازة to DQ rules, approvals, or "
        "data-source onboarding. If the user wants personal leave, respond with "
        '{"action":"complete"} only if they clearly asked for a leave-compliance '
        "REPORT; otherwise keep asking for the report outcome — the host may "
        "already have redirected them.\n"
        "- Do not ask 'what outcome on the Carbon Data Trust Platform' for "
        "trivia, names, or personal HR actions.\n"
        "\n"
        "If the user wants a data-quality rule (validate/check/flag a field, "
        "not-null, unique, allowed values, range, regex, format like an email "
        "or phone number), you MUST find out exactly WHICH field and table the "
        "rule applies to before completing — ask for the specific field/column "
        "name (or DataField id) and table. Never complete discovery for a DQ "
        "rule while the target field is still unknown."
    )

    def _discovery_prompt(self, brief: str, turns: list) -> list:
        """Build the chat messages for one discovery round."""
        messages = [
            {"role": "system", "content": self.DISCOVERY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Outcome to plan: {brief}"},
        ]
        for turn in turns:
            question = (turn.get("question") or "").strip()
            if question:
                messages.append({"role": "assistant", "content": question})
            reply = (turn.get("reply") or "").strip()
            if reply:
                messages.append({"role": "user", "content": reply})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Respond with JSON only: either "
                    '{"action":"ask","question":"<your question>"} to ask the '
                    'next clarifying question, or {"action":"complete"} when '
                    "you have enough to propose a plan."
                ),
            }
        )
        return messages

    def _ask_discovery_llm(self, brief: str, turns: list) -> dict:
        """One discovery round → ``{"action": "ask"|"complete", "question": ...}``.

        Routes through ``route_chat`` (lazily imported, mirroring
        ``_decompose``) so tests can patch it without hitting a live LLM.
        """
        from ai.engine.core.config import get_settings
        from ai.engine.llm.router import route_chat

        settings = get_settings()
        result = _run_async(
            route_chat(
                task="deep",
                instance_id=PLAN_INSTANCE_ID,
                conversation_id="discovery",
                messages=self._discovery_prompt(brief, turns),
                model=settings.LLM_MODEL,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        )
        text = (result or {}).get("content")
        try:
            data = json.loads((text or "").strip())
        except (json.JSONDecodeError, TypeError):
            data = {}
        action = (data.get("action") or "ask").strip().lower()
        question = (data.get("question") or "").strip()
        if action == "complete":
            return {"action": "complete", "question": None}
        if not question:
            question = (
                "Could you tell me a bit more about what you want to accomplish?"
            )
        return {"action": "ask", "question": question}

    @staticmethod
    def _enrich_brief(brief: str, turns: list) -> str:
        """Fold answered discovery turns into the brief for decomposition."""
        answered = [t for t in turns if (t.get("reply") or "").strip()]
        if not answered:
            return brief
        qa = "\n".join(
            f"Q: {(t.get('question') or '').strip()}\n"
            f"A: {(t.get('reply') or '').strip()}"
            for t in answered
        )
        return f"{brief}\n\nRequirements clarified during discovery:\n{qa}"

    def start_discovery(self, user, brief: str, conversation_id: str = "") -> dict:
        """Begin a guided discovery conversation (W5-B).

        Creates a Run in ``discovering`` state (no plan yet) and returns the
        first clarifying question from Pulse as the opening ``discovery_turn``
        frame. Out-of-scope briefs (advisory / personal leave / abuse) return
        a route payload without creating a stuck discovering run.
        """
        from ai.engine.cognition.scope_route import scope_route, status_for_route
        from ai.models.core import Run, generate_uuid

        brief = (brief or "").strip()
        if not brief:
            raise ValueError("brief is required.")
        if len(brief) > 4000:
            raise ValueError("brief is too long (max 4000 characters).")

        route = scope_route(brief, stage="brief")
        try:
            from ai.pulse_ux_telemetry import emit_ux
            emit_ux(
                "agent.scope_route",
                stage="brief",
                cls=getattr(route, "cls", None),
                plannable=bool(getattr(route, "plannable", False)),
            )
        except Exception:  # noqa: BLE001
            pass
        if not route.plannable:
            logger.info(
                "Discovery gated class=%s brief=%r",
                route.cls, brief[:80],
            )
            return {
                "id": None,
                "status": status_for_route(route),
                "run_status": None,
                "brief": brief,
                "question": None,
                "turns": [],
                "conversation_id": conversation_id or "",
                "route": route.to_dict(),
                "plannable": False,
            }

        first = self._ask_discovery_llm(brief, [])
        turns = [{"question": first["question"], "reply": None}]

        run_id = generate_uuid()
        Run.objects.create(
            id=run_id,
            instance_id=PLAN_INSTANCE_ID,
            conversation_id=conversation_id or "",
            host_user_id=str(user.pk),
            user_message=brief,
            status=STATUS_DISCOVERING,
            plan_json={"discovery_turns": turns, "brief": brief},
        )

        logger.info(
            "Discovery started id=%s user=%s question=%r",
            run_id, str(user.pk), first["question"],
        )
        return {
            "id": run_id,
            "status": "needs_input",
            "run_status": STATUS_DISCOVERING,
            "brief": brief,
            "question": first["question"],
            "turns": turns,
            "conversation_id": conversation_id or "",
            "route": route.to_dict(),
            "plannable": True,
        }

    def advance_discovery(self, user, plan_id: str, user_reply: str) -> dict:
        """Advance a discovery conversation by one user reply (W5-B).

        Appends the reply to ``discovery_turns``, asks Pulse for the next
        question or completion. On completion the enriched brief (original
        brief + discovery answers) is decomposed into a full plan and the Run
        transitions to ``pending_approval`` (RULE_21 — review only).
        Mid-loop digressions (leave, trivia) return a route card without
        forcing another platform outcome question.
        """
        from ai.engine.cognition.scope_route import scope_route, status_for_route

        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_DISCOVERING:
            raise PlanNotRunnableError(
                f"Only discovering plans accept replies (status: {run.status})."
            )

        reply = (user_reply or "").strip()
        if not reply:
            raise ValueError("reply is required.")

        plan_json = _coerce_plan_json(run.plan_json)
        turns = list(plan_json.get("discovery_turns") or [])
        brief = plan_json.get("brief") or run.user_message or ""

        # Fill the current pending turn with the user's reply.
        filled = False
        for turn in turns:
            if not (turn.get("reply") or "").strip():
                turn["reply"] = reply
                filled = True
                break
        if not filled:
            turns.append({"question": "", "reply": reply})

        reply_route = scope_route(reply, stage="reply")
        if not reply_route.plannable:
            run.plan_json = {
                "discovery_turns": turns,
                "brief": brief,
                "scope_route": reply_route.to_dict(),
            }
            run.save(update_fields=["plan_json", "updated_at"])
            logger.info(
                "Discovery digression id=%s class=%s",
                run.id, reply_route.cls,
            )
            return {
                "id": run.id,
                "status": status_for_route(reply_route),
                "run_status": STATUS_DISCOVERING,
                "question": None,
                "plan": None,
                "turns": turns,
                "route": reply_route.to_dict(),
                "plannable": False,
            }

        if len(turns) >= self.DISCOVERY_MAX_TURNS:
            decision = {"action": "complete", "question": None}
        else:
            decision = self._ask_discovery_llm(brief, turns)

        if decision.get("action") == "complete":
            return self._finalize_discovery_run(user, run, brief, turns)

        next_question = decision.get("question")
        turns.append({"question": next_question, "reply": None})
        run.plan_json = {"discovery_turns": turns, "brief": brief}
        run.save(update_fields=["plan_json", "updated_at"])

        return {
            "id": run.id,
            "status": "needs_input",
            "run_status": STATUS_DISCOVERING,
            "question": next_question,
            "plan": None,
            "turns": turns,
            "plannable": True,
        }

    def finalize_discovery(self, user, plan_id: str) -> dict:
        """Force-complete discovery with the current brief (no more questions).

        Used when the brief is already actionable or the user skips clarifying
        questions — prevents runs stuck forever in ``discovering`` with 0 steps.
        Out-of-scope briefs are refused instead of decomposing nonsense.
        """
        from ai.engine.cognition.scope_route import scope_route, status_for_route

        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_DISCOVERING:
            raise PlanNotRunnableError(
                f"Only discovering plans can be finalized (status: {run.status})."
            )
        plan_json = _coerce_plan_json(run.plan_json)
        turns = list(plan_json.get("discovery_turns") or [])
        brief = plan_json.get("brief") or run.user_message or ""
        # Keep answered turns; drop unanswered trailing questions.
        cleaned = []
        for t in turns:
            q = (t.get("question") or "").strip()
            r = (t.get("reply") or "").strip()
            if r:
                cleaned.append({"question": q, "reply": r})
            elif not q:
                continue
            # unanswered question — omit

        gate_text = self._enrich_brief(brief, cleaned)
        route = scope_route(gate_text, stage="brief")
        if not route.plannable:
            return {
                "id": run.id,
                "status": status_for_route(route),
                "run_status": STATUS_DISCOVERING,
                "plan": None,
                "turns": cleaned,
                "route": route.to_dict(),
                "plannable": False,
            }

        return self._finalize_discovery_run(user, run, brief, cleaned)

    def _finalize_discovery_run(self, user, run, brief: str, turns: list) -> dict:
        """Decompose enriched brief → pending_approval plan with steps."""
        from ai.models.core import RunStep

        enriched = self._enrich_brief(brief, turns)
        plan = self._decompose(user, enriched)
        plan_dict = self._plan_to_dict(plan)
        plan_dict["discovery_turns"] = turns
        plan_dict["brief"] = brief

        run.plan_json = plan_dict
        run.status = STATUS_PENDING_APPROVAL
        run.save(update_fields=["plan_json", "status", "updated_at"])

        RunStep.objects.filter(run_id=run.id).delete()
        for step in plan.steps:
            RunStep.objects.create(
                run_id=run.id,
                step_index=step.step_id,
                intent=step.intent,
                tool_name=step.tool_name,
                tool_args_json=step.tool_args or {},
                depends_on_json=step.depends_on or [],
                status=STEP_PENDING,
            )

        logger.info(
            "Discovery complete id=%s user=%s steps=%d",
            run.id, str(user.pk), len(plan.steps),
        )
        return {
            "id": run.id,
            "status": "plan_ready",
            "run_status": STATUS_PENDING_APPROVAL,
            "question": None,
            "plan": self.get_plan(user, run.id),
            "turns": turns,
        }

    def get_plan(self, user, plan_id: str) -> dict:
        """Fetch a plan + its steps (owner-scoped)."""
        run = self._get_owned_run(user, plan_id)
        from ai.models.core import RunStep

        steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
        return self._serialize_run(run, steps=steps)

    def list_plans(self, user, limit: int = 50) -> dict:
        """List the requesting user's plans, newest first."""
        from ai.models.core import Run

        limit = max(1, min(int(limit or 50), 100))
        runs = list(
            Run.objects.filter(
                host_user_id=str(user.pk), instance_id=PLAN_INSTANCE_ID
            ).order_by("-created_at")[:limit]
        )
        return {
            "plans": [self._serialize_run(run) for run in runs],
            "count": len(runs),
        }

    # ── W5-C: artifact delivery ───────────────────────────────────────────

    def list_artifacts(self, user, plan_id: str) -> dict:
        """List the artifacts attached to a plan (owner-scoped)."""
        from ai.models.core import RunArtifact

        run = self._get_owned_run(user, plan_id)
        artifacts = list(
            RunArtifact.objects.filter(run_id=run.id).order_by("created_at")
        )
        return {
            "plan_id": run.id,
            "artifacts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "mime_type": a.mime_type,
                    "size_bytes": a.size_bytes,
                    "step_index": a.step_index,
                    "download_url": _artifact_download_url(run.id, a.id),
                    "created_at": (
                        a.created_at.isoformat() if a.created_at else None
                    ),
                }
                for a in artifacts
            ],
            "count": len(artifacts),
        }

    def get_artifact(self, user, plan_id: str, artifact_id):
        """Fetch an artifact row (owner-scoped) for download streaming."""
        from ai.models.core import RunArtifact

        run = self._get_owned_run(user, plan_id)
        try:
            return RunArtifact.objects.get(id=artifact_id, run_id=run.id)
        except (RunArtifact.DoesNotExist, ValueError, TypeError):
            raise PlanNotAccessibleError(f"Artifact {artifact_id} not found.")

    def delete_artifact(self, user, plan_id: str, artifact_id) -> dict:
        """Hard-delete a plan artifact (file + row), owner-scoped."""
        artifact = self.get_artifact(user, plan_id, artifact_id)
        deleted_id = artifact.id
        # Remove the media file first so orphaned blobs never accumulate.
        try:
            if artifact.file:
                artifact.file.delete(save=False)
        except Exception:  # noqa: BLE001 - DB row must still go even if file is gone
            logger.warning(
                "Could not delete artifact file for id=%s plan=%s",
                deleted_id, plan_id, exc_info=True,
            )
        artifact.delete()
        return {"deleted": deleted_id, "plan_id": plan_id}

    # ── Consent: plan-level approve ───────────────────────────────────────

    def approve_plan(self, user, plan_id: str) -> dict:
        """Approve a pending_approval plan for execution (RULE_21 gate).

        Returns the plan payload; execution itself happens on ``run``.
        """
        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PENDING_APPROVAL:
            raise PlanNotRunnableError(
                f"Only pending plans can be approved (status: {run.status})."
            )
        run.status = STATUS_APPROVED
        run.save(update_fields=["status", "updated_at"])
        logger.info("Plan approved id=%s user=%s", plan_id, str(user.pk))
        return self.get_plan(user, plan_id)

    def decline_plan(self, user, plan_id: str) -> dict:
        """Decline a pending_approval plan — nothing is executed."""
        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PENDING_APPROVAL:
            raise PlanNotRunnableError(
                f"Only pending plans can be declined (status: {run.status})."
            )
        run.status = STATUS_CANCELLED
        run.save(update_fields=["status", "updated_at"])
        from ai.models.core import RunStep

        RunStep.objects.filter(run_id=run.id, status=STEP_PENDING).update(
            status=STEP_SKIPPED
        )
        return self.get_plan(user, plan_id)

    def delete_plan(self, user, plan_id: str) -> dict:
        """Delete a terminal-state plan (cancelled / failed / completed only)."""
        run = self._get_owned_run(user, plan_id)
        if run.status not in (STATUS_CANCELLED, STATUS_FAILED, STATUS_COMPLETED):
            raise PlanNotRunnableError(
                f"Only cancelled, failed, or completed plans can be deleted "
                f"(status: {run.status})."
            )
        run.delete()
        return {"deleted": True, "plan_id": plan_id}

    # ── W3-C: edit / pause / resume / fork ────────────────────────────────

    def edit_plan(
        self,
        user,
        plan_id: str,
        brief=None,
        step_deltas=None,
        mode: str = "replan",
    ) -> dict:
        """Edit a plan — ``mode=rename`` (label only) or ``mode=replan``.

        **rename** updates ``user_message`` only: no decompose, no step wipe,
        no status change.

        **replan** prefers a surgical edit when the feedback is additive
        (e.g. "add a chart") or ``step_deltas`` are supplied — full
        ``SkillAwarePlanner.decompose`` only for genuine brief rewrites.
        Near-duplicate intents are always collapsed. Editing NEVER
        auto-approves (RULE_21). Non-``pending_approval`` plans drop back
        to ``pending_approval``. A ``pre_edit_snapshot`` is stashed so
        Cancel can restore via ``discard_plan_edit``.
        """
        run = self._get_owned_run(user, plan_id)
        mode = (mode or "replan").strip().lower()
        if mode not in ("rename", "replan"):
            raise ValueError("mode must be 'rename' or 'replan'.")

        new_brief = (brief if brief is not None else run.user_message or "").strip()
        if not new_brief:
            raise ValueError("brief is required.")
        if len(new_brief) > 4000:
            raise ValueError("brief is too long (max 4000 characters).")

        if mode == "rename":
            run.user_message = new_brief
            plan_json = dict(_coerce_plan_json(run.plan_json))
            if plan_json:
                plan_json["brief"] = new_brief
                run.plan_json = plan_json
                run.save(
                    update_fields=["user_message", "plan_json", "updated_at"]
                )
            else:
                run.save(update_fields=["user_message", "updated_at"])
            logger.info(
                "Plan renamed id=%s user=%s", plan_id, str(user.pk),
            )
            result = self.get_plan(user, plan_id)
            result["diff"] = {"added": [], "removed": [], "changed": []}
            result["replan_gate"] = False
            result["edit_mode"] = "rename"
            return result

        old_plan_json = _coerce_plan_json(run.plan_json)
        old_steps = [
            s for s in old_plan_json.get("steps", []) if isinstance(s, dict)
        ]

        self._stash_pre_edit_snapshot(run)

        # Surgical paths — never wipe a good topology for "add a chart".
        if step_deltas:
            base = [dict(s) for s in old_steps] if old_steps else []
            if not base:
                plan = self._decompose(user, new_brief)
                base = self._plan_to_dict(plan)["steps"]
                plan_dict = self._plan_to_dict(plan)
            else:
                plan_dict = dict(old_plan_json)
            steps = self._dedupe_plan_steps(
                self._apply_step_deltas(base, step_deltas)
            )
            plan_dict["brief"] = new_brief
            plan_dict["steps"] = steps
            edit_kind = "delta"
        elif old_steps and self._is_incremental_plan_feedback(
            run.user_message or "", new_brief
        ):
            steps = self._surgical_incremental_steps(old_steps, new_brief)
            plan_dict = dict(old_plan_json)
            spine = (run.user_message or new_brief).strip()
            note = new_brief.strip()
            if len(note) <= 320 and note.lower() not in spine.lower():
                plan_dict["brief"] = f"{spine.rstrip('.')}. Also: {note}"
                new_brief = plan_dict["brief"]
            else:
                plan_dict["brief"] = new_brief
            plan_dict["steps"] = steps
            edit_kind = "incremental"
        else:
            plan = self._decompose(user, new_brief)
            plan_dict = self._plan_to_dict(plan)
            steps = self._dedupe_plan_steps(plan_dict.get("steps") or [])
            # Guard: if the LLM replan cloned the same intent 2+ times, keep
            # the prior spine and apply incremental surgery instead.
            fps = [self._intent_fingerprint(s.get("intent")) for s in (plan_dict.get("steps") or [])]
            dup_count = len(fps) - len({f for f in fps if f})
            if old_steps and dup_count >= 2:
                steps = self._surgical_incremental_steps(old_steps, new_brief)
                plan_dict = dict(old_plan_json)
                plan_dict["brief"] = new_brief
                plan_dict["steps"] = steps
                edit_kind = "incremental_guard"
            else:
                plan_dict["steps"] = steps
                edit_kind = "replan"

        diff = self._plan_diff(old_steps, steps)
        replan_gate = run.status != STATUS_PENDING_APPROVAL

        run.user_message = new_brief
        run.plan_json = plan_dict
        if replan_gate:
            run.status = STATUS_PENDING_APPROVAL
        run.save(
            update_fields=[
                "user_message",
                "plan_json",
                "status",
                "working_notes",
                "updated_at",
            ]
        )
        self._replace_run_steps(run.id, steps)

        logger.info(
            "Plan edited id=%s user=%s kind=%s replan_gate=%s added=%d removed=%d changed=%d",
            plan_id, str(user.pk), edit_kind, replan_gate,
            len(diff["added"]), len(diff["removed"]), len(diff["changed"]),
        )
        result = self.get_plan(user, plan_id)
        result["diff"] = diff
        result["replan_gate"] = replan_gate
        result["edit_mode"] = edit_kind
        return result

    def edit_step(self, user, plan_id: str, step_id, title=None,
                  instructions=None, depends_on=None) -> dict:
        """Edit one plan step — ``title`` → intent, plus instructions and
        depends_on — with the same diff-review rule as ``edit_plan``.

        A non-pending plan drops to ``pending_approval`` and all step
        execution state resets to ``pending``: the edited plan must be
        re-approved before anything executes (RULE_21).

        W6-E F-28 steering: on a PAUSED run, editing a not-yet-executed
        (``pending``) step's service-owned metadata (``instructions``/
        ``intent``) keeps the plan paused and is honored on resume — no
        re-approval, no ledger wipe. Editing an executed or consent-awaiting
        step on a paused run still drops to ``pending_approval`` (RULE_21).
        """
        from ai.models.core import RunStep

        run = self._get_owned_run(user, plan_id)
        plan_json = dict(_coerce_plan_json(run.plan_json))
        old_steps = [
            dict(s) for s in plan_json.get("steps", []) if isinstance(s, dict)
        ]
        steps = [dict(s) for s in old_steps]
        target = next(
            (s for s in steps if s.get("step_id") == int(step_id)), None
        )
        if target is None:
            raise PlanStepError(f"Step {step_id} not found on plan {run.id}.")

        if title is not None:
            title = str(title).strip()
            if title:
                target["intent"] = title
        if instructions is not None:
            target["instructions"] = str(instructions).strip()
        if depends_on is not None:
            target["depends_on"] = depends_on

        step_row = RunStep.objects.filter(
            run_id=run.id, step_index=int(step_id)
        ).first()
        # F-28: paused run + a step that has not executed yet → steer in
        # place (stay paused, resume honors the edit).
        steer_paused = (
            run.status == STATUS_PAUSED
            and step_row is not None
            and step_row.status == STEP_PENDING
        )

        plan_json["steps"] = steps
        run.plan_json = plan_json
        if steer_paused:
            replan_gate = False
            run.save(update_fields=["plan_json", "updated_at"])
            # Refresh just this step's metadata; execution state stays
            # pending so the resume re-runs it with the edited instructions.
            RunStep.objects.filter(
                run_id=run.id, step_index=int(step_id)
            ).update(
                intent=target["intent"],
                depends_on_json=target.get("depends_on") or [],
                status=STEP_PENDING,
                draft_text=None,
                critic_verdict=None,
                error=None,
                confirmation_token=None,
                tool_output_json=None,
            )
        else:
            replan_gate = run.status != STATUS_PENDING_APPROVAL
            if replan_gate:
                self._stash_pre_edit_snapshot(run)
                run.status = STATUS_PENDING_APPROVAL
                run.save(
                    update_fields=[
                        "plan_json", "status", "working_notes", "updated_at",
                    ]
                )
            else:
                run.save(update_fields=["plan_json", "updated_at"])

            # Reset execution state — the edited plan goes back to review.
            RunStep.objects.filter(run_id=run.id).update(
                status=STEP_PENDING,
                draft_text=None,
                critic_verdict=None,
                error=None,
                confirmation_token=None,
                tool_output_json=None,
            )
            RunStep.objects.filter(
                run_id=run.id, step_index=int(step_id)
            ).update(
                intent=target["intent"],
                depends_on_json=target.get("depends_on") or [],
            )

        diff = self._plan_diff(old_steps, steps, key="step_id")
        logger.info(
            "Plan step edited id=%s step=%s user=%s replan_gate=%s",
            plan_id, step_id, str(user.pk), replan_gate,
        )
        result = self.get_plan(user, plan_id)
        result["diff"] = diff
        result["replan_gate"] = replan_gate
        return result

    def pause_plan(self, user, plan_id: str) -> dict:
        """Pause a running plan (ledger-level).

        Only ``running`` → ``paused``. Step rows are left untouched — a step
        already ``awaiting_approval`` (consent pause) keeps its state; a plan
        pause never corrupts the consent gate.
        """
        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_RUNNING:
            raise PlanNotRunnableError(
                f"Only running plans can be paused (status: {run.status})."
            )
        run.status = STATUS_PAUSED
        run.save(update_fields=["status", "updated_at"])
        logger.info("Plan paused id=%s user=%s", plan_id, str(user.pk))
        return self.get_plan(user, plan_id)

    def resume_plan(self, user, plan_id: str) -> dict:
        """Pre-flight a resume: re-enter execution from ``paused``/``approved``.

        Reuses ``_RUNNABLE_STATUSES``; the actual re-entry into
        ``run_plan_stream`` (with ``resume_run_id=plan_id``) happens through
        the streaming run path.
        """
        run = self._get_owned_run(user, plan_id)
        if run.status not in _RUNNABLE_STATUSES:
            raise PlanNotRunnableError(
                f"Plan is not runnable (status: {run.status}). "
                "Resume from paused or approved only."
            )
        logger.info(
            "Plan resume pre-flighted id=%s user=%s status=%s",
            plan_id, str(user.pk), run.status,
        )
        return {
            "status": "resumed",
            "plan_id": run.id,
            "plan": self.get_plan(user, plan_id),
        }

    def fork_plan(self, user, plan_id: str) -> dict:
        """Clone a plan (plan_json + brief) into a NEW Run row.

        The fork is a copy, not a link: a fresh run id, its own RunStep rows
        (all pending), status ``pending_approval``. ``forked_from`` provenance
        is recorded in ``working_notes`` (no schema change — the engine never
        reads it).
        """
        from ai.models.core import Run, RunStep, generate_uuid

        source = self._get_owned_run(user, plan_id)
        plan_json = json.loads(json.dumps(source.plan_json or {}))
        steps = [
            s for s in plan_json.get("steps", []) if isinstance(s, dict)
        ]

        fork_id = generate_uuid()
        fork = Run(
            id=fork_id,
            instance_id=source.instance_id or PLAN_INSTANCE_ID,
            conversation_id=source.conversation_id or "",
            host_user_id=str(user.pk),
            user_message=source.user_message,
            status=STATUS_PENDING_APPROVAL,
            plan_json=plan_json,
            working_notes={"forked_from": source.id},
        )
        fork.save()
        for step in steps:
            RunStep.objects.create(
                run_id=fork_id,
                step_index=int(step.get("step_id", 0)),
                intent=step.get("intent", ""),
                tool_name=step.get("tool_name"),
                tool_args_json=step.get("tool_args") or {},
                depends_on_json=step.get("depends_on") or [],
                status=STEP_PENDING,
            )
        logger.info(
            "Plan forked id=%s from=%s user=%s",
            fork_id, source.id, str(user.pk),
        )
        return self.get_plan(user, fork_id)

    # ── W3-D: plan templates (Gap #3) ─────────────────────────────────────

    @staticmethod
    def _serialize_template(tpl) -> dict:
        """Product-facing template payload (RULE_23 — outcome terms only)."""
        plan_json = tpl.plan_json or {}
        steps = [s for s in plan_json.get("steps", []) if isinstance(s, dict)]
        return {
            "id": tpl.id,
            "name": tpl.name,
            "description": tpl.description or "",
            "source_plan_id": tpl.source_plan_id,
            "pattern": plan_json.get("pattern", "custom"),
            "skill_name": plan_json.get("skill_name"),
            "step_count": len(steps),
            "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
            "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
        }

    def promote_template(
        self, user, plan_id: str, name: str, description: str = ""
    ) -> dict:
        """Promote a plan's ``plan_json`` into a reusable template.

        Saving a template is a durable *read-only copy* of the plan shape —
        it never mutates domain data, so no step-level consent gate applies
        (the plan itself was already reviewed). The template captures the
        approved/executed step structure, not execution state.
        """
        from ai.models.core import PlanTemplate, generate_uuid

        source = self._get_owned_run(user, plan_id)
        name = (name or "").strip()
        if not name:
            raise ValueError("name is required.")
        if len(name) > 200:
            raise ValueError("name is too long (max 200 characters).")

        tpl = PlanTemplate(
            id=generate_uuid(),
            host_user_id=str(user.pk),
            name=name,
            description=(description or "").strip(),
            plan_json=json.loads(json.dumps(source.plan_json or {})),
            source_plan_id=source.id,
        )
        tpl.save()
        logger.info(
            "Plan template created id=%s from=%s user=%s",
            tpl.id, source.id, str(user.pk),
        )
        return self._serialize_template(tpl)

    def list_templates(self, user) -> dict:
        """List the requesting user's templates, newest first."""
        from ai.models.core import PlanTemplate

        templates = list(
            PlanTemplate.objects.filter(host_user_id=str(user.pk)).order_by(
                "-created_at"
            )
        )
        return {
            "templates": [self._serialize_template(t) for t in templates],
            "count": len(templates),
        }

    def create_from_template(self, user, template_id: str) -> dict:
        """Instantiate a template into a NEW reviewable plan (``pending_approval``).

        Reuses the ``fork_plan`` clone path (fresh Run + fresh pending RunStep
        rows) with ``from_template`` provenance — instantiation never
        auto-approves or executes (RULE_21).
        """
        from ai.models.core import PlanTemplate, Run, RunStep, generate_uuid

        try:
            tpl = PlanTemplate.objects.get(
                id=template_id, host_user_id=str(user.pk)
            )
        except PlanTemplate.DoesNotExist:
            raise PlanNotAccessibleError(f"Template {template_id} not found.")

        plan_json = json.loads(json.dumps(tpl.plan_json or {}))
        steps = [s for s in plan_json.get("steps", []) if isinstance(s, dict)]

        run_id = generate_uuid()
        run = Run(
            id=run_id,
            instance_id=PLAN_INSTANCE_ID,
            conversation_id="",
            host_user_id=str(user.pk),
            user_message=tpl.name,
            status=STATUS_PENDING_APPROVAL,
            plan_json=plan_json,
            working_notes={"from_template": tpl.id},
        )
        run.save()
        for step in steps:
            RunStep.objects.create(
                run_id=run_id,
                step_index=int(step.get("step_id", 0)),
                intent=step.get("intent", ""),
                tool_name=step.get("tool_name"),
                tool_args_json=step.get("tool_args") or {},
                depends_on_json=step.get("depends_on") or [],
                status=STEP_PENDING,
            )
        logger.info(
            "Plan instantiated id=%s from_template=%s user=%s",
            run_id, tpl.id, str(user.pk),
        )
        return self.get_plan(user, run_id)

    # ── W6-E F-29: scheduling / triggers ──────────────────────────────────

    @staticmethod
    def _cron_trigger(cron_expr: str):
        """Build an apscheduler ``CronTrigger`` from a standard 5-field cron expr."""
        from apscheduler.triggers.cron import CronTrigger

        return CronTrigger.from_crontab(cron_expr)

    def create_schedule(
        self,
        user,
        name: str,
        *,
        template_id: str | None = None,
        plan_json: dict | None = None,
        cron_expr: str | None = None,
        run_at=None,
        description: str | None = None,
    ) -> dict:
        """Create a ``RunSchedule`` — recurring ``cron_expr`` or one-off ``run_at``.

        ``template_id`` (a template the requesting user owns) or a
        ``plan_json`` snapshot supplies the plan shape. ``next_run_at`` is
        computed eagerly so ``run_due_schedules`` only compares timestamps
        (deterministic and idempotent).
        """
        from ai.models.core import PlanTemplate, RunSchedule, generate_uuid

        name = (name or "").strip()
        if not name:
            raise ValueError("name is required.")
        if template_id and plan_json:
            raise ValueError("Provide template_id OR plan_json, not both.")
        if not template_id and not plan_json:
            raise ValueError("template_id or plan_json is required.")
        if bool(cron_expr) == bool(run_at):
            raise ValueError("Provide exactly one of cron_expr or run_at.")

        tpl = None
        if template_id:
            try:
                tpl = PlanTemplate.objects.get(
                    id=template_id, host_user_id=str(user.pk)
                )
            except PlanTemplate.DoesNotExist:
                raise PlanNotAccessibleError(
                    f"Template {template_id} not found."
                )

        now = timezone.now()
        next_run: datetime | None = None
        if run_at is not None:
            next_run = run_at
        else:
            next_run = self._cron_trigger(cron_expr).get_next_fire_time(
                None, now
            )

        schedule = RunSchedule(
            id=generate_uuid(),
            instance_id=PLAN_INSTANCE_ID,
            host_user_id=str(user.pk),
            name=name,
            description=(description or "").strip(),
            template=tpl,
            plan_json=(
                json.loads(json.dumps(plan_json)) if plan_json else None
            ),
            cron_expr=cron_expr,
            run_at=run_at,
            next_run_at=next_run,
        )
        schedule.save()
        logger.info(
            "RunSchedule created id=%s user=%s cron=%s run_at=%s next=%s",
            schedule.id, str(user.pk), cron_expr, run_at, next_run,
        )
        return self._serialize_schedule(schedule)

    @staticmethod
    def _format_clock(hour: int, minute: int) -> str:
        """Format an hour/minute as ``9:00 AM`` / ``2:00 PM`` (12-hour)."""
        ampm = "AM" if hour < 12 else "PM"
        h12 = hour % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{minute:02d} {ampm}"

    @staticmethod
    def _ordinal(n: int) -> str:
        """English ordinal for a day-of-month (``1`` → ``1st``)."""
        n = int(n)
        if 11 <= (n % 100) <= 13:
            return f"{n}th"
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    @staticmethod
    def _schedule_preview(schedule) -> str:
        """Plain-language outcome copy for a schedule (RULE_23).

        One-off → ``"Once on 2026-08-25 at 2:00 PM"``; recurring → ``"Every day
        at 9:00 AM"`` / ``"Every Monday at 9:00 AM"`` / ``"Every 1st of the
        month at 9:00 AM"``. Raw ``cron_expr`` stays in the payload for power
        users — never surfaced here, and never engine/thread/fan-out terms.
        Times are rendered in the project's configured display timezone
        (admin-configurable via ``accounts.GeneralConfig.timezone``), default
        ``Africa/Cairo``.
        """
        if schedule.run_at:
            local = timezone.localtime(
                schedule.run_at, timezone=_display_timezone()
            )
            return (
                f"Once on {local.strftime('%Y-%m-%d')} at "
                f"{PlansService._format_clock(local.hour, local.minute)}"
            )
        expr = (schedule.cron_expr or "").strip()
        if not expr:
            return "Once"
        fields = expr.split()
        if len(fields) != 5:
            return "On a recurring schedule"
        minute, hour, dom, month, dow = fields
        try:
            h = int(hour)
            m = int(minute)
        except ValueError:
            # Sub-daily / non-clock cadence — keep outcome copy generic.
            return "On a recurring schedule"
        time_str = PlansService._format_clock(h, m)
        if dom == "*" and month == "*":
            if dow == "*":
                return f"Every day at {time_str}"
            if dow.isdigit() and 0 <= int(dow) <= 7:
                name = _CRON_WEEKDAY_NAMES[0 if int(dow) == 7 else int(dow)]
                return f"Every {name} at {time_str}"
        if dow == "*" and month == "*" and dom.isdigit():
            return (
                f"Every {PlansService._ordinal(int(dom))} of the month "
                f"at {time_str}"
            )
        return f"On a recurring schedule at {time_str}"

    @staticmethod
    def _schedule_owner(schedule) -> str:
        """Resolve a schedule's owner to a display name (best-effort).

        Returns ``display_name`` → ``full name`` → ``username``, or ``""`` when
        the owner is unresolvable (deleted user). Never leaks a raw PK.
        """
        if not schedule.host_user_id:
            return ""
        try:
            from django.contrib.auth import get_user_model

            owner = get_user_model().objects.get(pk=schedule.host_user_id)
            return (
                getattr(owner, "display_name", "")
                or owner.get_full_name()
                or owner.username
            )
        except Exception:  # noqa: BLE001 - best-effort owner resolution
            return ""

    @staticmethod
    def _serialize_schedule(schedule) -> dict:
        """Product-facing schedule payload (RULE_23 — outcome terms only)."""
        return {
            "id": schedule.id,
            "name": schedule.name,
            "description": schedule.description,
            "owner": PlansService._schedule_owner(schedule),
            "cron_expr": schedule.cron_expr,
            "run_at": schedule.run_at.isoformat() if schedule.run_at else None,
            "enabled": schedule.enabled,
            "last_run_at": (
                schedule.last_run_at.isoformat()
                if schedule.last_run_at else None
            ),
            "next_run_at": (
                schedule.next_run_at.isoformat()
                if schedule.next_run_at else None
            ),
            "template_id": schedule.template_id,
            "preview": PlansService._schedule_preview(schedule),
            "created_at": (
                schedule.created_at.isoformat()
                if schedule.created_at else None
            ),
        }

    def list_schedules(self, user) -> dict:
        """List the requesting user's schedules (owner scoping), soonest first."""
        from ai.models.core import RunSchedule

        schedules = list(
            RunSchedule.objects.filter(host_user_id=str(user.pk)).order_by(
                "next_run_at"
            )
        )
        return {
            "schedules": [self._serialize_schedule(s) for s in schedules],
            "count": len(schedules),
        }

    def delete_schedule(self, user, schedule_id: str) -> dict:
        """Delete a schedule the requesting user owns (CBAC)."""
        from ai.models.core import RunSchedule

        deleted, _ = RunSchedule.objects.filter(
            id=schedule_id, host_user_id=str(user.pk)
        ).delete()
        if not deleted:
            raise PlanNotAccessibleError(f"Schedule {schedule_id} not found.")
        logger.info("RunSchedule deleted id=%s user=%s", schedule_id, str(user.pk))
        return {"deleted": True, "schedule_id": schedule_id}

    def edit_schedule(
        self,
        user,
        schedule_id: str,
        *,
        name=None,
        description=None,
        cron_expr=None,
        run_at=None,
    ) -> dict:
        """Edit a schedule's name/description/trigger, recomputing ``next_run_at``.

        PATCH semantics: only supplied fields change. Supplying ``run_at``
        switches to a one-off trigger; supplying ``cron_expr`` switches to a
        recurring trigger. ``next_run_at`` is recomputed eagerly so
        ``run_due_schedules`` stays a pure timestamp comparison.
        """
        from ai.models.core import RunSchedule

        try:
            schedule = RunSchedule.objects.get(
                id=schedule_id, host_user_id=str(user.pk)
            )
        except RunSchedule.DoesNotExist:
            raise PlanNotAccessibleError(f"Schedule {schedule_id} not found.")

        update_fields = ["updated_at"]
        if name is not None:
            name = str(name).strip()
            if not name:
                raise ValueError("name is required.")
            schedule.name = name
            update_fields.append("name")
        if description is not None:
            schedule.description = str(description).strip()
            update_fields.append("description")

        # Trigger swap — a caller supplies at most one of cron_expr / run_at.
        if run_at is not None:
            schedule.run_at = run_at
            schedule.cron_expr = None
            update_fields += ["run_at", "cron_expr"]
        elif cron_expr is not None:
            schedule.cron_expr = cron_expr
            schedule.run_at = None
            update_fields += ["cron_expr", "run_at"]

        # Recompute next_run_at from the (possibly updated) trigger.
        now = timezone.now()
        if schedule.run_at is not None:
            schedule.next_run_at = schedule.run_at
        elif schedule.cron_expr:
            schedule.next_run_at = self._cron_trigger(
                schedule.cron_expr
            ).get_next_fire_time(None, now)
        else:
            schedule.next_run_at = None
        update_fields.append("next_run_at")

        schedule.save(update_fields=update_fields)
        logger.info(
            "RunSchedule edited id=%s user=%s next=%s",
            schedule_id, str(user.pk), schedule.next_run_at,
        )
        return self._serialize_schedule(schedule)

    def pause_schedule(self, user, schedule_id: str) -> dict:
        """Toggle a schedule's ``enabled`` flag (pause without deletion)."""
        from ai.models.core import RunSchedule

        try:
            schedule = RunSchedule.objects.get(
                id=schedule_id, host_user_id=str(user.pk)
            )
        except RunSchedule.DoesNotExist:
            raise PlanNotAccessibleError(f"Schedule {schedule_id} not found.")

        schedule.enabled = not schedule.enabled
        schedule.save(update_fields=["enabled", "updated_at"])
        logger.info(
            "RunSchedule pause toggled id=%s user=%s enabled=%s",
            schedule_id, str(user.pk), schedule.enabled,
        )
        return self._serialize_schedule(schedule)

    def materialize_due_schedules(self, *, dry_run: bool = False) -> dict:
        """Materialize every due schedule into a fresh ``pending_approval`` Run.

        Idempotent contract (F-29): due = ``enabled`` AND ``next_run_at <=
        now``. Each due schedule is claimed with an atomic compare-and-set on
        ``next_run_at`` so concurrent invocations fire exactly once. Runs are
        ``pending_approval`` (RULE_21 — nothing executes without approval),
        owned by the schedule's owner (CBAC), with ``working_notes``
        provenance. Cron schedules advance to their next occurrence;
        one-offs disable themselves after firing.
        """
        from ai.models.core import Run, RunSchedule, RunStep, generate_uuid

        now = timezone.now()
        due = list(
            RunSchedule.objects.filter(
                enabled=True, next_run_at__lte=now
            ).order_by("next_run_at")
        )
        materialized: list[dict] = []
        for s in due:
            plan_json = (
                json.loads(json.dumps(s.template.plan_json or {}))
                if s.template_id
                else json.loads(json.dumps(s.plan_json or {}))
            )
            if not plan_json.get("steps"):
                # Nothing materializable — leave due for inspection.
                continue
            if dry_run:
                materialized.append(
                    {"schedule_id": s.id, "name": s.name, "run_id": None}
                )
                continue
            # Atomic claim — exactly one concurrent invoker wins.
            claimed = RunSchedule.objects.filter(
                id=s.id, next_run_at=s.next_run_at
            ).update(last_run_at=now, updated_at=now)
            if claimed == 0:
                continue
            run_id = generate_uuid()
            run = Run(
                id=run_id,
                instance_id=s.instance_id or PLAN_INSTANCE_ID,
                conversation_id="",
                host_user_id=s.host_user_id,
                user_message=s.name,
                status=STATUS_PENDING_APPROVAL,
                plan_json=plan_json,
                working_notes={
                    "schedule_id": s.id,
                    "scheduled_at": s.next_run_at.isoformat(),
                },
            )
            run.save()
            for step in plan_json.get("steps", []):
                if not isinstance(step, dict):
                    continue
                RunStep.objects.create(
                    run_id=run_id,
                    step_index=int(step.get("step_id", 0)),
                    intent=step.get("intent", ""),
                    tool_name=step.get("tool_name"),
                    tool_args_json=step.get("tool_args") or {},
                    depends_on_json=step.get("depends_on") or [],
                    status=STEP_PENDING,
                )
            # Advance the schedule.
            if s.cron_expr:
                nxt = self._cron_trigger(s.cron_expr).get_next_fire_time(
                    now, now
                )
                RunSchedule.objects.filter(id=s.id).update(
                    next_run_at=nxt, updated_at=now
                )
            else:
                RunSchedule.objects.filter(id=s.id).update(
                    next_run_at=None, enabled=False, updated_at=now
                )
            materialized.append(
                {
                    "schedule_id": s.id,
                    "name": s.name,
                    "run_id": run_id,
                }
            )
            logger.info(
                "RunSchedule fired id=%s run=%s user=%s dry_run=%s",
                s.id, run_id, s.host_user_id, dry_run,
            )
        return {
            "dry_run": dry_run,
            "materialized": len(materialized),
            "runs": materialized,
        }

    # ── Bounded retry helpers (Gap #2) ────────────────────────────────────

    @staticmethod
    def _retry_backoff_delay(attempt: int) -> float:
        """Fixed exponential backoff: 1s, 2s, 4s … capped at 8s. No jitter."""
        return min(
            RETRY_BASE_DELAY_SECONDS * (2 ** max(attempt - 1, 0)),
            RETRY_MAX_DELAY_SECONDS,
        )

    @staticmethod
    def _mark_run_paused(run) -> None:
        """Mark a run paused (engine re-entry state) before a retry attempt."""
        run.status = STATUS_PAUSED
        run.save(update_fields=["status", "updated_at"])

    @staticmethod
    def _append_retry_audit(run, attempt: int, step_indexes: list) -> None:
        """Record a retry attempt in ``working_notes.audit`` (durable provenance)."""
        notes = dict(run.working_notes or {})
        audit = list(notes.get("audit") or [])
        audit.append(
            {
                "t": timezone.now().isoformat(),
                "kind": "run_retried",
                "step_id": step_indexes[0] if len(step_indexes) == 1 else None,
                "detail": {"attempt": attempt, "re_queued_steps": step_indexes},
            }
        )
        notes["audit"] = audit
        run.working_notes = notes
        run.save(update_fields=["working_notes", "updated_at"])

    async def _execute_plan_once(
        self,
        run,
        plan,
        user_pk: str,
        conversation_id: str,
        instance_config: dict,
        user_info,
    ) -> dict:
        """Run the ReAct loop once in a fresh engine session.

        Extracted from ``_run_plan_frames`` so the retry loop can re-enter the
        engine with a *fresh* SQLAlchemy session per attempt (the same pattern
        as ``DurableExecutionService.resume_run``). Step statuses are written
        durably by the loop; the caller re-reads them via the Django ORM.

        Returns the FlightDirector supervision state (ledger/repairs/fidelity)
        for persistence into ``working_notes.flight``.
        """
        from asgiref.sync import sync_to_async

        from ai.models.core import RunStep
        from ai.engine.core.database import get_session_factory
        from ai.engine.cognition.plan.loop import ReActLoop
        from ai.engine.cognition.turn.draft import DraftWitness
        from ai.engine.cognition.turn.critic import CriticWitness
        from ai.engine.cognition.turn.execute import ExecuteWitness
        from ai.engine.llm.prompts import build_chat_prompt
        from ai.host_executor import CarbonHostExecutor
        from ai.flight_director import FlightDirector

        config = instance_config or {}
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            executor = CarbonHostExecutor(
                db=db,
                instance_config=instance_config,
                user_token=f"inproc:carbon:{user_pk}",
                host_user_id=user_pk,
            )
            system_prompt = await build_chat_prompt(
                instance_name=config.get("display_name", "Carbon"),
                system_description=config.get("description", ""),
                user_info=user_info,
                persona=config.get("persona"),
                api_catalog=config.get("api_catalog"),
                navigation_routes=config.get("navigation_routes"),
                domain_topics=config.get("domain_topics"),
                instance_config=config,
                conversation_id=conversation_id,
                instance_id=PLAN_INSTANCE_ID,
            )
            execute_witness = ExecuteWitness(
                executor=executor,
                run_id=str(run.id),
                instance_id=PLAN_INSTANCE_ID,
                hook_ctx_defaults={
                    "instance_id": PLAN_INSTANCE_ID,
                    "conversation_id": conversation_id,
                    "host_user_id": user_pk,
                    "run_id": str(run.id),
                    "instance_config": instance_config,
                },
            )
            # W4-D Flight Director (additive): in-loop supervisor wired onto
            # the loop. It validates reference args via read-only host GETs and
            # runs the worker-fidelity guard; it never blocks the run.
            flight_director = FlightDirector(executor=executor, run=run)
            loop = ReActLoop(
                draft_witness=DraftWitness(executor=executor),
                critic_witness=CriticWitness(),
                executor=execute_witness,
                db=db,
                flight_director=flight_director,
            )
            # P1.3: a paused consent step resumes WITH its stored token so the
            # mutation re-executes (critic passes → tool runs). The token is
            # resolved PER STEP inside the loop's resume path
            # (``resume_tokens`` built from each ``awaiting_approval``
            # RunStep's own ``confirmation_token``) — a single shared token is
            # deliberately NOT forwarded here (RULE_21: it would let later
            # mutation steps skip their own consent gate).
            # Publish the plan run id for plugins (W5-C): the frozen engine
            # ToolContext has no ``run_id``, so export_document resolves its
            # owning plan from this thread-local during execution.
            set_current_plan_run(str(run.id))
            try:
                wf_raw = (getattr(run, "plan_json", None) or {}).get("workflow_graph")
                wf_ctx: dict = {"status": "ok"}

                async def _on_choice(node_id, chosen, evaluations):
                    # Journal via Django ORM on a worker thread (async-safe).
                    try:
                        await sync_to_async(PlansService.record_workflow_choice)(
                            str(run.id), node_id, dict(wf_ctx),
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "workflow choice journal failed run=%s node=%s",
                            run.id, node_id,
                        )

                async def _on_heal(observe_node_id, proposal):
                    try:
                        await sync_to_async(PlansService.record_workflow_heal)(
                            str(run.id), observe_node_id, proposal.journal_payload,
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "workflow heal journal failed run=%s node=%s",
                            run.id, observe_node_id,
                        )

                async def _on_compensation(failed_sid, comp_sid, comp_node):
                    try:
                        await sync_to_async(PlansService.record_workflow_compensation)(
                            str(run.id), failed_sid, comp_sid, comp_node,
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "workflow compensation journal failed run=%s", run.id,
                        )

                async def _on_wait(node_id, decision, duration_ms=0, until_guard=None):
                    try:
                        await sync_to_async(PlansService.record_workflow_wait)(
                            str(run.id),
                            node_id,
                            duration_ms=int(duration_ms or 0),
                            reason=str(getattr(decision, "reason", "immediate")),
                            until_guard=until_guard,
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "workflow wait journal failed run=%s node=%s",
                            run.id, node_id,
                        )

                await loop.run(
                    plan=plan,
                    instance_id=PLAN_INSTANCE_ID,
                    conversation_id=conversation_id,
                    user_message=run.user_message,
                    system_prompt=system_prompt,
                    instance_config=instance_config,
                    user_info=user_info,
                    host_user_id=user_pk,
                    resume_run_id=run.id,
                    flight_director=flight_director,
                    workflow_graph=wf_raw,
                    workflow_context=wf_ctx,
                    on_workflow_choice=_on_choice,
                    on_heal_proposed=_on_heal,
                    on_compensation_queued=_on_compensation,
                    on_wait_fired=_on_wait,
                )
            finally:
                set_current_plan_run(None)
            return flight_director.state()

    # ── W4-D/25-C: post-run acceptance closure ───────────────────────────

    @staticmethod
    def _step_http_method(step) -> str:
        """HTTP verb of a step's tool call (args override, api_name inference)."""
        args = getattr(step, "tool_args", None) or {}
        method = str(args.get("method", "")).upper()
        if method:
            return method
        api_name = str(args.get("api_name") or "").lower()
        if any(v in api_name for v in (
            "list", "get", "search", "read", "fetch",
        )):
            return "GET"
        return "POST"

    async def _readonly_step_runner(self, step, criterion, instructions,
                                    executor) -> dict:
        """Best-effort repair runner: re-executes a READ-ONLY step only.

        Mutation steps are NEVER auto re-run (RULE_21). Read-only steps
        (``call_host_api`` GET) are re-executed through the host executor; the
        repair instructions ride along in the outcome so the acceptance loop
        records exactly what was attempted and why.
        """
        if self._step_http_method(step) != "GET":
            return {
                "ok": False,
                "skipped": True,
                "reason": "mutation_step_not_rerun",
                "instructions": instructions,
            }
        endpoint = str((getattr(step, "tool_args", None) or {}).get("endpoint") or "")
        params = dict((getattr(step, "tool_args", None) or {}).get("params") or {})
        try:
            resp = await executor._call_api("GET", endpoint, params)
            return {
                "ok": resp.get("status_code") == 200,
                "status_code": resp.get("status_code"),
                "instructions": instructions,
            }
        except Exception as exc:  # noqa: BLE001 - a repair attempt never fails the run
            return {"ok": False, "error": str(exc)[:200],
                    "instructions": instructions}

    @staticmethod
    def _build_qos_metrics(run, results: list, flight_state: dict) -> dict:
        """Aggregate QoS metrics (spec §2 ``metrics_json`` shape).

        Derived from durable run rows + the persisted flight supervision state
        (retries from ``working_notes.audit``, rewrites from the ledger's
        repaired references, vetoes from step critic verdicts).
        """
        from ai.models.core import RunStep

        notes = run.working_notes or {}
        flight = dict(flight_state) if flight_state else dict(notes.get("flight") or {})
        audit = notes.get("audit") or []
        vetoes = RunStep.objects.filter(
            run_id=run.id, critic_verdict="veto"
        ).count()
        return {
            "retries": sum(
                1 for a in audit
                if isinstance(a, dict) and a.get("kind") == "run_retried"
            ),
            "rewrites": len(flight.get("repairs") or []),
            "vetoes": vetoes,
            "escalations": int(flight.get("escalations") or 0),
            "fidelity_failures": int(
                (flight.get("fidelity") or {}).get("failures") or 0
            ),
            "total_latency_ms": run.total_latency_ms,
            "total_llm_calls": run.total_llm_calls,
            "steps_total": len(results),
            "steps_met": sum(1 for r in results if r.get("verdict") == "met"),
            "steps_partial": sum(
                1 for r in results if r.get("verdict") == "partial"
            ),
            "steps_missed": sum(
                1 for r in results if r.get("verdict") == "missed"
            ),
        }

    async def _write_acceptance_report(self, run, plan, user_pk: str,
                                       flight_state: dict) -> dict:
        """Run post-run acceptance checks and write the durable report.

        Rebuilds the in-loop ledger from the persisted flight state, re-queries
        read-only host state through a fresh ``CarbonHostExecutor``, and writes
        the ``AcceptanceReport`` row via ``FlightDirector.build_acceptance_report``.
        The caller wraps this in try/except — closure never fails the run.
        """
        from asgiref.sync import sync_to_async

        from ai.models.core import RunStep
        from ai.flight_director import FlightDirector
        from ai.engine.core.database import get_session_factory
        from ai.host_executor import CarbonHostExecutor

        flight = dict(flight_state or {})
        fd = FlightDirector(run=run)
        ledger = FlightDirector._ledger_from_state(flight)
        step_statuses = await sync_to_async(
            lambda: {
                s.step_index: s.status
                for s in RunStep.objects.filter(run_id=run.id)
            }
        )()
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            executor = CarbonHostExecutor(
                db=db,
                instance_config=_plan_instance_config(user_pk),
                user_token=f"inproc:carbon:{user_pk}",
                host_user_id=user_pk,
            )
            results = await fd.run_acceptance_checks(
                plan, run, ledger, executor,
                step_statuses=step_statuses,
                step_runner=(
                    lambda step, criterion, instructions:
                    self._readonly_step_runner(
                        step, criterion, instructions, executor
                    )
                ),
            )
        metrics = self._build_qos_metrics(run, results, flight)
        report = await sync_to_async(fd.build_acceptance_report)(
            run, results, metrics
        )
        logger.info(
            "acceptance closure run=%s status=%s requirements=%d",
            run.id, report.get("status"), len(results),
        )
        return report

    # ── Execution: SSE streamed run ───────────────────────────────────────

    def run_plan_stream(self, user, plan_id: str):
        """Run an approved/paused plan, streaming SSE frames.

        Frame protocol (W3-A)::

            {"type": "plan_start", "plan": {...}}
            {"type": "step_start", "plan_id", "step_id", "intent"}
            {"type": "step_result", "plan_id", "step_id", "status", ...}
            {"type": "step_confirm", "plan_id", "step_id", "message"}   (consent)
            {"type": "step_end", "plan_id", "step_id", "status"}
            {"type": "done", "plan_id", "status": completed|paused|stopped|failed,
             "final_response"}
            {"type": "error", "error": ...}

        The engine ReActLoop runs to completion (or pauses at a consent gate)
        on a worker thread; frames are produced afterwards from the durable
        Run/RunStep rows — never mid-Loop internals.
        """
        q: queue.Queue = queue.Queue()

        def _collect():
            try:
                for frame in self._run_plan_frames_sync(user, plan_id):
                    q.put(frame)
            except Exception as exc:  # noqa: BLE001 - fail-visible contract
                logger.exception("plan run failed plan=%s", plan_id)
                q.put({"type": "error", "error": f"Plan run failed: {exc}"})
            finally:
                q.put(None)

        threading.Thread(target=_collect, daemon=True).start()

        while True:
            frame = q.get()
            if frame is None:
                break
            yield frame

    def _run_plan_frames_sync(self, user, plan_id: str):
        """Sync wrapper yielding frames from the async engine run.

        ``asyncio.run`` cannot drive an async *generator* directly, so the
        async generator is drained inside a collector coroutine first.
        """
        async def _collect():
            frames = []
            async for frame in self._run_plan_frames(user, plan_id):
                frames.append(frame)
            return frames

        yield from _run_async(_collect())

    async def _run_plan_frames(self, user, plan_id: str):
        """Async generator — one run of the ReAct loop over the plan."""
        from asgiref.sync import sync_to_async

        from ai.models.core import RunStep
        from ai.engine_runtime import _build_chat_user_info

        # Django ORM is sync-only — inside this async generator every ORM
        # touchpoint runs through thread-sensitive sync_to_async (same
        # thread, same DB connection).
        run = await sync_to_async(self._get_owned_run)(user, plan_id)
        if run.status not in _RUNNABLE_STATUSES:
            yield {
                "type": "error",
                "error": (
                    f"Plan is not runnable (status: {run.status}). "
                    "Approve it first, or confirm/decline the pending step "
                    "to resume a paused plan."
                ),
            }
            return

        user_pk = str(user.pk)
        plan = self._rebuild_plan(run)
        instance_config = _plan_instance_config(user_pk)
        user_info = _build_chat_user_info(user_pk)
        conversation_id = run.conversation_id or f"plan-{run.id}"

        # Arm the engine resume path: a paused-status run reuses the plan's
        # own Run row + RunStep rows (no duplicate ledger).
        run.status = STATUS_PAUSED
        await sync_to_async(run.save)(update_fields=["status", "updated_at"])

        yield {
            "type": "plan_start",
            "plan_id": run.id,
            "status": run.status,
            "plan": {
                "brief": run.user_message,
                "pattern": plan.pattern,
                "source": plan.source,
                "skill_name": plan.skill_name,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "intent": s.intent,
                        "tool_name": s.tool_name,
                        "depends_on": s.depends_on,
                    }
                    for s in plan.steps
                ],
            },
        }

        # W4-D Flight Director: deterministic contract gate (artifact-noun
        # coverage + per-step acceptance-criteria suggestions). Never blocks —
        # recorded into the flight state for later acceptance checks (25-C).
        from ai.flight_director import contract_gate

        contract = contract_gate(plan, run.user_message or "")

        # First attempt (fresh engine session).
        flight_state = await self._execute_plan_once(
            run, plan, user_pk, conversation_id, instance_config, user_info
        )

        # Bounded, deterministic retry for transient tool failures.
        for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
            await sync_to_async(run.refresh_from_db)()
            steps = await sync_to_async(
                lambda: list(
                    RunStep.objects.filter(run_id=run.id).order_by("step_index")
                )
            )()
            failed_steps = [s for s in steps if s.status == STEP_FAILED]
            awaiting = [s for s in steps if s.status == STEP_AWAITING_APPROVAL]
            # Never retry past a consent gate (RULE_21); surface it instead.
            if not failed_steps or awaiting:
                break
            await asyncio.sleep(self._retry_backoff_delay(attempt))
            for step in failed_steps:
                # Only *activities* are retried (P3-07b): a workflow step
                # cannot fail from a transient side effect.  Journal the retry
                # (``step_retried`` with the incrementing attempt) so replay
                # reconstructs the exact retry count deterministically.
                if self.is_activity(step):
                    await sync_to_async(_retry_activity_step)(run, step)
            await sync_to_async(self._mark_run_paused)(run)
            await sync_to_async(self._append_retry_audit)(
                run, attempt, [s.step_index for s in failed_steps]
            )
            flight_state = await self._execute_plan_once(
                run, plan, user_pk, conversation_id, instance_config, user_info
            )

        # W4-D Flight Director: persist supervision state + contract gate into
        # ``working_notes.flight`` (additive — never clobbers existing keys).
        try:
            _flight = dict(flight_state or {})
            _flight["contract"] = contract
            _notes = dict(run.working_notes or {})
            _notes["flight"] = _flight
            run.working_notes = _notes
            await sync_to_async(run.save)(update_fields=["working_notes", "updated_at"])
        except Exception:  # noqa: BLE001 - flight persistence never fails the run
            logger.exception("flight state persistence failed for run %s", run.id)

        # Re-read the durable row the loop finalized.
        await sync_to_async(run.refresh_from_db)()
        steps = await sync_to_async(
            lambda: list(
                RunStep.objects.filter(run_id=run.id).order_by("step_index")
            )
        )()
        paused_step = next(
            (s for s in steps if s.status == STEP_AWAITING_APPROVAL), None
        )

        # All steps finished → align plan status before the done frame so the
        # picker / SSE consumers see completed|failed correctly.
        await sync_to_async(_reconcile_run_status_from_steps)(run, steps)
        await sync_to_async(run.refresh_from_db)()

        # W5-C: surface any artifacts produced by this run on the live frames.
        from ai.models.core import RunArtifact

        run_artifacts = await sync_to_async(
            lambda: list(RunArtifact.objects.filter(run_id=run.id))
        )()
        artifacts_by_step: dict = {}
        for a in run_artifacts:
            artifacts_by_step.setdefault(a.step_index, []).append(a)

        # W4-D learning flywheel: feed the finalized run outcome back into the
        # SkillRegistry (Reflexion-style step feedback). Fires only on
        # terminal runs (completed/failed) — the retry loop above never
        # reaches here mid-flight, and feed_run_feedback re-guards status.
        try:
            from ai.feedback.skill_flywheel import feed_run_feedback

            feed_result = await sync_to_async(feed_run_feedback)(str(run.id))
            if feed_result:
                logger.info("skill flywheel: %s", feed_result)
        except Exception:  # BLE001 — learning must never fail a plan run
            logger.exception("skill flywheel failed for run %s", run.id)

        # W4-D/25-C Flight Director: post-run acceptance checks + durable QoS
        # report (spec §3.5–§3.6). Re-queries read-only host state and never
        # fails the run; non-terminal runs skip closure (mirrors the
        # feed_run_feedback terminal guard).
        if run.status in (STATUS_COMPLETED, STATUS_COMPLETED_WITH_GAPS, STATUS_FAILED):
            report = None
            try:
                report = await self._write_acceptance_report(
                    run, plan, user_pk, flight_state
                )
            except Exception:  # noqa: BLE001 - closure never fails the run
                logger.exception(
                    "acceptance report failed for run %s", run.id
                )

            # 25-D grow loop: outcome → learning + playbook (spec §3.6). Fires
            # only on the report just written — deterministic matchers, dedup
            # via (run, pattern), PlaybookBlock upsert. Learning never fails a
            # run: any error is logged and swallowed.
            if report is not None:
                try:
                    from ai.flight_director import enqueue_learning_from_report

                    applied = await sync_to_async(enqueue_learning_from_report)(
                        report, flight_state=flight_state, run=run
                    )
                    if applied:
                        logger.info("flight learning: %s", applied)
                except Exception:  # noqa: BLE001 - learning never fails the run
                    logger.exception(
                        "flight learning failed for run %s", run.id
                    )

        for step in steps:
            if step.status in (STEP_SKIPPED,):
                continue
            yield {
                "type": "step_start",
                "plan_id": run.id,
                "step_id": step.step_index,
                "intent": step.intent,
            }
            if step.status == STEP_AWAITING_APPROVAL and paused_step is not None:
                yield {
                    "type": "step_confirm",
                    "plan_id": run.id,
                    "step_id": step.step_index,
                    "intent": step.intent,
                    "message": (
                        "This step changes your data — review and confirm it "
                        "to continue, or decline to skip it."
                    ),
                }
            else:
                _ui_out, _ui_type = _step_tool_output_fields(step.tool_output_json)
                yield {
                    "type": "step_result",
                    "plan_id": run.id,
                    "step_id": step.step_index,
                    "intent": step.intent,
                    "status": step.status,
                    "verdict": step.critic_verdict,
                    "draft_text": step.draft_text,
                    "tool_output": _ui_out,
                    "output_type": _ui_type,
                    "error": step.error,
                    "consent_granted": bool(
                        isinstance(step.critic_flags_json, dict)
                        and step.critic_flags_json.get("consent_granted")
                    ),
                    "artifacts": [
                        {
                            "id": a.id,
                            "name": a.name,
                            "mime_type": a.mime_type,
                            "size_bytes": a.size_bytes,
                            "download_url": _artifact_download_url(run.id, a.id),
                        }
                        for a in artifacts_by_step.get(step.step_index, [])
                    ],
                }
                yield {
                    "type": "step_end",
                    "plan_id": run.id,
                    "step_id": step.step_index,
                    "status": step.status,
                }

        final_status = (
            STATUS_PAUSED if paused_step is not None else run.status
        )
        # SSE contract uses ``stopped`` for operator cancel (UI Stop button).
        if final_status == STATUS_CANCELLED:
            final_status = "stopped"
        yield {
            "type": "done",
            "plan_id": run.id,
            "status": final_status,
            "final_response": run.final_response,
        }

    # ── Consent: step-level confirm / decline ─────────────────────────────

    def confirm_step(self, user, plan_id: str, step_id) -> dict:
        """Confirm a paused consent step — executes the staged mutation.

        Mirrors the workspace ``tool-executions/confirm`` seam: the staged
        host mutation runs in-process as the requesting user via
        ``CarbonHostExecutor.confirm_execution``; the step is then marked
        completed so the next ``run`` resumes past it.
        """
        from asgiref.sync import async_to_sync

        from ai.engine.core.database import get_session_factory
        from ai.host_executor import CarbonHostExecutor

        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PAUSED:
            raise PlanNotRunnableError(
                f"Plan is not paused (status: {run.status})."
            )
        step = self._get_owned_step(run, step_id)
        if step.status != STEP_AWAITING_APPROVAL:
            raise PlanStepError(
                f"Step {step.step_index} is not awaiting approval "
                f"(status: {step.status})."
            )

        tool_output = _parse_tool_output_json(step.tool_output_json)
        raw = tool_output.get("result", "")
        parsed = {}
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        execution_id = (
            (parsed or {}).get("execution_id")
            or tool_output.get("execution_id")
        )
        user_pk = str(user.pk)
        instance_config = _plan_instance_config(user_pk)
        factory = get_session_factory(PLAN_INSTANCE_ID)

        async def _confirm():
            async with factory() as db:
                executor = CarbonHostExecutor(
                    db=db,
                    instance_config=instance_config,
                    user_token=f"inproc:carbon:{user_pk}",
                    host_user_id=user_pk,
                )
                return await executor.confirm_execution(
                    execution_id, expected_host_user_id=user_pk
                )

        def _grant_unstaged_consent(*, reason: str) -> dict:
            """Pre-execution / recovery path — token only; resume re-runs the tool."""
            if not step.confirmation_token:
                from uuid import uuid4
                step.confirmation_token = str(uuid4())
            # Drop the dead staged execution id so the next resume does not
            # re-enter confirm_execution on a failed/expired row.
            cleaned = dict(tool_output) if isinstance(tool_output, dict) else {}
            cleaned.pop("execution_id", None)
            if isinstance(cleaned.get("result"), dict):
                cleaned["result"] = {
                    k: v for k, v in cleaned["result"].items() if k != "execution_id"
                }
            elif isinstance(cleaned.get("result"), str):
                try:
                    nested = json.loads(cleaned["result"])
                    if isinstance(nested, dict) and "execution_id" in nested:
                        nested = {k: v for k, v in nested.items() if k != "execution_id"}
                        cleaned["result"] = json.dumps(nested)
                except (json.JSONDecodeError, TypeError):
                    pass
            step.tool_output_json = cleaned
            flags = step.critic_flags_json if isinstance(step.critic_flags_json, dict) else {}
            flags = {**(flags or {}), "consent_granted": True, "consent_recovery": reason}
            step.critic_flags_json = flags
            step.save(update_fields=[
                "confirmation_token", "tool_output_json", "critic_flags_json", "updated_at",
            ])
            StepJournal.append(
                run.id,
                canonical_step_id(step),
                EVENT_STEP_CONSENT_GRANTED,
                payload={"unstaged": True, "recovery": reason},
            )
            logger.info(
                "Plan step consent recorded (unstaged/%s) plan=%s step=%s user=%s",
                reason, plan_id, step.step_index, str(user.pk),
            )
            return {
                "status": "confirmed",
                "plan_id": plan_id,
                "step_id": step.step_index,
                "unstaged": True,
                "recovered": True,
            }

        if not execution_id:
            return _grant_unstaged_consent(reason="no_execution_id")

        try:
            async_to_sync(_confirm)()
        except Exception as exc:  # noqa: BLE001 - fail-visible with detail
            msg = str(exc)
            dead = (
                "not pending confirmation" in msg
                or "not found" in msg.lower()
                or "(status: failed)" in msg
                or "(status: cancelled)" in msg
                or "(status: expired)" in msg
            )
            if dead:
                logger.warning(
                    "Plan step confirm recovering from dead staged execution "
                    "plan=%s step=%s execution=%s: %s",
                    plan_id, step.step_index, execution_id, msg,
                )
                return _grant_unstaged_consent(reason="dead_staged_execution")
            logger.warning(
                "Plan step confirm failed plan=%s step=%s: %s",
                plan_id, step.step_index, exc, exc_info=True,
            )
            raise PlanStepError(f"Confirmation failed: {exc}")

        step.status = STEP_COMPLETED
        flags = step.critic_flags_json if isinstance(step.critic_flags_json, dict) else {}
        flags = {**(flags or {}), "consent_granted": True}
        step.critic_flags_json = flags
        step.save(update_fields=["status", "critic_flags_json", "updated_at"])
        # Journal the committed consent + completion (exactly-one-effect): a
        # confirmed step reconstructs as ``succeeded``, never re-executed.
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_CONSENT_GRANTED
        )
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_COMPLETED
        )
        logger.info(
            "Plan step confirmed plan=%s step=%s user=%s",
            plan_id, step.step_index, user_pk,
        )
        return {"status": "confirmed", "plan_id": plan_id, "step_id": step.step_index}

    def decline_step(self, user, plan_id: str, step_id) -> dict:
        """Decline a paused consent step — nothing is written.

        The staged mutation is discarded via
        ``CarbonHostExecutor.decline_execution``; the step is marked skipped
        so the next ``run`` resumes past it.
        """
        from asgiref.sync import async_to_sync

        from ai.engine.core.database import get_session_factory
        from ai.host_executor import CarbonHostExecutor

        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PAUSED:
            raise PlanNotRunnableError(
                f"Plan is not paused (status: {run.status})."
            )
        step = self._get_owned_step(run, step_id)
        if step.status != STEP_AWAITING_APPROVAL:
            raise PlanStepError(
                f"Step {step.step_index} is not awaiting approval "
                f"(status: {step.status})."
            )

        tool_output = _parse_tool_output_json(step.tool_output_json)
        raw = tool_output.get("result", "")
        parsed = {}
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        execution_id = (
            (parsed or {}).get("execution_id")
            or tool_output.get("execution_id")
        )
        if not execution_id:
            # Nothing staged — treat as a plain decline and skip the step.
            step.status = STEP_SKIPPED
            step.save(update_fields=["status", "updated_at"])
            StepJournal.append(
                run.id, canonical_step_id(step), EVENT_STEP_CONSENT_DECLINED
            )
            return {
                "status": "declined",
                "plan_id": plan_id,
                "step_id": step.step_index,
            }

        user_pk = str(user.pk)
        instance_config = _plan_instance_config(user_pk)
        factory = get_session_factory(PLAN_INSTANCE_ID)

        async def _decline():
            async with factory() as db:
                executor = CarbonHostExecutor(
                    db=db,
                    instance_config=instance_config,
                    user_token=f"inproc:carbon:{user_pk}",
                    host_user_id=user_pk,
                )
                await executor.decline_execution(
                    execution_id, expected_host_user_id=user_pk
                )

        try:
            async_to_sync(_decline)()
        except Exception as exc:  # noqa: BLE001 - fail-visible with detail
            logger.warning(
                "Plan step decline failed plan=%s step=%s: %s",
                plan_id, step.step_index, exc, exc_info=True,
            )
            raise PlanStepError(f"Decline failed: {exc}")

        step.status = STEP_SKIPPED
        step.save(update_fields=["status", "updated_at"])
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_CONSENT_DECLINED
        )
        logger.info(
            "Plan step declined plan=%s step=%s user=%s",
            plan_id, step.step_index, user_pk,
        )
        return {"status": "declined", "plan_id": plan_id, "step_id": step.step_index}

    # ── W-7: per-step controls ────────────────────────────────────────────

    def retry_step(self, user, plan_id: str, step_id) -> dict:
        """Re-queue a single failed step for re-execution (user-initiated).

        Only a ``failed`` step may be retried. The step is reset to
        ``pending`` with its error cleared and ``retry_count`` incremented —
        it is NOT executed inline. Re-execution happens when the durable
        ``run``/``resume`` path re-enters (the fail-closed command boundary +
        RULE_21 consent still apply there), keeping the exactly-one-effect
        contract intact. This is a user-initiated single-step retry, distinct
        from the automatic bounded transient retry (``_retry_activity_step``).

        If the run itself is ``failed`` (or an interrupted ``running``) it is
        flipped back to ``paused`` — mirroring the run-status transition
        ``durable_service.resume_run`` performs — so the UI's ``run``/``resume``
        picks the re-queued step up. Only this step is re-queued; sibling
        failed steps are left for the resume path's own reconciliation.
        """
        run = self._get_owned_run(user, plan_id)
        step = self._get_owned_step(run, step_id)
        if step.status != STEP_FAILED:
            raise PlanStepError(
                f"Step {step.step_index} cannot be retried "
                f"(status: {step.status}); only failed steps may be retried."
            )
        step.retry_count = (step.retry_count or 0) + 1
        step.status = STEP_PENDING
        step.error = None
        step.last_error = ""
        step.save(update_fields=[
            "status", "error", "last_error", "retry_count", "updated_at",
        ])
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_RETRIED,
            payload={"attempt": step.retry_count},
        )
        # Mirror ``durable_service.resume_run``'s run-status transition: a
        # failed / interrupted-running run becomes ``paused`` — the engine's
        # re-entry state for ``resume_run_id`` — so resume re-executes the
        # re-queued step. Runs already resumable (paused / approved) are left
        # untouched.
        if run.status in (STATUS_FAILED, STATUS_RUNNING):
            run.status = STATUS_PAUSED
            run.save(update_fields=["status", "updated_at"])
        logger.info(
            "Plan step retried plan=%s step=%s user=%s attempt=%s",
            plan_id, step.step_index, str(user.pk), step.retry_count,
        )
        return {"status": "retried", "plan_id": plan_id, "step_id": step.step_index}

    def skip_step(self, user, plan_id: str, step_id) -> dict:
        """Skip a single step — mark it satisfied without executing it.

        Allowed from ``pending`` / ``failed`` / ``awaiting_approval`` /
        ``paused``. A skipped step is treated as *committed* by the workflow
        driver's ``depends_on`` gating (``workflow.COMMITTED_STATUSES`` holds
        ``skipped``), so its dependents still unblock. No host effect runs —
        skipping only transitions step state.
        """
        run = self._get_owned_run(user, plan_id)
        step = self._get_owned_step(run, step_id)
        if step.status not in (
            STEP_PENDING, STEP_FAILED, STEP_AWAITING_APPROVAL, STEP_PAUSED
        ):
            raise PlanStepError(
                f"Step {step.step_index} cannot be skipped "
                f"(status: {step.status})."
            )
        prior = step.status
        step.status = STEP_SKIPPED
        step.save(update_fields=["status", "updated_at"])
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_SKIPPED,
            payload={"from": prior},
        )
        logger.info(
            "Plan step skipped plan=%s step=%s user=%s from=%s",
            plan_id, step.step_index, str(user.pk), prior,
        )
        return {"status": "skipped", "plan_id": plan_id, "step_id": step.step_index}

    def cancel_step(self, user, plan_id: str, step_id) -> dict:
        """Cancel a single step — abandon it; the run continues.

        Allowed from ``pending`` / ``running`` / ``paused``. The step is marked
        ``skipped`` (abandoned, not re-run) so dependents still unblock. This
        is single-step only — cancelling the whole run is ``stop_plan``. No
        host effect runs; cancel only transitions step state.
        """
        run = self._get_owned_run(user, plan_id)
        step = self._get_owned_step(run, step_id)
        if step.status not in (STEP_PENDING, STEP_RUNNING, STEP_PAUSED):
            raise PlanStepError(
                f"Step {step.step_index} cannot be cancelled "
                f"(status: {step.status})."
            )
        prior = step.status
        step.status = STEP_SKIPPED
        step.save(update_fields=["status", "updated_at"])
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_CANCELLED,
            payload={"from": prior},
        )
        logger.info(
            "Plan step cancelled plan=%s step=%s user=%s from=%s",
            plan_id, step.step_index, str(user.pk), prior,
        )
        return {
            "status": "cancelled", "plan_id": plan_id, "step_id": step.step_index,
        }

    def pause_step(self, user, plan_id: str, step_id) -> dict:
        """Hold a running step at ``paused`` (user-initiated).

        Only a ``running`` step may be paused. Pausing does not stop any
        in-flight host effect — the boundary owns effect execution — it marks
        the step held so the driver does not advance past it until
        ``resume_step`` returns it to ``pending``.
        """
        run = self._get_owned_run(user, plan_id)
        step = self._get_owned_step(run, step_id)
        if step.status != STEP_RUNNING:
            raise PlanStepError(
                f"Step {step.step_index} cannot be paused "
                f"(status: {step.status}); only running steps may be paused."
            )
        step.status = STEP_PAUSED
        step.save(update_fields=["status", "updated_at"])
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_PAUSED
        )
        logger.info(
            "Plan step paused plan=%s step=%s user=%s",
            plan_id, step.step_index, str(user.pk),
        )
        return {"status": "paused", "plan_id": plan_id, "step_id": step.step_index}

    def resume_step(self, user, plan_id: str, step_id) -> dict:
        """Release a paused step back to ``pending`` (user-initiated).

        Only a ``paused`` step may be resumed. The step returns to ``pending``
        so the driver re-runs it on the next ``run``/``resume`` — no effect is
        executed here.
        """
        run = self._get_owned_run(user, plan_id)
        step = self._get_owned_step(run, step_id)
        if step.status != STEP_PAUSED:
            raise PlanStepError(
                f"Step {step.step_index} cannot be resumed "
                f"(status: {step.status}); only paused steps may be resumed."
            )
        step.status = STEP_PENDING
        step.save(update_fields=["status", "updated_at"])
        StepJournal.append(
            run.id, canonical_step_id(step), EVENT_STEP_RESUMED
        )
        logger.info(
            "Plan step resumed plan=%s step=%s user=%s",
            plan_id, step.step_index, str(user.pk),
        )
        return {"status": "resumed", "plan_id": plan_id, "step_id": step.step_index}

    # ── Stop (cancel) / compensate / audit ────────────────────────────────

    @staticmethod
    def _apply_cancel(run) -> None:
        """Transition the run to ``cancelled`` and skip every not-yet-started step.

        Only steps still in a pre-execution state (``planned`` / ``ready`` /
        ``awaiting_approval``) are skipped; a step that already began or
        committed is left untouched so no effect is fabricated and none is
        re-run. ``cancel`` performs no executor work of its own — it can never
        start a new effect.
        """
        from ai.models.core import RunStep

        run.status = STATUS_CANCELLED
        run.run_state = run_machine.RUN_CANCELLED
        run.completed_at = run.completed_at or timezone.now()
        run.save(
            update_fields=["status", "run_state", "completed_at", "updated_at"]
        )
        RunStep.objects.filter(
            run_id=run.id,
            step_state__in=(
                run_machine.RUN_PLANNED,
                run_machine.RUN_READY,
                run_machine.RUN_AWAITING_APPROVAL,
            ),
        ).update(
            status=STEP_SKIPPED,
            step_state=run_machine.RUN_CANCELLED,
        )

    @staticmethod
    def _apply_compensate(run, note: str, command) -> None:
        """Record a distinct compensation effect on the run.

        The compensation is written to ``run.working_notes["compensation"]`` —
        deliberately separate from any ``cancel`` transition — so the reversal
        of prior effects is auditable and never aliased to a plain stop.
        """
        notes = dict(run.working_notes or {})
        notes["compensation"] = {
            "action": "compensate",
            "status": "compensated",
            "note": note or "",
            "by": command.principal,
            "capability": command.capability,
            "at": timezone.now().isoformat(),
        }
        run.working_notes = notes
        run.save(update_fields=["working_notes", "updated_at"])

    def cancel_plan(self, user, plan_id: str) -> dict:
        """Cancel a plan run: stop work, skip remaining steps, no new effects.

        Idempotent and fail-closed: the ``cancel`` action is authorized through
        the PDP (its own policy row, ``action="cancel"``) before any state is
        changed, and it never requires a grant (a user can always stop their
        own run).
        """
        from asgiref.sync import async_to_sync

        run = self._get_owned_run(user, plan_id)
        if run.status in (
            STATUS_COMPLETED, STATUS_COMPLETED_WITH_GAPS, STATUS_FAILED, STATUS_CANCELLED,
        ):
            return {**self.get_plan(user, plan_id), "message": CANCEL_MESSAGE}

        async def _executor(command):
            from asgiref.sync import sync_to_async

            # Run the Django ORM mutation back on the caller's thread so it
            # joins the surrounding transaction (the boundary's async body
            # otherwise runs the write on the loop's worker thread).
            await sync_to_async(self._apply_cancel, thread_sensitive=True)(run)
            return {"cancelled": True, "plan_id": plan_id}

        boundary = _lifecycle_boundary("cancel", executor=_executor)
        outcome = async_to_sync(boundary.execute)(
            _lifecycle_command(user, run, "cancel")
        )
        if outcome.status not in ("executed", "confirmed"):
            raise PlanForbiddenError(
                outcome.error or outcome.reason or "cancel refused (fail-closed)"
            )
        logger.info("Plan cancelled id=%s user=%s", plan_id, str(user.pk))
        return {**self.get_plan(user, plan_id), "message": CANCEL_MESSAGE}

    def stop_plan(self, user, plan_id: str) -> dict:
        """Request cancellation of a plan run (idempotent) — ``cancel`` semantics."""
        return self.cancel_plan(user, plan_id)

    def rerun_plan(self, user, plan_id: str) -> dict:
        """Re-run an already-executed plan from a clean slate (workspace convenience).

        Allowed for a ``completed`` / ``completed_with_gaps`` / ``failed`` /
        ``cancelled`` run. Every step is reset to ``pending`` (outputs, verdicts,
        tokens and errors cleared) while ``step_index`` order and ``depends_on``
        are preserved, and the run is returned to ``approved`` — a runnable
        status — so the existing ``run_plan_stream`` re-executes it. Nothing
        executes here (RULE_21): the fail-closed boundary + consent still apply
        when the caller triggers the run. Distinct from durable ``replay_run``
        (which stages to ``replaying`` for the admin audit surface).
        """
        run = self._get_owned_run(user, plan_id)
        if run.status not in (
            STATUS_COMPLETED,
            STATUS_COMPLETED_WITH_GAPS,
            STATUS_FAILED,
            STATUS_CANCELLED,
        ):
            raise PlanNotRunnableError(
                f"Only an executed plan can be re-run (status: {run.status}). "
                "Re-run a completed, failed, cancelled, or completed-with-gaps plan."
            )
        from ai.models.core import RunStep

        steps = list(
            RunStep.objects.filter(run_id=run.id).order_by("step_index")
        )
        # Track D — preserve prior Answer so Output can show a Rerun receipt.
        notes = dict(run.working_notes or {})
        prior_body = (run.final_response or "").strip()
        if prior_body:
            notes["prior_run"] = {
                "final_response": prior_body[:12000],
                "status": run.status,
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
                "step_count": len(steps),
            }
            run.working_notes = notes
        for step in steps:
            step.status = STEP_PENDING
            step.confirmation_token = None
            step.error = None
            step.last_error = ""
            step.critic_verdict = None
            step.draft_text = None
            step.tool_output_json = None
            step.critic_flags_json = None
            step.latency_ms = None
            step.retry_count = 0
            step.save(update_fields=[
                "status", "confirmation_token", "error", "last_error",
                "critic_verdict", "draft_text", "tool_output_json",
                "critic_flags_json", "latency_ms", "retry_count", "updated_at",
            ])
        previous_status = run.status
        run.status = STATUS_APPROVED
        run.final_response = None
        run.completed_at = None
        update_fields = [
            "status", "final_response", "completed_at", "updated_at",
        ]
        if prior_body:
            update_fields.append("working_notes")
        run.save(update_fields=update_fields)
        logger.info(
            "Plan re-run staged id=%s user=%s of=%s steps=%d",
            plan_id, str(user.pk), previous_status, len(steps),
        )
        try:
            from ai.pulse_ux_telemetry import emit_ux
            emit_ux(
                "agent.rerun",
                of=previous_status,
                reset_count=len(steps),
                had_prior=bool(prior_body),
            )
        except Exception:  # noqa: BLE001
            pass
        return {
            **self.get_plan(user, plan_id),
            "rerun": {"of": previous_status, "reset_count": len(steps)},
        }

    def compensate_plan(self, user, plan_id: str, note: str = "") -> dict:
        """Reverse prior effects of a plan run (requires its own approval).

        ``compensate`` is a *separate* authorized action from ``cancel``: it is
        routed through the command boundary with ``requires_grant=True`` and
        its own capability (``run.compensate``), so a ``cancel`` authorization
        never satisfies it. Without an active, fully-matching ``ApprovalGrant``
        the boundary refuses fail-closed and no compensation record is written.
        """
        from asgiref.sync import async_to_sync

        run = self._get_owned_run(user, plan_id)
        existing = (run.working_notes or {}).get("compensation")
        if existing and existing.get("status") == "compensated":
            return {
                **self.get_plan(user, plan_id),
                "message": COMPENSATE_MESSAGE,
                "compensation": existing,
            }

        async def _executor(command):
            from asgiref.sync import sync_to_async

            # Run the Django ORM mutation back on the caller's thread (see
            # ``cancel_plan``) so the compensation record joins the same
            # transaction as the run it annotates.
            await sync_to_async(self._apply_compensate, thread_sensitive=True)(
                run, note or "", command
            )
            return {"compensated": True, "plan_id": plan_id}

        command = _lifecycle_command(user, run, "compensate")
        command.params = {"note": note or ""}
        boundary = _lifecycle_boundary("compensate", executor=_executor)
        outcome = async_to_sync(boundary.execute)(command)
        if outcome.status == "deferred":
            raise PlanNotRunnableError(
                outcome.error or "compensate deferred to approval inbox"
            )
        if outcome.status not in ("executed", "confirmed"):
            raise PlanForbiddenError(
                outcome.error or outcome.reason
                or "compensate refused (no authorized grant)"
            )
        logger.info("Plan compensated id=%s user=%s", plan_id, str(user.pk))
        return {
            **self.get_plan(user, plan_id),
            "message": COMPENSATE_MESSAGE,
            "compensation": (run.working_notes or {}).get("compensation"),
        }

    def get_ledger(self, user, plan_id: str) -> dict:
        """Audit ledger for a plan: steps, confirmations, replans, latency,
        tokens, provenance, actor."""
        from ai.models.core import RunStep

        run = self._get_owned_run(user, plan_id)
        steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
        plan_json = _coerce_plan_json(run.plan_json)

        actor_name = str(user)
        try:
            from django.contrib.auth import get_user_model

            owner = get_user_model().objects.get(pk=run.host_user_id)
            actor_name = getattr(owner, "display_name", "") or (
                owner.get_full_name() or owner.username
            )
        except Exception:  # noqa: BLE001 - best-effort actor resolution
            pass

        confirmations = [
            {
                "step_id": s.step_index,
                "intent": s.intent,
                "status": s.status,
            }
            for s in steps
            if s.status in (STEP_AWAITING_APPROVAL, STEP_COMPLETED)
            and s.confirmation_token is not None
        ]
        # Fallback: any step that ever reached the consent gate carries a
        # confirmation token after a pause.
        if not confirmations:
            confirmations = [
                {
                    "step_id": s.step_index,
                    "intent": s.intent,
                    "status": s.status,
                }
                for s in steps
                if s.confirmation_token
            ]

        return {
            "plan_id": run.id,
            "brief": run.user_message,
            "status": run.status,
            "actor": {
                "user_id": run.host_user_id,
                "display_name": actor_name,
            },
            "provenance": {
                "pattern": plan_json.get("pattern", "custom"),
                "source": plan_json.get("source", "single_step"),
                "skill_name": plan_json.get("skill_name"),
                "needs_confirmation": bool(
                    plan_json.get("needs_confirmation", False)
                ),
                "created_at": run.created_at.isoformat()
                if run.created_at
                else None,
                "completed_at": run.completed_at.isoformat()
                if run.completed_at
                else None,
            },
            "usage": {
                "total_latency_ms": run.total_latency_ms,
                "total_llm_calls": run.total_llm_calls,
                "total_tokens": run.total_tokens or 0,
            },
            "steps": [
                {
                    "step_id": s.step_index,
                    "intent": s.intent,
                    "tool_name": s.tool_name,
                    "status": s.status,
                    "critic_verdict": s.critic_verdict,
                    "latency_ms": s.latency_ms,
                    "error": s.error,
                    "consent_granted": bool(
                        isinstance(s.critic_flags_json, dict)
                        and s.critic_flags_json.get("consent_granted")
                    ),
                    "confirmed": s.status == STEP_COMPLETED
                    and s.confirmation_token is not None,
                    "skipped": s.status == STEP_SKIPPED,
                }
                for s in steps
            ],
            "confirmations": confirmations,
            "replans": sum(
                1 for s in steps if (s.critic_verdict or "") == "veto"
            ),
            "final_response": run.final_response,
        }

    # ── W4-D/25-C: QoS + supervision endpoints ───────────────────────────

    def get_qos_report(self, user, plan_id: str) -> dict:
        """Acceptance QoS report for a plan (owner-scoped; 404 missing / 403 outsider).

        Returns the durable ``AcceptanceReport`` row when one exists; legacy
        runs without a row are reconstructed deterministically from the
        durable flight state (spec §4 — outcome terms only).
        """
        from ai.models.core import AcceptanceReport, RunStep

        run = self._resolve_plan_access(user, plan_id)
        row = (
            AcceptanceReport.objects.filter(run_id=run.id)
            .order_by("-created_at")
            .first()
        )
        if row is not None:
            from ai.flight_director import serialize_acceptance_report

            report = serialize_acceptance_report(run, row)
        else:
            steps = list(
                RunStep.objects.filter(run_id=run.id).order_by("step_index")
            )
            report = self._compute_legacy_report(run, steps)
        return {"report": report}

    def get_flight_state(self, user, plan_id: str) -> dict:
        """Supervision state for a plan (owner-scoped; 404 missing / 403 outsider)."""
        run = self._resolve_plan_access(user, plan_id)
        flight = (run.working_notes or {}).get("flight") or {}
        return {"supervision": flight}

    @staticmethod
    def _compute_legacy_report(run, steps: list) -> dict:
        """Reconstruct an acceptance report for a legacy run with no row.

        Deterministic reconstruction from the durable flight state (contract
        criteria + fidelity escalations) and the step rows — no host
        re-queries, so evidence is explicitly labelled ``reconstructed``.
        """
        from ai.flight_director import _overall_status

        notes = run.working_notes or {}
        flight = notes.get("flight") or {}
        contract = flight.get("contract") or {}
        suggested = contract.get("suggested_criteria") or {}
        escalated_steps = set(
            (flight.get("fidelity") or {}).get("escalated_steps") or []
        )
        requirements: list[dict] = []
        for s in steps:
            criterion = suggested.get(str(s.step_index))
            if criterion is None:
                continue
            if s.step_index in escalated_steps:
                verdict = "partial"
            elif s.status == "completed":
                verdict = "met"
            else:
                verdict = "missed"
            requirements.append({
                "step_id": s.step_index,
                "intent": s.intent,
                "criterion": criterion,
                "verdict": verdict,
                "evidence": {
                    "query": "reconstructed-from-flight-state",
                    "matches": {"step_status": s.status},
                },
                "repairs": [],
                "escalated": s.step_index in escalated_steps,
            })
        status = _overall_status(requirements)
        metrics = PlansService._build_qos_metrics(run, requirements, flight)
        return {
            "status": status,
            "requirements": requirements,
            "metrics": metrics,
            "final_response": run.final_response,
            "supervision": flight,
        }
