# File: people/services.py
# Service layer for the People app (Facade pattern).
#
# Thin facade over calculation_engine. Views (future NIR phases) call these
# services; services contain NO DRF imports (no rest_framework, no Response).
# RULE_3: people imports only core apps + its own engine — never a sibling
# hosted app (emissions, stores, …).

from . import calculation_engine
from .models import ComplianceRule


class CalculationService:
    """Facade over the rule-agnostic Calculation Engine.

    Resolves the active rule for a category from the versioned library and
    delegates the deterministic computation to calculation_engine.
    """

    @staticmethod
    def calculate_eosi(employee, *, allow_non_authoritative: bool = False, as_of=None):
        return calculation_engine.calculate_eosi(
            employee,
            ComplianceRule.objects,
            allow_non_authoritative=allow_non_authoritative,
            as_of=as_of,
        )

    @staticmethod
    def calculate_leave_accrual(employee, *, allow_non_authoritative: bool = False, as_of=None):
        return calculation_engine.calculate_leave_accrual(
            employee,
            ComplianceRule.objects,
            allow_non_authoritative=allow_non_authoritative,
            as_of=as_of,
        )

    @staticmethod
    def calculate_overtime(employee, inputs, *, allow_non_authoritative: bool = False):
        return calculation_engine.calculate_overtime(
            employee,
            inputs,
            ComplianceRule.objects,
            allow_non_authoritative=allow_non_authoritative,
        )

    @staticmethod
    def calculate_gross_pay(employee, inputs, *, allow_non_authoritative: bool = False):
        return calculation_engine.calculate_gross_pay(
            employee,
            inputs,
            ComplianceRule.objects,
            allow_non_authoritative=allow_non_authoritative,
        )
