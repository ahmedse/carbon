"""seed_people_dq — Seed gate-eligible DQ rules for the People & Payroll domain.

Idempotent: re-running creates nothing new and leaves existing rules/bindings
untouched. Binds DQRules to typed models via ``ModelRuleAssignment``
(ADR 0025) so the Tier-1 write gate (``people/validation.py:validate_write``)
enforces them at write time.

Reference-set-backed rules (nationality, gender, employment/contract type,
rotation, job family) resolve their ``ReferenceSet`` id at seed time and are
**skipped with a warning** if the set is missing (reference data is seeded by
admins via ``seed_gofsco``; RULE_16 — never fabricate).

Run:
    cd backend && python manage.py seed_people_dq
"""
from django.core.management.base import BaseCommand

from dq.models import DQRule, ModelRuleAssignment
from mdm.models import ReferenceSet


def _definition(name, rule_type, dimension, severity, params):
    return {
        'schema_version': 1,
        'name': name,
        'level': 'field',
        'dimension': dimension,
        'type': rule_type,
        'severity': severity,
        'params': params,
        'enforcement': {'on_write': True},
        'active': True,
    }


def _ref_set_id(set_name):
    """Resolve a ReferenceSet id by name; None if not yet seeded."""
    rs = ReferenceSet.objects.filter(name__iexact=set_name).first()
    return rs.id if rs else None


def _allowed_ref(set_name):
    """params builder for allowed_values over a governed ReferenceSet."""
    sid = _ref_set_id(set_name)
    return None if sid is None else {'reference_set': sid}


# ── Rule catalog ────────────────────────────────────────────────────────────
# Each entry: name, model_label, field_name, rule_type, dimension, severity,
# and a params dict or callable (callable returns None to skip when its
# reference set is unseeded).
RULES = [
    # ── Employee master ──
    dict(name='employee-no-format', model='people.Employee', field='employee_no',
         rule_type='regex', dimension='validity', severity='warn',
         params={'pattern': r'^(\d{4,5}|[A-Z]{2}-\d{3})$'}),
    dict(name='civil-id-format', model='people.Employee', field='civil_id',
         rule_type='regex', dimension='validity', severity='error',
         params={'pattern': r'^\d{12}$'}),
    dict(name='gender-allowed', model='people.Employee', field='gender',
         rule_type='allowed_values', dimension='validity', severity='error',
         params=lambda: _allowed_ref('gender')),
    dict(name='nationality-code-allowed', model='people.Employee',
         field='nationality_code', rule_type='allowed_values', dimension='validity',
         severity='warn', params=lambda: _allowed_ref('nationality')),
    dict(name='employment-type-allowed', model='people.Employee',
         field='employment_type_code', rule_type='allowed_values',
         dimension='validity', severity='error',
         params=lambda: _allowed_ref('employment_type')),
    dict(name='contract-type-allowed', model='people.Employee',
         field='contract_type_code', rule_type='allowed_values',
         dimension='validity', severity='error',
         params=lambda: _allowed_ref('contract_type')),
    dict(name='rotation-allowed', model='people.Employee', field='rotation',
         rule_type='allowed_values', dimension='validity', severity='warn',
         params=lambda: _allowed_ref('rotation_pattern')),
    dict(name='basic-salary-non-negative', model='people.Employee',
         field='basic_salary', rule_type='range', dimension='validity',
         severity='error', params={'min': 0}),

    # ── Position ──
    dict(name='position-status-allowed', model='people.Position', field='status',
         rule_type='allowed_values', dimension='validity', severity='error',
         params={'values': ['proposed', 'open', 'filled', 'frozen', 'closed']}),
    dict(name='position-fte-range', model='people.Position', field='fte',
         rule_type='range', dimension='validity', severity='warn',
         params={'min': 0.05, 'max': 10}),
    dict(name='job-family-allowed', model='people.Position',
         field='job_family_code', rule_type='allowed_values', dimension='validity',
         severity='warn', params=lambda: _allowed_ref('job_family')),

    # ── Payroll ──
    dict(name='payroll-run-status-allowed', model='people.PayrollRun',
         field='status', rule_type='allowed_values', dimension='validity',
         severity='error',
         params={'values': ['draft', 'computed', 'validated', 'committed', 'failed']}),
    dict(name='payslip-line-type-allowed', model='people.PayslipLine',
         field='line_type', rule_type='allowed_values', dimension='validity',
         severity='warn',
         params={'values': ['gross', 'basic', 'overtime', 'leave_pay',
                            'eosi_accrual', 'gosi', 'deduction']}),

    # ── Leave ──
    dict(name='entitled-days-non-negative', model='people.LeaveEntitlement',
         field='entitled_days', rule_type='range', dimension='validity',
         severity='error', params={'min': 0}),
    dict(name='used-days-non-negative', model='people.LeaveEntitlement',
         field='used_days', rule_type='range', dimension='validity',
         severity='error', params={'min': 0}),
    dict(name='leave-days-non-negative', model='people.LeaveRecord',
         field='days', rule_type='range', dimension='validity',
         severity='error', params={'min': 0}),
]


class Command(BaseCommand):
    help = 'Seed gate-eligible DQ rules + ModelRuleAssignments for People & Payroll (idempotent).'

    def handle(self, *args, **options):
        created_rules = 0
        created_bindings = 0
        skipped = 0

        for spec in RULES:
            params = spec['params']() if callable(spec['params']) else spec['params']
            if params is None:
                self.stdout.write(self.style.WARNING(
                    f"  skip {spec['name']}: reference set not seeded"
                ))
                skipped += 1
                continue

            definition = _definition(
                spec['name'], spec['rule_type'], spec['dimension'],
                spec['severity'], params,
            )
            rule, rule_created = DQRule.objects.get_or_create(
                name=spec['name'],
                defaults={
                    'rule_type': spec['rule_type'],
                    'rule_level': 'field_validation',
                    'is_active': True,
                    'definition': definition,
                },
            )
            if rule_created:
                created_rules += 1
            # Keep the definition current on re-runs (e.g. reconciled pattern).
            elif rule.definition != definition:
                rule.definition = definition
                rule.save(update_fields=['definition'])

            _, binding_created = ModelRuleAssignment.objects.get_or_create(
                rule=rule,
                model_label=spec['model'],
                field_name=spec['field'],
                defaults={'is_active': True},
            )
            if binding_created:
                created_bindings += 1

        self.stdout.write(self.style.SUCCESS(
            f"seed_people_dq: {created_rules} rules created, "
            f"{created_bindings} bindings created, {skipped} skipped "
            f"(unseeded reference sets)"
        ))
