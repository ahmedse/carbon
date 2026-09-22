"""Revise a loan subject when its correspondence is edited (sent_back)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from .models import Loan

SUBJECT_TYPE = 'people.Loan'


class LoanReviseError(Exception):
    def __init__(self, detail, *, error_kind=None, status_code=400, **extra):
        super().__init__(detail)
        self.detail = detail
        self.error_kind = error_kind
        self.status_code = status_code
        self.extra = extra


def _parse_loan_fields(payload: dict):
    if not isinstance(payload, dict):
        raise LoanReviseError('payload must be an object', error_kind='invalid_payload')

    loan_type = payload.get('loan_type')
    if loan_type is None or (isinstance(loan_type, str) and not loan_type.strip()):
        raise LoanReviseError('loan_type is required', error_kind='loan_type_required')

    try:
        from mdm.governed import resolve_reference_value
        loan_type_rv = resolve_reference_value(
            'loan_type',
            loan_type.strip() if isinstance(loan_type, str) else loan_type,
            require_current=False,
        )
    except Exception:
        loan_type_rv = None
    if loan_type_rv is None:
        raise LoanReviseError(
            f'Unknown loan_type {loan_type!r}',
            error_kind='invalid_loan_type',
        )

    try:
        principal = Decimal(str(payload.get('principal')))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise LoanReviseError(
            'principal must be a positive number',
            error_kind='invalid_principal',
        ) from exc
    if principal <= 0:
        raise LoanReviseError(
            'principal must be a positive number',
            error_kind='invalid_principal',
        )

    try:
        interest_rate = Decimal(str(payload.get('interest_rate', '0')))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise LoanReviseError(
            'interest_rate must be a non-negative number',
            error_kind='invalid_interest',
        ) from exc
    if interest_rate < 0:
        raise LoanReviseError(
            'interest_rate must be a non-negative number',
            error_kind='invalid_interest',
        )

    try:
        term_months = int(payload.get('term_months'))
    except (ValueError, TypeError) as exc:
        raise LoanReviseError(
            'term_months must be a positive integer',
            error_kind='invalid_term',
        ) from exc
    if term_months <= 0:
        raise LoanReviseError(
            'term_months must be a positive integer',
            error_kind='invalid_term',
        )

    try:
        start_date = date.fromisoformat(str(payload.get('start_date', '')))
    except (ValueError, TypeError) as exc:
        raise LoanReviseError(
            'Invalid start_date (expected ISO date)',
            error_kind='invalid_dates',
        ) from exc

    notes = payload.get('notes', '') or ''
    if not isinstance(notes, str):
        notes = str(notes)

    return loan_type_rv, principal, interest_rate, term_months, start_date, notes


def _requester_profile(corr):
    try:
        return corr.requester.employee_profile
    except ObjectDoesNotExist:
        return None
    except AttributeError:
        return None


def _ensure_draft_loan(corr, loan_type_rv, principal, interest_rate, term_months, start_date, notes):
    loan = None
    if corr.subject_id:
        loan = Loan.objects.select_related('employee', 'loan_type').filter(
            pk=corr.subject_id,
        ).first()

    if loan is not None:
        if loan.status != 'draft':
            if corr.status == 'sent_back':
                loan.status = 'draft'
                loan.save(update_fields=['status'])
            else:
                raise LoanReviseError(
                    f'Cannot revise loan in status {loan.status!r}',
                    error_kind='invalid_status',
                    status_code=409,
                )
        return loan

    profile = _requester_profile(corr)
    if profile is None:
        raise LoanReviseError(
            'Requester has no employee profile to attach loan',
            error_kind='no_profile',
            status_code=409,
        )

    loan = Loan.objects.create(
        employee=profile,
        loan_type=loan_type_rv,
        principal=principal,
        interest_rate=interest_rate,
        term_months=term_months,
        start_date=start_date,
        notes=notes,
        status='draft',
    )
    corr.subject_type = SUBJECT_TYPE
    corr.subject_id = loan.pk
    corr.save(update_fields=['subject_type', 'subject_id', 'updated_at'])
    return loan


def apply_loan_payload_edit(corr, payload: dict) -> tuple[dict, str]:
    if corr.subject_type and corr.subject_type != SUBJECT_TYPE:
        raise LoanReviseError(
            'Correspondence subject is not a loan',
            error_kind='wrong_subject',
            status_code=409,
        )

    loan_type_rv, principal, interest_rate, term_months, start_date, notes = (
        _parse_loan_fields(payload)
    )

    with transaction.atomic():
        loan = _ensure_draft_loan(
            corr, loan_type_rv, principal, interest_rate, term_months, start_date, notes,
        )
        loan.loan_type = loan_type_rv
        loan.principal = principal
        loan.interest_rate = interest_rate
        loan.term_months = term_months
        loan.start_date = start_date
        loan.notes = notes
        loan.save(update_fields=[
            'loan_type', 'principal', 'interest_rate', 'term_months',
            'start_date', 'notes',
        ])

    normalized = {
        'loan_type': loan_type_rv.code,
        'principal': str(principal),
        'interest_rate': str(interest_rate),
        'term_months': term_months,
        'start_date': str(start_date),
        'notes': notes,
    }
    title = f'Loan request {loan_type_rv.code} {principal}'
    return normalized, title
