# File: people/serializers.py
# DRF serializers for the People & Payroll domain (NIR-1C).
#
# Thin serializers over the frozen NIR-1A models. ``auto_now``/``auto_now_add``
# timestamps are read-only; ``PayrollRun.status``/``committed_at`` are
# read-only because status transitions live in ``services.py``.
# ``PayslipLineSerializer`` exposes the lineage fields (``rule_id``,
# ``rule_version``, ``inputs``) per NIBRAS-MASTER-STRATEGY.md §6.3.

from django.utils import timezone

from rest_framework import serializers

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
    class Meta:
        model = ComplianceRule
        fields = [
            'id', 'rule_id', 'version', 'name', 'description',
            'jurisdiction', 'category', 'effective_date', 'formula_ref',
            'source_citation', 'inputs_schema', 'is_authoritative',
            'provenance', 'test_cases', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


def _validate_reference_code(value, set_name):
    """Validate a governed-enum code against ReferenceSet ``set_name`` current values.

    Lenient by design:
    - empty/blank -> valid (optional field)
    - ReferenceSet named ``set_name`` does not exist yet -> skip (reference data
      is seeded by admins, not by this code; RULE_16 no fabrication)
    - code not in current values -> ValidationError
    """
    if not value:
        return value
    from mdm.models import ReferenceSet
    rs = ReferenceSet.objects.filter(name__iexact=set_name).first()
    if rs is None:
        return value
    current_codes = set(
        rs.get_current_values(as_of=timezone.localdate())
        .values_list('code', flat=True)
    )
    if value not in current_codes:
        raise serializers.ValidationError(
            f"{value!r} is not a current value of reference set {set_name!r}"
        )
    return value


class EmployeeSerializer(serializers.ModelSerializer):
    manager = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True,
    )
    position = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Employee
        fields = [
            'id', 'org_unit', 'employee_no', 'full_name', 'nationality',
            'basic_salary', 'join_date', 'rotation', 'is_active', 'photo',
            'name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family',
            'civil_id', 'date_of_birth', 'gender', 'nationality_code',
            'employment_type_code', 'contract_type_code', 'kuwaitization',
            'manager', 'position', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_nationality_code(self, value):
        return _validate_reference_code(value, 'nationality')

    def validate_employment_type_code(self, value):
        return _validate_reference_code(value, 'employment_type')

    def validate_contract_type_code(self, value):
        return _validate_reference_code(value, 'contract_type')


class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = [
            'id', 'org_unit', 'period_start', 'period_end', 'status',
            'created_at', 'committed_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'committed_at']


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
    class Meta:
        model = PayslipLine
        fields = [
            'id', 'payroll_run', 'employee', 'line_type', 'amount',
            'rule_id', 'rule_version', 'inputs', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = [
            'id', 'org_unit', 'code', 'title', 'grade', 'reports_to',
            'is_management', 'status', 'fte', 'job_family_code',
        ]
        read_only_fields = ['id']

    def validate_job_family_code(self, value):
        return _validate_reference_code(value, 'job_family')


class LeaveEntitlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveEntitlement
        fields = [
            'id', 'employee', 'year', 'leave_type', 'entitled_days',
            'used_days', 'carried_forward', 'notes',
        ]
        read_only_fields = ['id']


class LeaveRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRecord
        fields = [
            'id', 'employee', 'leave_type', 'start_date', 'end_date',
            'days', 'status', 'calendar_split', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BenefitTypeSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = Loan
        fields = [
            'id', 'employee', 'loan_type', 'principal', 'interest_rate',
            'term_months', 'start_date', 'status', 'notes',
        ]
        read_only_fields = ['id']


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
    class Meta:
        model = AttendancePermission
        fields = [
            'id', 'employee', 'date', 'permission_type', 'hours',
            'approved', 'notes',
        ]
        read_only_fields = ['id']


class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = [
            'id', 'employee', 'cert_type', 'number', 'issued_date',
            'expiry_date', 'notes',
        ]
        read_only_fields = ['id']


class RotationScheduleSerializer(serializers.ModelSerializer):
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
