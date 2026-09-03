# File: people/admin.py
# Django admin registration for the People app models.

from django.contrib import admin

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
    Position,
    RotationSchedule,
)


@admin.register(ComplianceRule)
class ComplianceRuleAdmin(admin.ModelAdmin):
    list_display = [
        'rule_id', 'version', 'name', 'category', 'jurisdiction',
        'effective_date', 'is_authoritative',
    ]
    list_filter = ['category', 'jurisdiction', 'is_authoritative']
    search_fields = ['rule_id', 'name', 'formula_ref']
    ordering = ['category', 'rule_id', '-effective_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        'employee_no', 'full_name', 'org_unit', 'basic_salary', 'join_date', 'is_active',
    ]
    list_filter = ['org_unit', 'is_active']
    search_fields = ['employee_no', 'full_name', 'nationality']
    ordering = ['employee_no']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ['id', 'org_unit', 'period_start', 'period_end', 'status', 'created_at']
    list_filter = ['status', 'org_unit']
    ordering = ['-period_start']
    readonly_fields = ['created_at', 'committed_at']


@admin.register(PayslipLine)
class PayslipLineAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'payroll_run', 'employee', 'line_type', 'amount', 'rule_id', 'rule_version',
    ]
    list_filter = ['line_type']
    search_fields = ['employee__employee_no', 'employee__full_name', 'rule_id']
    ordering = ['id']
    readonly_fields = ['created_at']


@admin.register(PayrollRunValidation)
class PayrollRunValidationAdmin(admin.ModelAdmin):
    list_display = ['id', 'payroll_run', 'rule_key', 'passed', 'checked', 'failed', 'created_at']
    list_filter = ['passed', 'rule_key']
    search_fields = ['rule_key', 'payroll_run__id']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'org_unit', 'grade', 'reports_to', 'is_management']
    list_filter = ['org_unit', 'is_management', 'grade']
    search_fields = ['code', 'title']
    ordering = ['org_unit', 'code']


@admin.register(LeaveEntitlement)
class LeaveEntitlementAdmin(admin.ModelAdmin):
    list_display = ['employee', 'year', 'leave_type', 'entitled_days', 'used_days', 'carried_forward']
    list_filter = ['year', 'leave_type']
    search_fields = ['employee__employee_no', 'employee__full_name']
    ordering = ['employee', 'year', 'leave_type']


@admin.register(LeaveRecord)
class LeaveRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'days', 'status']
    list_filter = ['status', 'leave_type']
    search_fields = ['employee__employee_no', 'employee__full_name']
    ordering = ['-start_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(BenefitType)
class BenefitTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'is_eosi_base', 'is_taxable']
    list_filter = ['category', 'is_eosi_base', 'is_taxable']
    search_fields = ['code', 'name']
    ordering = ['category', 'code']


@admin.register(EmployeeBenefit)
class EmployeeBenefitAdmin(admin.ModelAdmin):
    list_display = ['employee', 'benefit_type', 'monthly_amount', 'effective_start', 'effective_end']
    list_filter = ['benefit_type', 'effective_start']
    search_fields = ['employee__employee_no', 'employee__full_name', 'benefit_type__name']
    ordering = ['employee', 'benefit_type']


class LoanInstallmentInline(admin.TabularInline):
    model = LoanInstallment
    extra = 0


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['id', 'employee', 'loan_type', 'principal', 'term_months', 'start_date', 'status']
    list_filter = ['status', 'loan_type']
    search_fields = ['employee__employee_no', 'employee__full_name']
    ordering = ['-start_date']
    inlines = [LoanInstallmentInline]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'hours_worked', 'overtime_hours', 'status']
    list_filter = ['status', 'date']
    search_fields = ['employee__employee_no', 'employee__full_name']
    ordering = ['-date']


@admin.register(AttendancePermission)
class AttendancePermissionAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'permission_type', 'hours', 'approved']
    list_filter = ['approved', 'permission_type']
    search_fields = ['employee__employee_no', 'employee__full_name']
    ordering = ['-date']


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'cert_type', 'number', 'issued_date', 'expiry_date']
    list_filter = ['cert_type']
    search_fields = ['employee__employee_no', 'employee__full_name', 'number']
    ordering = ['expiry_date']


@admin.register(RotationSchedule)
class RotationScheduleAdmin(admin.ModelAdmin):
    list_display = ['employee', 'pattern', 'start_date', 'is_active']
    list_filter = ['is_active', 'pattern']
    search_fields = ['employee__employee_no', 'employee__full_name']
    ordering = ['-start_date']


@admin.register(CompensationComponent)
class CompensationComponentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'direction', 'category', 'sort_order', 'is_active']
    list_filter = ['direction', 'category', 'is_active', 'is_eosi_base', 'is_gosi_base']
    search_fields = ['code', 'name', 'name_ar']
    ordering = ['direction', 'sort_order', 'code']


@admin.register(CompensationPlan)
class CompensationPlanAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'org_unit', 'pay_grade_code', 'job_family_code',
        'component', 'amount', 'currency', 'frequency',
        'effective_start', 'effective_end', 'is_active',
    ]
    list_filter = ['frequency', 'is_active', 'pay_grade_code', 'job_family_code']
    search_fields = ['component__code', 'component__name', 'pay_grade_code', 'job_family_code']
    ordering = ['pay_grade_code', 'component', '-effective_start']
    readonly_fields = ['created_at']


@admin.register(EmployeeCompensation)
class EmployeeCompensationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'employee', 'component', 'amount', 'currency', 'frequency',
        'effective_start', 'effective_end', 'is_verified', 'created_at',
    ]
    list_filter = ['frequency', 'is_verified', 'component']
    search_fields = [
        'employee__employee_no', 'employee__full_name',
        'component__code', 'component__name',
    ]
    ordering = ['employee', 'component', '-effective_start']
    readonly_fields = ['created_at', 'verified_at']
