"""People host governance package (ADR-0045 SoD gate)."""

from people.governance.sod import (  # noqa: F401
    ACTION_ACTIVATE,
    ACTION_APPROVE,
    ACTION_COMMIT,
    ACTION_SUBMIT,
    SUBJECT_ATTENDANCE_PERMISSION,
    SUBJECT_EMPLOYEE,
    SUBJECT_PAYROLL_RUN,
    SUBJECT_WPS_FILING,
    SoDViolation,
    get_preparer,
    record_preparer,
    require_distinct_actor,
    require_sod,
)
