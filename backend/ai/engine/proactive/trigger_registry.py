"""
Trigger Registry — CRUD operations for proactive triggers and seeding from domain packs.

Triggers define conditions the system watches for: threshold crossings,
trend deviations, and signal correlations.
"""
import json
import logging
from datetime import datetime

from ai.engine.core.clock import utcnow
from typing import Optional

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.knowledge_graph.models import KgProactiveTrigger, TRIGGER_CATEGORIES, TRIGGER_SEVERITIES

logger = logging.getLogger("pulse.proactive.trigger_registry")


# ── Condition validation ─────────────────────────────────────────────────────

# Per-category required fields as enforced by trigger_evaluator.py
# Each entry: (field_path, type_check, description)
# field_path supports "signals[*].table" for nested list items.

_VALIDATORS: dict[str, dict[str, tuple]] = {
    "threshold": {
        "table": (str, "required: table name in host DB"),
        "column": (str, "required: column name to measure"),
        "value": ((int, float), "required: threshold value to compare against"),
    },
    "trend": {
        "table": (str, "required: table name in host DB"),
        "column": (str, "required: column name to track trend over"),
    },
    "correlation": {
        "signals": (list, "required: list of signal dicts, minimum 2 entries"),
    },
}

# Per-signal required fields for correlation
_SIGNAL_FIELDS = {
    "table": (str, "required in each correlation signal"),
    "column": (str, "required in each correlation signal"),
}

# Known zombie patterns — conditions that can never be evaluator-executable
_ZOMBIE_MARKERS = frozenset({"auto_generated", "api_path", "type", "metric", "field"})


def validate_condition(category: str, condition: dict) -> list[str]:
    """
    Validate a trigger condition against what the evaluator requires.

    Returns a list of violation strings (empty = valid).  Checks:
      - category is known (threshold / trend / correlation)
      - required fields are present with correct types
      - correlation signals list has ≥2 entries and each has table+column
      - zombie markers (auto_generated, api_path, type, metric, field)
        are flagged as non-evaluatable shapes
    """
    violations: list[str] = []

    if category not in _VALIDATORS:
        return [f"Unknown category '{category}' — must be threshold, trend, or correlation"]

    req = _VALIDATORS[category]

    # 1) Required fields
    for field, (expected_type, desc) in req.items():
        if field not in condition or condition[field] is None:
            violations.append(f"Missing required field '{field}' ({desc})")
        elif not isinstance(condition[field], expected_type):
            type_name = (
                " | ".join(t.__name__ for t in expected_type)
                if isinstance(expected_type, tuple)
                else expected_type.__name__
            )
            violations.append(
                f"Field '{field}' must be {type_name}, got {type(condition[field]).__name__}"
            )

    # 2) Correlation-specific: signals count + per-signal fields
    if category == "correlation":
        signals = condition.get("signals", [])
        if isinstance(signals, list):
            if len(signals) < 2:
                violations.append(
                    f"Correlation requires at least 2 signals, got {len(signals)}"
                )
            for i, sig in enumerate(signals):
                if not isinstance(sig, dict):
                    violations.append(f"signals[{i}] must be a dict, got {type(sig).__name__}")
                    continue
                for sfield, (stype, sdesc) in _SIGNAL_FIELDS.items():
                    if sfield not in sig or sig[sfield] is None:
                        violations.append(
                            f"signals[{i}] missing '{sfield}' ({sdesc})"
                        )
                    elif not isinstance(sig[sfield], stype):
                        violations.append(
                            f"signals[{i}].{sfield} must be {stype.__name__}, "
                            f"got {type(sig[sfield]).__name__}"
                        )
        else:
            violations.append(f"'signals' must be a list, got {type(signals).__name__}")

    # 3) Zombie-marker detection: if condition has only zombie keys (or
    #    zombie keys dominate), flag it.  A condition that has "rule" or
    #    "auto_generated" or "api_path" as its *only* meaningful keys is
    #    a zombie.  We detect this after required-field checks so the
    #    user sees both "missing required field" PLUS "zombie pattern".
    condition_keys = set(condition.keys())
    zombie_keys_in_use = condition_keys & _ZOMBIE_MARKERS
    if zombie_keys_in_use:
        # Only flag if the condition is missing core evaluator fields —
        # i.e. the zombie markers are in place OF real fields, not in
        # addition to them.
        core_fields: set[str] = set(req.keys())
        has_core = bool(condition_keys & core_fields)
        if not has_core:
            violations.append(
                f"Zombie condition: contains only non-evaluatable keys "
                f"{sorted(zombie_keys_in_use)} — the evaluator requires "
                f"{sorted(core_fields)}"
            )

    return violations


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create_trigger(
    db: AsyncSession,
    instance_id: str,
    name: str,
    category: str,
    description: str,
    condition: dict,
    *,
    severity: str = "info",
    data_sources: list | None = None,
    context_queries: list | None = None,
    recommended_actions: list | None = None,
    recipients: list | None = None,
    cooldown_seconds: int = 3600,
    source: str = "manual",
    _skip_validation: bool = False,
) -> str:
    """Create a proactive trigger. Returns its ID.

    All callers go through condition validation unless _skip_validation
    is True (reserved for tests that construct deliberately-valid conditions
    against known-good shapes — never for production callers).
    """
    if category not in TRIGGER_CATEGORIES:
        raise ValueError(f"Invalid category: {category}")
    if severity not in TRIGGER_SEVERITIES:
        raise ValueError(f"Invalid severity: {severity}")

    if not _skip_validation:
        violations = validate_condition(category, condition)
        if violations:
            msg = (
                f"Refusing to persist trigger '{name}' ({category}) — "
                f"condition cannot be evaluated: {'; '.join(violations)}"
            )
            logger.warning(msg)
            raise ValueError(msg)

    trigger = KgProactiveTrigger(
        instance_id=instance_id,
        name=name,
        category=category,
        description=description,
        severity=severity,
        condition_json=json.dumps(condition),
        data_sources_json=json.dumps(data_sources or []),
        context_queries_json=json.dumps(context_queries or []),
        recommended_actions_json=json.dumps(recommended_actions or []),
        recipients_json=json.dumps(recipients or []),
        cooldown_seconds=cooldown_seconds,
        source=source,
    )
    db.add(trigger)
    await db.commit()
    logger.info(f"Created trigger '{name}' ({category}/{severity}) for {instance_id}")
    return trigger.id


