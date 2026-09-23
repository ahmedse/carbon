# File: people/models.py
# People & Payroll domain models (Nibras HRMS wedge).
#
# The ComplianceRule model is the *versioned* Compliance Rule Library seam
# (docs/NIBRAS-MASTER-STRATEGY.md §6.2): rules are DATA, never hardcoded in the
# Calculation Engine. Every rule starts non-authoritative (is_authoritative=False,
# provenance=None) until sourced from KLL / PIFSS / WPS.
#
# RULE_12: employee + payroll data are org-scoped via the OrgUnit FK.

from django.conf import settings
from django.db import models


class ComplianceRule(models.Model):
    """A versioned compliance rule. The rule library is the seam that
    authoritative KLL / PIFSS / WPS figures drop into without engine changes."""

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

    jurisdiction = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Jurisdiction from ReferenceSet 'jurisdiction' (e.g. KW)",
    )
    category = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Category from ReferenceSet 'compliance_category'",
    )
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
        ordering = ['category__sort_order', 'category__code', 'rule_id', '-effective_date']
        verbose_name = "Compliance Rule"
        verbose_name_plural = "Compliance Rules"

    def __str__(self):
        cat = self.category.code if self.category_id else '?'
        return f"{self.rule_id} v{self.version} ({cat})"


class Employee(models.Model):
    """Minimal employee master (org-scoped).

    P3 profile enrichment: bilingual identity + Kuwait HR profile fields
    (civil ID, DOB, gender, governed lookups, kuwaitization flag,
    reporting manager). Bucket-1 lookups are FKs to ``mdm.ReferenceValue``
    (ADR-0027); see ``GovernedValueField`` in mdm/serializers.py.
    """

    org_unit = models.ForeignKey(
        'mdm.OrgUnit',
        on_delete=models.PROTECT,
        related_name='employees',
        help_text="Owning organisational unit (RULE_12 org-scoping)",
    )
    employee_no = models.CharField(max_length=64, unique=True)
    full_name = models.CharField(max_length=200)
    user = models.OneToOneField(
        'accounts.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_profile',
        help_text='Linked platform account (self-service). Null until a user is linked.',
    )
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
    gender = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Gender from ReferenceSet 'gender'",
    )
    employment_type = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Employment type from ReferenceSet 'employment_type'",
    )
    contract_type = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Contract type from ReferenceSet 'contract_type'",
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
    nationality = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Nationality from ReferenceSet 'nationality'",
    )
    basic_salary = models.DecimalField(max_digits=14, decimal_places=3)
    join_date = models.DateField(
        null=True, blank=True,
        help_text="Service start date (null = unknown, e.g. bulk ERP import)",
    )
    rotation = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Rotation pattern from ReferenceSet 'rotation_pattern'",
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
        constraints = [
            models.UniqueConstraint(
                fields=['org_unit', 'period_start', 'period_end'],
                condition=models.Q(status__in=['draft', 'computed', 'validated', 'committed']),
                name='people_payrollrun_one_active_period',
            ),
        ]

    def __str__(self):
        return f"Payroll #{self.pk} {self.org_unit} {self.period_start}→{self.period_end} ({self.status})"


class PayslipLine(models.Model):
    """A single calculated line in a payroll run — the lineage carrier.

    ``rule_id`` / ``rule_version`` / ``inputs`` record exactly which rule
    version and inputs produced the amount (NIBRAS-MASTER-STRATEGY.md §6.3).
    """

    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='lines')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='payslip_lines')
    line_type = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Line type from ReferenceSet 'payslip_line_type'",
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
        code = self.line_type.code if self.line_type_id else self.line_type
        return f"{self.employee} {code} = {self.amount}"


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


class WpsFiling(models.Model):
    """GOSI/WPS SIF filing lifecycle state for one committed payroll run.

    Distinct from a raw WPS download: generate persists artifact metadata,
    validate records pass/fail, submit is irreversible (idempotent).
    """

    STATUS_CHOICES = [
        ("generated", "Generated"),
        ("validated", "Validated"),
        ("submitted", "Submitted"),
    ]

    payroll_run = models.OneToOneField(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="wps_filing",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="generated")
    content_hash = models.CharField(max_length=64, blank=True, default="")
    record_count = models.PositiveIntegerField(default=0)
    csv_bytes = models.BinaryField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    validation_passed = models.BooleanField(default=False)
    validation_issues = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    receipt_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="LOCAL-WPS-* is a Carbon export id. PAM/bank receipt is recorded separately.",
    )
    reconciled = models.BooleanField(
        default=False,
        help_text="True only after an external PAM or bank acknowledgement. Local submit does not set this.",
    )

    class Meta:
        verbose_name = "WPS Filing"
        verbose_name_plural = "WPS Filings"

    def __str__(self):
        return f"WPS filing run #{self.payroll_run_id} ({self.status})"


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
    grade = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Grade from ReferenceSet 'grade'",
    )
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
    job_family = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Job family from ReferenceSet 'job_family'",
    )

    class Meta:
        ordering = ['org_unit', 'code']
        verbose_name = "Position"
        verbose_name_plural = "Positions"

    def __str__(self):
        return f"{self.code} — {self.title}"


