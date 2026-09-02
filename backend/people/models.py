# File: people/models.py
# People & Payroll domain models (Nibras HRMS wedge).
#
# The ComplianceRule model is the *versioned* Compliance Rule Library seam
# (docs/NIBRAS-MASTER-STRATEGY.md §6.2): rules are DATA, never hardcoded in the
# Calculation Engine. Every rule starts non-authoritative (is_authoritative=False,
# provenance=None) until sourced from KLL / PIFSS / WPS.
#
# RULE_12: employee + payroll data are org-scoped via the OrgUnit FK.

from django.db import models


class ComplianceRule(models.Model):
    """A versioned compliance rule. The rule library is the seam that
    authoritative KLL / PIFSS / WPS figures drop into without engine changes."""

    CATEGORY_CHOICES = [
        ('leave', 'Leave'),
        ('eosi', 'EOSI'),
        ('gosi', 'GOSI'),
        ('wps', 'WPS'),
        ('overtime', 'Overtime'),
        ('payroll', 'Payroll'),
        ('other', 'Other'),
    ]

    # ``rule_id`` is unique only together with ``version`` — a rule can have
    # multiple dated versions in the library (versioned seam).
    rule_id = models.CharField(
        max_length=120,
        help_text="Stable slug identifier, e.g. 'kw-eosi-accrual'",
    )
    version = models.CharField(
        max_length=40,
        help_text="Version string, e.g. '2026.1'",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    jurisdiction = models.CharField(max_length=10, default='KW')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    effective_date = models.DateField(help_text="Date the rule becomes effective")
    formula_ref = models.CharField(
        max_length=200, blank=True, help_text="e.g. 'KLL Art. 51'",
    )
    source_citation = models.TextField(
        blank=True, help_text="Authoritative citation — EMPTY until sourced",
    )

    # ``inputs_schema`` names the inputs the formula consumes and (optionally)
    # carries a generic, rule-agnostic formula expression (see calculation_engine).
    inputs_schema = models.JSONField(default=dict, blank=True)
    is_authoritative = models.BooleanField(
        default=False, help_text="False until sourced from KLL / PIFSS / WPS",
    )
    provenance = models.JSONField(
        null=True, blank=True,
        help_text="Source doc / URL / reviewed-by — null until sourced",
    )
    test_cases = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('rule_id', 'version')
        ordering = ['category', 'rule_id', '-effective_date']
        verbose_name = "Compliance Rule"
        verbose_name_plural = "Compliance Rules"

    def __str__(self):
        return f"{self.rule_id} v{self.version} ({self.category})"


class Employee(models.Model):
    """Minimal employee master (org-scoped).

    P3 profile enrichment: bilingual identity + Kuwait HR profile fields
    (civil ID, DOB, gender, governed-enum codes, kuwaitization flag,
    reporting manager). The ``*_code`` fields are validated against
    ``mdm.ReferenceSet`` in the API layer (see people/serializers.py).
    """

    org_unit = models.ForeignKey(
        'mdm.OrgUnit',
        on_delete=models.PROTECT,
        related_name='employees',
        help_text="Owning organisational unit (RULE_12 org-scoping)",
    )
    employee_no = models.CharField(max_length=64, unique=True)
    full_name = models.CharField(max_length=200)
    # ── P3 profile enrichment (bilingual identity + Kuwait HR profile) ──
    # New fields are blank/null-safe so existing rows survive the migration.
    name_en_given = models.CharField(max_length=120, blank=True, default='')
    name_en_family = models.CharField(max_length=120, blank=True, default='')
    name_ar_given = models.CharField(max_length=120, blank=True, default='')
    name_ar_family = models.CharField(max_length=120, blank=True, default='')
    civil_id = models.CharField(
        max_length=32, blank=True, default='', db_index=True,
        help_text="Civil ID (Kuwait) — plain text, no validation of checksum",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=16, blank=True, default='',
        help_text="Free text (e.g. 'male'/'female'); NOT a governed enum",
    )
    nationality_code = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Code from ReferenceSet 'nationality' (governed enum)",
    )
    employment_type_code = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Code from ReferenceSet 'employment_type' (governed enum)",
    )
    contract_type_code = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Code from ReferenceSet 'contract_type' (governed enum)",
    )
    kuwaitization = models.BooleanField(
        default=False,
        help_text="Kuwaiti national (nationalization target flag)",
    )
    manager = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='direct_reports',
        help_text="Reporting manager (self FK; RULE_3 soft ref to Employee)",
    )
    position = models.ForeignKey(
        'Position', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='incumbents',
        help_text='Current single position (same-app FK; incumbent resolution)',
    )
    nationality = models.CharField(max_length=100, blank=True)
    basic_salary = models.DecimalField(max_digits=14, decimal_places=3)
    join_date = models.DateField(help_text="Service start date")
    rotation = models.CharField(
        max_length=32, blank=True,
        help_text="Config label only (e.g. '1/1'), NOT calculation logic",
    )
    photo = models.ImageField(
        upload_to='people/photos/',
        null=True, blank=True,
        help_text="Profile photo (JPEG/PNG ≤2 MB)",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_no']
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def __str__(self):
        return f"{self.employee_no} — {self.full_name}"


class PayrollRun(models.Model):
    """A governed payroll run for one org unit and one period."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('validated', 'Validated'),
        ('committed', 'Committed'),
        ('failed', 'Failed'),
    ]

    org_unit = models.ForeignKey(
        'mdm.OrgUnit',
        on_delete=models.PROTECT,
        related_name='payroll_runs',
        help_text="Owning organisational unit (RULE_12 org-scoping)",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-period_start']
        verbose_name = "Payroll Run"
        verbose_name_plural = "Payroll Runs"

    def __str__(self):
        return f"Payroll #{self.pk} {self.org_unit} {self.period_start}→{self.period_end} ({self.status})"


class PayslipLine(models.Model):
    """A single calculated line in a payroll run — the lineage carrier.

    ``rule_id`` / ``rule_version`` / ``inputs`` record exactly which rule
    version and inputs produced the amount (NIBRAS-MASTER-STRATEGY.md §6.3).
    """

    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='lines')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='payslip_lines')
    line_type = models.CharField(
        max_length=40,
        help_text="gross | basic | overtime | leave_pay | eosi_accrual | gosi | deduction | …",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=3)
    rule_id = models.CharField(max_length=120)
    rule_version = models.CharField(max_length=40)
    inputs = models.JSONField(
        default=dict, blank=True, help_text="Exact inputs that produced the amount",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = "Payslip Line"
        verbose_name_plural = "Payslip Lines"

    def __str__(self):
        return f"{self.employee} {self.line_type} = {self.amount}"


class PayrollRunValidation(models.Model):
    """Run-scoped DQ validation summary (ADR 0025 / NIR-3D).

    One row per finding for a run — a summary (rule_key + counts + sample
    failures), NEVER a per-row persisted result store (no ``DQResult``).
    """

    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='validations')
    rule_key = models.CharField(max_length=200)
    passed = models.BooleanField()
    checked = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    sample_failures = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Payroll Run Validation"
        verbose_name_plural = "Payroll Run Validations"

    def __str__(self):
        return f"{self.rule_key} @ run #{self.payroll_run_id}: {'pass' if self.passed else 'fail'}"


class Position(models.Model):
    """A position within an organisational unit (M1 — Org & Positions)."""

    org_unit = models.ForeignKey(
        'mdm.OrgUnit',
        on_delete=models.PROTECT,
        related_name='positions',
        help_text="Owning organisational unit (RULE_12 org-scoping)",
    )
    code = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    grade = models.CharField(max_length=64, blank=True)
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
    )
    is_management = models.BooleanField(default=False)

    # ── P4 position lifecycle + governed job classification (additive) ──
    STATUS_CHOICES = [('proposed', 'Proposed'), ('open', 'Open'), ('filled', 'Filled'), ('frozen', 'Frozen'), ('closed', 'Closed')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='filled')
    fte = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    job_family_code = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Code from ReferenceSet 'job_family' (governed enum)",
    )

    class Meta:
        ordering = ['org_unit', 'code']
        verbose_name = "Position"
        verbose_name_plural = "Positions"

    def __str__(self):
        return f"{self.code} — {self.title}"


class LeaveEntitlement(models.Model):
    """Annual leave entitlement for an employee (M3 — Leave)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_entitlements')
    year = models.PositiveSmallIntegerField()
    leave_type = models.CharField(max_length=40)
    entitled_days = models.DecimalField(max_digits=8, decimal_places=2)
    used_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    carried_forward = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('employee', 'year', 'leave_type')
        ordering = ['employee', 'year', 'leave_type']
        verbose_name = "Leave Entitlement"
        verbose_name_plural = "Leave Entitlements"

    def __str__(self):
        return f"{self.employee} {self.year} {self.leave_type} ({self.entitled_days} days)"


class LeaveRecord(models.Model):
    """A submitted leave record with optional calendar-year split (M3)."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_records')
    leave_type = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    calendar_split = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Leave Record"
        verbose_name_plural = "Leave Records"

    def __str__(self):
        return f"{self.employee} {self.leave_type} {self.start_date}→{self.end_date} ({self.status})"


class BenefitType(models.Model):
    """A categorised benefit definition (M5 — C&B)."""

    CATEGORY_CHOICES = [
        ('accommodation', 'Accommodation'),
        ('vehicle', 'Vehicle'),
        ('medical', 'Medical'),
        ('school', 'School'),
        ('tickets', 'Tickets'),
        ('other', 'Other'),
    ]

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    is_eosi_base = models.BooleanField(default=False)
    is_taxable = models.BooleanField(default=False)

    class Meta:
        ordering = ['category', 'code']
        verbose_name = "Benefit Type"
        verbose_name_plural = "Benefit Types"

    def __str__(self):
        return f"{self.code} — {self.name}"


class EmployeeBenefit(models.Model):
    """C&B ledger linking an employee to a benefit type (M5)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='benefits')
    benefit_type = models.ForeignKey(BenefitType, on_delete=models.PROTECT, related_name='employee_benefits')
    monthly_amount = models.DecimalField(max_digits=14, decimal_places=3)
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['employee', 'benefit_type']
        verbose_name = "Employee Benefit"
        verbose_name_plural = "Employee Benefits"

    def __str__(self):
        return f"{self.employee} — {self.benefit_type}"


