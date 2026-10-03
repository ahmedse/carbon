# people/inbound_cartridges.py — typed load objects (ADR-0060).
# inbound.registry is imported; inbound never imports this module.

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date

from catalog.audit_utils import emit_governance_event
from inbound.registry import register
from inbound.smoke import envelope, issue, row_result
from mdm.models import OrgUnit, ReferenceValue

from .models import Employee, LeaveEntitlement, LeaveRecord, Position

EMPLOYEE_FIELDS = [
    {'name': 'employee_no', 'label': 'Employee number', 'required': True},
    {'name': 'full_name', 'label': 'Full name', 'required': True},
    {'name': 'name_en_given', 'label': 'Given name (EN)', 'required': False},
    {'name': 'name_en_family', 'label': 'Family name (EN)', 'required': False},
    {'name': 'civil_id', 'label': 'Civil ID', 'required': False},
    {'name': 'org_unit', 'label': 'Org unit code', 'required': True},
    {'name': 'position', 'label': 'Position title', 'required': False},
    {'name': 'join_date', 'label': 'Join date', 'required': False},
    {'name': 'basic_salary', 'label': 'Basic salary', 'required': True},
    {'name': 'kuwaitization', 'label': 'Kuwaitization', 'required': False},
    {'name': 'nationality', 'label': 'Nationality code', 'required': False, 'ref_set': 'nationality'},
    {'name': 'gender', 'label': 'Gender code', 'required': False, 'ref_set': 'gender'},
    {'name': 'employment_type', 'label': 'Employment type', 'required': False, 'ref_set': 'employment_type'},
    {'name': 'rotation', 'label': 'Rotation', 'required': False, 'ref_set': 'rotation_pattern'},
    {'name': 'manager_employee_no', 'label': 'Manager employee number', 'required': False},
    {'name': 'is_active', 'label': 'Active', 'required': False},
]

BALANCE_FIELDS = [
    {'name': 'employee_no', 'label': 'Employee number', 'required': True},
    {'name': 'year', 'label': 'Year', 'required': True},
    {'name': 'leave_type', 'label': 'Leave type code', 'required': True, 'ref_set': 'leave_type'},
    {'name': 'entitled_days', 'label': 'Entitled days', 'required': True},
    {'name': 'used_days', 'label': 'Used days', 'required': False},
    {'name': 'carried_forward', 'label': 'Carried forward', 'required': False},
]

HISTORY_FIELDS = [
    {'name': 'employee_no', 'label': 'Employee number', 'required': True},
    {'name': 'leave_type', 'label': 'Leave type code', 'required': True, 'ref_set': 'leave_type'},
    {'name': 'start_date', 'label': 'Start date', 'required': True},
    {'name': 'end_date', 'label': 'End date', 'required': True},
    {'name': 'days', 'label': 'Days', 'required': True},
    {'name': 'status', 'label': 'Status', 'required': False},
]


def _truthy(value) -> bool:
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'y')


