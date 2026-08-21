"""Phase 24-D — capture DQ feedback events.

Capture is a pure, idempotent insert (unique ``idempotency_key``) — it never
mutates rules and never blocks the caller (views call it best-effort).

The functions take **primitives**, not DQ model instances, so ``ai`` never
imports from domain apps (see ``ai/models/base.py``); the DQ views/commands
resolve and pass ids + name snapshots.
"""

from __future__ import annotations

import logging

from ai.models.feedback import DqFeedbackEvent
from ai.feedback.signals import EVENT_SIGNAL_MAP, score_for

logger = logging.getLogger("carbon.ai.feedback.capture")


def _create_event(
    *,
    event_type: str,
    idempotency_key: str,
    source: str,
    signal_type: str,
    quality_score: float,
    org_unit_id=None,
    suggestion_id=None,
    rule_id=None,
    rule_name="",
    table_id=None,
    table_name="",
    field_name="",
    message_id="",
    user_id=None,
    payload=None,
    correction_text="",
) -> DqFeedbackEvent:
    """get_or_create on the idempotency key — a retried capture is a no-op."""
    defaults = {
        "event_type": event_type,
        "source": source,
        "signal_type": signal_type,
        "quality_score": quality_score,
        "org_unit_id": org_unit_id,
        "suggestion_id": suggestion_id,
        "rule_id": rule_id,
        "rule_name": rule_name or "",
        "table_id": table_id,
        "table_name": table_name or "",
        "field_name": field_name or "",
        "message_id": message_id or "",
        "user_id": user_id,
        "payload": payload or {},
        "correction_text": correction_text or "",
    }
    event, created = DqFeedbackEvent.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults=defaults,
    )
    if created:
        logger.info(
            "captured %s  key=%s  rule=%s", event_type, idempotency_key, rule_name
        )
    return event


def capture_suggestion_feedback(
    suggestion,
    verdict: str,
    *,
    user=None,
    rule_id=None,
    reason: str = "",
) -> DqFeedbackEvent | None:
    """Capture accept/reject of a persisted DQSuggestion (verdict: accepted|rejected).

    ``suggestion`` is a dq.models.DQSuggestion instance (passed by the DQ
    view). Returns the event row (or the existing one on retry).
    """
    event_type = f"suggest_{verdict}"
    if event_type not in EVENT_SIGNAL_MAP:
        logger.warning("unknown suggestion verdict %r — ignored", verdict)
        return None

    payload = {
        "name": (suggestion.payload or {}).get("name", "") if suggestion.payload else "",
        "definition": suggestion.payload,
        "rationale": suggestion.rationale,
        "confidence": suggestion.confidence,
        "reason": reason or "",
    }
    return _create_event(
        event_type=event_type,
        idempotency_key=f"suggest-{verdict}-{suggestion.id}",
        source="suggest",
        signal_type=EVENT_SIGNAL_MAP[event_type][0],
        quality_score=score_for(event_type),
        org_unit_id=_safe_org_unit_id(suggestion),
        suggestion_id=suggestion.id,
        rule_id=rule_id,
        rule_name=payload["name"],
        table_id=getattr(suggestion.data_table, "id", None),
        table_name=getattr(suggestion.data_table, "name", ""),
        user_id=user.id if user and getattr(user, "id", None) else None,
        payload=payload,
    )


def capture_rule_correction(
    *,
    rule_id,
    rule_name="",
    table_id=None,
    table_name="",
    field_name="",
    corrected_definition,
    previous_definition=None,
    correction_text="",
    user_id=None,
    message_id="",
    org_unit_id=None,
) -> DqFeedbackEvent:
    """Capture a user-corrected DQ rule (payload = corrected definition)."""
    return _create_event(
        event_type="rule_corrected",
        idempotency_key=f"rule-corrected-{rule_id}-{message_id or user_id or 'anon'}",
        source="nl_check",
        signal_type="correction",
        quality_score=score_for("rule_corrected"),
        org_unit_id=org_unit_id,
        rule_id=rule_id,
        rule_name=rule_name,
        table_id=table_id,
        table_name=table_name,
        field_name=field_name,
        message_id=message_id,
        user_id=user_id,
        payload={
            "corrected_definition": corrected_definition,
            "previous_definition": previous_definition,
        },
        correction_text=correction_text,
    )