class LeavePolicy(models.Model):
    """Named, lifecycle-managed, applicability-scoped leave policy registry.

    Multiple policies may exist per leave type (no unique constraint on
    ``leave_type``). ``status`` is the lifecycle source of truth (draft →
    active → deprecated); ``is_active`` is retained only for transition
    compatibility. ``applies_to_org_units`` / ``applies_to_contract_types``
    are empty meaning "applies to all". ``name`` is the primary identity.
    """

    ACCRUAL_UPFRONT = 'upfront'
    ACCRUAL_MONTHLY = 'monthly'
    ACCRUAL_CHOICES = [
        (ACCRUAL_UPFRONT, 'Upfront — full allocation on 1 Jan'),
        (ACCRUAL_MONTHLY, 'Monthly — entitled_days ÷ 12 per month'),
    ]

    GENDER_ANY = 'any'
    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_CHOICES = [
        (GENDER_ANY, 'Any'),
        (GENDER_MALE, 'Male only'),
        (GENDER_FEMALE, 'Female only'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_DEPRECATED = 'deprecated'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DEPRECATED, 'Deprecated'),
    ]

    # ── LPR-5 Kuwait HR applicability (GOFSCO issue #2/#3) ──
    # Kuwaitization flag scope: Kuwaiti nationals (42-day leave) vs expats
    # (30-day leave) are governed by different policies under KLL / KOC.
    KUWAIT_ANY = 'any'
    KUWAIT_ONLY = 'kuwaiti'
    KUWAIT_NON = 'non_kuwaiti'
    KUWAIT_CHOICES = [
        (KUWAIT_ANY, 'Any'),
        (KUWAIT_ONLY, 'Kuwaiti only'),
        (KUWAIT_NON, 'Non-Kuwaiti only'),
    ]

    leave_type = models.ForeignKey(
        'mdm.ReferenceValue', on_delete=models.PROTECT, related_name='+',
        help_text="Leave type from ReferenceSet 'leave_type'",
    )
    default_entitled_days = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text='Days granted to every employee per year by default',
    )
    max_carryover_days = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text='Maximum unused days that may carry forward to next year (0 = no carryover)',
    )
    is_carryover_allowed = models.BooleanField(
        default=False,
        help_text='Allow unused balance to carry forward at year-end',
    )
    accrual_method = models.CharField(
        max_length=10, choices=ACCRUAL_CHOICES, default=ACCRUAL_UPFRONT,
    )
    gender_restriction = models.CharField(
        max_length=10, choices=GENDER_CHOICES, default=GENDER_ANY,
    )
    requires_approval = models.BooleanField(
        default=True,
        help_text='Leave requests of this type require manager approval',
    )
    min_service_days = models.PositiveIntegerField(
        default=0,
        help_text='Minimum days of service before the employee may request this leave (0 = no minimum)',
    )
    is_active = models.BooleanField(default=True)
    # ── LPR-1A registry fields (additive; null/blank-safe) ──
    name = models.CharField(
        max_length=200, blank=True,
        help_text="Human-readable policy name (primary identity)",
    )
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
        help_text="Lifecycle state (supersedes is_active)",
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    applies_to_org_units = models.ManyToManyField(
        'mdm.OrgUnit', blank=True, related_name='+',
        help_text="Scope to these org units; empty = all org units",
    )
    applies_to_contract_types = models.JSONField(
        default=list, blank=True,
        help_text="List of contract_type codes; empty = all contract types",
    )
    applies_to_kuwaitization = models.CharField(
        max_length=16, choices=KUWAIT_CHOICES, default=KUWAIT_ANY,
        help_text="Kuwaitization scope: any / Kuwaiti only / non-Kuwaiti only (GOFSCO 42-day vs 30-day leave)",
    )
    applies_to_rotations = models.JSONField(
        default=list, blank=True,
        help_text="List of rotation pattern codes (e.g. ['1/1','2/1']); empty = all rotations (GOFSCO rotation leave)",
    )
    notes = models.TextField(blank=True)
    # ── LPR-4 registry grouping + tagging (additive; null/blank-safe) ──
    category = models.CharField(
        max_length=100, blank=True,
        help_text="Grouping bucket for the policy registry (e.g. Leave, Attendance, Travel, Benefits, Conduct)",
    )
    tags = models.JSONField(
        default=list, blank=True,
        help_text="List of free-form tags for discovery (e.g. ['remote', 'probation'])",
    )
    updated_by = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='updated_leave_policies',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Leave Policy'
        verbose_name_plural = 'Leave Policies'
        ordering = ['leave_type__sort_order', 'leave_type__code']

    def __str__(self):
        code = self.leave_type.code if self.leave_type_id else str(self.leave_type)
        return f"{self.name} ({code})"