async def list_triggers(
    db: AsyncSession,
    instance_id: str,
    *,
    category: str | None = None,
    enabled_only: bool = True,
) -> list[dict]:
    """List triggers for an instance."""
    stmt = select(KgProactiveTrigger).where(
        KgProactiveTrigger.instance_id == instance_id,
    )
    if enabled_only:
        stmt = stmt.where(KgProactiveTrigger.enabled == True)  # noqa: E712
    if category:
        stmt = stmt.where(KgProactiveTrigger.category == category)
    stmt = stmt.order_by(KgProactiveTrigger.severity.desc(), KgProactiveTrigger.name)

    result = await db.execute(stmt)
    return [_trigger_to_dict(t) for t in result.scalars().all()]


async def get_trigger(db: AsyncSession, trigger_id: str) -> dict | None:
    """Get a single trigger by ID."""
    result = await db.execute(
        select(KgProactiveTrigger).where(KgProactiveTrigger.id == trigger_id)
    )
    trigger = result.scalar_one_or_none()
    return _trigger_to_dict(trigger) if trigger else None


async def update_trigger(
    db: AsyncSession,
    trigger_id: str,
    **updates,
) -> bool:
    """Update a trigger's fields. Returns True if found."""
    result = await db.execute(
        select(KgProactiveTrigger).where(KgProactiveTrigger.id == trigger_id)
    )
    trigger = result.scalar_one_or_none()
    if not trigger:
        return False

    json_fields = {
        "condition": "condition_json",
        "data_sources": "data_sources_json",
        "context_queries": "context_queries_json",
        "recommended_actions": "recommended_actions_json",
        "recipients": "recipients_json",
    }
    for key, value in updates.items():
        if key in json_fields:
            setattr(trigger, json_fields[key], json.dumps(value))
        elif hasattr(trigger, key):
            setattr(trigger, key, value)

    await db.commit()
    return True


async def delete_trigger(db: AsyncSession, trigger_id: str) -> bool:
    """Delete a trigger. Returns True if found."""
    result = await db.execute(
        select(KgProactiveTrigger).where(KgProactiveTrigger.id == trigger_id)
    )
    trigger = result.scalar_one_or_none()
    if not trigger:
        return False
    await db.delete(trigger)
    await db.commit()
    return True


