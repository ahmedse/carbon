# File: people/serializers.py
# DRF serializers for the People & Payroll domain (NIR-1C).
#
# Thin serializers over the frozen NIR-1A models. ``auto_now``/``auto_now_add``
# timestamps are read-only; ``PayrollRun.status``/``committed_at`` are
# read-only because status transitions live in ``services.py``.
# ``PayslipLineSerializer`` exposes the lineage fields (``rule_id``,
# ``rule_version``, ``inputs``) per NIBRAS-MASTER-STRATEGY.md §6.3.

from rest_framework import serializers

from .models import ComplianceRule, Employee, PayrollRun, PayslipLine


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


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            'id', 'org_unit', 'employee_no', 'full_name', 'nationality',
            'basic_salary', 'join_date', 'rotation', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = [
            'id', 'org_unit', 'period_start', 'period_end', 'status',
            'created_at', 'committed_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'committed_at']


class PayslipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipLine
        fields = [
            'id', 'payroll_run', 'employee', 'line_type', 'amount',
            'rule_id', 'rule_version', 'inputs', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
