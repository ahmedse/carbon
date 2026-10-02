"""Default-OFF Pulse readiness machinery for the aast-med surface.

Nothing in this package is imported by the Ask turn, the engine, or the Moodle
host seam. Importing it changes no behaviour; the gate, notice registry and
evaluator are inert until explicitly constructed (tests do).

* :mod:`ai.moodle_readiness.gate` — consent + cohort + RBAC gate, default deny.
* :mod:`ai.moodle_readiness.notices` — staff/student notice registry, default
  unpublished.
* :mod:`ai.moodle_readiness.evaluator` — computes the four frozen ladders from
  typed inputs; no rung result is hardcoded.

Spec: ``docs/pulse/aast-med/READINESS-SPEC.md``.
L5: ``docs/pulse/aast-med/L5-PASSABILITY.md``.
Rollout: ``docs/pulse/aast-med/K10-RUNBOOK.md``.
Deferred: ``docs/pulse/aast-med/DEFERRED.md``.
"""
from __future__ import annotations

from ai.moodle_readiness.evaluator import (
    ReadinessInputs,
    ReadinessReport,
    RungResult,
    evaluate,
    repo_inputs,
)
from ai.moodle_readiness.gate import (
    Cohort,
    ConsentRecord,
    GateDecision,
    GateReason,
    StudentSurfaceContext,
    consult_student_surface,
)
from ai.moodle_readiness.notices import (
    REQUIRED_DOES_NOT,
    STAFF_NOTICE_TEXT,
    STUDENT_NOTICE_TEXT,
    Notice,
    NoticeDraftError,
    NoticeRegistry,
)
from ai.moodle_readiness.pilot import (
    PILOT_COHORT_IDNUMBER,
    PILOT_COURSE,
    PILOT_STUDENT_USERNAMES,
    pilot_consent,
    pilot_gate,
    pilot_inputs,
)

__all__ = [
    "Cohort",
    "ConsentRecord",
    "GateDecision",
    "GateReason",
    "Notice",
    "NoticeDraftError",
    "NoticeRegistry",
    "PILOT_COHORT_IDNUMBER",
    "PILOT_COURSE",
    "PILOT_STUDENT_USERNAMES",
    "REQUIRED_DOES_NOT",
    "ReadinessInputs",
    "ReadinessReport",
    "RungResult",
    "STAFF_NOTICE_TEXT",
    "STUDENT_NOTICE_TEXT",
    "StudentSurfaceContext",
    "consult_student_surface",
    "evaluate",
    "pilot_consent",
    "pilot_gate",
    "pilot_inputs",
    "repo_inputs",
]
