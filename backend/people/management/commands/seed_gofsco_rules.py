# File: people/management/commands/seed_gofsco_rules.py
#
# Idempotent seed of AUTHORITATIVE compliance rules + leave policies + benefit
# types for the GOFSCO (Kuwait) HR configuration.
#
# Unlike ``seed_test_rules`` (test-only, non-authoritative), these rows are
# intended to be the real Kuwait figures: ``is_authoritative=True``, provenance
# cites the source, and the leave policies encode the Kuwaiti (42-day) vs expat
# (30-day) split plus rotation scoping.
#
# Derived from: raw/GOFSCO app/20260728/Issues with Hard Task HRMS System.docx
# and Kuwait Labour Law (Private Sector) Law No. 6 of 2010.

from datetime import date

from django.core.management.base import BaseCommand

from mdm.models import ReferenceSet, ReferenceValue

from people.models import BenefitType, ComplianceRule, LeavePolicy

KLL_SOURCE = "Kuwait Labour Law (Private Sector) Law No. 6 of 2010"
GOFSCO_SOURCE = "GOFSCO HRMS Issues (Issues with Hard Task HRMS System.docx, 2026-07-28)"


def _ensure_reference_set(name, slug, values):
    """Idempotently create a ReferenceSet and its ReferenceValues."""
    rs, _ = ReferenceSet.objects.get_or_create(
        name=name,
        defaults={'slug': slug, 'is_active': True, 'lifecycle_state': 'active'},
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


# ── Authoritative compliance rules ──────────────────────────────────────────
# (rule_id, version, name, category, formula_ref, inputs_schema)
AUTHORITATIVE_RULES = [
    (
        "kw-eosi-accrual-expat",
        "2026.1",
        "EOSI indemnity — expatriate (15 days/yr yrs 1-5, 30 days/yr yr 6+)",
        "eosi",
        f"{KLL_SOURCE} Art. 51 (expat daily-rate divisor 26)",
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
        "kw-eosi-accrual-kuwaiti",
        "2026.1",
        "EOSI indemnity — Kuwaiti national (daily-rate divisor 21)",
        "eosi",
        f"{KLL_SOURCE} Art. 51 (Kuwaiti daily-rate divisor 21)",
        {
            "inputs": ["basic_salary", "service_years"],
            "formula": {
                "type": "tiered_accrual",
                "params": {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": 21,
                    "tiers": [
                        {"up_to": 5, "days_per_year": 15},
                        {"up_to": None, "days_per_year": 30},
                    ],
                },
            },
        },
    ),
    (
        "kw-leave-accrual-kuwaiti",
        "2026.1",
        "Annual leave accrual — Kuwaiti national (42 days/yr)",
        "leave",
        f"{KLL_SOURCE} (Kuwaiti leave entitlement)",
        {
            "inputs": ["basic_salary", "service_years"],
            "formula": {
                "type": "tiered_accrual",
                "params": {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": 26,
                    "tiers": [{"up_to": None, "days_per_year": 42}],
                },
            },
        },
    ),
    (
        "kw-leave-accrual-expat",
        "2026.1",
        "Annual leave accrual — expatriate (30 days/yr)",
        "leave",
        f"{KLL_SOURCE} Art. 70 (expat leave entitlement)",
        {
            "inputs": ["basic_salary", "service_years"],
            "formula": {
                "type": "tiered_accrual",
                "params": {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": 26,
                    "tiers": [{"up_to": None, "days_per_year": 30}],
                },
            },
        },
    ),
    (
        "kw-overtime",
        "2026.1",
        "Overtime pay (hours x overtime rate)",
        "overtime",
        f"{KLL_SOURCE} Art. 66",
        {
            "inputs": ["hours", "overtime_rate"],
            "formula": {
                "type": "multiply",
                "params": {"a": "hours", "b": "overtime_rate"},
            },
        },
    ),
    (
        "kw-gross-pay",
        "2026.1",
        "Gross pay (sum of compensation components)",
        "payroll",
        f"{KLL_SOURCE} + WPS file structure",
        {
            "inputs": ["basic", "housing", "transport", "overtime", "leave_pay"],
            "formula": {
                "type": "sum",
                "params": {
                    "components": ["basic", "housing", "transport", "overtime", "leave_pay"],
                },
            },
        },
    ),
]

# ── Benefit types (GOFSCO C&B six categories) ───────────────────────────────
BENEFIT_TYPES = [
    ("ACCOM", "Accommodation", "accommodation", False, False),
    ("VEHICLE", "Company Vehicle", "vehicle", False, True),
    ("MEDICAL", "Medical Insurance", "medical", False, False),
    ("SCHOOL", "Schooling Allowance", "school", False, False),
    ("TICKETS", "Flight Tickets", "tickets", False, False),
    ("OT_BASE", "Overtime Base", "other", False, True),
]

# ── Leave policies ──────────────────────────────────────────────────────────
# leave_type_code, name, category, tags, kuwaitization, rotations, days
LEAVE_POLICIES = [
    (
        "annual", "Annual Leave — Kuwaiti (42 days)", "Leave",
        ["annual", "kuwaiti", "governed"], LeavePolicy.KUWAIT_ONLY, [], 42,
    ),
    (
        "annual", "Annual Leave — Expat (30 days)", "Leave",
        ["annual", "expat", "governed"], LeavePolicy.KUWAIT_NON, [], 30,
    ),
    (
        "sick", "Sick Leave", "Leave",
        ["sick"], LeavePolicy.KUWAIT_ANY, [], 21,
    ),
    (
        "emergency", "Emergency Leave", "Leave",
        ["emergency"], LeavePolicy.KUWAIT_ANY, [], 3,
    ),
    (
        "maternity", "Maternity Leave", "Leave",
        ["maternity"], LeavePolicy.KUWAIT_ANY, [], 90,
    ),
    (
        "unpaid", "Unpaid Leave", "Leave",
        ["unpaid"], LeavePolicy.KUWAIT_ANY, [], 30,
    ),
    (
        "annual", "Rotation Leave — Field Rotation", "Leave",
        ["annual", "rotation", "field"], LeavePolicy.KUWAIT_ANY, ["2/1", "3/1"], 30,
    ),
]


class Command(BaseCommand):
    help = "Seed AUTHORITATIVE GOFSCO compliance rules, leave policies, and benefit types (idempotent)."

    def handle(self, *args, **options):
        # 1. Governed reference metadata (leave_type) for LeavePolicy.leave_type FK.
        leave_type_rs = _ensure_reference_set(
            "leave_type", "leave-type", [
                ("annual", "Annual"), ("sick", "Sick"),
                ("emergency", "Emergency"), ("maternity", "Maternity"),
                ("unpaid", "Unpaid"),
            ],
        )
        leave_types = {
            rv.code: rv
            for rv in ReferenceValue.objects.filter(reference_set=leave_type_rs)
        }

        # 2. Benefit types.
        bt_created = 0
        for code, name, category, is_eosi_base, is_taxable in BENEFIT_TYPES:
            _, was_created = BenefitType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "is_eosi_base": is_eosi_base,
                    "is_taxable": is_taxable,
                    "is_active": True,
                },
            )
            bt_created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f"✓ Benefit types: {bt_created} created, rest up-to-date ({len(BENEFIT_TYPES)} total)"
        ))

        # 3. Authoritative compliance rules.
        rule_created = rule_updated = 0
        for rule_id, version, name, category, formula_ref, inputs_schema in AUTHORITATIVE_RULES:
            _, was_created = ComplianceRule.objects.update_or_create(
                rule_id=rule_id,
                version=version,
                defaults={
                    "name": name,
                    "description": "Authoritative Kuwait compliance rule (GOFSCO configuration).",
                    "category": category,
                    "effective_date": date(2026, 1, 1),
                    "formula_ref": formula_ref,
                    "source_citation": f"{KLL_SOURCE}; {GOFSCO_SOURCE}",
                    "inputs_schema": inputs_schema,
                    "is_authoritative": True,
                    "provenance": {
                        "source": GOFSCO_SOURCE,
                        "citation": KLL_SOURCE,
                        "reviewed_by": "HR Compliance",
                        "reviewed_on": "2026-07-28",
                    },
                    "test_cases": [],
                },
            )
            if was_created:
                rule_created += 1
            else:
                rule_updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"✓ Authoritative rules: {rule_created} created, {rule_updated} up-to-date "
            f"({len(AUTHORITATIVE_RULES)} total) — all is_authoritative=True"
        ))

        # 4. Leave policies (scoped by Kuwaitization + rotation).
        lp_created = lp_updated = 0
        for code, name, category, tags, kuwait, rotations, days in LEAVE_POLICIES:
            leave_type = leave_types.get(code)
            if leave_type is None:
                self.stderr.write(self.style.WARNING(
                    f"⚠ Skipping policy '{name}': leave_type code '{code}' missing"
                ))
                continue
            policy = LeavePolicy.objects.filter(
                leave_type=leave_type, name=name,
            ).first()
            defaults = {
                "leave_type": leave_type,
                "name": name,
                "category": category,
                "tags": tags,
                "default_entitled_days": days,
                "accrual_method": LeavePolicy.ACCRUAL_UPFRONT,
                "max_carryover_days": 15,
                "is_carryover_allowed": True,
                "status": LeavePolicy.STATUS_ACTIVE,
                "effective_from": date(2026, 1, 1),
                "applies_to_kuwaitization": kuwait,
                "applies_to_rotations": rotations,
                "notes": "Authoritative GOFSCO leave policy.",
            }
            if policy is None:
                LeavePolicy.objects.create(**defaults)
                lp_created += 1
            else:
                for field, value in defaults.items():
                    if field == "leave_type":
                        continue
                    setattr(policy, field, value)
                policy.save()
                lp_updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"✓ Leave policies: {lp_created} created, {lp_updated} up-to-date "
            f"({len(LEAVE_POLICIES)} total)"
        ))

        self.stdout.write(self.style.SUCCESS(
            "✓ GOFSCO authoritative configuration seeded."
        ))
