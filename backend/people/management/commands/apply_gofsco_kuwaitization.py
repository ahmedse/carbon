# people/management/commands/apply_gofsco_kuwaitization.py
# Applies real GOFSCO Kuwaitization data extracted from KOC contract appendices.
# Source: raw/GOFSCO app/20260913/gofsco_extracted_data.json
# Idempotent — safe to re-run.
import json
from pathlib import Path
from datetime import date

from django.core.management.base import BaseCommand

SOURCE_JSON = (
    Path(__file__).resolve().parents[4]
    / "raw/GOFSCO app/20260913/gofsco_extracted_data.json"
)

KOC_POLICY_SOURCE = "KOC Kuwaitization Appendix (KOC Contract Specifications, KOC-C-004)"
KLL_SOURCE = "Kuwait Labour Law No. 6/2010 + Ministerial Order 176/2012"


class Command(BaseCommand):
    help = "Apply real GOFSCO Kuwaitization data — marks employees, creates koc_contract refs and compliance rules."

    def handle(self, *args, **options):
        from mdm.models import ReferenceSet, ReferenceValue
        from people.models import Employee, ComplianceRule

        data = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
        contracts = data["contracts"]
        kuwaiti_employees = data["kuwaiti_employees"]

        # ── 1. koc_contract reference set ──────────────────────────────────
        koc_rs, _ = ReferenceSet.objects.update_or_create(
            slug="koc-contract",
            defaults={
                "name": "KOC Contract",
                "description": "KOC field-services contracts held by GOFSCO (contract code = short name; metadata.contract_no = KOC contract number)",
            },
        )
        rv_created = rv_updated = 0
        koc_rv_map = {}
        for c in contracts:
            rv, was_created = ReferenceValue.objects.update_or_create(
                reference_set=koc_rs,
                code=c["code"],
                defaults={
                    "label": c["name"],
                    "sort_order": c["sr"],
                    "is_active": True,
                    "metadata": {
                        "contract_no": c["contract_no"],
                        "required": c["required"],
                        "supplied": c["supplied"],
                        "vacancy": c["vacancy"],
                        "reimbursement": c["reimbursement"],
                    },
                },
            )
            koc_rv_map[c["code"]] = rv
            if was_created:
                rv_created += 1
            else:
                rv_updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"✓ koc_contract reference set: {rv_created} created, {rv_updated} updated ({len(contracts)} total)"
        ))

        # ── 2. Mark 54 Kuwaiti employees ───────────────────────────────────
        matched = not_found = already_set = updated = 0
        for row in kuwaiti_employees:
            emp_no = row["employee_no"]
            try:
                emp = Employee.objects.get(employee_no=emp_no)
            except Employee.DoesNotExist:
                self.stderr.write(self.style.WARNING(f"  ⚠ emp {emp_no} ({row['full_name']}) not in DB — skipped"))
                not_found += 1
                continue
            matched += 1
            changed = False
            if not emp.kuwaitization:
                emp.kuwaitization = True
                changed = True
            if emp.nationality_id is None or (
                emp.nationality and emp.nationality.code != "KWT"
            ):
                kwt = ReferenceValue.objects.filter(
                    reference_set__name="nationality", code="KWT",
                ).first()
                if kwt:
                    emp.nationality = kwt
                    changed = True
            if changed:
                emp.save(update_fields=["kuwaitization", "nationality"])
                updated += 1
            else:
                already_set += 1
        self.stdout.write(self.style.SUCCESS(
            f"✓ Kuwaiti employees: {updated} updated, {already_set} already correct, "
            f"{not_found} not found in DB ({len(kuwaiti_employees)} in source)"
        ))

        # ── 3. Kuwaitization compliance rules (one per KOC contract) ───────
        rule_created = rule_updated = 0
        for c in contracts:
            rule_id = f"koc-kuwaitization-{c['code']}"
            reimb = c["reimbursement"]
            reimb_note = (
                f"Salary: {reimb['salary']}; PIFSS emp: {reimb['pifss_employee']}; "
                f"PIFSS co: {reimb['pifss_company']}; Increments: {reimb['increments']}; "
                f"Medical: {reimb['medical']}; Bonus: {reimb['annual_bonus']}; "
                f"Tickets: {reimb['annual_tickets']}"
            )
            cat_rv, _ = ReferenceValue.objects.get_or_create(
                reference_set=ReferenceSet.objects.get_or_create(
                    name="compliance_category",
                    defaults={
                        "slug": "compliance-category",
                        "is_active": True,
                        "lifecycle_state": "active",
                    },
                )[0],
                code="other",
                defaults={"label": "Other", "is_active": True},
            )
            # Prefer a dedicated kuwaitization value when present; else 'other'.
            kuw = ReferenceValue.objects.filter(
                reference_set__name="compliance_category", code="kuwaitization",
            ).first()
            juris = ReferenceValue.objects.filter(
                reference_set__name="jurisdiction", code="KW",
            ).first()
            _, was_created = ComplianceRule.objects.update_or_create(
                rule_id=rule_id,
                version="2026.1",
                defaults={
                    "name": f"Kuwaitization Quota — {c['name']} (Contract {c['contract_no']})",
                    "description": (
                        f"KOC-mandated Kuwaitization quota for {c['name']}. "
                        f"Required: {c['required']} Kuwaiti nationals; "
                        f"Supplied: {c['supplied']}; Vacancy: {c['vacancy']}. "
                        f"Reimbursement: {reimb_note}."
                    ),
                    "category": kuw or cat_rv,
                    "jurisdiction": juris,
                    "effective_date": date(2026, 1, 1),
                    "formula_ref": KOC_POLICY_SOURCE,
                    "source_citation": f"{KOC_POLICY_SOURCE}; {KLL_SOURCE}",
                    "inputs_schema": {
                        "inputs": ["kuwaiti_headcount", "required_quota"],
                        "formula": {
                            "type": "quota_check",
                            "params": {
                                "contract_no": c["contract_no"],
                                "contract_name": c["name"],
                                "required": c["required"],
                                "supplied": c["supplied"],
                                "vacancy": c["vacancy"],
                                "compliant": c["vacancy"] == 0,
                            },
                        },
                    },
                    "is_authoritative": True,
                    "provenance": {
                        "source": KOC_POLICY_SOURCE,
                        "citation": KLL_SOURCE,
                        "reviewed_by": "HR Compliance",
                        "reviewed_on": "2026-09-13",
                        "contract_no": c["contract_no"],
                        "supply_date": "2026-09-13",
                    },
                    "test_cases": [],
                },
            )
            if was_created:
                rule_created += 1
            else:
                rule_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"✓ Kuwaitization compliance rules: {rule_created} created, {rule_updated} updated ({len(contracts)} total)"
        ))

        # ── 4. Summary ─────────────────────────────────────────────────────
        total_req = sum(c["required"] for c in contracts)
        total_sup = sum(c["supplied"] for c in contracts)
        total_vac = sum(c["vacancy"] for c in contracts)
        pct = round(100 * total_sup / total_req, 1) if total_req else 0
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Kuwaitization compliance: {total_sup}/{total_req} filled "
            f"({pct}%), {total_vac} vacancies"
        ))
        self.stdout.write("  Per-contract:")
        for c in contracts:
            flag = "✓" if c["vacancy"] == 0 else "⚠"
            self.stdout.write(
                f"  {flag}  {c['name']:40s}  req={c['required']:2d}  sup={c['supplied']:2d}  vac={c['vacancy']:2d}"
            )
