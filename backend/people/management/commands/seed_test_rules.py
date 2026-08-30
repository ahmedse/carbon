# File: people/management/commands/seed_test_rules.py
#
# Idempotent seed of NON-AUTHORITATIVE, TEST-ONLY ComplianceRule rows.
#
# These rules exist ONLY to exercise the rule-agnostic Calculation Engine and its
# lineage output. They are NOT authoritative Kuwait figures — no KLL / PIFSS / WPS
# source is cited, ``provenance`` is ``None``, and ``source_citation`` is empty.
# They are excluded from production calculation paths by construction (the engine
# refuses non-authoritative rules unless explicitly opted in).

from datetime import date

from django.core.management.base import BaseCommand

from people.models import ComplianceRule

_NAME_PREFIX = "[TEST ONLY — NON-AUTHORITATIVE]"

# (rule_id, version, name_suffix, category, effective_date, inputs_schema)
TEST_RULES = [
    (
        "kw-eosi-accrual-test",
        "2026.1",
        "EOSI accrual (15 days/yr yrs 1-5, 30 days/yr yr 6+)",
        "eosi",
        date(2026, 1, 1),
        {
            "inputs": ["basic_salary", "service_years"],
            "formula": {
                "type": "tiered_accrual",
                "params": {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": 26,
                    "tiers": [
                        {"up_to": 5, "days_per_year": 15},
                        {"up_to": None, "days_per_year": 30},
                    ],
                },
            },
        },
    ),
    (
        "kw-leave-accrual-test",
        "2026.1",
        "Annual leave accrual (30 days/yr flat)",
        "leave",
        date(2026, 1, 1),
        {
            "inputs": ["basic_salary", "service_years"],
            "formula": {
                "type": "tiered_accrual",
                "params": {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": 26,
                    "tiers": [
                        {"up_to": None, "days_per_year": 30},
                    ],
                },
            },
        },
    ),
    (
        "kw-overtime-test",
        "2026.1",
        "Overtime pay (hours x overtime rate)",
        "overtime",
        date(2026, 1, 1),
        {
            "inputs": ["hours", "overtime_rate"],
            "formula": {
                "type": "multiply",
                "params": {"a": "hours", "b": "overtime_rate"},
            },
        },
    ),
    (
        "kw-gross-pay-test",
        "2026.1",
        "Gross pay (sum of components)",
        "payroll",
        date(2026, 1, 1),
        {
            "inputs": ["basic", "overtime", "leave_pay"],
            "formula": {
                "type": "sum",
                "params": {"components": ["basic", "overtime", "leave_pay"]},
            },
        },
    ),
]


class Command(BaseCommand):
    help = "Seed NON-AUTHORITATIVE test-only compliance rules (idempotent)."

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for rule_id, version, name_suffix, category, effective_date, inputs_schema in TEST_RULES:
            _, was_created = ComplianceRule.objects.update_or_create(
                rule_id=rule_id,
                version=version,
                defaults={
                    "name": f"{_NAME_PREFIX} {name_suffix}",
                    "description": (
                        "TEST-ONLY rule to exercise the Calculation Engine. "
                        "No authoritative Kuwait source — not for production use."
                    ),
                    "category": category,
                    "effective_date": effective_date,
                    "formula_ref": "TEST ONLY — no authoritative source",
                    "source_citation": "",
                    "inputs_schema": inputs_schema,
                    "is_authoritative": False,
                    "provenance": None,
                    "test_cases": [],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"✓ Seeded test-only rules: {created} created, {updated} up-to-date "
            f"({len(TEST_RULES)} total) — all is_authoritative=False."
        ))
