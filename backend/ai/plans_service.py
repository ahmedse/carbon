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
import threading
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger("carbon.ai.plans_service")

# Engine instance namespace (mirrors the chat/action paths).
PLAN_INSTANCE_ID = "carbon"

# Run statuses this service owns (superset of the engine's status set).
STATUS_DISCOVERING = "discovering"
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
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
    STEP_PENDING: RUNNABLE_PENDING,
    STEP_AWAITING_APPROVAL: RUNNABLE_PENDING,
}

# Cron day-of-week names, indexed 0-6 (Sunday-first; cron 7 == Sunday).
_CRON_WEEKDAY_NAMES = (
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
)

# Statuses from which a plan may (re)enter execution.
_RUNNABLE_STATUSES = {STATUS_APPROVED, STATUS_PAUSED}


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
    result = data.get("result", data)
    if isinstance(result, str):
        return "text"
    if isinstance(result, dict):
        if any(k in result for k in ("series", "labels", "values", "x", "y")):
            return "chart"
        if any(k in result for k in ("columns", "headers", "rows")):
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


def _with_output_type(tool_output_json):
    """Return the tool output with ``_output_type`` injected (W5-C B4).

    Keeps the original value intact when it already carries a hint or is empty.
    """
    data = _parse_tool_output_json(tool_output_json)
    if not data:
        return tool_output_json
    if isinstance(data, dict) and "_output_type" not in data:
        data = dict(data)
        data["_output_type"] = _infer_output_type(data)
    return data


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

        plan_json = run.plan_json or {}
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
        # Artifacts grouped by step (W5-C): one query for the whole run.
        artifacts_by_step: dict = {}
        for a in RunArtifact.objects.filter(run_id=run.id):
            artifacts_by_step.setdefault(a.step_index, []).append(a)
        return {
            "id": run.id,
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
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
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
                    "error": s.error,
                    "tool_output": _with_output_type(s.tool_output_json),
                    "output_type": _infer_output_type(s.tool_output_json),
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
        }

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
        stable). ``changed`` entries carry ``{"old": ..., "new": ...}`` pairs.
        """
        def _key(s):
            s = s if isinstance(s, dict) else {}
            if key == "step_id":
                return s.get("step_id")
            return cls._normalize_intent(s.get("intent"))

        old = {_key(s): s for s in old_steps if isinstance(s, dict)}
        new = {_key(s): s for s in new_steps if isinstance(s, dict)}
        added = [s for k, s in new.items() if k not in old]
        removed = [s for k, s in old.items() if k not in new]
        changed = [
            {"old": old[k], "new": new[k]}
            for k in old.keys() & new.keys()
            if cls._step_key(old[k]) != cls._step_key(new[k])
        ]
        return {"added": added, "removed": removed, "changed": changed}

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
        """
        from ai.engine.cognition.plan.planner import Plan, PlanPhase, PlanStep

        plan_json = run.plan_json or {}
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
            for s in plan_json.get("steps", [])
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
        return self.get_plan(user, run_id)

    # ── W5-B: guided discovery conversation ───────────────────────────────

    DISCOVERY_MAX_TURNS = 5

    DISCOVERY_SYSTEM_PROMPT = (
        "You are Pulse, the planning assistant for the Carbon Data Trust "
        "Platform. Before proposing a plan, you clarify the user's outcome "
        "with a short series of focused questions. Ask ONE concise question "
        "at a time. When you have enough information, respond with complete."
        "\n\n"
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

        Uses the shared ``chat_completion`` seam (lazily imported, mirroring
        ``_decompose``) so tests can patch it without hitting a live LLM.
        """
        from ai.engine.core.config import get_settings
        from ai.engine.llm.provider import chat_completion

        settings = get_settings()
        text = _run_async(
            chat_completion(
                self._discovery_prompt(brief, turns),
                model=settings.LLM_MODEL,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        )
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
        frame.
        """
        from ai.models.core import Run, generate_uuid

        brief = (brief or "").strip()
        if not brief:
            raise ValueError("brief is required.")
        if len(brief) > 4000:
            raise ValueError("brief is too long (max 4000 characters).")

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
        }

    def advance_discovery(self, user, plan_id: str, user_reply: str) -> dict:
        """Advance a discovery conversation by one user reply (W5-B).

        Appends the reply to ``discovery_turns``, asks Pulse for the next
        question or completion. On completion the enriched brief (original
        brief + discovery answers) is decomposed into a full plan and the Run
        transitions to ``pending_approval`` (RULE_21 — review only).
        """
        from ai.models.core import RunStep

        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_DISCOVERING:
            raise PlanNotRunnableError(
                f"Only discovering plans accept replies (status: {run.status})."
            )

        reply = (user_reply or "").strip()
        if not reply:
            raise ValueError("reply is required.")

        plan_json = run.plan_json or {}
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

        if len(turns) >= self.DISCOVERY_MAX_TURNS:
            decision = {"action": "complete", "question": None}
        else:
            decision = self._ask_discovery_llm(brief, turns)

        if decision.get("action") == "complete":
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

    def edit_plan(self, user, plan_id: str, brief=None, step_deltas=None) -> dict:
        """Re-plan from a (possibly new) brief and return the step diff.

        Always re-runs ``SkillAwarePlanner.decompose`` and returns
        ``{added, removed, changed}`` for review — editing NEVER auto-approves
        (RULE_21). Any plan that is not ``pending_approval`` (approved,
        running, paused, completed, …) drops back to ``pending_approval`` so
        the user explicitly re-approves the revised plan before execution.
        """
        run = self._get_owned_run(user, plan_id)

        new_brief = (brief or run.user_message or "").strip()
        if not new_brief:
            raise ValueError("brief is required.")
        if len(new_brief) > 4000:
            raise ValueError("brief is too long (max 4000 characters).")

        old_plan_json = run.plan_json or {}
        old_steps = [
            s for s in old_plan_json.get("steps", []) if isinstance(s, dict)
        ]

        plan = self._decompose(user, new_brief)
        steps = self._plan_to_dict(plan)["steps"]
        if step_deltas:
            steps = self._apply_step_deltas(steps, step_deltas)

        diff = self._plan_diff(old_steps, steps)
        replan_gate = run.status != STATUS_PENDING_APPROVAL

        run.user_message = new_brief
        run.plan_json = self._plan_to_dict(plan)
        run.plan_json["steps"] = steps
        if replan_gate:
            run.status = STATUS_PENDING_APPROVAL
        run.save(
            update_fields=["user_message", "plan_json", "status", "updated_at"]
        )
        self._replace_run_steps(run.id, steps)

        logger.info(
            "Plan edited id=%s user=%s replan_gate=%s added=%d removed=%d changed=%d",
            plan_id, str(user.pk), replan_gate,
            len(diff["added"]), len(diff["removed"]), len(diff["changed"]),
        )
        result = self.get_plan(user, plan_id)
        result["diff"] = diff
        result["replan_gate"] = replan_gate
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
        plan_json = dict(run.plan_json or {})
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
                run.status = STATUS_PENDING_APPROVAL
            run.save(update_fields=["plan_json", "status", "updated_at"])

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
        from ai.engine_runtime import _carbon_instance_config
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
                instance_config=_carbon_instance_config(user_pk),
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
        from ai.engine_runtime import (
            _build_chat_user_info,
            _carbon_instance_config,
        )

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
        instance_config = _carbon_instance_config(user_pk)
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
                step.status = STEP_PENDING
                step.error = None
                await sync_to_async(step.save)(
                    update_fields=["status", "error", "updated_at"]
                )
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
        if run.status in (STATUS_COMPLETED, STATUS_FAILED):
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
                yield {
                    "type": "step_result",
                    "plan_id": run.id,
                    "step_id": step.step_index,
                    "intent": step.intent,
                    "status": step.status,
                    "verdict": step.critic_verdict,
                    "draft_text": step.draft_text,
                    "tool_output": _with_output_type(step.tool_output_json),
                    "output_type": _infer_output_type(step.tool_output_json),
                    "error": step.error,
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

        from ai.engine_runtime import _carbon_instance_config
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
            # Plan-level mutation consent (Fix A): the tool never staged an
            # execution — this is the PRE-execution consent pause. Confirming
            # here only GRANTS consent; nothing executes yet. The step stays
            # awaiting_approval with its confirmation_token so the next resume
            # re-executes it WITH the token (critic passes → tool runs → row
            # persists completed). Declining the same step marks it skipped
            # (see decline_step). Idempotent: a second confirm is a no-op.
            if not step.confirmation_token:
                from uuid import uuid4
                step.confirmation_token = str(uuid4())
            step.save(update_fields=["confirmation_token", "updated_at"])
            logger.info(
                "Plan step consent recorded (unstaged) plan=%s step=%s user=%s",
                plan_id, step.step_index, str(user.pk),
            )
            return {
                "status": "confirmed",
                "plan_id": plan_id,
                "step_id": step.step_index,
                "unstaged": True,
            }

        user_pk = str(user.pk)
        instance_config = _carbon_instance_config(user_pk)
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

        try:
            async_to_sync(_confirm)()
        except Exception as exc:  # noqa: BLE001 - fail-visible with detail
            logger.warning(
                "Plan step confirm failed plan=%s step=%s: %s",
                plan_id, step.step_index, exc, exc_info=True,
            )
            raise PlanStepError(f"Confirmation failed: {exc}")

        step.status = STEP_COMPLETED
        step.save(update_fields=["status", "updated_at"])
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

        from ai.engine_runtime import _carbon_instance_config
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
            return {
                "status": "declined",
                "plan_id": plan_id,
                "step_id": step.step_index,
            }

        user_pk = str(user.pk)
        instance_config = _carbon_instance_config(user_pk)
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
        logger.info(
            "Plan step declined plan=%s step=%s user=%s",
            plan_id, step.step_index, user_pk,
        )
        return {"status": "declined", "plan_id": plan_id, "step_id": step.step_index}

    # ── Stop / audit ──────────────────────────────────────────────────────

    def stop_plan(self, user, plan_id: str) -> dict:
        """Request cancellation of a plan run (idempotent)."""
        run = self._get_owned_run(user, plan_id)
        if run.status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
            return self.get_plan(user, plan_id)

        from ai.models.core import RunStep

        run.status = STATUS_CANCELLED
        run.completed_at = run.completed_at or timezone.now()
        run.save(update_fields=["status", "completed_at", "updated_at"])
        RunStep.objects.filter(run_id=run.id, status=STEP_PENDING).update(
            status=STEP_SKIPPED
        )
        logger.info("Plan stopped id=%s user=%s", plan_id, str(user.pk))
        return self.get_plan(user, plan_id)

    def get_ledger(self, user, plan_id: str) -> dict:
        """Audit ledger for a plan: steps, confirmations, replans, latency,
        tokens, provenance, actor."""
        from ai.models.core import RunStep

        run = self._get_owned_run(user, plan_id)
        steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
        plan_json = run.plan_json or {}

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
