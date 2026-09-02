import logging
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

TRACKED_EMPLOYEE_FIELDS = {
    'org_unit_id', 'full_name', 'basic_salary', 'nationality',
    'join_date', 'rotation', 'is_active',
    'name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family',
    'civil_id', 'date_of_birth', 'gender', 'nationality_code',
    'employment_type_code', 'contract_type_code', 'kuwaitization',
    'manager_id', 'position_id',
}
TRACKED_POSITION_FIELDS = {
    'org_unit_id', 'code', 'title', 'grade', 'reports_to_id', 'is_management',
    'status', 'fte', 'job_family_code',
}


def _json_safe(value):
    """Coerce non-JSON-serializable model values (date/Decimal) to primitives.
    psycopg2's JSON adapter uses the stdlib encoder — no date/Decimal support."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def snapshot_employee(employee):
    return {
        f: _json_safe(getattr(employee, f))
        for f in TRACKED_EMPLOYEE_FIELDS
        if hasattr(employee, f)
    }


def snapshot_position(position):
    return {
        f: _json_safe(getattr(position, f))
        for f in TRACKED_POSITION_FIELDS
        if hasattr(position, f)
    }


def record_event(*, entity_type, entity_id, event_kind, effective_date, user,
                 before, after, notes=''):
    """Append a PersonnelEvent. Best-effort by design: failures are logged at
    CRITICAL but NEVER block the caller's mutation (see DESIGN §4.3 correction).
    Call inside the caller's transaction.atomic() block."""
    from .models import PersonnelEvent
    try:
        PersonnelEvent.objects.create(
            entity_type=entity_type,
            entity_id=entity_id,
            event_kind=event_kind,
            effective_date=effective_date,
            recorded_by=user,
            before=before,
            after=after,
            notes=notes,
        )
    except Exception:
        logger.critical(
            "PersonnelEvent emit failed: %s#%s kind=%s",
            entity_type, entity_id, event_kind, exc_info=True,
        )
