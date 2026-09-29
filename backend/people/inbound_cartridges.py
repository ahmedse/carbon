# people/inbound_cartridges.py — typed load objects (ADR-0060).
# inbound.registry is imported; inbound never imports this module.

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from catalog.audit_utils import emit_governance_event
from inbound.registry import register
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
    reject_rows = []
    sample = []
    existing = set(
        Employee.objects.filter(
            employee_no__in=[(r.get('employee_no') or '').strip() for r in rows if r.get('employee_no')],
        ).values_list('employee_no', flat=True)
    )
    for i, row in enumerate(rows, start=1):
        no = (row.get('employee_no') or '').strip()
        reasons = []
        if not no:
            reasons.append('employee_no empty')
        if not (row.get('full_name') or '').strip():
            reasons.append('full_name empty')
        if _org(row.get('org_unit')) is None:
            reasons.append('org_unit unresolved')
        if _dec(row.get('basic_salary')) is None:
            reasons.append('basic_salary missing')
        verdict = 'reject' if reasons else ('update' if no in existing else 'insert')
        if verdict == 'reject':
            reject += 1
            reject_rows.append({'row': i, 'key': no, 'verdict': verdict, 'reason': '; '.join(reasons)})
        elif verdict == 'update':
            update += 1
        else:
            insert += 1
        if len(sample) < 20:
            sample.append({'row': i, 'key': no, 'verdict': verdict, 'reason': '; '.join(reasons)})
    return {
        'insert': insert, 'update': update, 'skip': skip, 'reject': reject,
        'sample': sample, 'reject_rows': reject_rows,
        'reconcile_preview': {'employees': insert + update},
    }


def employee_snapshot_commit(rows, *, batch, user, smoke, **_kwargs):
    written = 0
    pending_managers = []
    for row in rows:
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
        for fld in ('name_en_given', 'name_en_family', 'civil_id', 'join_date'):
            if row.get(fld):
                defaults[fld] = row[fld]
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
    reject_rows = []
    sample = []
    for i, row in enumerate(rows, start=1):
        no = (row.get('employee_no') or '').strip()
        reasons = []
        emp = Employee.objects.filter(employee_no=no).first() if no else None
        if emp is None:
            reasons.append('employee not found')
        if not str(row.get('year') or '').isdigit():
            reasons.append('year invalid')
        if _ref('leave_type', row.get('leave_type')) is None:
            reasons.append('leave_type unresolved')
        if _dec(row.get('entitled_days')) is None:
            reasons.append('entitled_days missing')
        if reasons:
            reject += 1
            reject_rows.append({'row': i, 'key': no, 'verdict': 'reject', 'reason': '; '.join(reasons)})
        else:
            exists = LeaveEntitlement.objects.filter(
                employee=emp, year=int(row['year']),
                leave_type=_ref('leave_type', row.get('leave_type')),
            ).exists()
            if exists:
                update += 1
            else:
                insert += 1
        if len(sample) < 20:
            sample.append({'row': i, 'key': no, 'verdict': 'reject' if reasons else 'ok', 'reason': '; '.join(reasons)})
    return {
        'insert': insert, 'update': update, 'skip': skip, 'reject': reject,
        'sample': sample, 'reject_rows': reject_rows,
        'reconcile_preview': {'entitlements': insert + update},
    }


def leave_balance_commit(rows, *, batch, user, smoke, **_kwargs):
    written = 0
    for row in rows:
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
    reject_rows = []
    sample = []
    for i, row in enumerate(rows, start=1):
        no = (row.get('employee_no') or '').strip()
        reasons = []
        emp = Employee.objects.filter(employee_no=no).first() if no else None
        if emp is None:
            reasons.append('employee not found')
        if _ref('leave_type', row.get('leave_type')) is None:
            reasons.append('leave_type unresolved')
        if not row.get('start_date') or not row.get('end_date'):
            reasons.append('dates required')
        if _dec(row.get('days')) is None:
            reasons.append('days missing')
        if reasons:
            reject += 1
            reject_rows.append({'row': i, 'key': no, 'verdict': 'reject', 'reason': '; '.join(reasons)})
        else:
            exists = LeaveRecord.objects.filter(
                employee=emp,
                leave_type=_ref('leave_type', row.get('leave_type')),
                start_date=row.get('start_date'),
                end_date=row.get('end_date'),
            ).exists()
            if exists:
                update += 1
            else:
                insert += 1
        if len(sample) < 20:
            sample.append({'row': i, 'key': no, 'verdict': 'reject' if reasons else 'ok', 'reason': '; '.join(reasons)})
    return {
        'insert': insert, 'update': update, 'skip': skip, 'reject': reject,
        'sample': sample, 'reject_rows': reject_rows,
        'reconcile_preview': {'leave_records': insert + update},
    }


def leave_history_commit(rows, *, batch, user, smoke, **_kwargs):
    """Conversion history. Must not increment LeaveEntitlement.used_days."""
    written = 0
    days_sum = Decimal('0')
    for row in rows:
        emp = Employee.objects.filter(employee_no=(row.get('employee_no') or '').strip()).first()
        ltype = _ref('leave_type', row.get('leave_type'))
        days = _dec(row.get('days'))
        if emp is None or ltype is None or days is None:
            continue
        status = (row.get('status') or 'approved').strip().lower()
        if status not in dict(LeaveRecord.STATUS_CHOICES):
            status = 'approved'
        rec, created = LeaveRecord.objects.update_or_create(
            employee=emp, leave_type=ltype,
            start_date=row.get('start_date'), end_date=row.get('end_date'),
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