async def record_fire(db: AsyncSession, trigger_id: str) -> None:
    """Record that a trigger has fired (update last_fired_at and fire_count)."""
    result = await db.execute(
        select(KgProactiveTrigger).where(KgProactiveTrigger.id == trigger_id)
    )
    trigger = result.scalar_one_or_none()
    if trigger:
        trigger.last_fired_at = utcnow()
        trigger.fire_count += 1
        await db.commit()


# ── Domain pack seeding ───────────────────────────────────────────────────────

async def seed_from_domain_pack(
    db: AsyncSession,
    instance_id: str,
    pack: dict,
    instance_config: dict | None = None,
) -> int:
    """
    Seed proactive triggers from a domain pack's validation_rules and
    schema_metadata.  Returns count of triggers created.

    Heuristics:
      - validation_rules.business_constraints → threshold triggers
      - schema_metadata.tables with alert/alarm/event in name → correlation seeds
      - vocabulary.glossary entries with threshold-like descriptions → trend triggers
      - If pack is empty and domain hints suggest power/energy, seed domain defaults
    """
    created = 0

    # 1) Business constraints → threshold triggers
    #    These are name-only — no table/column/value.  Skip with a log
    #    line; they cannot produce evaluator-executable conditions.
    validation = pack.get("validation_rules", {})
    constraints = validation.get("business_constraints", [])
    if constraints:
        logger.info(
            "Skipping %d business constraints for %s — no table/column/value derivable "
            "from constraint names alone",
            len(constraints), instance_id,
        )

    # 2) Alert/alarm tables → potential triggers
    #    We have table names but no column/value to monitor.
    #    Skip with a log line.
    schema = pack.get("schema_metadata", {})
    alert_tables = [
        tn for tn in schema.get("tables", {}).keys()
        if any(kw in tn.lower() for kw in ("alert", "alarm", "event", "incident", "fault"))
    ]
    if alert_tables:
        logger.info(
            "Skipping %d alert/alarm tables for %s — table name alone insufficient "
            "to derive evaluable threshold/trend/correlation condition",
            len(alert_tables), instance_id,
        )

    # 3) Domain-specific defaults when the pack is empty
    #    All previously hardcoded power-domain defaults were api_path-style
    #    conditions the SQL-only evaluator cannot execute.  Dropped entirely.
    #    See TASK-RESULTS-BE-00-proactive.md §Decision for rationale.
    #    If no triggers were created and the pack is empty, log a note.
    pack_is_empty = not any(pack.get(k) for k in ("validation_rules", "schema_metadata", "vocabulary"))
    if pack_is_empty and created == 0:
        logger.info(
            "Empty domain pack for %s — no triggers seeded (host DB tables unknown)",
            instance_id,
        )

    if created:
        logger.info(f"Seeded {created} triggers from domain pack for {instance_id}")
    return created


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _trigger_exists(db: AsyncSession, instance_id: str, name: str, source: str) -> bool:
    """Check if a trigger with the same name+source already exists."""
    result = await db.execute(
        select(sa_func.count()).select_from(KgProactiveTrigger).where(
            KgProactiveTrigger.instance_id == instance_id,
            KgProactiveTrigger.name == name,
            KgProactiveTrigger.source == source,
        )
    )
    return (result.scalar() or 0) > 0


def _trigger_to_dict(t: KgProactiveTrigger) -> dict:
    """Serialize a trigger ORM object to a plain dict."""
    return {
        "id": t.id,
        "instance_id": t.instance_id,
        "name": t.name,
        "category": t.category,
        "description": t.description,
        "severity": t.severity,
        "enabled": t.enabled,
        "condition": json.loads(t.condition_json),
        "data_sources": json.loads(t.data_sources_json),
        "context_queries": json.loads(t.context_queries_json),
        "recommended_actions": json.loads(t.recommended_actions_json),
        "recipients": json.loads(t.recipients_json),
        "cooldown_seconds": t.cooldown_seconds,
        "last_fired_at": t.last_fired_at.isoformat() if t.last_fired_at else None,
        "fire_count": t.fire_count,
        "source": t.source,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