class Loan(models.Model):
    """A deduction loan for an employee."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paid_off', 'Paid Off'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.CharField(max_length=40)
    principal = models.DecimalField(max_digits=14, decimal_places=3)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    term_months = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Loan"
        verbose_name_plural = "Loans"

    def __str__(self):
        return f"{self.employee} {self.loan_type} ({self.principal})"


class LoanInstallment(models.Model):
    """A scheduled installment of a loan."""

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('paid', 'Paid'),
        ('skipped', 'Skipped'),
    ]

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='installments')
    installment_no = models.PositiveIntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=3)
    principal_portion = models.DecimalField(max_digits=14, decimal_places=3)
    interest_portion = models.DecimalField(max_digits=14, decimal_places=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    class Meta:
        unique_together = ('loan', 'installment_no')
        ordering = ['installment_no']
        verbose_name = "Loan Installment"
        verbose_name_plural = "Loan Installments"

    def __str__(self):
        return f"{self.loan} #{self.installment_no} ({self.amount})"


class AttendanceRecord(models.Model):
    """A single day's attendance for an employee (M7)."""

    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'Leave'),
        ('permission', 'Permission'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    # ADR 0025 lineage seam: inbound attendance is a governed measurement stored
    # in dataschema.DataRow; this FK points back to the source row so any
    # payslip figure derived from it can carry the source id / row_hash.
    source_row = models.ForeignKey(
        'dataschema.DataRow',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='people_attendance_records',
        help_text="Source governed measurement row (ADR 0025 lineage seam)",
    )

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"

    def __str__(self):
        return f"{self.employee} {self.date} ({self.status})"


class AttendancePermission(models.Model):
    """An employee attendance permission (no-deduction leave category, M7).

    Named ``AttendancePermission`` (not ``Permission``) to avoid colliding with
    ``django.contrib.auth.models.Permission`` when the NIR-3E API surface
    imports both.
    """

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='permissions')
    date = models.DateField()
    permission_type = models.CharField(max_length=64)
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    approved = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = "Attendance Permission"
        verbose_name_plural = "Attendance Permissions"

    def __str__(self):
        return f"{self.employee} {self.date} {self.permission_type} ({self.hours}h)"


