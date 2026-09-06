# correspondence/management/commands/seed_correspondence.py
# Seeds the governed MDM reference sets for the e-Office Correspondence domain.
# Idempotent — uses update_or_create; safe to run repeatedly.

from django.core.management.base import BaseCommand
from django.db import transaction

from correspondence.models import WorkflowPolicy, WorkflowPolicyStep
from mdm.models import ReferenceSet, ReferenceValue


# (set_name, description, [(code, label_en, label_ar), ...]) in listed sort order.
REFERENCE_SETS = [
    (
        'correspondence_type',
        'Types of correspondence handled by the e-Office workflow.',
        [
            ('leave_request', 'Leave Request', 'طلب إجازة'),
            ('loan_request', 'Loan Request', 'طلب سلفة'),
            ('profile_change', 'Profile Change', 'تعديل بيانات'),
            ('internal_memo', 'Internal Memo', 'مذكرة داخلية'),
            ('circular', 'Circular', 'تعميم'),
            ('decision', 'Decision', 'قرار'),
        ],
    ),
    (
        'leave_type',
        'Kinds of leave available to employees.',
        [
            ('annual', 'Annual Leave', 'إجازة سنوية'),
            ('sick', 'Sick Leave', 'إجازة مرضية'),
            ('emergency', 'Emergency Leave', 'إجازة طارئة'),
            ('unpaid', 'Unpaid Leave', 'إجازة بدون أجر'),
            ('maternity', 'Maternity Leave', 'إجازة وضع'),
            ('paternity', 'Paternity Leave', 'إجازة أبوة'),
        ],
    ),
    (
        'memo_type',
        'Kinds of internal memorandum.',
        [
            ('internal_note', 'Internal Note', 'ملاحظة داخلية'),
            ('directive', 'Directive', 'توجيه'),
            ('announcement', 'Announcement', 'إعلان'),
        ],
    ),
]


class Command(BaseCommand):
    help = (
        'Seeds correspondence reference sets '
        '(correspondence_type, leave_type, memo_type) — idempotent.'
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            for name, description, values in REFERENCE_SETS:
                self._seed_set(name, description, values)
            self._seed_default_leave_policy()

    def _seed_set(self, name, description, values):
        ref_set, created = ReferenceSet.objects.update_or_create(
            name=name,
            defaults={
                'description': description,
                'is_active': True,
                'lifecycle_state': ReferenceSet.LIFECYCLE_ACTIVE,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f'ReferenceSet {name!r} {"created" if created else "unchanged"}')
        )

        for index, (code, label_en, label_ar) in enumerate(values, start=1):
            value, value_created = ReferenceValue.objects.update_or_create(
                reference_set=ref_set,
                code=code,
                defaults={
                    'label': label_en,
                    'description': f'{label_en} ({label_ar})',
                    'is_active': True,
                    'sort_order': index,
                    'metadata': {'label_ar': label_ar, 'sort': index},
                },
            )
            self.stdout.write(
                f'  {name}:{code} {"created" if value_created else "unchanged"}'
            )

    def _seed_default_leave_policy(self):
        leave_request_value = ReferenceValue.objects.get(
            reference_set__name='correspondence_type', code='leave_request'
        )
        policy, policy_created = WorkflowPolicy.objects.update_or_create(
            corr_type=leave_request_value, org_unit=None, version='1.0.0',
            defaults={
                'name': 'Leave Request Default',
                'is_active': True,
                'numbering_format': '{PREFIX}-{YEAR}-{SEQ:04d}',
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'WorkflowPolicy leave_request v1.0.0 '
                f'{"created" if policy_created else "unchanged"}'
            )
        )

        step, step_created = WorkflowPolicyStep.objects.update_or_create(
            policy=policy, order=1,
            defaults={
                'role': 'manager',
                'intent': 'approve',
                'skip_if_self': True,
                'is_active': True,
            },
        )
        self.stdout.write(
            f'  WorkflowPolicyStep order=1 '
            f'{"created" if step_created else "unchanged"}'
        )