class LeavePolicyVersion(models.Model):
    """Immutable snapshot of a ``LeavePolicy`` at a point in time (LPR-3A).

    Each configuration change is recorded as a new version. The live
    ``LeavePolicy`` row remains the current config; versions capture the exact
    field values that were in effect when a version was forked. ``effective_to``
    is closed on the prior open version when the next one is forked, so the
    version chain derives the policy's effective-date transitions.
    """

    policy = models.ForeignKey(
        LeavePolicy, on_delete=models.CASCADE, related_name='versions',
    )
    version_number = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    snapshot = models.JSONField(default=dict)
    change_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('policy', 'version_number')
        ordering = ['policy', '-version_number']
        verbose_name = 'Leave Policy Version'
        verbose_name_plural = 'Leave Policy Versions'

    def __str__(self):
        return f"{self.policy} v{self.version_number}"


class LeaveEntitlement(models.Model):
    """Annual leave entitlement for an employee (M3 — Leave)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_entitlements')
    year = models.PositiveSmallIntegerField()
    leave_type = models.ForeignKey(
        'mdm.ReferenceValue', on_delete=models.PROTECT, related_name='+'
    )
    entitled_days = models.DecimalField(max_digits=8, decimal_places=2)
    used_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    carried_forward = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    policy = models.ForeignKey(
        'LeavePolicy', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
        help_text="Policy that created this entitlement (provenance; null = manual/legacy)",
    )
    policy_version = models.ForeignKey(
        'LeavePolicyVersion', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
        help_text="Policy version that created this entitlement (provenance; null = legacy/manual)",
    )

    class Meta:
        unique_together = ('employee', 'year', 'leave_type')
        ordering = ['employee', 'year', 'leave_type']
        verbose_name = "Leave Entitlement"
        verbose_name_plural = "Leave Entitlements"

    def __str__(self):
        code = self.leave_type.code if self.leave_type_id else self.leave_type
        return f"{self.employee} {self.year} {code} ({self.entitled_days} days)"


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
    leave_type = models.ForeignKey(
        'mdm.ReferenceValue', on_delete=models.PROTECT, related_name='+'
    )
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
        code = self.leave_type.code if self.leave_type_id else self.leave_type
        return f"{self.employee} {code} {self.start_date}→{self.end_date} ({self.status})"


class BenefitType(models.Model):
    """A categorised benefit definition (M5 — C&B)."""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        help_text="Category from ReferenceSet 'benefit_category'",
    )
    is_eosi_base = models.BooleanField(default=False)
    is_taxable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category__sort_order', 'category__code', 'code']
        verbose_name = "Benefit Type"
        verbose_name_plural = "Benefit Types"

    def __str__(self):
        return f"{self.code} — {self.name}"


class CompensationComponent(models.Model):
    """Governed catalog of earning/deduction component types.

    Replaces the free-text ``PayslipLine.line_type``. Every component has a
    direction (earning vs. deduction) and policy flags consumed by the
    calculation engine (EOSI base, GOSI base, WPS file inclusion).

    ``governing_rule`` links to the ComplianceRule that sets limits/rates
    for this component — e.g. GOSI employee share is governed by GOSI-KW.
    """

    DIRECTION_CHOICES = [('earning', 'Earning'), ('deduction', 'Deduction')]

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    category = models.CharField(
        max_length=64, blank=True,
        help_text="Code from ReferenceSet 'compensation_category'",
    )
    # Policy flags for the calculation engine
    is_eosi_base = models.BooleanField(default=False, help_text="Included in EOSI/gratuity base")
    is_gosi_base = models.BooleanField(default=False, help_text="Included in GOSI contribution base")
    is_wps_relevant = models.BooleanField(default=True, help_text="Appears in WPS file")
    is_taxable = models.BooleanField(default=False)
    is_variable = models.BooleanField(default=False, help_text="Variable each month (overtime, commission)")
    governing_rule = models.ForeignKey(
        'ComplianceRule', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='governed_components',
        help_text="ComplianceRule that sets limits/rates for this component",
    )
    sort_order = models.PositiveSmallIntegerField(default=100)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['direction', 'sort_order', 'code']
        verbose_name = "Compensation Component"
        verbose_name_plural = "Compensation Components"

    def __str__(self):
        return f"{self.code} ({self.direction})"


class CompensationPlan(models.Model):
    """Compensation matrix row: what a given grade/family/org receives per component.

    This is the 'template' layer. When an employee is placed in a position,
    the plan rows matching (org_unit subtree, pay_grade, job_family) are
    materialised as EmployeeCompensation ledger rows. Config-driven, not
    hardcoded — GOFSCO specifics live here as data, not code.
    """

    org_unit = models.ForeignKey(
        'mdm.OrgUnit', null=True, blank=True, on_delete=models.PROTECT,
        related_name='compensation_plan_rows',
        help_text="Null = global plan row (applies to all org units)",
    )
    pay_grade_code = models.CharField(
        max_length=40, blank=True,
        help_text="Code from ReferenceSet 'pay_grade' (blank = all grades)",
    )
    job_family_code = models.CharField(
        max_length=40, blank=True,
        help_text="Code from ReferenceSet 'job_family' (blank = all families)",
    )
    component = models.ForeignKey(
        CompensationComponent, on_delete=models.PROTECT, related_name='plan_rows',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=3)
    currency = models.CharField(max_length=3, default='KWD')
    frequency = models.CharField(
        max_length=10,
        choices=[('monthly', 'Monthly'), ('annual', 'Annual')],
        default='monthly',
    )
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['pay_grade_code', 'component', '-effective_start']
        verbose_name = "Compensation Plan Row"
        verbose_name_plural = "Compensation Plan"

    def __str__(self):
        scope = f"{self.org_unit or 'global'} | {self.pay_grade_code or 'any'}"
        return f"{scope} | {self.component.code} = {self.amount}"


class EmployeeCompensation(models.Model):
    """Additive, effective-dated compensation ledger — the single source of truth
    for every earning and deduction an employee receives.

    Design rules:
    - Never UPDATE existing rows; append new effective-dated rows.
    - 'Current salary' = sum of rows where effective_start <= today and
      (effective_end is NULL or effective_end >= today).
    - Employee.basic_salary is migrated as an initial 'basic' component row.
    - Every insert emits a PersonnelEvent('salary_change') via the view layer.

    ``source_rule`` / ``source_plan`` / ``reason_event`` form the provenance
    chain: WHY does this employee get this amount (traceability to NIBRAS §6.3).
    """

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='compensation_lines',
    )
    component = models.ForeignKey(
        CompensationComponent, on_delete=models.PROTECT, related_name='employee_lines',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=3)
    currency = models.CharField(max_length=3, default='KWD')
    frequency = models.CharField(
        max_length=10,
        choices=[('monthly', 'Monthly'), ('annual', 'Annual')],
        default='monthly',
    )
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True, help_text="Null = open-ended (current)")
    # Provenance
    source_rule = models.ForeignKey(
        'ComplianceRule', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='compensation_lines',
        help_text="ComplianceRule that produced this amount",
    )
    source_plan = models.ForeignKey(
        CompensationPlan, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='employee_lines',
        help_text="CompensationPlan row this was inherited from",
    )
    reason_event = models.ForeignKey(
        'PersonnelEvent', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='compensation_changes',
        help_text="PersonnelEvent that triggered this change",
    )
    reason_note = models.TextField(blank=True)
    source_benefit = models.ForeignKey(
        'EmployeeBenefit', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='compensation_lines',
        help_text="EmployeeBenefit this line mirrors (benefit → salary reflection)",
    )
    # Verification seam
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='verified_compensation_lines',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_compensation_lines',
    )

    class Meta:
        ordering = ['employee', 'component', '-effective_start']
        verbose_name = "Employee Compensation Line"
        verbose_name_plural = "Employee Compensation Ledger"
        indexes = [
            models.Index(fields=['employee', 'effective_start']),
            models.Index(fields=['component', 'effective_start']),
        ]

    def __str__(self):
        end = self.effective_end or '∞'
        return f"{self.employee} | {self.component.code} | {self.amount} {self.currency} | {self.effective_start}→{end}"


class EmployeeBenefit(models.Model):
    """C&B ledger linking an employee to a benefit type (M5)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='benefits')
    benefit_type = models.ForeignKey(BenefitType, on_delete=models.PROTECT, related_name='employee_benefits')
    monthly_amount = models.DecimalField(max_digits=14, decimal_places=3)
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    reflect_in_salary = models.BooleanField(
        default=False,
        help_text="When True, mirror monthly_amount into the compensation ledger as an earning line.",
    )
    component = models.ForeignKey(
        CompensationComponent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='benefit_lines',
        help_text="Earning compensation component this benefit reflects into.",
    )

    class Meta:
        ordering = ['employee', 'benefit_type']
        verbose_name = "Employee Benefit"
        verbose_name_plural = "Employee Benefits"

    def __str__(self):
        return f"{self.employee} — {self.benefit_type}"