def _dec(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


_BOM = '\ufeff'
_DATE_SPLIT = re.compile(r'[/.\-]')


def _clean(value) -> str:
    """Trim whitespace and a leading BOM; empty/whitespace-only -> ''."""
    if value is None:
        return ''
    return str(value).replace(_BOM, '').strip()


def _date(value):
    """Parse a date cell deterministically, or return None when empty/unparseable.

    Accepted, in this precedence:

    * ``YYYY-MM-DD`` (ISO; also ``YYYY-M-D``) — year first.
    * ``YYYY/M/D`` and ``YYYY.M.D`` — year first.
    * the shipped template order ``M/D/YYYY`` and ``M/D/YY`` — month first.

    ``/``, ``-`` and ``.`` are interchangeable, surrounding whitespace and a
    leading BOM are ignored, and empty/whitespace-only is ``None`` (missing is
    allowed; no date is invented). A value is only read day-first when that is
    unambiguous — the first component is greater than 12 (``25/12/2024``);
    otherwise the documented template order (month-first) wins, so
    ``03/04/2024`` is 2024-03-04.
    """
    text = _clean(value)
    if not text:
        return None
    parsed = parse_date(text)
    if parsed is not None:
        return parsed
    parts = [part.strip() for part in _DATE_SPLIT.split(text)]
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    first, second, third = parts
    if len(first) == 4:
        year, month, day = int(first), int(second), int(third)
    elif len(third) in (2, 4):
        if int(first) > 12:
            day, month, year = int(first), int(second), int(third)
        else:
            month, day, year = int(first), int(second), int(third)
        if len(third) == 2:
            year += 2000 if year <= 68 else 1900
    else:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _org(code: str):
    code = (code or '').strip()
    if not code:
        return None
    return (
        OrgUnit.objects.filter(code=code).first()
        or OrgUnit.objects.filter(slug=code).first()
        or OrgUnit.objects.filter(name=code).first()
    )


def _ref(set_name: str, code: str):
    code = (code or '').strip()
    if not code:
        return None
    return ReferenceValue.objects.filter(
        reference_set__name=set_name, code=code,
    ).first()


def _position(title: str, org):
    title = (title or '').strip()
    if not title or org is None:
        return None
    obj = Position.objects.filter(title=title, org_unit=org).first()
    if obj:
        return obj
    return Position.objects.create(title=title, code=title[:64], org_unit=org)


def employee_snapshot_smoke(rows, **_kwargs):
    insert = update = skip = reject = 0
    results = []
    reject_rows = []
    existing = set(
        Employee.objects.filter(
            employee_no__in=[(r.get('employee_no') or '').strip() for r in rows if r.get('employee_no')],
        ).values_list('employee_no', flat=True)
    )
    for i, row in enumerate(rows, start=1):
        no = (row.get('employee_no') or '').strip()
        issues = []
        if not no:
            issues.append(issue(
                'employee_no', 'employee_no empty',
                'Fill the employee number column; it is the key for this row.',
            ))
        if not (row.get('full_name') or '').strip():
            issues.append(issue(
                'full_name', 'full_name empty',
                'Fill the full name column.',
            ))
        if _org(row.get('org_unit')) is None:
            issues.append(issue(
                'org_unit', 'org_unit unresolved',
                'Use an existing org unit code, slug, or name.',
            ))
        if _dec(row.get('basic_salary')) is None:
            issues.append(issue(
                'basic_salary', 'basic_salary missing',
                'Enter a numeric basic salary (for example 100.000).',
            ))
        join_text = _clean(row.get('join_date'))
        if join_text and _date(join_text) is None:
            issues.append(issue(
                'join_date', 'join_date invalid',
                'Use a date like 2024-01-02 (YYYY-MM-DD) or 1/2/2024 (M/D/YYYY).',
            ))
        if issues:
            verdict = 'reject'
            reject += 1
        elif no in existing:
            verdict = 'update'
            update += 1
        else:
            verdict = 'insert'
            insert += 1
        entry = row_result(i, no, verdict, issues)
        results.append(entry)
        if verdict == 'reject':
            reject_rows.append(entry)
    return envelope(
        counts={'insert': insert, 'update': update, 'skip': skip, 'reject': reject},
        results=results,
        reject_rows=reject_rows,
        reconcile_preview={'employees': insert + update},
    )


def employee_snapshot_commit(rows, *, batch, user, smoke, progress=None, **_kwargs):
    written = 0
    pending_managers = []
    for index, row in enumerate(rows, start=1):
        # Per-row beat for the durable commit run; the service batches the
        # persistence/publish (~50 rows or ~1s), so this is cheap.
        if progress:
            progress(index, written)
        no = (row.get('employee_no') or '').strip()
        org = _org(row.get('org_unit'))
        salary = _dec(row.get('basic_salary'))
        if not no or org is None or salary is None or not (row.get('full_name') or '').strip():
            continue
        defaults = {
            'full_name': row.get('full_name').strip(),
            'org_unit': org,
            'basic_salary': salary,
            'is_active': True if row.get('is_active') in (None, '') else _truthy(row.get('is_active')),
        }
        for fld in ('name_en_given', 'name_en_family', 'civil_id'):
            if row.get(fld):
                defaults[fld] = row[fld]
        join_date = _date(row.get('join_date'))
        if join_date:
            defaults['join_date'] = join_date
        if row.get('kuwaitization') not in (None, ''):
            defaults['kuwaitization'] = _truthy(row.get('kuwaitization'))
        if row.get('position'):
            defaults['position'] = _position(row.get('position'), org)
        for fld, set_name in (
            ('nationality', 'nationality'),
            ('gender', 'gender'),
            ('employment_type', 'employment_type'),
            ('rotation', 'rotation_pattern'),
        ):
            if row.get(fld):
                ref = _ref(set_name, row.get(fld))
                if ref:
                    defaults[fld] = ref
        emp, created = Employee.objects.update_or_create(employee_no=no, defaults=defaults)
        emit_governance_event(
            entity_type='Employee', entity_id=emp.id,
            action='inbound_insert' if created else 'inbound_update',
            before={}, after={'employee_no': no, 'batch_id': batch.id},
            user=user,
        )
        mgr_no = (row.get('manager_employee_no') or '').strip()
        if mgr_no:
            pending_managers.append((emp.id, mgr_no))
        written += 1
    for emp_id, mgr_no in pending_managers:
        mgr = Employee.objects.filter(employee_no=mgr_no).first()
        if mgr and mgr.id != emp_id:
            Employee.objects.filter(id=emp_id).update(manager=mgr)
    return {'written': written, 'reconcile': {'employees': written}}


def leave_balance_smoke(rows, **_kwargs):
    insert = update = skip = reject = 0
    results = []
    reject_rows = []
    for i, row in enumerate(rows, start=1):
        no = (row.get('employee_no') or '').strip()
        issues = []
        emp = Employee.objects.filter(employee_no=no).first() if no else None
        leave_type = _ref('leave_type', row.get('leave_type'))
        if emp is None:
            issues.append(issue(
                'employee_no', 'employee not found',
                'Add the employee first, or correct the employee number.',
            ))
        if not str(row.get('year') or '').isdigit():
            issues.append(issue(
                'year', 'year invalid',
                'Enter the leave year as four digits (for example 2026).',
            ))
        if leave_type is None:
            issues.append(issue(
                'leave_type', 'leave_type unresolved',
                'Use a leave type code that exists in the leave type reference set.',
            ))
        if _dec(row.get('entitled_days')) is None:
            issues.append(issue(
                'entitled_days', 'entitled_days missing',
                'Enter the entitled days as a number.',
            ))
        if issues:
            verdict = 'reject'
            reject += 1
        else:
            exists = LeaveEntitlement.objects.filter(
                employee=emp, year=int(row['year']), leave_type=leave_type,
            ).exists()
            if exists:
                update += 1
            else:
                insert += 1
            verdict = 'ok'
        entry = row_result(i, no, verdict, issues)
        results.append(entry)
        if verdict == 'reject':
            reject_rows.append(entry)
    return envelope(
        counts={'insert': insert, 'update': update, 'skip': skip, 'reject': reject},
        results=results,
        reject_rows=reject_rows,
        reconcile_preview={'entitlements': insert + update},
    )


def leave_balance_commit(rows, *, batch, user, smoke, progress=None, **_kwargs):
    written = 0
    for index, row in enumerate(rows, start=1):
        if progress:
            progress(index, written)
        emp = Employee.objects.filter(employee_no=(row.get('employee_no') or '').strip()).first()
        ltype = _ref('leave_type', row.get('leave_type'))
        if emp is None or ltype is None or not str(row.get('year') or '').isdigit():
            continue
        entitled = _dec(row.get('entitled_days'))
        if entitled is None:
            continue
        ent, _ = LeaveEntitlement.objects.update_or_create(
            employee=emp, year=int(row['year']), leave_type=ltype,
            defaults={
                'entitled_days': entitled,
                'used_days': _dec(row.get('used_days')) or Decimal('0'),
                'carried_forward': _dec(row.get('carried_forward')) or Decimal('0'),
            },
        )
        emit_governance_event(
            entity_type='LeaveEntitlement', entity_id=ent.id,
            action='inbound_balance', before={}, after={'batch_id': batch.id},
            user=user,
        )
        written += 1
    return {'written': written, 'reconcile': {'entitlements': written}}


def leave_history_smoke(rows, **_kwargs):
    insert = update = skip = reject = 0
    results = []
    reject_rows = []
    for i, row in enumerate(rows, start=1):
        no = (row.get('employee_no') or '').strip()
        issues = []
        emp = Employee.objects.filter(employee_no=no).first() if no else None
        leave_type = _ref('leave_type', row.get('leave_type'))
        if emp is None:
            issues.append(issue(
                'employee_no', 'employee not found',
                'Add the employee first, or correct the employee number.',
            ))
        if leave_type is None:
            issues.append(issue(
                'leave_type', 'leave_type unresolved',
                'Use a leave type code that exists in the leave type reference set.',
            ))
        start_date = _date(row.get('start_date'))
        end_date = _date(row.get('end_date'))
        if not _clean(row.get('start_date')) or not _clean(row.get('end_date')):
            issues.append(issue(
                'start_date', 'dates required',
                'Fill both the start date and the end date (YYYY-MM-DD or M/D/YYYY).',
            ))
        else:
            if start_date is None:
                issues.append(issue(
                    'start_date', 'start_date invalid',
                    'Use a date like 2024-01-02 (YYYY-MM-DD) or 1/2/2024 (M/D/YYYY).',
                ))
            if end_date is None:
                issues.append(issue(
                    'end_date', 'end_date invalid',
                    'Use a date like 2024-01-10 (YYYY-MM-DD) or 1/10/2024 (M/D/YYYY).',
                ))
        if _dec(row.get('days')) is None:
            issues.append(issue(
                'days', 'days missing',
                'Enter the number of leave days as a number.',
            ))
        if issues:
            verdict = 'reject'
            reject += 1
        else:
            exists = LeaveRecord.objects.filter(
                employee=emp,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
            ).exists()
            if exists:
                update += 1
            else:
                insert += 1
            verdict = 'ok'
        entry = row_result(i, no, verdict, issues)
        results.append(entry)
        if verdict == 'reject':
            reject_rows.append(entry)
    return envelope(
        counts={'insert': insert, 'update': update, 'skip': skip, 'reject': reject},
        results=results,
        reject_rows=reject_rows,
        reconcile_preview={'leave_records': insert + update},
    )


def leave_history_commit(rows, *, batch, user, smoke, progress=None, **_kwargs):
    """Conversion history. Must not increment LeaveEntitlement.used_days."""
    written = 0
    days_sum = Decimal('0')
    for index, row in enumerate(rows, start=1):
        if progress:
            progress(index, written)
        emp = Employee.objects.filter(employee_no=(row.get('employee_no') or '').strip()).first()
        ltype = _ref('leave_type', row.get('leave_type'))
        days = _dec(row.get('days'))
        start_date = _date(row.get('start_date'))
        end_date = _date(row.get('end_date'))
        if emp is None or ltype is None or days is None or start_date is None or end_date is None:
            continue
        status = (row.get('status') or 'approved').strip().lower()
        if status not in dict(LeaveRecord.STATUS_CHOICES):
            status = 'approved'
        rec, created = LeaveRecord.objects.update_or_create(
            employee=emp, leave_type=ltype,
            start_date=start_date, end_date=end_date,
            defaults={'days': days, 'status': status},
        )
        emit_governance_event(
            entity_type='LeaveRecord', entity_id=rec.id,
            action='inbound_history', before={}, after={'batch_id': batch.id},
            user=user,
        )
        written += 1
        days_sum += days
    return {'written': written, 'reconcile': {'leave_records': written, 'days': str(days_sum)}}


def register_people_cartridges():
    register(
        kind='typed_object',
        key='people.employee_snapshot',
        label='Employee snapshot',
        label_ar='لقطة الموظف',
        fields=EMPLOYEE_FIELDS,
        smoke=employee_snapshot_smoke,
        commit=employee_snapshot_commit,
    )
    register(
        kind='typed_object',
        key='people.leave_opening_balance',
        label='Leave opening balance',
        label_ar='رصيد الإجازة الافتتاحي',
        fields=BALANCE_FIELDS,
        smoke=leave_balance_smoke,
        commit=leave_balance_commit,
    )
    register(
        kind='typed_object',
        key='people.leave_history',
        label='Leave history',
        label_ar='سجل الإجازات',
        fields=HISTORY_FIELDS,
        smoke=leave_history_smoke,
        commit=leave_history_commit,
    )