def capture_result_flag(
    *,
    flag_type: str,  # always_pass | false_positive
    rule_id,
    rule_name="",
    table_id=None,
    table_name="",
    org_unit_id=None,
    window_key: str,
    stats=None,
) -> DqFeedbackEvent:
    """Capture a heuristic outcome flag (always-pass / false-positive)."""
    event_type = f"result_{flag_type}"
    if event_type not in EVENT_SIGNAL_MAP:
        logger.warning("unknown result flag %r — ignored", flag_type)
        return None
    return _create_event(
        event_type=event_type,
        idempotency_key=f"result-{flag_type}-{rule_id}-{window_key}",
        source="result",
        signal_type="retire_candidate",
        quality_score=score_for(event_type),
        org_unit_id=org_unit_id,
        rule_id=rule_id,
        rule_name=rule_name,
        table_id=table_id,
        table_name=table_name,
        payload={"stats": stats or {}},
    )


def capture_drift(
    *,
    table_id,
    table_name="",
    field_name="",
    detected_at,
    details=None,
    org_unit_id=None,
) -> DqFeedbackEvent:
    """Capture a drift event (source data for future tuning)."""
    return _create_event(
        event_type="drift_detected",
        idempotency_key=f"drift-{table_id}-{field_name}-{detected_at}",
        source="drift",
        signal_type="drift",
        quality_score=score_for("drift_detected"),
        org_unit_id=org_unit_id,
        table_id=table_id,
        table_name=table_name,
        field_name=field_name,
        payload={"details": details or {}},
    )


def capture_workspace_feedback(message) -> DqFeedbackEvent | None:
    """Capture a DQ feedback signal from a judged AIMessage, if it carries DQ context.

    The AI workspace stores DQ context in ``metadata_json["dq"]`` (e.g.
    ``{"rule_id": ..., "table_id": ..., "field_name": ..., "definition": ...}``).
    No DQ context → no-op (returns None). Best-effort from the caller.
    """
    from ai.models import AIMessage

    if message.role != "assistant":
        return None
    meta = message.metadata_json or {}
    dq_ctx = meta.get("dq") or {}
    if not dq_ctx:
        return None
    if message.outcome not in ("accepted", "rejected", "corrected"):
        return None

    rule_id = dq_ctx.get("rule_id")
    if not rule_id:
        return None

    if message.outcome == "corrected":
        return capture_rule_correction(
            rule_id=rule_id,
            rule_name=dq_ctx.get("rule_name", ""),
            table_id=dq_ctx.get("table_id"),
            table_name=dq_ctx.get("table_name", ""),
            field_name=dq_ctx.get("field_name", ""),
            corrected_definition=dq_ctx.get("definition") or message.correction_text,
            previous_definition=dq_ctx.get("previous_definition"),
            correction_text=message.correction_text or "",
            user_id=(
                str(message.conversation.user_id)
                if message.conversation and message.conversation.user_id
                else None
            ),
            message_id=str(message.id),
            org_unit_id=dq_ctx.get("org_unit_id"),
        )

    # accepted / rejected workspace outcomes map to suggestion-style signals.
    event_type = f"suggest_{message.outcome}"
    return _create_event(
        event_type=event_type,
        idempotency_key=f"workspace-{message.outcome}-{message.id}",
        source="nl_check",
        signal_type=EVENT_SIGNAL_MAP[event_type][0],
        quality_score=score_for(event_type),
        org_unit_id=dq_ctx.get("org_unit_id"),
        rule_id=rule_id,
        rule_name=dq_ctx.get("rule_name", ""),
        table_id=dq_ctx.get("table_id"),
        table_name=dq_ctx.get("table_name", ""),
        field_name=dq_ctx.get("field_name", ""),
        message_id=str(message.id),
        user_id=(
            str(message.conversation.user_id)
            if message.conversation and message.conversation.user_id
            else None
        ),
        payload={
            "definition": dq_ctx.get("definition"),
            "note": "workspace outcome captured via metadata_json[dq]",
        },
    )


def _safe_org_unit_id(suggestion):
    """Best-effort org resolution from a DQSuggestion's table module."""
    try:
        table = suggestion.data_table
        if table is not None and getattr(table, "module_id", None):
            from core.models import Module

            module = Module.objects.filter(id=table.module_id).only("org_unit_id").first()
            if module:
                return module.org_unit_id
    except Exception:  # noqa: BLE001 — never let capture break the caller
        logger.debug("org_unit resolution failed for suggestion %s", suggestion.id)
    return None