class Loan(models.Model):
    """A deduction loan for an employee."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paid_off', 'Paid Off'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Loan type from ReferenceSet 'loan_type'",
    )
    principal = models.DecimalField(max_digits=14, decimal_places=3)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    term_months = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Loan"
        verbose_name_plural = "Loans"

    def __str__(self):
        code = self.loan_type.code if self.loan_type_id else self.loan_type
        return f"{self.employee} {code} ({self.principal})"


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

    ``status`` is the workflow outcome mirror (pending / approved / rejected /
    cancelled). ``approved`` is kept in sync (True iff status == approved) for
    existing API/FE readers.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='permissions')
    date = models.DateField()
    permission_type = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Permission type from ReferenceSet 'permission_type'",
    )
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True,
    )
    approved = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = "Attendance Permission"
        verbose_name_plural = "Attendance Permissions"

    def __str__(self):
        code = self.permission_type.code if self.permission_type_id else self.permission_type
        return f"{self.employee} {self.date} {code} ({self.hours}h)"

    def save(self, *args, **kwargs):
        # ``approved`` mirrors ``status``; accept legacy writers that only flip
        # the bool (admin PATCH / seeds) by promoting pending → approved.
        if self.approved and self.status in ('pending', ''):
            self.status = 'approved'
        self.approved = self.status == 'approved'
        super().save(*args, **kwargs)


class Certification(models.Model):
    """An employee certification (GOFSCO KOC)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='certifications')
    cert_type = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Cert type from ReferenceSet 'cert_type'",
    )
    number = models.CharField(max_length=128, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['expiry_date']
        verbose_name = "Certification"
        verbose_name_plural = "Certifications"

    def __str__(self):
        code = self.cert_type.code if self.cert_type_id else self.cert_type
        return f"{self.employee} {code} ({self.number})"


class RotationSchedule(models.Model):
    """A rotation schedule configuration (GOFSCO — config only, no logic)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='rotation_schedules')
    pattern = models.ForeignKey(
        'mdm.ReferenceValue',
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Pattern from ReferenceSet 'rotation_pattern'",
    )
    start_date = models.DateField()
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Rotation Schedule"
        verbose_name_plural = "Rotation Schedules"

    def __str__(self):
        code = self.pattern.code if self.pattern_id else self.pattern
        return f"{self.employee} {code} ({self.start_date})"


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


class SoDPreparation(models.Model):
    """First-writer preparer stamp for host SoD (ADR-0045 / NPS-1).

    Polymorphic subject (payroll_run | wps_filing | employee |
    attendance_permission). Irreversible effects call
    ``people.governance.sod.require_distinct_actor``.
    """

    subject_type = models.CharField(max_length=64)
    subject_id = models.PositiveIntegerField()
    process_key = models.CharField(max_length=128, blank=True)
    preparer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sod_preparations',
    )
    prepared_at = models.DateTimeField()

    class Meta:
        verbose_name = "SoD preparation"
        verbose_name_plural = "SoD preparations"
        constraints = [
            models.UniqueConstraint(
                fields=['subject_type', 'subject_id'],
                name='people_sodprep_subject_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['subject_type', 'subject_id']),
        ]

    def __str__(self):
        return f"{self.subject_type}:{self.subject_id} by {self.preparer_id}"
