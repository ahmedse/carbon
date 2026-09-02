# people/management/commands/seed_gofsco.py
# Seeds realistic GOFSCO (Gas & Oil Field Services Company, Kuwait) HR data.
# Derived from: raw/GOFSCO app/20260728/Issues with Hard Task HRMS System.docx
# Context: KOC field-services company; rotation statuses; Kuwait Labour Law;
# Kuwaitization; KOC gate-pass certifications; EOSI; GOSI; WPS.

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seed realistic GOFSCO HR data (employees, entitlements, certs, benefits, loans)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Clear existing people data before seeding (non-destructive by default)',
        )

    def handle(self, *args, **options):
        from mdm.models import OrgUnit
        from people.models import (
            BenefitType, Certification, Employee, EmployeeBenefit,
            LeaveEntitlement, Loan, PayrollRun, PersonnelEvent, Position,
        )
        from people.chronicle import record_event, snapshot_employee

        if options['clear']:
            PersonnelEvent.objects.all().delete()
            Loan.objects.all().delete()
            EmployeeBenefit.objects.all().delete()
            Certification.objects.all().delete()
            LeaveEntitlement.objects.all().delete()
            PayrollRun.objects.all().delete()
            Employee.objects.all().delete()
            Position.objects.all().delete()
            BenefitType.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing people data'))

        # ── Governed reference metadata (mdm.ReferenceSet) ────────────────
        # Configures the governed enums that Employee/Position serializers
        # validate against (nationality, employment_type, contract_type,
        # job_family) plus supporting HR taxonomies. Without these, the
        # serializer code-validation is silently skipped (RULE_16).
        from mdm.models import ReferenceSet, ReferenceValue

        def _ref_set(name, slug, description, values):
            rs, _ = ReferenceSet.objects.get_or_create(
                name=name,
                defaults={
                    'slug': slug,
                    'description': description,
                    'is_active': True,
                    'lifecycle_state': 'active',
                },
            )
            ReferenceSet.objects.filter(pk=rs.pk).update(
                name=name, slug=slug, is_active=True, lifecycle_state='active',
            )
            for idx, (code, label) in enumerate(values):
                ReferenceValue.objects.update_or_create(
                    reference_set=rs, code=code,
                    defaults={'label': label, 'is_active': True, 'sort_order': idx},
                )
            return rs

        _ref_set('nationality', 'nationality', 'Employee nationalities', [
            ('KWT', 'Kuwaiti'), ('EGY', 'Egyptian'), ('IND', 'Indian'),
            ('PHL', 'Filipino'), ('PAK', 'Pakistani'), ('BGD', 'Bangladeshi'),
            ('NPL', 'Nepali'), ('LKA', 'Sri Lankan'), ('JOR', 'Jordanian'),
            ('SYR', 'Syrian'), ('USA', 'American'), ('GBR', 'British'),
        ])
        _ref_set('employment_type', 'employment-type', 'Employment types', [
            ('full-time', 'Full-Time'), ('part-time', 'Part-Time'),
            ('contract', 'Contract'), ('secondment', 'Secondment'),
        ])
        _ref_set('contract_type', 'contract-type', 'Contract types', [
            ('indeterminate', 'Indeterminate (Open-ended)'),
            ('fixed-term', 'Fixed-Term'),
            ('project', 'Project-Based'),
        ])
        _ref_set('job_family', 'job-family', 'Job families', [
            ('operations', 'Operations'), ('maintenance', 'Maintenance'),
            ('engineering', 'Engineering'), ('hse', 'HSE'),
            ('hr', 'Human Resources'), ('finance', 'Finance'),
            ('admin', 'Administration'),
        ])
        _ref_set('gender', 'gender', 'Genders', [
            ('male', 'Male'), ('female', 'Female'),
        ])
        _ref_set('rotation_pattern', 'rotation-pattern', 'Rotation schedules', [
            ('1/1', '1 week on / 1 week off'),
            ('2/1', '2 weeks on / 1 week off'),
            ('3/1', '3 weeks on / 1 week off'),
            ('5/1', '5 weeks on / 1 week off'),
            ('office', 'Office (non-rotational)'),
        ])
        _ref_set('benefit_category', 'benefit-category', 'Benefit categories', [
            ('accommodation', 'Accommodation'), ('vehicle', 'Vehicle'),
            ('medical', 'Medical'), ('school', 'School'),
            ('tickets', 'Tickets'), ('overtime', 'Overtime'),
        ])
        _ref_set('leave_type', 'leave-type', 'Leave types', [
            ('annual', 'Annual'), ('sick', 'Sick'), ('emergency', 'Emergency'),
            ('maternity', 'Maternity'), ('unpaid', 'Unpaid'),
        ])

        # ── Resolve / create org units ────────────────────────────────────
        from django.utils.text import slugify

        def _ou(code, name, parent=None):
            slug_base = slugify(code)
            try:
                ou, _ = OrgUnit.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'parent': parent, 'slug': slug_base},
                )
            except Exception:
                OrgUnit.objects.filter(code=code).update(name=name)
                ou = OrgUnit.objects.get(code=code)
            return ou

        root_ou  = _ou('GOFSCO', 'GOFSCO — Gas & Oil Field Services Company')
        ops_ou   = _ou('OPS',   'Operations Division',       root_ou)
        hr_ou    = _ou('HR',    'Human Resources',           root_ou)
        finance_ou = _ou('FIN', 'Finance & Accounting',      root_ou)
        maint_ou = _ou('MAINT', 'Maintenance & Technical',   ops_ou)

        # ── Benefit Types ─────────────────────────────────────────────────
        BT_DEFS = [
            ('ACCOM', 'Accommodation Allowance', 'accommodation', True, False),
            ('VEHICLE', 'Company Vehicle Allowance', 'vehicle', True, False),
            ('MEDICAL', 'Medical Insurance', 'medical', False, False),
            ('SCHOOL', 'School Fees', 'school', False, False),
            ('TICKETS', 'Annual Air Tickets', 'tickets', True, False),
            ('OT_BASE', 'Overtime Base', 'other', True, False),
        ]
        bt_map = {}
        for code, name, cat, is_eosi, is_tax in BT_DEFS:
            bt, _ = BenefitType.objects.get_or_create(
                code=code, defaults={'name': name, 'category': cat, 'is_eosi_base': is_eosi, 'is_taxable': is_tax},
            )
            bt_map[code] = bt

        # ── Positions ─────────────────────────────────────────────────────
        pos_ops_mgr, _ = Position.objects.get_or_create(
            code='POS-001', defaults={
                'title': 'Operations Manager', 'org_unit': ops_ou,
                'grade': 'M1', 'is_management': True, 'status': 'filled', 'fte': decimal.Decimal('1.0'),
            },
        )
        pos_sr_eng, _ = Position.objects.get_or_create(
            code='POS-002', defaults={
                'title': 'Senior Field Engineer', 'org_unit': ops_ou,
                'grade': 'E3', 'is_management': False, 'status': 'filled', 'fte': decimal.Decimal('1.0'),
                'reports_to': pos_ops_mgr,
            },
        )
        pos_ops_sup, _ = Position.objects.get_or_create(
            code='POS-003', defaults={
                'title': 'Operations Supervisor', 'org_unit': ops_ou,
                'grade': 'E2', 'is_management': False, 'status': 'filled', 'fte': decimal.Decimal('1.0'),
                'reports_to': pos_sr_eng,
            },
        )
        pos_hr_off, _ = Position.objects.get_or_create(
            code='POS-004', defaults={
                'title': 'HR Officer', 'org_unit': hr_ou,
                'grade': 'A2', 'is_management': False, 'status': 'filled', 'fte': decimal.Decimal('1.0'),
            },
        )
        pos_tech, _ = Position.objects.get_or_create(
            code='POS-005', defaults={
                'title': 'Field Technician', 'org_unit': maint_ou,
                'grade': 'T2', 'is_management': False, 'status': 'filled', 'fte': decimal.Decimal('1.0'),
                'reports_to': pos_ops_sup,
            },
        )
        pos_field_op, _ = Position.objects.get_or_create(
            code='POS-006', defaults={
                'title': 'Field Operator', 'org_unit': ops_ou,
                'grade': 'T1', 'is_management': False, 'status': 'filled', 'fte': decimal.Decimal('1.0'),
                'reports_to': pos_tech,
            },
        )

        # Backfill job-family metadata (governed enum) onto seeded positions.
        for pos, fam in [
            (pos_ops_mgr, 'operations'),
            (pos_sr_eng, 'engineering'),
            (pos_ops_sup, 'operations'),
            (pos_hr_off, 'hr'),
            (pos_tech, 'maintenance'),
            (pos_field_op, 'operations'),
        ]:
            if pos.job_family_code != fam:
                pos.job_family_code = fam
                pos.save(update_fields=['job_family_code'])

        # ── Employees ─────────────────────────────────────────────────────
        # Based on GOFSCO context: mixed Kuwaiti nationals + expats,
        # multiple rotation statuses, different benefit packages.
        EMP_DEFS = [
            {
                'employee_no': 'GF-001',
                'full_name': 'Mohammed Al-Rashidi',
                'name_en_given': 'Mohammed', 'name_en_family': 'Al-Rashidi',
                'name_ar_given': 'محمد', 'name_ar_family': 'الراشدي',
                'civil_id': '281041200123',
                'date_of_birth': date(1981, 4, 12),
                'gender': 'male',
                'nationality': 'Kuwaiti',
                'nationality_code': 'KWT',
                'org_unit': ops_ou,
                'position': pos_sr_eng,
                'basic_salary': decimal.Decimal('1800.000'),
                'join_date': date(2019, 3, 15),
                'rotation': '1/1',
                'employment_type_code': 'full-time',
                'contract_type_code': 'indeterminate',
                'kuwaitization': True,
                'is_active': True,
            },
            {
                'employee_no': 'GF-002',
                'full_name': 'Ahmed Ibrahim Hassan',
                'name_en_given': 'Ahmed', 'name_en_family': 'Hassan',
                'name_ar_given': 'أحمد', 'name_ar_family': 'حسن',
                'civil_id': '299010101234',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'male',
                'nationality': 'Egyptian',
                'nationality_code': 'EGY',
                'org_unit': ops_ou,
                'position': pos_ops_sup,
                'basic_salary': decimal.Decimal('1400.000'),
                'join_date': date(2021, 6, 1),
                'rotation': '2/1',
                'employment_type_code': 'full-time',
                'contract_type_code': 'fixed-term',
                'kuwaitization': False,
                'is_active': True,
            },
            {
                'employee_no': 'GF-003',
                'full_name': 'Fatima Al-Shalabi',
                'name_en_given': 'Fatima', 'name_en_family': 'Al-Shalabi',
                'name_ar_given': 'فاطمة', 'name_ar_family': 'الشلبي',
                'civil_id': '298061510045',
                'date_of_birth': date(1993, 6, 15),
                'gender': 'female',
                'nationality': 'Kuwaiti',
                'nationality_code': 'KWT',
                'org_unit': hr_ou,
                'position': pos_hr_off,
                'basic_salary': decimal.Decimal('1200.000'),
                'join_date': date(2020, 9, 10),
                'rotation': '',
                'employment_type_code': 'full-time',
                'contract_type_code': 'indeterminate',
                'kuwaitization': True,
                'is_active': True,
            },
            {
                'employee_no': 'GF-004',
                'full_name': 'Rajesh Kumar',
                'name_en_given': 'Rajesh', 'name_en_family': 'Kumar',
                'name_ar_given': '', 'name_ar_family': '',
                'civil_id': '300021800456',
                'date_of_birth': date(1988, 2, 18),
                'gender': 'male',
                'nationality': 'Indian',
                'nationality_code': 'IND',
                'org_unit': maint_ou,
                'position': pos_tech,
                'basic_salary': decimal.Decimal('850.000'),
                'join_date': date(2022, 11, 20),
                'rotation': '3/1',
                'employment_type_code': 'full-time',
                'contract_type_code': 'fixed-term',
                'kuwaitization': False,
                'is_active': True,
            },
            {
                'employee_no': 'GF-005',
                'full_name': 'Carlos Santos',
                'name_en_given': 'Carlos', 'name_en_family': 'Santos',
                'name_ar_given': '', 'name_ar_family': '',
                'civil_id': '303041500789',
                'date_of_birth': date(1995, 4, 15),
                'gender': 'male',
                'nationality': 'Filipino',
                'nationality_code': 'PHL',
                'org_unit': ops_ou,
                'position': pos_field_op,
                'basic_salary': decimal.Decimal('650.000'),
                'join_date': date(2023, 4, 1),
                'rotation': '5/1',
                'employment_type_code': 'full-time',
                'contract_type_code': 'fixed-term',
                'kuwaitization': False,
                'is_active': True,
            },
        ]

        emp_map = {}
        for d in EMP_DEFS:
            emp, created = Employee.objects.update_or_create(
                employee_no=d['employee_no'],
                defaults={k: v for k, v in d.items() if k != 'employee_no'},
            )
            emp_map[d['employee_no']] = emp
            if created:
                record_event(
                    entity_type='Employee', entity_id=emp.pk, event_kind='hired',
                    effective_date=emp.join_date,
                    user=None, before=None, after=snapshot_employee(emp),
                    notes=f'Joined {d["org_unit"].name} — seeded from GOFSCO HR records',
                )

        # ── Leave Entitlements (current + prior year) ─────────────────────
        # Kuwait Labour Law: expats = 30 days after 1yr, Kuwaitization (KWT) = 42 days
        CURRENT = timezone.localdate().year
        ENT_DEFS = [
            # emp_no, year, leave_type, entitled, used, carried
            ('GF-001', CURRENT, 'annual', 42, 8, 0),      # Kuwaitization = 42 days
            ('GF-001', CURRENT, 'sick', 30, 2, 0),
            ('GF-001', CURRENT - 1, 'annual', 42, 42, 0), # All used prior year
            ('GF-002', CURRENT, 'annual', 30, 15, 5),     # 5 carried from prior yr
            ('GF-002', CURRENT, 'sick', 30, 0, 0),
            ('GF-002', CURRENT - 1, 'annual', 30, 25, 5),
            ('GF-003', CURRENT, 'annual', 42, 12, 0),     # Kuwaitization = 42 days
            ('GF-003', CURRENT, 'sick', 30, 5, 0),
            ('GF-003', CURRENT, 'emergency', 5, 2, 0),
            ('GF-004', CURRENT, 'annual', 30, 18, 0),
            ('GF-004', CURRENT, 'sick', 15, 3, 0),
            ('GF-005', CURRENT, 'annual', 30, 8, 0),
            ('GF-005', CURRENT, 'sick', 15, 0, 0),
        ]
        for emp_no, yr, ltype, entitled, used, carried in ENT_DEFS:
            emp = emp_map.get(emp_no)
            if emp:
                LeaveEntitlement.objects.update_or_create(
                    employee=emp, year=yr, leave_type=ltype,
                    defaults={
                        'entitled_days': decimal.Decimal(str(entitled)),
                        'used_days': decimal.Decimal(str(used)),
                        'carried_forward': decimal.Decimal(str(carried)),
                    },
                )

        # ── Certifications (KOC field-services required certs) ────────────
        today_d = timezone.localdate()
        CERT_DEFS = [
            # emp_no, cert_type, number, issued, expiry (None = no expiry)
            ('GF-001', 'BOSIET', 'BST-2024-001', date(2024, 3, 10), date(2026, 9, 25)),  # expiring ~23 days
            ('GF-001', 'H2S Safety', 'H2S-2021-441', date(2021, 7, 20), date(2026, 7, 19)),  # EXPIRED
            ('GF-001', 'KOC Gate Pass (Green)', 'KGP-7821', date(2024, 1, 5), date(2027, 1, 5)),
            ('GF-001', 'First Aid & CPR', 'FA-2025-088', date(2025, 1, 15), date(2027, 1, 15)),
            ('GF-001', 'Fire Warden', 'FW-2023-321', date(2023, 6, 1), date(2026, 12, 1)),  # 90d notice
            ('GF-002', 'H2S Safety', 'H2S-2024-222', date(2024, 9, 1), date(2026, 9, 1)),   # EXPIRED 1d ago
            ('GF-002', 'First Aid & CPR', 'FA-2024-205', date(2024, 3, 20), date(2026, 3, 20)),  # EXPIRED
            ('GF-002', 'KOC Gate Pass (Blue)', 'KGP-9012', date(2024, 6, 10), date(2027, 6, 10)),
            ('GF-002', 'Fire Warden', 'FW-2024-088', date(2024, 11, 1), date(2026, 11, 1)),
            ('GF-003', 'KOC Visitor Pass', 'KVP-3411', date(2025, 2, 1), date(2026, 12, 1)),
            ('GF-003', 'First Aid & CPR', 'FA-2025-099', date(2025, 8, 1), date(2027, 8, 1)),
            ('GF-004', 'BOSIET', 'BST-2023-774', date(2023, 11, 5), date(2025, 11, 5)),   # EXPIRED
            ('GF-004', 'H2S Safety', 'H2S-2025-891', date(2025, 5, 10), date(2027, 5, 10)),
            ('GF-004', 'KOC Gate Pass (Blue)', 'KGP-5544', date(2025, 3, 1), date(2028, 3, 1)),
            ('GF-004', 'Confined Space Entry', 'CSE-2024-012', date(2024, 7, 20), date(2026, 10, 1)),  # 29d
            ('GF-005', 'BOSIET', 'BST-2024-902', date(2024, 4, 1), date(2026, 4, 1)),     # EXPIRED
            ('GF-005', 'H2S Safety', 'H2S-2025-333', date(2025, 9, 1), date(2027, 9, 1)),
            ('GF-005', 'KOC Gate Pass (Blue)', 'KGP-6677', date(2025, 4, 1), date(2027, 4, 1)),
        ]
        for emp_no, cert_type, number, issued, expiry in CERT_DEFS:
            emp = emp_map.get(emp_no)
            if emp:
                Certification.objects.update_or_create(
                    employee=emp, cert_type=cert_type, number=number,
                    defaults={'issued_date': issued, 'expiry_date': expiry},
                )

        # ── Employee Benefits ─────────────────────────────────────────────
        BEN_DEFS = [
            # emp_no, benefit_type_code, monthly_amount, start
            ('GF-001', 'ACCOM', decimal.Decimal('250.000'), date(2019, 4, 1)),
            ('GF-001', 'VEHICLE', decimal.Decimal('150.000'), date(2019, 4, 1)),
            ('GF-001', 'MEDICAL', decimal.Decimal('0.000'), date(2019, 4, 1)),     # KOC covers
            ('GF-001', 'TICKETS', decimal.Decimal('200.000'), date(2019, 4, 1)),
            ('GF-002', 'ACCOM', decimal.Decimal('180.000'), date(2021, 7, 1)),
            ('GF-002', 'MEDICAL', decimal.Decimal('0.000'), date(2021, 7, 1)),
            ('GF-002', 'TICKETS', decimal.Decimal('180.000'), date(2021, 7, 1)),
            ('GF-003', 'ACCOM', decimal.Decimal('200.000'), date(2020, 10, 1)),
            ('GF-003', 'MEDICAL', decimal.Decimal('0.000'), date(2020, 10, 1)),
            ('GF-003', 'TICKETS', decimal.Decimal('160.000'), date(2020, 10, 1)),
            ('GF-004', 'ACCOM', decimal.Decimal('120.000'), date(2022, 12, 1)),
            ('GF-004', 'MEDICAL', decimal.Decimal('0.000'), date(2022, 12, 1)),
            ('GF-005', 'ACCOM', decimal.Decimal('100.000'), date(2023, 5, 1)),
            ('GF-005', 'MEDICAL', decimal.Decimal('0.000'), date(2023, 5, 1)),
        ]
        for emp_no, bt_code, amount, start in BEN_DEFS:
            emp = emp_map.get(emp_no)
            bt = bt_map.get(bt_code)
            if emp and bt:
                EmployeeBenefit.objects.update_or_create(
                    employee=emp, benefit_type=bt,
                    defaults={'monthly_amount': amount, 'effective_start': start},
                )

        # ── Loans ─────────────────────────────────────────────────────────
        from people.models import LoanInstallment
        LOAN_DEFS = [
            # emp_no, loan_type, principal, rate, months, start, status
            ('GF-001', 'Personal Loan', decimal.Decimal('3000.000'), decimal.Decimal('0.000'), 12, date(2025, 6, 1), 'active'),
            ('GF-002', 'Emergency Loan', decimal.Decimal('1500.000'), decimal.Decimal('0.000'), 6, date(2026, 1, 1), 'active'),
            ('GF-004', 'Personal Loan', decimal.Decimal('1000.000'), decimal.Decimal('0.000'), 10, date(2024, 3, 1), 'paid_off'),
        ]
        for emp_no, ltype, principal, rate, months, start, status in LOAN_DEFS:
            emp = emp_map.get(emp_no)
            if emp:
                from people.models import Loan
                loan, _ = Loan.objects.update_or_create(
                    employee=emp, loan_type=ltype, start_date=start,
                    defaults={'principal': principal, 'interest_rate': rate, 'term_months': months, 'status': status},
                )

        # ── Timeline events (salary changes, promotions) ──────────────────
        EV_DEFS = [
            # emp_no, event_kind, effective_date, notes, before_salary, after_salary
            ('GF-001', 'salary_change', date(2021, 4, 1), 'Annual increment Y2', 1600, 1800),
            ('GF-001', 'contract_renewed', date(2022, 3, 15), 'Contract renewed — indeterminate', None, None),
            ('GF-001', 'salary_change', date(2024, 1, 1), 'KOC contract rate adjustment', 1800, 1900),
            ('GF-002', 'promoted', date(2023, 6, 1), 'Promoted to Supervisor after 2yr service', None, None),
            ('GF-002', 'salary_change', date(2023, 6, 1), 'Salary adjustment on promotion', 1200, 1400),
            ('GF-003', 'transferred', date(2022, 1, 10), 'Transferred from Operations to HR', None, None),
            ('GF-004', 'contract_renewed', date(2024, 11, 20), 'Fixed-term contract renewed for 2 years', None, None),
        ]
        for emp_no, kind, eff_date, notes, before_sal, after_sal in EV_DEFS:
            emp = emp_map.get(emp_no)
            if emp:
                before = {'basic_salary': str(before_sal)} if before_sal else {}
                after = {'basic_salary': str(after_sal)} if after_sal else {}
                record_event(
                    entity_type='Employee', entity_id=emp.pk, event_kind=kind,
                    effective_date=eff_date, user=None,
                    before=before or None, after=after or None, notes=notes,
                )

        count = Employee.objects.count()
        from mdm.models import ReferenceSet
        self.stdout.write(self.style.SUCCESS(
            f'GOFSCO seed complete: {count} employees, {len(EMP_DEFS)} upserted, '
            f'{Certification.objects.count()} certifications, '
            f'{LeaveEntitlement.objects.count()} leave entitlements, '
            f'{EmployeeBenefit.objects.count()} benefits, '
            f'{ReferenceSet.objects.count()} reference sets (metadata)'
        ))
