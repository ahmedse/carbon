"""
Durable execution service (Phase W3-E) — crash-resume / replay / timeline.

Extends the W3-A/W3-C plan lifecycle (``ai.plans_service``) with three
durable-execution surfaces, all owner-scoped (CBAC via ``Run.host_user_id``):

    GET  /ai/runs/{run_id}/timeline/   ordered event log for a run
    POST /ai/runs/{run_id}/resume/     crash-safe resume (reconcile + re-enter)
    POST /ai/runs/{run_id}/replay/     consent-gated replay staging (RULE_21)

Design contracts (TASKS.md W3-E, docs/DESIGN-AGENT-CATALOG.md §2):

  * NO changes under ``backend/ai/engine/**`` — the engine is only *called*
    through the public seams W3-C already uses (``ReActLoop.run`` with
    ``resume_run_id`` via ``plans_service.run_plan_stream``). This service
    never touches engine internals.
  * NO new migrations — everything rides the existing ``Run`` / ``RunStep``
    columns (``plan_json``, ``working_notes``, ``status``,
    ``confirmation_token``, timestamps); the audit trail lives in
    ``working_notes.audit`` (a JSON list — no schema change).
  * Reuse over re-implementation: ``PlansService.resume_plan`` is *called*
    for the canonical resume pre-flight — its ``_RUNNABLE_STATUSES``
    semantics match the post-reconciliation state, so its logic is reused,
    not duplicated. Replay is a separate path because nothing in W3-C
    stages a deterministic re-execution (documented below).
  * Fail-visible (design §2): a missing/unowned run raises
    ``PlanNotAccessibleError``; a non-runnable status raises
    ``PlanNotRunnableError``; a missing consent raises ``PlanConsentError``.
  * RULE_21: ``replay_run`` requires an explicit ``confirm=True`` and never
    auto-starts execution — it only stages (resets step rows, marks the run
    ``replaying``). Resume marks the run *resumed* (product term) and
    persists the engine's re-entry state ``paused`` (the W3-C contract for
    ``resume_run_id``); re-execution re-enters through the existing SSE run
    stream — no side effects here.
  * RULE_23: event kinds are product terms (``plan_created``,
    ``step_completed``, ``run_resumed`` …) — never engine class names.
  * Time: ``django.utils.timezone.now()`` only.

Why ``resume_run`` is not just ``resume_plan``: the W3-C pre-flight requires
status ``paused``/``approved`` and performs no step reconciliation. A crash
can leave a run stuck at ``running`` with stale ``running`` steps.
Crash-resume first reconciles interrupted state (stale ``running`` steps →
``pending``, ``failed`` steps → ``pending``, completed/skipped stay done,
``awaiting_approval`` stays gated — never auto-confirmed, RULE_21), then
delegates the pre-flight to ``PlansService.resume_plan``.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from ai.plans_service import (
    PlansService,
    PlanNotAccessibleError,
    PlanNotRunnableError,
    STATUS_APPROVED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STEP_AWAITING_APPROVAL,
    STEP_COMPLETED,
    STEP_FAILED,
    STEP_PENDING,
    STEP_SKIPPED,
)
from ai.observability_api import _redact_secrets

logger = logging.getLogger("carbon.ai.durable_service")

# Step status the engine owns that the W3-C service does not re-export.
STEP_RUNNING = "running"

# Service-level staged statuses (W3-E product terms).
STATUS_RESUMED = "resumed"      # response term — durably materialized as paused
STATUS_REPLAYING = "replaying"  # staged replay marker (never auto-executes)

# Statuses with an executed history that may be replayed (reset to pending).
# ``running`` is deliberately excluded: resetting a live run underneath the
# loop could double-execute mutations (RULE_21). ``pending_approval`` /
# ``approved`` never executed. ``replaying`` is already staged.
_REPLAYABLE_STATUSES = {
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
}

# Resumable statuses: paused / approved (W3-C) or interrupted (stuck running).
_RESUMABLE_STATUSES = {STATUS_RUNNING, STATUS_PAUSED, STATUS_APPROVED}


class PlanConsentError(Exception):
    """Raised when a RULE_21 consent gate is not satisfied (e.g. replay)."""


class DurableExecutionService:
    """Crash-safe resume, consent-gated replay, and run timeline."""

    def __init__(self):
        self._plans = PlansService()

    # ── Shared helpers ───────────────────────────────────────────────────

    @staticmethod
    def _get_owned_run(user, plan_id):
        """CBAC owner scoping — identical contract to ``plans_service``."""
        return PlansService._get_owned_run(user, plan_id)

    @staticmethod
    def _append_audit(run, kind: str, detail=None, step_id=None) -> None:
        """Append a durable audit event to ``working_notes.audit``.

        ``working_notes`` is an existing JSONField — no schema change. The
        timeline endpoint merges these events with the ones it derives from
        row timestamps/statuses.
        """
        notes = dict(run.working_notes or {})
        audit = list(notes.get("audit") or [])
        item = {"t": timezone.now().isoformat(), "kind": kind}
        if detail is not None:
            item["detail"] = detail
        if step_id is not None:
            item["step_id"] = step_id
        audit.append(item)
        notes["audit"] = audit
        run.working_notes = notes

    @staticmethod
    def _ev(seq: int, t, kind: str, step_id=None, detail=None) -> dict:
        """Build one timeline event; ``t`` may be a datetime or an ISO str."""
        ts = t.isoformat() if isinstance(t, datetime) else (t or None)
        ev = {"t": ts, "kind": kind, "seq": seq}
        if step_id is not None:
            ev["step_id"] = step_id
        if detail is not None:
            ev["detail"] = detail
        return ev

    # ── Timeline ─────────────────────────────────────────────────────────

    def timeline(self, user, plan_id: str) -> dict:
        """Ordered event log for a run (read-only, fail-visible).

        Events are derived from durable facts only — ``Run`` timestamps,
        ``RunStep`` rows, ``working_notes`` provenance (``forked_from`` /
        ``replay``) and the audit trail (``working_notes.audit``) written by
        this service's resume/replay ops. Sorted ascending by timestamp.
        """
        from ai.models.core import RunStep

        run = self._get_owned_run(user, plan_id)
        steps = list(
            RunStep.objects.filter(run_id=run.id).order_by("step_index")
        )
        notes = run.working_notes or {}

        events: list[dict] = []

        # Plan created (always present).
        events.append(
            self._ev(0, run.created_at, "plan_created",
                     detail={"brief": run.user_message})
        )
        # Provenance: forked from another plan (W3-C fork_plan).
        if notes.get("forked_from"):
            events.append(
                self._ev(1, run.created_at, "plan_forked",
                         detail={"from_plan_id": notes["forked_from"]})
            )
        # Provenance: replay staged (written by replay_run).
        replay = notes.get("replay")
        if isinstance(replay, dict) and replay.get("at"):
            events.append(
                self._ev(1, replay["at"], "plan_replayed",
                         detail={"of": replay.get("of")})
            )

        # Per-step events: pending (created) + current-state terminal event.
        for idx, step in enumerate(steps, start=2):
            created = step.created_at
            updated = step.updated_at or created
            events.append(
                self._ev(idx, created, "step_pending",
                         step_id=step.step_index,
                         detail={"intent": step.intent})
            )
            state_event = self._step_status_event(step)
            if state_event:
                events.append(
                    self._ev(idx, updated, state_event[0],
                             step_id=step.step_index, detail=state_event[1])
                )
            consent_event = self._consent_event(step)
            if consent_event:
                events.append(
                    self._ev(idx, updated, consent_event[0],
                             step_id=step.step_index, detail=consent_event[1])
                )

        # Run-level current-status event.
        run_event = self._run_status_event(run)
        if run_event:
            t = run.completed_at or run.updated_at
            events.append(self._ev(10 ** 6, t, run_event[0], detail=run_event[1]))

        # Durable audit trail (run_resumed / run_replayed / step_edited …).
        for item in self._audit_events(run):
            events.append(item)

        events.sort(key=lambda e: (e["t"] or "", e["seq"]))
        for e in events:
            e.pop("seq", None)

        return {"run_id": run.id, "status": run.status, "events": events}

    # ── Run comparison (Gap #4) ──────────────────────────────────────────

    def compare_runs(self, user, run_a_id: str, run_b_id: str) -> dict:
        """Side-by-side diff of two runs' step ledgers (read-only, fail-visible).

        Reuses the same durable facts as ``timeline`` — ``Run`` status +
        ``RunStep`` rows — and aligns them by ``step_index`` so an operator
        can see exactly where two runs of the same plan diverged (a step
        added/removed, or whose terminal status/error differs).
        """
        from ai.models.core import RunStep

        run_a = self._get_owned_run(user, run_a_id)
        run_b = self._get_owned_run(user, run_b_id)

        steps_a = {
            s.step_index: s
            for s in RunStep.objects.filter(run_id=run_a.id)
        }
        steps_b = {
            s.step_index: s
            for s in RunStep.objects.filter(run_id=run_b.id)
        }

        step_diff = []
        for idx in sorted(set(steps_a) | set(steps_b)):
            sa = steps_a.get(idx)
            sb = steps_b.get(idx)
            entry = {
                "step_index": idx,
                "intent": sa.intent if sa else sb.intent,
                "a_status": sa.status if sa else None,
                "b_status": sb.status if sb else None,
                "only_in": (
                    "a" if (sa and not sb) else ("b" if (sb and not sa) else None)
                ),
            }
            if sa and sb and sa.status != sb.status:
                entry["status_changed"] = True
            if sa and sa.error:
                entry["a_error"] = sa.error
            if sb and sb.error:
                entry["b_error"] = sb.error
            step_diff.append(entry)

        return {
            "a": {
                "run_id": run_a.id,
                "status": run_a.status,
                "brief": run_a.user_message,
                "step_count": len(steps_a),
            },
            "b": {
                "run_id": run_b.id,
                "status": run_b.status,
                "brief": run_b.user_message,
                "step_count": len(steps_b),
            },
            "status_changed": run_a.status != run_b.status,
            "step_diff": step_diff,
            "diverged_steps": [
                e for e in step_diff
                if e.get("status_changed") or e.get("only_in")
            ],
        }

    @staticmethod
    def _step_status_event(step):
        """Current step state → ``(kind, detail)`` product event, or None.

        ``pending`` steps have no terminal event — only their created event.
        """
        status = step.status
        if status == STEP_COMPLETED:
            detail = {"verdict": step.critic_verdict or "pass"}
            tool_output = _redact_secrets(step.tool_output_json)
            if tool_output:
                detail["tool_output"] = tool_output
            return ("step_completed", detail)
        if status == STEP_FAILED:
            return ("step_failed",
                    {"error": step.error or "The step did not complete."})
        if status == STEP_SKIPPED:
            return ("step_skipped", {})
        if status == STEP_AWAITING_APPROVAL:
            return (
                "step_awaiting_approval",
                {"message": "This step changes your data — it is waiting "
                            "for your review."},
            )
        if status == STEP_RUNNING:
            return ("step_started",
                    {"detail": "Execution was interrupted — re-queue this "
                               "step with resume."})
        return None

    @staticmethod
    def _consent_event(step):
        """Consent transition → ``(kind, detail)`` product event, or None.

        A step that reached the consent gate carries a ``confirmation_token``
        (set by the engine before pausing on ``awaiting_approval``). Confirming
        advances it to ``completed``; declining skips it. Both retain the token,
        so the token's presence plus the terminal status is the durable marker
        that a consent decision was consumed (RULE_21). Event kinds are product
        terms — never engine class names (RULE_23).
        """
        if not step.confirmation_token:
            return None
        if step.status == STEP_COMPLETED:
            return (
                "step_confirmed",
                {"step_id": step.step_index, "choice": "confirmed"},
            )
        if step.status == STEP_SKIPPED:
            return (
                "step_declined",
                {"step_id": step.step_index, "choice": "declined"},
            )
        return None

    @staticmethod
    def _run_status_event(run):
        """Current run status → ``(kind, detail)`` product event, or None."""
        mapping = {
            STATUS_APPROVED: ("plan_approved", {}),
            STATUS_RUNNING: ("plan_running", {}),
            STATUS_PAUSED: ("plan_paused", {}),
            STATUS_COMPLETED: ("plan_completed", {}),
            STATUS_FAILED: ("plan_failed", {}),
            STATUS_CANCELLED: ("plan_cancelled", {}),
            STATUS_REPLAYING: ("plan_replaying", {"staged": True}),
        }
        return mapping.get(run.status)

    @staticmethod
    def _audit_events(run):
        """``working_notes.audit`` list → timeline events (verbatim)."""
        notes = run.working_notes or {}
        audit = notes.get("audit") or []
        out = []
        for i, item in enumerate(audit, start=1):
            if not isinstance(item, dict):
                continue
            ev = {
                "t": item.get("t"),
                "kind": item.get("kind") or "run_event",
                "seq": 10_000 + i,
            }
            if item.get("step_id") is not None:
                ev["step_id"] = item["step_id"]
            if item.get("detail") is not None:
                ev["detail"] = item["detail"]
            out.append(ev)
        return out

    # ── Crash-safe resume ────────────────────────────────────────────────

    def resume_run(self, user, plan_id: str) -> dict:
        """Crash-safe resume: reconcile interrupted state, then reuse the
        W3-C pre-flight (``PlansService.resume_plan``).

        Reconciliation (idempotent):

          * ``running`` steps (stale — the server died mid-step) → ``pending``
          * ``failed`` steps → ``pending`` (re-runnable)
          * ``completed`` / ``skipped`` steps stay done
          * ``awaiting_approval`` steps stay gated — resume never
            auto-confirms a consent step (RULE_21)

        A ``running`` run (interrupted) is marked ``paused`` — the engine's
        re-entry state for ``resume_run_id``; ``paused``/``approved`` runs
        are untouched. The response carries ``status: "resumed"`` (product
        term) exactly like ``resume_plan``; the actual re-execution re-enters
        through the existing SSE run stream (no side effects here).
        """
        from ai.models.core import RunStep

        run = self._get_owned_run(user, plan_id)
        if run.status not in _RESUMABLE_STATUSES:
            raise PlanNotRunnableError(
                f"Plan is not resumable (status: {run.status}). "
                "Resume from a paused, approved, or interrupted running plan."
            )

        steps = list(RunStep.objects.filter(run_id=run.id))
        re_queued: list[int] = []
        for step in steps:
            if step.status in (STEP_RUNNING, STEP_FAILED):
                re_queued.append(step.step_index)
                step.status = STEP_PENDING
                step.error = None
                step.save(update_fields=["status", "error", "updated_at"])
            # completed / skipped / pending / awaiting_approval — untouched.

        interrupted = run.status == STATUS_RUNNING
        if interrupted:
            run.status = STATUS_PAUSED

        # Persist plan_json + reconciled state durably.
        run.plan_json = run.plan_json or {}
        self._append_audit(
            run, "run_resumed",
            detail={"crash_recovery": interrupted,
                    "re_queued_steps": re_queued},
        )
        run.save(update_fields=[
            "plan_json", "working_notes", "status", "updated_at",
        ])

        # REUSE the W3-C pre-flight — its _RUNNABLE_STATUSES now holds.
        preflight = self._plans.resume_plan(user, plan_id)

        logger.info(
            "Run crash-resumed id=%s user=%s interrupted=%s re_queued=%s",
            plan_id, str(user.pk), interrupted, re_queued,
        )
        return {
            **preflight,
            "crash_recovery": interrupted,
            "reconciled_steps": {
                "re_queued": re_queued,
                "preserved": [
                    s.step_index for s in steps
                    if s.step_index not in re_queued
                ],
            },
            "timeline": self.timeline(user, plan_id),
        }

    # ── Replay (consent-gated, staging only) ─────────────────────────────

    def replay_run(self, user, plan_id: str, *, confirm: bool = False) -> dict:
        """Stage a deterministic replay of an executed run (RULE_21).

        Resets every step to ``pending`` — clearing ``confirmation_token``,
        outputs, verdicts and errors, while preserving ``step_index`` order
        and ``depends_on`` — marks the run ``replaying``, and returns the
        new timeline plus the steps that will re-run.

        STAGING ONLY: no engine run is started and nothing executes here;
        re-execution re-enters through the existing run path after the
        operator triggers it. The ``confirm=True`` flag is mandatory —
        without it ``PlanConsentError`` is raised (RULE_21 no auto-mutation).
        """
        from ai.models.core import RunStep

        if confirm is not True:
            raise PlanConsentError(
                "Replay changes execution state — pass {\"confirm\": true}."
            )

        run = self._get_owned_run(user, plan_id)
        if run.status not in _REPLAYABLE_STATUSES:
            raise PlanNotRunnableError(
                f"Only executed plans can be replayed (status: {run.status}). "
                "Replay a completed, failed, or cancelled run."
            )

        steps = list(
            RunStep.objects.filter(run_id=run.id).order_by("step_index")
        )
        for step in steps:
            step.status = STEP_PENDING
            step.confirmation_token = None
            step.error = None
            step.critic_verdict = None
            step.draft_text = None
            step.tool_output_json = None
            step.latency_ms = None
            step.save(update_fields=[
                "status", "confirmation_token", "error", "critic_verdict",
                "draft_text", "tool_output_json", "latency_ms", "updated_at",
            ])

        previous_status = run.status
        run.status = STATUS_REPLAYING
        run.final_response = None
        run.completed_at = None
        notes = dict(run.working_notes or {})
        notes["replay"] = {
            "of": previous_status,
            "at": timezone.now().isoformat(),
        }
        run.working_notes = notes
        self._append_audit(run, "run_replayed", detail={"of": previous_status})
        run.save(update_fields=[
            "status", "final_response", "completed_at",
            "working_notes", "updated_at",
        ])

        re_run = [s.step_index for s in steps]
        logger.info(
            "Run replay staged id=%s user=%s of=%s steps=%d",
            plan_id, str(user.pk), previous_status, len(re_run),
        )
        return {
            "status": STATUS_REPLAYING,
            "plan_id": run.id,
            "replay": {
                "staged": True,
                "of": previous_status,
                "re_run_steps": re_run,
                "reset_count": len(re_run),
            },
            "timeline": self.timeline(user, plan_id),
        }