class Certification(models.Model):
    """An employee certification (GOFSCO KOC)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='certifications')
    cert_type = models.CharField(max_length=64)
    number = models.CharField(max_length=128, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['expiry_date']
        verbose_name = "Certification"
        verbose_name_plural = "Certifications"

    def __str__(self):
        return f"{self.employee} {self.cert_type} ({self.number})"


class RotationSchedule(models.Model):
    """A rotation schedule configuration (GOFSCO — config only, no logic)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='rotation_schedules')
    pattern = models.CharField(max_length=32)
    start_date = models.DateField()
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Rotation Schedule"
        verbose_name_plural = "Rotation Schedules"

    def __str__(self):
        return f"{self.employee} {self.pattern} ({self.start_date})"


class PersonnelEvent(models.Model):
    """Append-only domain chronicle (HR semantics): replay, timelines, KPIs.
    Bitemporal: effective_date (real-world) vs recorded_at (entry). No update/delete API."""

    ENTITY_CHOICES = [('Employee', 'Employee'), ('Position', 'Position')]
    KIND_CHOICES = [
        ('hired', 'Hired'), ('transferred', 'Transferred'), ('promoted', 'Promoted'),
        ('salary_change', 'Salary Change'), ('grade_change', 'Grade Change'),
        ('contract_renewed', 'Contract Renewed'), ('rotation_changed', 'Rotation Changed'),
        ('deactivated', 'Deactivated'), ('reactivated', 'Reactivated'),
        ('profile_updated', 'Profile Updated'),
        ('position_opened', 'Position Opened'), ('position_filled', 'Position Filled'),
        ('position_frozen', 'Position Frozen'), ('position_closed', 'Position Closed'),
    ]

    entity_type = models.CharField(max_length=20, choices=ENTITY_CHOICES, db_index=True)
    entity_id = models.PositiveIntegerField(db_index=True)
    event_kind = models.CharField(max_length=32, choices=KIND_CHOICES, db_index=True)
    effective_date = models.DateField(
        db_index=True,
        help_text='Real-world date the change took effect (drives EOSI/KPIs)',
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True, help_text='When the change was entered into the system',
    )
    recorded_by = models.ForeignKey(
        'accounts.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='personnel_events',
    )
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-effective_date', '-recorded_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id', 'effective_date']),
            models.Index(fields=['event_kind', 'effective_date']),
        ]
