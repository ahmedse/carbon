# File: people/sensitivity.py
# Progressive-disclosure policy for sensitive employee fields.
#
# Info is revealed in tiers, never all-at-once:
#   L0 Operational — always visible (name, employee_no, org unit, rotation, status).
#   L1 Personal    — masked by default in the UI (civil_id, date_of_birth).
#   L2 Compensation— RESTRICTED: stripped by the API unless the caller holds
#                    ``people:view_compensation``; every reveal is audited via
#                    ``catalog.audit_utils.emit_governance_event``.
#
# This module is the single source of truth for which fields are sensitive and
# who may see them. Views call ``mask_employee`` / ``mask_employee_list`` before
# responding; the compensation reveal endpoint lives in ``views.py``.

from __future__ import annotations

from .permissions import is_global_admin

# Fields removed from employee payloads for callers without compensation access.
COMPENSATION_FIELDS = ('basic_salary',)

# Tier-1 fields — returned in the payload but masked by default in the UI.
# (Masking is a client concern; these are listed here for documentation and so
# the reveal endpoint can share one taxonomy.)
PII_FIELDS = ('civil_id', 'date_of_birth')


def can_view_compensation(user) -> bool:
    """True if the user may see compensation amounts (global admin or CBAC)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if is_global_admin(user):
        return True
    from accounts.capabilities import has_capability
    return has_capability(user, 'people:view_compensation')


def mask_employee(data: dict, user) -> dict:
    """Strip compensation fields from a single employee payload when unauthorized."""
    if can_view_compensation(user):
        return data
    masked = dict(data)
    for field in COMPENSATION_FIELDS:
        masked.pop(field, None)
    return masked


def mask_employee_list(results: list, user) -> list:
    """Strip compensation fields from every employee payload in ``results``."""
    return [mask_employee(d, user) for d in results]
