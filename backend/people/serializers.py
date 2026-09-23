# File: people/serializers.py
# DRF serializers for the People & Payroll domain (NIR-1C).
#
# Thin serializers over the frozen NIR-1A models. ``auto_now``/``auto_now_add``
# timestamps are read-only; ``PayrollRun.status``/``committed_at`` are
# read-only because status transitions live in ``services.py``.
# ``PayslipLineSerializer`` exposes the lineage fields (``rule_id``,
# ``rule_version``, ``inputs``) per NIBRAS-MASTER-STRATEGY.md §6.3.
#
# Bucket-1 governed lookups use ``mdm.serializers.GovernedValueField``
# (ADR-0027 / NSR-7B): read ``{id, code, label, set}``; write id or code.

from rest_framework import serializers

from correspondence.models import Correspondence
from mdm.models import ReferenceValue
from mdm.serializers import GovernedValueField

from .civil_id import validate as _validate_civil_id
from .leave_days import LeaveDaysField

from .models import (
    AttendancePermission,
    AttendanceRecord,
    BenefitType,
    Certification,
    CompensationComponent,
    CompensationPlan,
    ComplianceRule,
    Employee,
    EmployeeBenefit,
    EmployeeCompensation,
    LeaveEntitlement,
    LeavePolicy,
    LeavePolicyVersion,
    LeaveRecord,
    Loan,
    LoanInstallment,
    PayrollRun,
    PayrollRunValidation,
    PayslipLine,
    PersonnelEvent,
    Position,
    RotationSchedule,
)


