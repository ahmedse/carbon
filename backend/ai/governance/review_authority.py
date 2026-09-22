"""Map Pulse human_task capabilities → host CBAC authority (NPS-2 / ADR-0045).

Plane B inbox tasks historically defaulted ``required_authority`` to
``ai:operator``. That is correct for generic Pulse governance, but **wrong**
for Nibras HR process reviews — managers / finance / people_lead hold the
real authority, not the AI operator role.

This module is the shared resolver (platform-shaped, not per-view). Unmapped
capabilities keep ``ai:operator`` so non-HR Pulse tasks stay unchanged.
"""

from __future__ import annotations

from accounts.capabilities import (
    AI_OPERATOR,
    ALL_CAPABILITIES,
    CORRESPONDENCE_ACT,
    CORRESPONDENCE_FINANCE,
    PEOPLE_MANAGE,
)

DEFAULT_REQUIRED_AUTHORITY = AI_OPERATOR.key

# Nibras `*.review` capability_id → host CBAC key that may approve/decline.
# Keep in sync with domain_packs/nibras processes + ADR-0045 NPS-2/NPS-3 matrix.
REVIEW_AUTHORITY_BY_CAPABILITY: dict[str, str] = {
    "leave.request.review": CORRESPONDENCE_ACT.key,
    "loan.request.review": CORRESPONDENCE_FINANCE.key,
    "payroll.run.review": PEOPLE_MANAGE.key,
    "gosi_wps.sif.review": PEOPLE_MANAGE.key,
    "employee.onboarding.review": PEOPLE_MANAGE.key,
    "attendance.permission.review": CORRESPONDENCE_ACT.key,
}


def resolve_required_authority(capability: str | None) -> str:
    """Return the CBAC key that must approve a human task for ``capability``.

    Fail-open to the platform default only for *unmapped* capabilities (generic
    Pulse). Mapped Nibras reviews never fall back to ``ai:operator``.
    """
    if not capability:
        return DEFAULT_REQUIRED_AUTHORITY
    mapped = REVIEW_AUTHORITY_BY_CAPABILITY.get(capability)
    if mapped is not None:
        return mapped
    return DEFAULT_REQUIRED_AUTHORITY


def known_hr_review_authorities() -> frozenset[str]:
    """Distinct host CBAC keys used as Nibras review authorities."""
    return frozenset(REVIEW_AUTHORITY_BY_CAPABILITY.values())


def assert_registry_keys_are_cbac() -> None:
    """Fail-closed guard: every mapped authority must exist in ALL_CAPABILITIES."""
    missing = sorted(
        key
        for key in known_hr_review_authorities()
        if key not in ALL_CAPABILITIES
    )
    if missing:
        raise AssertionError(
            f"REVIEW_AUTHORITY_BY_CAPABILITY references unknown CBAC keys: {missing}"
        )
