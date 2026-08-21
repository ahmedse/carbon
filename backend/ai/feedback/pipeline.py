"""Phase 24-D — DQ feedback pipeline (idempotent + revertible effects).

Applies captured ``DqFeedbackEvent`` rows to the KG feedback ledger without
ever mutating production rules (RULE_21 — DQRule/DQResult writes require human
confirmation; the pipeline only *flags* ``needs_review`` candidates).

Effect table
------------
    suggest_accepted        → KgFeedbackRecord explicit_positive (canonical
                              promotion — accepted suggestion scores 1.0)
    suggest_rejected        → KgFeedbackRecord explicit_negative
    rule_corrected          → KgFeedbackRecord correction + KgGoldenPair
                              candidate (pending human review)
    result_always_pass      → needs_review flag (retire_candidate; human confirms)
    result_false_positive   → needs_review flag (retire_candidate; human confirms)
    drift_detected          → record only (raw drift signal; no ledger write)

Idempotency: an event is applied exactly once — ``applied_at`` guard plus the
row's unique ``idempotency_key``; the engine ledger write is guarded by a
deterministic ``message_id`` (``dq-{event.id}``) so a retry after a partial
failure never duplicates ``KgFeedbackRecord`` rows.

Revertibility: ``apply_event`` records every ledger row it created in
``revert_payload``; ``revert_event`` deletes those rows and clears
``applied_at``, restoring the pre-apply state.
"""

from __future__ import annotations

import asyncio
import json
import logging

from django.utils import timezone

from ai.models.feedback import DqFeedbackEvent
from ai.feedback.signals import EVENT_SIGNAL_MAP

logger = logging.getLogger("carbon.ai.feedback.pipeline")


# ── Public API ────────────────────────────────────────────────────────────────

def pending_count() -> int:
    """Number of captured events awaiting pipeline effects."""
    return DqFeedbackEvent.objects.filter(applied_at__isnull=True).count()


def apply_pending(limit: int = 200) -> int:
    """Sweep unapplied events (management-command entry point). Returns count."""
    applied = 0
    qs = (
        DqFeedbackEvent.objects.filter(applied_at__isnull=True)
        .order_by("created_at")[:limit]
    )
    for event in qs:
        try:
            if apply_event(event):
                applied += 1
        except Exception:  # noqa: BLE001 — one bad event never blocks the sweep
            logger.exception("pipeline apply failed for event %s", event.id)
    return applied


def apply_event(event: DqFeedbackEvent) -> bool:
    """Apply one event's effects exactly once. Returns True when newly applied.

    Effect writes (engine ledger) happen *before* the ``applied_at`` stamp so a
    failure between the two leaves the event unapplied and retry-safe: the
    ledger guard (deterministic message_id) makes the re-run a no-op.
    """
    if event.applied_at:
        return False

    effect, revert = _effects_for(event)

    event.effect = effect
    event.revert_payload = revert
    event.applied_at = timezone.now()
    event.save(update_fields=[
        "effect", "revert_payload", "applied_at",
        "needs_review", "review_status", "updated_at",
    ])
    logger.info(
        "applied %s  event=%s  effect=%s", event.event_type, event.id, effect.get("type")
    )
    return True


def revert_event(event: DqFeedbackEvent) -> bool:
    """Revert an applied event (delete ledger rows, clear applied_at)."""
    if not event.applied_at:
        return False
    revert = event.revert_payload or {}
    _revert_ledger(revert)
    event.effect = {}
    event.revert_payload = {}
    event.applied_at = None
    event.needs_review = False
    event.review_status = "pending"
    event.reviewed_by = ""
    event.reviewed_at = None
    event.save(update_fields=[
        "effect", "revert_payload", "applied_at",
        "needs_review", "review_status", "reviewed_by", "reviewed_at",
        "updated_at",
    ])
    logger.info("reverted event=%s", event.id)
    return True


def confirm_review(event: DqFeedbackEvent, *, reviewer: str, verdict: str) -> None:
    """Human confirmation gate for retire candidates (RULE_21).

    ``verdict``: confirmed | dismissed. Confirmation records who/when on the
    event row; it never mutates DQRule — the actual retirement is a separate,
    human-driven ops action.
    """
    if verdict not in ("confirmed", "dismissed"):
        raise ValueError("verdict must be 'confirmed' or 'dismissed'")
    if event.event_type not in ("result_always_pass", "result_false_positive"):
        raise ValueError(f"{event.event_type} is not a retire-candidate event")
    event.review_status = verdict
    event.reviewed_by = reviewer
    event.reviewed_at = timezone.now()
    event.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "updated_at"])