class ComplianceRuleSerializer(serializers.ModelSerializer):
    category = GovernedValueField(set_name='compliance_category', allow_null=False)
    jurisdiction = GovernedValueField(set_name='jurisdiction', allow_null=False)

    class Meta:
        model = ComplianceRule
        fields = [
            'id', 'rule_id', 'version', 'name', 'description',
            'jurisdiction', 'category', 'effective_date', 'formula_ref',
            'source_citation', 'inputs_schema', 'is_authoritative',
            'provenance', 'test_cases', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeSerializer(serializers.ModelSerializer):
    manager = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True,
    )
    position = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(), required=False, allow_null=True,
    )
    # Linked platform account (auto-provisioned on hire). Read-only so the API
    # never mutates the account through the employee payload.
    user_id = serializers.IntegerField(read_only=True, default=None)
    username = serializers.CharField(source='user.username', read_only=True, default=None)
    # NSR-4A: optional opening monthly basic for the compensation ledger.
    # Write-only — never echoed; not an Employee model field. When provided,
    # hire hooks append an *unverified* ledger line (verify before payroll).
    opening_basic = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, allow_null=True, write_only=True,
    )
    nationality = GovernedValueField(set_name='nationality', required=False)
    employment_type = GovernedValueField(set_name='employment_type', required=False)
    contract_type = GovernedValueField(set_name='contract_type', required=False)
    gender = GovernedValueField(set_name='gender', required=False)
    rotation = GovernedValueField(set_name='rotation_pattern', required=False)

    class Meta:
        model = Employee
        fields = [
            'id', 'org_unit', 'employee_no', 'full_name', 'nationality',
            'basic_salary', 'join_date', 'rotation', 'is_active', 'photo',
            'name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family',
            'civil_id', 'date_of_birth', 'gender',
            'employment_type', 'contract_type', 'kuwaitization',
            'manager', 'position', 'user_id', 'username', 'opening_basic',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'username', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data.pop('opening_basic', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('opening_basic', None)
        return super().update(instance, validated_data)

    def validate_civil_id(self, value):
        """Enforce 12-digit Civil ID format (error); check-digit only when
        ``ENFORCE_CHECK_DIGIT`` is on (see people/civil_id.py — RULE_16)."""
        ok, errors = _validate_civil_id(value)
        if not ok:
            raise serializers.ValidationError(errors[0] if errors else 'Invalid Civil ID')
        return value

    def validate(self, attrs):
        """Cross-field sanity: DOB must precede join date (impossible otherwise)."""
        dob = attrs.get('date_of_birth')
        join = attrs.get('join_date')
        if dob and join and dob >= join:
            raise serializers.ValidationError({
                'date_of_birth': 'Date of birth must be before join date',
            })
        return attrs


class PayrollRunSerializer(serializers.ModelSerializer):
    preparer_username = serializers.SerializerMethodField()
    commit_requires_other_user = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRun
        fields = [
            'id', 'org_unit', 'period_start', 'period_end', 'status',
            'created_at', 'committed_at',
            'preparer_username', 'commit_requires_other_user',
        ]
        read_only_fields = [
            'id', 'status', 'created_at', 'committed_at',
            'preparer_username', 'commit_requires_other_user',
        ]

    def validate(self, attrs):
        org_unit = attrs.get('org_unit', getattr(self.instance, 'org_unit', None))
        period_start = attrs.get(
            'period_start', getattr(self.instance, 'period_start', None),
        )
        period_end = attrs.get(
            'period_end', getattr(self.instance, 'period_end', None),
        )
        if org_unit and period_start and period_end:
            from people.payroll_service import (
                PayrollServiceError,
                assert_unique_active_period,
            )

            try:
                assert_unique_active_period(
                    org_unit,
                    period_start,
                    period_end,
                    exclude_pk=getattr(self.instance, 'pk', None),
                )
            except PayrollServiceError as exc:
                raise serializers.ValidationError(str(exc))
        return attrs

    def get_preparer_username(self, obj):
        from people.governance.sod import SUBJECT_PAYROLL_RUN, get_preparer

        preparer = get_preparer(subject_type=SUBJECT_PAYROLL_RUN, subject_id=obj.pk)
        return preparer.username if preparer is not None else None

    def get_commit_requires_other_user(self, obj):
        return (
            obj.status in ('computed', 'validated')
            and self.get_preparer_username(obj) is not None
        )


class CompensationComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompensationComponent
        fields = [
            'id', 'code', 'name', 'name_ar', 'direction', 'category',
            'is_eosi_base', 'is_gosi_base', 'is_wps_relevant', 'is_taxable',
            'is_variable', 'governing_rule', 'sort_order',
            'valid_from', 'valid_to', 'is_active',
        ]
        read_only_fields = ['id']


class CompensationPlanSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source='component.code', read_only=True)
    component_name = serializers.CharField(source='component.name', read_only=True)
    component_direction = serializers.CharField(source='component.direction', read_only=True)

    class Meta:
        model = CompensationPlan
        fields = [
            'id', 'org_unit', 'pay_grade_code', 'job_family_code',
            'component', 'component_code', 'component_name', 'component_direction',
            'amount', 'currency', 'frequency',
            'effective_start', 'effective_end', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'component_code', 'component_name', 'component_direction']


class EmployeeCompensationSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source='component.code', read_only=True)
    component_name = serializers.CharField(source='component.name', read_only=True)
    component_direction = serializers.CharField(source='component.direction', read_only=True)
    component_is_eosi_base = serializers.BooleanField(source='component.is_eosi_base', read_only=True)
    component_is_gosi_base = serializers.BooleanField(source='component.is_gosi_base', read_only=True)
    component_sort_order = serializers.IntegerField(source='component.sort_order', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_username', read_only=True, default=None)
    created_by_name = serializers.CharField(source='created_by.get_username', read_only=True, default=None)

    class Meta:
        model = EmployeeCompensation
        fields = [
            'id', 'employee', 'component', 'component_code', 'component_name',
            'component_direction', 'component_is_eosi_base', 'component_is_gosi_base',
            'component_sort_order',
            'amount', 'currency', 'frequency',
            'effective_start', 'effective_end',
            'source_rule', 'source_plan', 'reason_event', 'reason_note',
            'source_benefit',
            'is_verified', 'verified_by', 'verified_by_name', 'verified_at',
            'created_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'created_by_name',
            'component_code', 'component_name', 'component_direction',
            'component_is_eosi_base', 'component_is_gosi_base', 'component_sort_order',
            'verified_by_name', 'source_benefit',
        ]


class PayslipLineSerializer(serializers.ModelSerializer):
    line_type = GovernedValueField(set_name='payslip_line_type', allow_null=False)

    class Meta:
        model = PayslipLine
        fields = [
            'id', 'payroll_run', 'employee', 'line_type', 'amount',
            'rule_id', 'rule_version', 'inputs', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PositionSerializer(serializers.ModelSerializer):
    grade = GovernedValueField(set_name='grade', required=False)
    job_family = GovernedValueField(set_name='job_family', required=False)

    class Meta:
        model = Position
        fields = [
            'id', 'org_unit', 'code', 'title', 'grade', 'reports_to',
            'is_management', 'status', 'fte', 'job_family',
        ]
        read_only_fields = ['id']


class LeaveEntitlementSerializer(serializers.ModelSerializer):
    leave_type = serializers.SlugRelatedField(
        slug_field='code',
        queryset=ReferenceValue.objects.filter(reference_set__name='leave_type'),
    )
    leave_type_id = serializers.IntegerField(read_only=True)
    leave_type_label = serializers.SerializerMethodField()
    employee_no = serializers.CharField(source='employee.employee_no', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    policy = serializers.IntegerField(source='policy_id', read_only=True, allow_null=True)
    policy_name = serializers.SerializerMethodField()
    policy_version = serializers.IntegerField(source='policy_version_id', read_only=True, allow_null=True)
    policy_version_number = serializers.SerializerMethodField()
    entitled_days = LeaveDaysField()
    used_days = LeaveDaysField()
    carried_forward = LeaveDaysField()

    class Meta:
        model = LeaveEntitlement
        fields = [
            'id', 'employee', 'employee_no', 'employee_name', 'year', 'leave_type',
            'leave_type_id', 'leave_type_label', 'entitled_days',
            'used_days', 'carried_forward', 'notes',
            'policy', 'policy_name', 'policy_version', 'policy_version_number',
        ]
        read_only_fields = [
            'id', 'employee_no', 'employee_name', 'leave_type_id',
            'policy', 'policy_name', 'policy_version',
        ]

    def get_leave_type_label(self, obj):
        return obj.leave_type.label if obj.leave_type_id else None

    def get_policy_name(self, obj):
        return obj.policy.name if obj.policy_id else None

    def get_policy_version_number(self, obj):
        return obj.policy_version.version_number if obj.policy_version_id else None


class LeavePolicySerializer(serializers.ModelSerializer):
    leave_type = serializers.SlugRelatedField(
        slug_field='code',
        queryset=ReferenceValue.objects.filter(reference_set__name='leave_type'),
    )
    leave_type_label = serializers.SerializerMethodField()
    employee_count = serializers.IntegerField(read_only=True, default=0)
    latest_version = serializers.SerializerMethodField()
    version_count = serializers.SerializerMethodField()

    class Meta:
        model = LeavePolicy
        fields = [
            'id', 'name', 'description', 'status',
            'effective_from', 'effective_to',
            'leave_type', 'leave_type_label',
            'default_entitled_days', 'max_carryover_days', 'is_carryover_allowed',
            'accrual_method', 'gender_restriction', 'requires_approval',
            'min_service_days', 'is_active', 'notes',
            'applies_to_org_units', 'applies_to_contract_types',
            'applies_to_kuwaitization', 'applies_to_rotations',
            'category', 'tags',
            'employee_count', 'latest_version', 'version_count', 'updated_at',
        ]
        read_only_fields = [
            'id', 'updated_at', 'employee_count', 'latest_version', 'version_count',
        ]

    def get_leave_type_label(self, obj):
        return obj.leave_type.label if obj.leave_type_id else None

    def get_latest_version(self, obj):
        newest = obj.versions.order_by('-version_number').first()
        return newest.version_number if newest else None

    def get_version_count(self, obj):
        return obj.versions.count()


class LeavePolicyVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavePolicyVersion
        fields = [
            'id', 'policy', 'version_number', 'effective_from', 'effective_to',
            'change_summary', 'created_by', 'created_at', 'snapshot',
        ]
        read_only_fields = [
            'id', 'policy', 'version_number', 'effective_from', 'effective_to',
            'created_by', 'created_at', 'snapshot',
        ]


class LeaveRecordSerializer(serializers.ModelSerializer):
    leave_type = serializers.SlugRelatedField(
        slug_field='code',
        queryset=ReferenceValue.objects.filter(reference_set__name='leave_type'),
    )
    leave_type_id = serializers.IntegerField(read_only=True)
    leave_type_label = serializers.SerializerMethodField()
    employee_no = serializers.CharField(source='employee.employee_no', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    days = LeaveDaysField()

    class Meta:
        model = LeaveRecord
        fields = [
            'id', 'employee', 'employee_no', 'employee_name',
            'leave_type', 'leave_type_id', 'leave_type_label',
            'start_date', 'end_date',
            'days', 'status', 'calendar_split', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'employee_no', 'employee_name', 'leave_type_id',
            'created_at', 'updated_at',
        ]

    def get_leave_type_label(self, obj):
        return obj.leave_type.label if obj.leave_type_id else None


class BenefitTypeSerializer(serializers.ModelSerializer):
    category = GovernedValueField(set_name='benefit_category', required=False)

    class Meta:
        model = BenefitType
        fields = [
            'id', 'code', 'name', 'category', 'is_eosi_base', 'is_taxable',
            'is_active',
        ]
        read_only_fields = ['id']


class EmployeeBenefitSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source='component.code', read_only=True, default=None)
    component_name = serializers.CharField(source='component.name', read_only=True, default=None)

    class Meta:
        model = EmployeeBenefit
        fields = [
            'id', 'employee', 'benefit_type', 'monthly_amount',
            'effective_start', 'effective_end', 'notes',
            'reflect_in_salary', 'component', 'component_code', 'component_name',
        ]
        read_only_fields = ['id', 'component_code', 'component_name']


class LoanSerializer(serializers.ModelSerializer):
    loan_type = GovernedValueField(set_name='loan_type', allow_null=False)

    class Meta:
        model = Loan
        fields = [
            'id', 'employee', 'loan_type', 'principal', 'interest_rate',
            'term_months', 'start_date', 'status', 'notes',
        ]
        read_only_fields = ['id']


class SelfLoanSerializer(LoanSerializer):
    """ESS loan list — expose Correspondence status for in-flight drafts.

    Loan subject stays ``draft`` until terminal approve→``active`` (same
    pattern as LeaveRecord). UI must not show eternal ``draft`` while the
    request is awaiting manager/finance in Team (ADR-0045 Plane A).
    """

    reference_no = serializers.SerializerMethodField()
    correspondence_id = serializers.SerializerMethodField()
    correspondence_status = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta(LoanSerializer.Meta):
        fields = LoanSerializer.Meta.fields + [
            'reference_no', 'correspondence_id', 'correspondence_status',
        ]
        read_only_fields = fields

    def _correspondence(self, obj):
        cache = getattr(self, '_corr_cache', None)
        if cache is None:
            cache = self._corr_cache = {}
        if obj.pk not in cache:
            cache[obj.pk] = Correspondence.objects.filter(
                subject_type='people.Loan', subject_id=obj.pk,
            ).first()
        return cache[obj.pk]

    def get_reference_no(self, obj):
        corr = self._correspondence(obj)
        return corr.reference_no if corr else None

    def get_correspondence_id(self, obj):
        corr = self._correspondence(obj)
        return corr.id if corr else None

    def get_correspondence_status(self, obj):
        corr = self._correspondence(obj)
        return corr.status if corr else obj.status

    def get_status(self, obj):
        corr_status = self.get_correspondence_status(obj)
        if obj.status == 'draft' and corr_status and corr_status != 'draft':
            return corr_status
        return obj.status


class LoanInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanInstallment
        fields = [
            'id', 'loan', 'installment_no', 'due_date', 'amount',
            'principal_portion', 'interest_portion', 'status',
        ]
        read_only_fields = ['id']


class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'employee', 'date', 'hours_worked', 'overtime_hours',
            'status', 'source_row',
        ]
        read_only_fields = ['id']


class AttendancePermissionSerializer(serializers.ModelSerializer):
    permission_type = GovernedValueField(set_name='permission_type', allow_null=False)

    class Meta:
        model = AttendancePermission
        fields = [
            'id', 'employee', 'date', 'permission_type', 'hours',
            'status', 'approved', 'notes',
        ]
        read_only_fields = ['id', 'status']


class CertificationSerializer(serializers.ModelSerializer):
    cert_type = GovernedValueField(set_name='cert_type', allow_null=False)

    class Meta:
        model = Certification
        fields = [
            'id', 'employee', 'cert_type', 'number', 'issued_date',
            'expiry_date', 'notes',
        ]
        read_only_fields = ['id']


class RotationScheduleSerializer(serializers.ModelSerializer):
    pattern = GovernedValueField(set_name='rotation_pattern', allow_null=False)

    class Meta:
        model = RotationSchedule
        fields = [
            'id', 'employee', 'pattern', 'start_date', 'config', 'is_active',
        ]
        read_only_fields = ['id']


class PayrollRunValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRunValidation
        fields = [
            'id', 'payroll_run', 'rule_key', 'passed', 'checked', 'failed',
            'sample_failures', 'created_at',
        ]
        read_only_fields = [
            'id', 'payroll_run', 'rule_key', 'passed', 'checked', 'failed',
            'sample_failures', 'created_at',
        ]


class PersonnelEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonnelEvent
        fields = ['id', 'entity_type', 'entity_id', 'event_kind',
                  'effective_date', 'recorded_at', 'recorded_by',
                  'before', 'after', 'notes']
        read_only_fields = ['id', 'recorded_at']
