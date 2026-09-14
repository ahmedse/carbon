"""Host predicates for the Phase 3 pilot (P3-02).

Pure, deterministic, host-side assertion functions — the reviewed host
implementations of the read-only ``assertion`` capabilities in the domain pack.
They never touch the database and never mutate state (RULE_21); they only
inspect an already-loaded rule's revision metadata.

The predicate ``dq.rule.active_revision_matches_approved_revision`` expresses
the pilot's postcondition: after ``publish``, the rule's *active* revision must
equal its *approved* revision (docs/pulse/PILOT.md step "verify"). It reads the
two revisions from a rule-like object's ``definition`` dict first (the DQ
source of truth), then a plain mapping, then plain attributes — and fails
closed (returns ``False``) when either revision is missing or incoercible.
"""

from __future__ import annotations

from typing import Any


def _revision(rule: Any, key: str) -> str | int | None:
    """Extract a revision value from a rule-like object, prefer the definition."""
    definition = getattr(rule, "definition", None)
    if isinstance(definition, dict) and key in definition:
        return definition[key]
    if isinstance(rule, dict) and key in rule:
        return rule[key]
    return getattr(rule, key, None)


def dq_rule_active_revision_matches_approved_revision(rule: Any) -> bool:
    """True iff the rule's active revision equals its approved revision.

    Fail-closed: missing/incoercible revisions → ``False`` (never a false
    "verified" on absent data).
    """
    active = _revision(rule, "active_revision")
    approved = _revision(rule, "approved_revision")
    if active is None or approved is None:
        return False
    try:
        return str(active) == str(approved)
    except (TypeError, ValueError):
        return False
