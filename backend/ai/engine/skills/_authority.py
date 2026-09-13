"""P1-06 — gate-only promotion authority and status transition table.

The admission gate (``skills/gate.py``) is the single door through which a
skill may reach ``instance_promoted``.  This module holds two things:

* ``SKILL_STATUS_TRANSITIONS`` — the explicit, closed table of legal status
  transitions.  ``instance_promoted`` is a *gate-only* destination: no storage
  helper may move a skill into that status on its own.
* ``_PROMOTION_TOKEN`` — an opaque singleton capability minted here.  The
  private promotion helper on ``SkillsStore`` requires this token and raises
  ``RuntimeError`` when it is missing or forged, so no code path other than
  the gate can silently promote a skill past the critics.

Nothing here is a stub: the table is authoritative for every transition the
gate or registry performs, and the token check is a hard identity comparison.
"""

from __future__ import annotations

# Explicit transition table.  ``instance_promoted`` is the gate-only
# destination: it may only be reached through a successful admission.
SKILL_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"user_approved", "instance_promoted", "deprecated"}),
    "user_approved": frozenset({"instance_promoted", "draft", "deprecated"}),
    "instance_promoted": frozenset({"deprecated"}),
    "deprecated": frozenset(),
}


def assert_allowed_transition(current: str, target: str) -> None:
    """Raise ``ValueError`` unless ``current → target`` is a legal transition.

    Unknown current states fail closed: no entry in the table means no
    transition is allowed.
    """
    allowed = SKILL_STATUS_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValueError(
            f"Illegal skill status transition: {current!r} → {target!r}"
        )


class _PromotionToken:
    """Opaque capability.  Only the singleton ``_PROMOTION_TOKEN`` is valid."""

    __slots__ = ()


_PROMOTION_TOKEN = _PromotionToken()


def check_promotion_token(token: object) -> None:
    """Raise ``RuntimeError`` unless ``token`` is the gate's singleton.

    This is the enforcement mechanism for "callable only from the gate": the
    private promotion helpers accept a token argument and reject anything but
    the exact singleton instance, so a direct call without it fails closed.
    """
    if token is not _PROMOTION_TOKEN:
        raise RuntimeError(
            "skill promotion is gate-only: call the admission gate, not this "
            "private helper directly"
        )
