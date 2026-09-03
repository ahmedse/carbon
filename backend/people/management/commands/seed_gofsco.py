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

        # ── Compensation components (the governed catalog) ─────────────────
        # These replace PayslipLine.line_type free text. Policy flags feed the
        # calculation engine: EOSI base (Kuwait gratuity), GOSI base, WPS file.
        from people.models import CompensationComponent

        COMP_COMPONENTS = [
            # code,              name,                          direction,   eosi,  gosi,  wps,   taxable, variable, sort
            ('basic',            'Basic Salary',                'earning',   True,  True,  True,  False,   False,    10),
            ('housing',          'Housing Allowance',           'earning',   True,  False, True,  False,   False,    20),
            ('transport',        'Transport Allowance',         'earning',   False, False, True,  False,   False,    30),
            ('social',           'Social Allowance',            'earning',   False, False, True,  False,   False,    35),
            ('kuwaitization',    'Kuwaitization Allowance',     'earning',   False, False, True,  False,   False,    40),
            ('overtime',         'Overtime Pay',                'earning',   False, False, True,  False,   True,     50),
            ('tickets',          'Annual Air Tickets',          'earning',   True,  False, True,  False,   False,    60),
            ('school',           'School Fees',                 'earning',   False, False, False, False,   False,    70),
            ('vehicle',          'Vehicle Allowance',           'earning',   True,  False, True,  False,   False,    80),
            ('other_allowance',  'Other Allowance',             'earning',   False, False, True,  False,   True,     90),
            ('gosi_employee',    'GOSI Employee Contribution',  'deduction', False, False, True,  False,   False,   110),
            ('eosi_accrual',     'EOSI / Gratuity Accrual',    'deduction', False, False, False, False,   False,   120),
            ('loan_deduction',   'Loan / Advance Deduction',   'deduction', False, False, True,  False,   True,    130),
            ('wps_deduction',    'WPS Deduction',               'deduction', False, False, True,  False,   False,   140),
            ('other_deduction',  'Other Deduction',             'deduction', False, False, True,  False,   True,    150),
        ]
        for (code, name, direction, eosi, gosi, wps, taxable, variable, sort) in COMP_COMPONENTS:
            CompensationComponent.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'direction': direction,
                    'is_eosi_base': eosi,
                    'is_gosi_base': gosi,
                    'is_wps_relevant': wps,
                    'is_taxable': taxable,
                    'is_variable': variable,
                    'sort_order': sort,
                    'is_active': True,
                },
            )
        self.stdout.write(self.style.SUCCESS(f'  Compensation components: {CompensationComponent.objects.count()} total'))

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
                # Idempotent: skip if a re-seed already recorded this event.
                if PersonnelEvent.objects.filter(
                    entity_type='Employee', entity_id=emp.pk,
                    event_kind=kind, effective_date=eff_date,
                ).exists():
                    continue
                before = {'basic_salary': str(before_sal)} if before_sal else {}
                after = {'basic_salary': str(after_sal)} if after_sal else {}
                record_event(
                    entity_type='Employee', entity_id=emp.pk, event_kind=kind,
                    effective_date=eff_date, user=None,
                    before=before or None, after=after or None, notes=notes,
                )

        # ── Loan + GOSI demo rules (NON-AUTHORITATIVE data) ──────────────
        # Law constants (rates, divisors) live in ComplianceRule rows per the
        # Calculation Engine's "rules are DATA" contract — never inline in code.
        from people.models import ComplianceRule, LoanInstallment
        from people import calculation_engine

        DEMO_RULES = [
            {
                'rule_id': 'kw-gosi-demo', 'version': '2026.1', 'category': 'gosi',
                'name': '[DEMO — NON-AUTHORITATIVE] GOSI contribution (age-banded)',
                'inputs_schema': {
                    'inputs': ['gross_salary', 'employee_age'],
                    'formula': {'type': 'gosi', 'params': {
                        'salary_input': 'gross_salary', 'age_input': 'employee_age',
                        'employee_bands': [
                            {'max_age': 30, 'rate': 0.055},
                            {'max_age': None, 'rate': 0.075},
                        ],
                        'employer_bands': [{'max_age': None, 'rate': 0.11}],
                    }},
                },
            },
            {
                'rule_id': 'kw-loan-flat-demo', 'version': '2026.1', 'category': 'other',
                'name': '[DEMO — NON-AUTHORITATIVE] Flat-rate loan amortization',
                'inputs_schema': {
                    'inputs': ['principal', 'interest_rate', 'term_months'],
                    'formula': {'type': 'loan', 'params': {
                        'method': 'flat', 'rate_is_annual': True,
                        'rate_is_percent': False, 'periods_per_year': 12,
                    }},
                },
            },
        ]
        demo_rule_map = {}
        for rd in DEMO_RULES:
            rule, _ = ComplianceRule.objects.update_or_create(
                rule_id=rd['rule_id'], version=rd['version'],
                defaults={
                    'name': rd['name'], 'category': rd['category'],
                    'effective_date': date(2026, 1, 1),
                    'formula_ref': 'DEMO ONLY — no authoritative source',
                    'source_citation': '', 'inputs_schema': rd['inputs_schema'],
                    'is_authoritative': False, 'provenance': None, 'test_cases': [],
                },
            )
            demo_rule_map[rd['category']] = rule
        loan_rule = demo_rule_map['other']

        # ── Loan installments (engine-amortized, no inline math) ──────────
        def _add_months(d, n):
            m = d.month - 1 + n
            return date(d.year + m // 12, m % 12 + 1, 1)

        for loan in Loan.objects.filter(employee__in=emp_map.values()):
            schedule = calculation_engine.calculate_loan_schedule(
                loan_rule, loan, allow_non_authoritative=True)
            for inst in schedule['installments']:
                due = _add_months(loan.start_date, inst['installment_no'] - 1)
                today_d = timezone.localdate()
                if loan.status == 'paid_off':
                    status = 'paid'
                elif due <= today_d and loan.status == 'active':
                    status = 'paid'
                else:
                    status = 'scheduled'
                LoanInstallment.objects.update_or_create(
                    loan=loan, installment_no=inst['installment_no'],
                    defaults={'due_date': due, 'amount': inst['amount'],
                              'principal_portion': inst['principal_portion'],
                              'interest_portion': inst['interest_portion'],
                              'status': status},
                )

        # ── EmployeeCompensation (active comp lines per employee) ─────────
        from people.models import EmployeeCompensation
        comp_map = {c.code: c for c in CompensationComponent.objects.all()}
        START = date(2024, 1, 1)

        EC_DEFS = [
            # emp_no, component_code, amount
            ('GF-001', 'basic',          decimal.Decimal('1800.000')),
            ('GF-001', 'housing',        decimal.Decimal('250.000')),
            ('GF-001', 'transport',      decimal.Decimal('100.000')),
            ('GF-001', 'social',         decimal.Decimal('75.000')),
            ('GF-001', 'kuwaitization',  decimal.Decimal('200.000')),
            ('GF-001', 'vehicle',        decimal.Decimal('150.000')),
            ('GF-002', 'basic',          decimal.Decimal('1400.000')),
            ('GF-002', 'housing',        decimal.Decimal('180.000')),
            ('GF-002', 'transport',      decimal.Decimal('80.000')),
            ('GF-002', 'social',         decimal.Decimal('50.000')),
            ('GF-003', 'basic',          decimal.Decimal('1200.000')),
            ('GF-003', 'housing',        decimal.Decimal('200.000')),
            ('GF-003', 'transport',      decimal.Decimal('60.000')),
            ('GF-003', 'social',         decimal.Decimal('75.000')),
            ('GF-003', 'kuwaitization',  decimal.Decimal('150.000')),
            ('GF-004', 'basic',          decimal.Decimal('850.000')),
            ('GF-004', 'housing',        decimal.Decimal('120.000')),
            ('GF-004', 'transport',      decimal.Decimal('50.000')),
            ('GF-005', 'basic',          decimal.Decimal('650.000')),
            ('GF-005', 'housing',        decimal.Decimal('100.000')),
            ('GF-005', 'transport',      decimal.Decimal('40.000')),
        ]
        for emp_no, code, amount in EC_DEFS:
            emp = emp_map.get(emp_no)
            comp = comp_map.get(code)
            if emp and comp:
                # Append-only ledger: close any pre-existing open row for this
                # component before materialising, so a repeated seed never
                # double-counts an earning/deduction.
                EmployeeCompensation.objects.filter(
                    employee=emp, component=comp, effective_end__isnull=True,
                ).update(effective_end=START)
                EmployeeCompensation.objects.update_or_create(
                    employee=emp, component=comp,
                    defaults={'amount': amount, 'currency': 'KWD', 'frequency': 'monthly',
                              'effective_start': START, 'effective_end': None,
                              'reason_note': 'Seeded from GOFSCO HR records', 'is_verified': True},
                )

        # ── CompensationPlan (grade bands) ────────────────────────────────
        from people.models import CompensationPlan
        PLAN_DEFS = [
            # grade, job_family, component, amount, org_unit
            ('M1', 'operations', 'basic',    decimal.Decimal('2500.000'), ops_ou),
            ('M1', 'operations', 'housing',  decimal.Decimal('350.000'),  ops_ou),
            ('M1', 'operations', 'vehicle',  decimal.Decimal('200.000'),  ops_ou),
            ('E3', 'engineering','basic',    decimal.Decimal('1800.000'), ops_ou),
            ('E3', 'engineering','housing',  decimal.Decimal('250.000'),  ops_ou),
            ('E2', 'operations', 'basic',    decimal.Decimal('1400.000'), ops_ou),
            ('E2', 'operations', 'housing',  decimal.Decimal('180.000'),  ops_ou),
            ('A2', 'hr',         'basic',    decimal.Decimal('1200.000'), hr_ou),
            ('A2', 'hr',         'housing',  decimal.Decimal('200.000'),  hr_ou),
            ('T2', 'maintenance','basic',    decimal.Decimal('850.000'),  maint_ou),
            ('T2', 'maintenance','housing',  decimal.Decimal('120.000'),  maint_ou),
            ('T1', 'operations', 'basic',    decimal.Decimal('650.000'),  ops_ou),
            ('T1', 'operations', 'housing',  decimal.Decimal('100.000'),  ops_ou),
        ]
        for grade, family, code, amount, ou in PLAN_DEFS:
            comp = comp_map.get(code)
            if comp:
                CompensationPlan.objects.update_or_create(
                    org_unit=ou, pay_grade_code=grade, job_family_code=family, component=comp,
                    defaults={'amount': amount, 'currency': 'KWD', 'frequency': 'monthly',
                              'effective_start': START, 'is_active': True},
                )

        # ── Rotation schedules ────────────────────────────────────────────
        from people.models import RotationSchedule
        ROT_DEFS = [
            # emp_no, pattern, start_date, config
            ('GF-001', '1/1', date(2019, 3, 15), {'on_weeks': 1, 'off_weeks': 1, 'field': 'KOC GC-17'}),
            ('GF-002', '2/1', date(2021, 6,  1), {'on_weeks': 2, 'off_weeks': 1, 'field': 'KOC GC-17'}),
            ('GF-004', '3/1', date(2022, 11, 20), {'on_weeks': 3, 'off_weeks': 1, 'field': 'KOC GC-17'}),
            ('GF-005', '5/1', date(2023, 4,  1), {'on_weeks': 5, 'off_weeks': 1, 'field': 'KOC GC-17'}),
        ]
        for emp_no, pattern, start, config in ROT_DEFS:
            emp = emp_map.get(emp_no)
            if emp:
                RotationSchedule.objects.update_or_create(
                    employee=emp, pattern=pattern,
                    defaults={'start_date': start, 'config': config, 'is_active': True},
                )

        # ── Leave records (matching used_days in entitlements) ─────────────
        from people.models import LeaveRecord
        today_d = timezone.localdate()
        YEAR = today_d.year
        LR_DEFS = [
            # emp_no, leave_type, start_date, end_date, days, status
            ('GF-001', 'annual', date(YEAR, 8,  3), date(YEAR, 8, 12), decimal.Decimal('8'), 'approved'),
            ('GF-001', 'sick',   date(YEAR, 5, 10), date(YEAR, 5, 11), decimal.Decimal('2'), 'approved'),
            ('GF-002', 'annual', date(YEAR, 7,  5), date(YEAR, 7, 21), decimal.Decimal('15'), 'approved'),
            ('GF-002', 'annual', date(YEAR-1, 10, 1), date(YEAR-1, 10, 27), decimal.Decimal('25'), 'approved'),
            ('GF-003', 'annual', date(YEAR, 6, 15), date(YEAR, 6, 28), decimal.Decimal('12'), 'approved'),
            ('GF-003', 'sick',   date(YEAR, 3,  2), date(YEAR, 3,  4), decimal.Decimal('2'), 'approved'),
            ('GF-003', 'sick',   date(YEAR, 5, 20), date(YEAR, 5, 22), decimal.Decimal('2'), 'approved'),
            ('GF-003', 'sick',   date(YEAR, 7, 14), date(YEAR, 7, 14), decimal.Decimal('1'), 'approved'),
            ('GF-003', 'emergency', date(YEAR, 4, 8), date(YEAR, 4, 9), decimal.Decimal('2'), 'approved'),
            ('GF-004', 'annual', date(YEAR, 8,  5), date(YEAR, 8, 26), decimal.Decimal('18'), 'approved'),
            ('GF-004', 'sick',   date(YEAR, 6,  1), date(YEAR, 6,  3), decimal.Decimal('3'), 'approved'),
            ('GF-005', 'annual', date(YEAR, 7, 20), date(YEAR, 7, 29), decimal.Decimal('8'), 'approved'),
        ]
        for emp_no, ltype, start, end, days, status in LR_DEFS:
            emp = emp_map.get(emp_no)
            if emp:
                LeaveRecord.objects.update_or_create(
                    employee=emp, leave_type=ltype, start_date=start,
                    defaults={'end_date': end, 'days': days, 'status': status,
                              'calendar_split': days > 10},
                )

        # ── Payroll runs (Apr–Aug 2026) with engine-computed lines ─────────
        from people.models import PayrollRun, PayslipLine

        gosi_rule = demo_rule_map['gosi']
        all_rules = ComplianceRule.objects.all()
        eosi_rule = ComplianceRule.objects.filter(category='eosi').order_by('-effective_date').first()

        # Single source of truth for per-employee compensation amounts.
        emp_comp = {k: {} for k in emp_map}
        for emp_no, code, amount in EC_DEFS:
            emp_comp.setdefault(emp_no, {})[code] = amount

        def _gosi_base(emp_no):
            return sum(
                (a for c, a in emp_comp[emp_no].items() if comp_map[c].is_gosi_base),
                decimal.Decimal('0'),
            )

        def _gosi_employee_share(emp, emp_no):
            age = None
            if emp.date_of_birth:
                age = (date(YEAR, 1, 1) - emp.date_of_birth).days // 365
            res = calculation_engine.calculate_gosi(
                gosi_rule, _gosi_base(emp_no), employee_age=age,
                allow_non_authoritative=True)
            return res['lineage']['employee_share']

        def _monthly_eosi(emp, as_of):
            res = calculation_engine.calculate_eosi(
                emp, all_rules, allow_non_authoritative=True, as_of=as_of)
            months = max(1, (as_of - emp.join_date).days // 30)
            return (res['value'] / decimal.Decimal(months)).quantize(decimal.Decimal('0.001'))

        PAYROLL_MONTHS = [
            (date(YEAR, 4, 1), date(YEAR, 4, 30), 'committed'),
            (date(YEAR, 5, 1), date(YEAR, 5, 31), 'committed'),
            (date(YEAR, 6, 1), date(YEAR, 6, 30), 'committed'),
            (date(YEAR, 7, 1), date(YEAR, 7, 31), 'committed'),
            (date(YEAR, 8, 1), date(YEAR, 8, 31), 'validated'),
        ]

        def _lines_for(emp, emp_no, period_start):
            year, month = period_start.year, period_start.month
            lines = []
            for code, amount in emp_comp[emp_no].items():
                comp = comp_map[code]
                lines.append({'line_type': comp.direction, 'amount': amount,
                              'rule_id': code, 'rule_version': '',
                              'inputs': {'component': code}})
            if emp.kuwaitization:
                share = _gosi_employee_share(emp, emp_no)
                lines.append({'line_type': 'deduction', 'amount': share,
                              'rule_id': gosi_rule.rule_id, 'rule_version': gosi_rule.version,
                              'inputs': {'component': 'gosi_employee', 'employee_share': str(share)}})
            if eosi_rule:
                eosi = _monthly_eosi(emp, period_start)
                lines.append({'line_type': 'deduction', 'amount': eosi,
                              'rule_id': eosi_rule.rule_id, 'rule_version': eosi_rule.version,
                              'inputs': {'component': 'eosi_accrual'}})
            for loan in emp.loans.filter(status='active'):
                inst = loan.installments.filter(due_date__year=year, due_date__month=month).first()
                if inst:
                    lines.append({'line_type': 'deduction', 'amount': inst.amount,
                                  'rule_id': loan_rule.rule_id, 'rule_version': loan_rule.version,
                                  'inputs': {'component': 'loan_deduction', 'loan_id': loan.pk}})
            return lines

        payroll_emps = [k for k in ['GF-001','GF-002','GF-003','GF-004','GF-005'] if k in emp_map]

        for p_start, p_end, p_status in PAYROLL_MONTHS:
            run, _ = PayrollRun.objects.update_or_create(
                org_unit=root_ou, period_start=p_start, period_end=p_end,
                defaults={'status': p_status},
            )
            PayslipLine.objects.filter(payroll_run=run).delete()
            for emp_no in payroll_emps:
                emp = emp_map[emp_no]
                for line in _lines_for(emp, emp_no, p_start):
                    PayslipLine.objects.create(payroll_run=run, employee=emp, **line)

        # ── Attendance records (last 60 working days) ──────────────────────
        from people.models import AttendanceRecord
        work_emps = payroll_emps
        day = today_d - timedelta(days=1)
        recorded = 0
        while recorded < 60:
            if day.weekday() < 5:  # Mon-Fri
                for emp_no in work_emps:
                    emp = emp_map[emp_no]
                    # Mark leave days as 'leave', else present
                    on_leave = any(
                        lr.start_date <= day <= lr.end_date
                        for lr in LeaveRecord.objects.filter(employee=emp, status='approved')
                    )
                    status = 'leave' if on_leave else 'present'
                    hours = decimal.Decimal('0') if on_leave else decimal.Decimal('8.00')
                    # Field workers get occasional overtime
                    ot = decimal.Decimal('0')
                    if not on_leave and emp_no in ('GF-001', 'GF-002', 'GF-004') and day.day % 7 == 0:
                        ot = decimal.Decimal('2.00')
                    AttendanceRecord.objects.update_or_create(
                        employee=emp, date=day,
                        defaults={'hours_worked': hours, 'overtime_hours': ot, 'status': status},
                    )
                recorded += 1
            day -= timedelta(days=1)

        count = Employee.objects.count()
        from mdm.models import ReferenceSet
        self.stdout.write(self.style.SUCCESS(
            f'GOFSCO seed complete: {count} employees | '
            f'{Certification.objects.count()} certs | '
            f'{LeaveEntitlement.objects.count()} leave entitlements | '
            f'{LeaveRecord.objects.count()} leave records | '
            f'{EmployeeBenefit.objects.count()} benefits | '
            f'{LoanInstallment.objects.count()} loan installments | '
            f'{RotationSchedule.objects.count()} rotation schedules | '
            f'{EmployeeCompensation.objects.count()} comp lines | '
            f'{CompensationPlan.objects.count()} comp plans | '
            f'{PayrollRun.objects.count()} payroll runs | '
            f'{PayslipLine.objects.count()} payslip lines | '
            f'{AttendanceRecord.objects.count()} attendance records | '
            f'{ReferenceSet.objects.count()} reference sets'
        ))
