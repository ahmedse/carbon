"""P3-08 — Reconciliation worker for ``outcome_unknown`` steps.

Host-side worker. It is the ONLY component allowed to resolve an
``awaiting_reconciliation`` step. It performs an authoritative read-back by a
persisted **operation id**, resolves deterministically, and escalates when the
read-back is inconclusive. It never re-dispatches an effect.

Resolution rules (fail-closed):

  * read-back ``committed`` → step ``succeeded`` (NO re-run — exactly one effect)
  * read-back ``absent``    → step ``failed``
  * anything else           → durable :class:`ReconciliationEscalation`
                               (never guess success, never blind-retry)

"Exactly one effect" is enforced structurally: this module has **no effect
dispatch code path at all**. Every branch either reads back and records the
verdict, or writes an escalation — it never calls an executor. A step whose
dispatch timed out but actually committed is marked ``succeeded`` on read-back
``committed``, so the effect stays at its single occurrence.

Read-back seam: callers may inject ``read_back(step) -> ReadBackResult``, or
register a provider per effect name via :func:`register_read_back`. With no
provider registered the read-back is inconclusive and the step escalates.

Cron (no Celery; run ``manage.py reconcile_outcomes``)::

    */5 * * * * cd /home/ahmed/ws/carbon/backend && /home/ahmed/ws/carbon/.venv/bin/python manage.py reconcile_outcomes

The engine never imports this module (RULE_20 / ADR-0007).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from django.utils import timezone

from ai import run_machine
from ai.models.core import Run, RunStep
from ai.models.reconciliation import (
    READBACK_ABSENT,
    READBACK_COMMITTED,
    READBACK_UNKNOWN,
    ReconciliationEscalation,
)
from ai.plans_service import PlansService

logger = logging.getLogger("carbon.ai.reconciliation")

# Reconciliation outcome actions (closed vocabulary, product terms).
ACTION_RESOLVED_SUCCEEDED = "resolved_succeeded"
ACTION_RESOLVED_FAILED = "resolved_failed"
ACTION_ESCALATED = "escalated"
ACTION_TERMINAL = "terminal"
ACTION_NOT_AWAITING = "not_awaiting_reconciliation"
ACTION_ERROR = "error"


class ReadBackResult:
    """An authoritative downstream verdict for one effect's operation id.

    ``status`` is one of ``committed`` / ``absent`` / ``unknown``. Anything not
    in that set raises — the reconciler never accepts a guessed verdict.
    """

    __slots__ = ("status", "detail")

    def __init__(self, status: str, detail: str = "") -> None:
        if status not in {READBACK_COMMITTED, READBACK_ABSENT, READBACK_UNKNOWN}:
            raise ValueError(f"Unknown read-back status {status!r}")
        self.status = status
        self.detail = detail


ReadBackFn = Callable[[RunStep], ReadBackResult]

# Effect-name → authoritative read-back handler. Empty until a downstream
# integration registers one; absent a handler the read-back is inconclusive
# (fail-closed) and the step escalates.
_READ_BACK_PROVIDERS: dict[str, ReadBackFn] = {}


def register_read_back(effect_name: str, fn: ReadBackFn) -> None:
    """Register an authoritative read-back handler for an effect/tool name.

    Future downstream integrations (export systems, workflow engines, external
    APIs) register a handler here keyed by the step's ``tool_name``. The
    handler must query the downstream system by ``step.operation_id`` and
    return a :class:`ReadBackResult`.
    """
    _READ_BACK_PROVIDERS[effect_name] = fn


def _default_read_back(step: RunStep) -> ReadBackResult:
    """Resolve the registered read-back provider for ``step.tool_name``.

    Fail-closed: no provider, or a provider that raises, yields ``unknown`` so
    the step escalates — never a guessed success.
    """
    fn = _READ_BACK_PROVIDERS.get(step.tool_name or "")
    if fn is None:
        return ReadBackResult(
            READBACK_UNKNOWN,
            detail=(
                f"no read-back provider registered for effect "
                f"{step.tool_name or '(none)'!r}"
            ),
        )
    try:
        return fn(step)
    except Exception as exc:  # noqa: BLE001 - fail-closed: any read-back error → unknown
        logger.exception("Read-back failed for step %s", step.id)
        return ReadBackResult(READBACK_UNKNOWN, detail=f"read-back raised: {exc!r}")


@dataclass(frozen=True)
class ReconciliationResult:
    """Outcome of reconciling a single step (product terms, no engine names)."""

    step_id: str
    action: str
    escalation_id: str = ""
    detail: str = ""


def _process_id_for(step: RunStep) -> str:
    """Resolve the owning process id (Run.definition_id) for an escalation."""
    return (
        Run.objects.filter(id=step.run_id)
        .values_list("definition_id", flat=True)
        .first()
        or ""
    )


def _escalate(
    step: RunStep,
    status: str,
    detail: str,
    *,
    now,
) -> ReconciliationEscalation:
    """Idempotently record a durable escalation for a step (never resolves).

    Keyed uniquely on ``(run_id, step_id)`` so repeated scheduler passes do not
    stack duplicate items. ``get_or_create`` is atomic (race-safe).
    """
    escalation, _created = ReconciliationEscalation.objects.get_or_create(
        run_id=step.run_id,
        step_id=step.step_id,
        defaults={
            "process_id": _process_id_for(step),
            "operation_id": step.operation_id or "",
            "read_back_status": status,
            "read_back_detail": detail or "",
            "reason": (
                "outcome_unknown step could not be deterministically reconciled"
            ),
        },
    )
    return escalation


def reconcile_step(
    step: RunStep,
    *,
    read_back: ReadBackFn | None = None,
    now=None,
) -> ReconciliationResult:
    """Reconcile one ``awaiting_reconciliation`` step (never re-dispatches).

    ``read_back`` is an optional authoritative read-back callable; when omitted
    the registered provider for ``step.tool_name`` is used (see
    :func:`register_read_back`). ``now`` is injectable for deterministic tests.

    Returns a :class:`ReconciliationResult` describing what happened. The step's
    durable ``step_state`` is advanced via the closed transition table only on a
    deterministic verdict — never on a guess.
    """
    now = now or timezone.now()

    # Already terminal → nothing to do (idempotent).
    if step.step_state in {
        run_machine.RUN_SUCCEEDED,
        run_machine.RUN_FAILED,
        run_machine.RUN_CANCELLED,
    }:
        return ReconciliationResult(step.id, ACTION_TERMINAL)

    # Only awaiting_reconciliation may be resolved by this worker.
    if step.step_state != run_machine.RUN_AWAITING_RECONCILIATION:
        return ReconciliationResult(
            step.id, ACTION_NOT_AWAITING,
            detail=f"step_state={step.step_state!r} is not awaiting_reconciliation",
        )

    # Fail-closed: no persisted operation id → cannot read back authoritatively.
    operation_id = (step.operation_id or "").strip()
    if not operation_id:
        escalation = _escalate(
            step, READBACK_UNKNOWN, "missing operation id; cannot read back",
            now=now,
        )
        return ReconciliationResult(
            step.id, ACTION_ESCALATED, escalation_id=escalation.id,
            detail="missing operation id",
        )

    verdict = (read_back or _default_read_back)(step)

    if verdict.status == READBACK_COMMITTED:
        # The effect already happened downstream — mark succeeded, NO re-run.
        PlansService.advance_step(
            step, run_machine.RUN_SUCCEEDED, outcome="succeeded"
        )
        return ReconciliationResult(
            step.id, ACTION_RESOLVED_SUCCEEDED, detail=verdict.detail,
        )

    if verdict.status == READBACK_ABSENT:
        # Definitively absent/failed downstream — mark failed.
        PlansService.advance_step(
            step,
            run_machine.RUN_FAILED,
            outcome="failed",
            error=f"read-back absent: {verdict.detail}",
        )
        return ReconciliationResult(
            step.id, ACTION_RESOLVED_FAILED, detail=verdict.detail,
        )

    # Inconclusive → escalate. Never guess, never re-execute.
    escalation = _escalate(
        step, READBACK_UNKNOWN, verdict.detail or "read-back inconclusive",
        now=now,
    )
    return ReconciliationResult(
        step.id, ACTION_ESCALATED, escalation_id=escalation.id,
        detail=verdict.detail,
    )


def reconcile_pending(
    *,
    step_qs=None,
    read_back: ReadBackFn | None = None,
    limit: int = 0,
) -> list[ReconciliationResult]:
    """Scan ``awaiting_reconciliation`` steps and reconcile each.

    ``step_qs`` overrides the default scan (useful for tests / scoped scans).
    Fail-closed per step: a step that raises is recorded as an ``error`` result
    and never marked success.
    """
    if step_qs is None:
        step_qs = RunStep.objects.filter(
            step_state=run_machine.RUN_AWAITING_RECONCILIATION
        )
    if limit and limit > 0:
        step_qs = step_qs[:limit]

    results: list[ReconciliationResult] = []
    for step in list(step_qs):
        try:
            results.append(reconcile_step(step, read_back=read_back))
        except Exception as exc:  # noqa: BLE001 - per-step resilience, never success
            logger.exception("Reconciliation failed for step %s", step.id)
            results.append(
                ReconciliationResult(step.id, ACTION_ERROR, detail=str(exc))
            )
    return results
