"""Seed the Nibras People & Payroll process knowledge base (S-PROC-01).

This command populates the durable ``KnowledgeEntity`` rows that the
``search_knowledge`` tool reads for ``instance_id="nibras"`` — the instance id
resolved by ``ai.instance_registry.resolve_instance_id()`` when
``DJANGO_BRAND=nibras``. It is what makes process grounding non-empty: before
this command, the knowledge base was empty and every "how does payroll work?"
question returned "I couldn't find specific details".

Idempotent by natural key ``(instance_id, entity_type, name)``. ``--reset``
clears the Nibras instance + its knowledge rows first.

Usage:
    python manage.py seed_nibras_knowledge            # upsert (idempotent)
    python manage.py seed_nibras_knowledge --reset    # wipe nibras rows, reseed
    python manage.py seed_nibras_knowledge --instance nibras --app people

IMPORTANT — this seeds via the Django ORM (``ai.models.core.KnowledgeEntity``)
NOT via ``KnowledgeStore.store_entities``. The engine's lexical fallback
(``KnowledgeStore._lexical_search``) reads Django ORM rows, so the durable rows
must exist here for grounding to work without a vector backend.

The descriptions deliberately spell out both the canonical Nibras stage names
(draft → compute → validate → commit) and the activity verbs (calculation,
validation, approval, posting, disbursement, reconciliation) so both the
persona and the QA acceptance checks can cite concrete stages.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from ai.models.core import Instance, KnowledgeEntity

# (entity_type, name, semantic_description)
KNOWLEDGE_SPECS = [
    # ── Processes ──────────────────────────────────────────────────────
    (
        "process",
        "Payroll Run Lifecycle",
        "The payroll run lifecycle has four sequential stages: "
        "(1) draft — initial setup where the run is created for a pay period "
        "and preliminary calculations are generated; "
        "(2) compute — the calculation stage where tax and statutory deduction "
        "rules (GOSI employee share, loan installments) are applied to produce "
        "payslip lines; "
        "(3) validate — the validation and approval stage where variance checks "
        "and approval gates run against the previous period; "
        "(4) commit — the final posting stage that is irreversible and triggers "
        "WPS Wage Protection System SIF file generation for salary disbursement. "
        "After commit, reconciliation confirms every employee's net pay and the "
        "SIF totals match before disbursement to bank accounts.",
    ),
    (
        "process",
        "Payroll Validation Gates",
        "Payroll validation and approval gates run between compute and commit. "
        "The system checks variance against the prior pay period, flags new hires "
        "and terminations, verifies GOSI contribution totals, and confirms loan "
        "installment deductions sum to the expected schedule. A run cannot reach "
        "the commit (posting) stage until all validation gates pass; an authorised "
        "user approves the validated run before it is posted.",
    ),
    (
        "process",
        "Payroll Reconciliation",
        "Payroll reconciliation is the post-commit check that the gross-to-net "
        "calculation is complete and correct for every employee: gross pay minus "
        "GOSI employee share minus loan installment equals net pay. It compares "
        "the committed run totals against the WPS SIF file and the disbursement "
        "batch, flagging any employee whose net amount does not reconcile.",
    ),
    (
        "process",
        "Loan Schedule Lifecycle",
        "A loan has a principal and a fixed monthly installment deducted from the "
        "payslip until the principal is recovered. Each payroll compute stage "
        "generates a loan_installment payslip line for the due amount; payments "
        "are tracked per installment (paid or due). Early repayment is possible "
        "with HR approval and advances are reconciled against the outstanding "
        "balance before posting.",
    ),
    (
        "process",
        "Leave Calendar-Split",
        "When a leave spans a month boundary, the days are split proportionally "
        "across each pay period so the correct number of days falls into each "
        "payroll run. This calendar-split drives the leave accrual and any "
        "unpaid-leave deduction applied at the compute stage.",
    ),
    (
        "process",
        "Employee Onboarding",
        "Employee onboarding creates the HR record that payroll depends on: "
        "personal data, position, org unit, basic salary, join date, contract "
        "type, and active status. A new hire appears in the next payroll run "
        "draft only after onboarding is complete and the contract is active.",
    ),
    # ── Concepts ───────────────────────────────────────────────────────
    (
        "concept",
        "Payslip Line Types",
        "A payslip is made of line types: gross (total earnings before "
        "deductions), gosi (the GOSI employee share deduction), loan_installment "
        "(a scheduled loan repayment deduction), and net (gross minus all "
        "deductions — the amount actually paid to the employee). Net-pay "
        "verification is always gross minus GOSI minus loan_installment.",
    ),
    (
        "concept",
        "GOSI Contributions",
        "GOSI is the social insurance scheme for Saudi and GCC labour law. Both "
        "employee and employer contribute: the employee share is deducted from "
        "gross pay as the gosi payslip line, and the employer share is paid on "
        "top of gross. The exact percentage is rule-configured per scheme, "
        "nationality, and contract — never assume a single universal rate; "
        "recommend checking the system configuration.",
    ),
    (
        "concept",
        "WPS Wage Protection System",
        "WPS is the Wage Protection System. Committing a payroll run generates a "
        "mandatory SIF file submitted to the labour ministry confirming salaries "
        "have been paid. The SIF file is the disbursement proof for the pay "
        "period and is the source of truth for reconciliation.",
    ),
    (
        "concept",
        "Net Pay Verification",
        "Net pay verification confirms gross minus GOSI employee share minus loan "
        "installment equals net for every payslip line. Read the payroll run "
        "output with list_payslip_lines before stating any salary figure; never "
        "state a figure that was not read from a tool result.",
    ),
]


class Command(BaseCommand):
    help = (
        "Seed Nibras People & Payroll process knowledge (KnowledgeEntity) for "
        "instance_id='nibras' so process grounding (S-PROC-01) is non-empty."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the Nibras instance and its knowledge rows before seeding.",
        )
        parser.add_argument(
            "--instance",
            default="nibras",
            help="Engine instance id to seed (default: nibras).",
        )
        parser.add_argument(
            "--app",
            default="people",
            help="App identifier for the seeded rows (default: people).",
        )

    def handle(self, *args, **options):
        instance_id = options["instance"]
        app_identifier = options["app"]

        with transaction.atomic():
            if options.get("reset"):
                KnowledgeEntity.objects.filter(instance_id=instance_id).delete()
                Instance.objects.filter(name=instance_id).delete()
                self.stdout.write(
                    self.style.WARNING(f"Cleared existing '{instance_id}' rows.")
                )

            instance, instance_created = self._seed_instance(instance_id)
            created = 0
            existing = 0
            for entity_type, name, description in KNOWLEDGE_SPECS:
                obj, was_created = KnowledgeEntity.objects.get_or_create(
                    instance_id=instance_id,
                    entity_type=entity_type,
                    name=name,
                    defaults={
                        "semantic_description": description,
                        "app_identifier": app_identifier,
                        "visibility": "shared",
                    },
                )
                if was_created:
                    created += 1
                else:
                    # Refresh description on re-run so content stays current.
                    obj.semantic_description = description
                    obj.app_identifier = app_identifier
                    obj.visibility = "shared"
                    obj.save(update_fields=[
                        "semantic_description", "app_identifier", "visibility",
                    ])
                    existing += 1

        self.stdout.write(self.style.SUCCESS("Nibras knowledge seed complete."))
        self.stdout.write(
            f"  instance      {instance.name!r} "
            f"({'created' if instance_created else 'existing'})"
        )
        self.stdout.write(
            f"  KnowledgeEntity  created={created} updated={existing} "
            f"(instance_id={instance_id!r}, app={app_identifier!r})"
        )

    def _seed_instance(self, instance_id: str):
        from django.conf import settings as dj_settings

        platform_name = (
            getattr(dj_settings, "PLATFORM_TITLE", "")
            or getattr(dj_settings, "PLATFORM_NAME", "")
            or "Nibras — People & Payroll"
        )
        instance, created = Instance.objects.get_or_create(
            name=instance_id,
            defaults={
                "display_name": platform_name,
                "host_db_url": (
                    "postgresql://carbon:****@localhost:5432/carbon"
                ),
                "host_api_url": "http://127.0.0.1:8009",
                "status": "active",
                "config": {"domain": "people-payroll", "advisory_only": True},
            },
        )
        return instance, created
