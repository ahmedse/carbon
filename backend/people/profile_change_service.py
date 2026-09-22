# File: people/profile_change_service.py
# NSR-5A — apply allowlisted Employee fields when a profile_change
# correspondence is approved.
#
# Submit stores free-form ``payload.changes`` as ``{field: {from?, to}}``
# (see ProfileChangeSelfView). Only a narrow allowlist of safe personal /
# display fields is applied on approve. Unknown keys are ignored (not
# written). Reject / cancel never call this path.
#
# Structural / payroll / identity-control fields (org_unit, employee_no,
# basic_salary, manager, position, civil_id, is_active, employment/contract
# codes, kuwaitization, …) are intentionally excluded. Submit and edit both
# reject non-allowlisted keys (parity); apply still ignores unknowns as a
# defense-in-depth on approve.

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from catalog.audit_utils import emit_governance_event

from .chronicle import record_event, snapshot_employee
from .models import Employee

logger = logging.getLogger(__name__)

# Narrow allowlist: personal/display CharField + DOB only. Keep in sync with
# TASK-RESULTS NSR-5A documentation when extending.
PROFILE_CHANGE_ALLOWLIST = frozenset({
    'full_name',
    'name_en_given',
    'name_en_family',
    'name_ar_given',
    'name_ar_family',
    'nationality',
    'gender',
    'date_of_birth',
})


def _coerce_value(field: str, raw: Any) -> Any:
    """Coerce a payload ``to`` value to something assignable on Employee."""
    if field == 'date_of_birth':
        if raw is None or raw == '':
            return None
        if isinstance(raw, date) and not isinstance(raw, datetime):
            return raw
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, str):
            return date.fromisoformat(raw[:10])
        raise ValueError(f'unsupported date_of_birth value: {raw!r}')
    if field in ('nationality', 'gender'):
        if raw is None or raw == '':
            return None
        from mdm.governed import resolve_reference_value
        from mdm.models import ReferenceValue
        set_name = 'nationality' if field == 'nationality' else 'gender'
        try:
            return resolve_reference_value(set_name, raw, require_current=False)
        except Exception:
            # Allow label writes from legacy profile_change payloads.
            rv = ReferenceValue.objects.filter(
                reference_set__name=set_name, label__iexact=str(raw).strip(),
            ).first()
            if rv is None:
                raise ValueError(f'unknown {field} value: {raw!r}')
            return rv
    if raw is None:
        return ''
    return str(raw)


def extract_allowlisted_updates(changes: dict | None) -> dict[str, Any]:
    """Return ``{field: coerced_to}`` for allowlisted keys only.

    Unknown keys and malformed change entries are skipped (ignored). A bad
    coerced value for an allowlisted key is also skipped (logged) so a single
    bad field cannot block the rest — and never raises into the signal path.
    """
    if not isinstance(changes, dict) or not changes:
        return {}

    updates: dict[str, Any] = {}
    for field, change in changes.items():
        if field not in PROFILE_CHANGE_ALLOWLIST:
            continue
        if not isinstance(change, dict) or 'to' not in change:
            continue
        try:
            updates[field] = _coerce_value(field, change['to'])
        except (TypeError, ValueError) as exc:
            logger.warning(
                'profile_change: skip field %r — coerce failed: %s', field, exc,
            )
    return updates


def apply_profile_change(*, employee: Employee, changes: dict | None, actor) -> dict[str, Any]:
    """Apply allowlisted changes to ``employee``. Returns the applied dict.

    No-ops (and returns ``{}``) when there is nothing allowlisted to write or
    when every allowlisted value already matches. Emits chronicle + governance
    only when at least one field actually changes.
    """
    updates = extract_allowlisted_updates(changes)
    if not updates:
        return {}

    pending = {
        field: value
        for field, value in updates.items()
        if getattr(employee, field) != value
    }
    if not pending:
        return {}

    before = snapshot_employee(employee)
    with transaction.atomic():
        for field, value in pending.items():
            setattr(employee, field, value)
        employee.save(update_fields=[*pending.keys(), 'updated_at'])

        after = snapshot_employee(employee)
        record_event(
            entity_type='Employee',
            entity_id=employee.pk,
            event_kind='profile_updated',
            effective_date=timezone.localdate(),
            user=actor,
            before=before,
            after=after,
            notes='Applied from approved profile_change correspondence',
        )
        emit_governance_event(
            entity_type='Employee',
            entity_id=employee.pk,
            action='profile_change_applied',
            before={k: before.get(k) for k in pending},
            after={k: after.get(k) for k in pending},
            user=actor,
        )

    return pending


def reverse_profile_change(
    *,
    employee: Employee,
    changes: dict | None,
    actor,
    reason: str = 'Reverted profile_change correspondence',
) -> dict[str, Any]:
    """Restore allowlisted fields from payload ``from`` values when present.

    Fields without a usable ``from`` are skipped (cannot safely invent prior
    state). No-ops when nothing reverseable remains.
    """
    if not isinstance(changes, dict) or not changes:
        return {}

    pending: dict[str, Any] = {}
    for field, change in changes.items():
        if field not in PROFILE_CHANGE_ALLOWLIST:
            continue
        if not isinstance(change, dict) or 'from' not in change:
            continue
        try:
            value = _coerce_value(field, change['from'])
        except (TypeError, ValueError) as exc:
            logger.warning(
                'profile_change reverse: skip field %r — coerce failed: %s',
                field, exc,
            )
            continue
        if getattr(employee, field) != value:
            pending[field] = value

    if not pending:
        return {}

    before = snapshot_employee(employee)
    with transaction.atomic():
        for field, value in pending.items():
            setattr(employee, field, value)
        employee.save(update_fields=[*pending.keys(), 'updated_at'])

        after = snapshot_employee(employee)
        record_event(
            entity_type='Employee',
            entity_id=employee.pk,
            event_kind='profile_updated',
            effective_date=timezone.localdate(),
            user=actor,
            before=before,
            after=after,
            notes=reason,
        )
        emit_governance_event(
            entity_type='Employee',
            entity_id=employee.pk,
            action='profile_change_reverted',
            before={k: before.get(k) for k in pending},
            after={k: after.get(k) for k in pending},
            user=actor,
        )

    return pending