# ── Effect computation ────────────────────────────────────────────────────────

def _effects_for(event: DqFeedbackEvent) -> tuple[dict, dict]:
    """Compute (effect, revert_payload) for an unapplied event.

    Side effect: engine ledger write for user-signal event types (guarded, so a
    retry never duplicates rows).
    """
    if event.event_type in ("result_always_pass", "result_false_positive"):
        # Retire candidate — flag for human confirmation only (RULE_21).
        event.needs_review = True
        return (
            {"type": "retire_candidate", "flag": "needs_review", "reason": event.event_type},
            {},
        )
    if event.event_type == "drift_detected":
        # Raw drift signal — the ledger is not the right home; record only.
        return ({"type": "record_only", "reason": "drift"}, {})

    signal_type = EVENT_SIGNAL_MAP[event.event_type][0]  # explicit_* | correction
    corrected_definition = None
    if event.event_type == "rule_corrected":
        payload = event.payload or {}
        corrected = payload.get("corrected_definition")
        if corrected:
            corrected_definition = (
                corrected if isinstance(corrected, str)
                else json.dumps(corrected, ensure_ascii=False)
            )
        else:
            corrected_definition = event.correction_text or None

    revert = _write_engine_feedback(event, signal_type, corrected_definition)
    return ({"type": "ledger", "signal_type": signal_type, **revert}, revert)


# ── Engine ledger writes (mirror ai/learning.py — Sprint 10 bridge) ──────────

def _already_recorded(event: DqFeedbackEvent, signal_type: str) -> bool:
    """True when a KgFeedbackRecord already exists for this event+signal."""
    from ai.models import KgFeedbackRecord
    from ai.store import DEFAULT_APP_IDENTIFIER

    return KgFeedbackRecord.objects.filter(
        instance_id=DEFAULT_APP_IDENTIFIER,
        message_id=f"dq-{event.id}",
        signal_type=signal_type,
    ).exists()


def _write_engine_feedback(
    event: DqFeedbackEvent, signal_type: str, corrected_definition: str | None
) -> dict:
    """Write KgFeedbackRecord (+ candidate KgGoldenPair) via the engine.

    Returns {"record_id": ..., "golden_pair_id": ...} for revert_payload, or {}
    when the ledger row already exists (idempotent retry after partial failure).
    """
    from ai.store import DEFAULT_APP_IDENTIFIER, get_store
    from ai.engine.knowledge_graph.feedback import record_feedback

    if _already_recorded(event, signal_type):
        return {}

    instance_id = DEFAULT_APP_IDENTIFIER
    conversation_id = f"dq-feedback-{event.id}"
    message_id = f"dq-{event.id}"
    subject = (
        event.rule_name or event.table_name or event.field_name or "dq-feedback"
    )

    factory = get_store().get_session_factory(instance_id)
    session = factory()

    async def _go() -> str:
        async with session:
            return await record_feedback(
                db=session,
                instance_id=instance_id,
                conversation_id=conversation_id,
                message_id=message_id,
                signal_type=signal_type,
                user_id=str(event.user_id or ""),
                original_utterance=subject,
                resolved_utterance=event.correction_text or subject,
                generated_sql="",
                corrected_sql=corrected_definition,
                user_comment=None,
            )

    rec_id = asyncio.run(_go())
    revert = {"record_id": rec_id}

    if signal_type == "correction" and corrected_definition:
        from ai.models import KgGoldenPair

        pair = KgGoldenPair.objects.filter(source_feedback_id=rec_id).first()
        if pair:
            revert["golden_pair_id"] = str(pair.id)
    return revert


def _revert_ledger(revert: dict) -> None:
    """Delete ledger rows created by apply (from revert_payload)."""
    if not revert:
        return
    from ai.models import KgFeedbackRecord, KgGoldenPair

    rec_id = revert.get("record_id")
    if rec_id:
        KgFeedbackRecord.objects.filter(id=rec_id).delete()
    pair_id = revert.get("golden_pair_id")
    if pair_id:
        KgGoldenPair.objects.filter(id=pair_id).delete()
