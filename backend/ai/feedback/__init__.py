"""Phase 24-D — DQ feedback loop (capture → pipeline → learning).

Public surface:

  * capture — best-effort, idempotent event capture (views/commands call these)
  * pipeline — idempotent + revertible effects over captured events
  * signals  — event_type → engine signal taxonomy mapping + scoring

The package never imports from domain apps and never mutates production
rules (RULE_21 — pipeline only flags ``needs_review`` candidates for human
confirmation).
"""

from ai.feedback.capture import (
    capture_drift,
    capture_result_flag,
    capture_rule_correction,
    capture_suggestion_feedback,
    capture_workspace_feedback,
)
from ai.feedback.pipeline import (
    apply_event,
    apply_pending,
    confirm_review,
    pending_count,
    revert_event,
)
from ai.feedback.signals import EVENT_SIGNAL_MAP, score_for

__all__ = [
    "EVENT_SIGNAL_MAP",
    "apply_event",
    "apply_pending",
    "capture_drift",
    "capture_result_flag",
    "capture_rule_correction",
    "capture_suggestion_feedback",
    "capture_workspace_feedback",
    "confirm_review",
    "pending_count",
    "revert_event",
    "score_for",
]
