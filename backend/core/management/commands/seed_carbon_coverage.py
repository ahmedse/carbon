"""
core/management/commands/seed_carbon_coverage.py

Populate the GHG Protocol configuration layer that seed_carbon_raw.py
intentionally leaves empty: Inventory Coverage (declared universe),
SBTi targets, coverage goals, coverage actions, and the small cleanups
(org-unit rename, duplicate rule rename, boundary fix, factor hardening).

Ground rules (agreed, no fabrication):
  - InventorySource = the DECLARED universe only — sources AASTMT is
    accountable for (inventory `present` + `pending`). `not_applicable`
    sources are NOT declared (they do not exist at that campus) and are
    reported in the audit, not stored as model rows.
  - InventorySourceStatus is the honest state machine:
      covered   -> has a linked DataTable AND a Calculation
      declared  -> in the inventory but not yet calculated
  - SBTi targets are POLICY choices (not measured data): SBTi 1.5°C
    absolute contraction, aligned to Egypt's 42% renewable-by-2030 goal.
    Marked status='draft' pending board ratification.

Idempotent: update_or_create / get_or_create throughout. Safe to re-run.
Does NOT touch Users/Groups or other apps.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Populate inventory coverage, SBTi targets, coverage goals/actions + cleanups."

    def handle(self, *args, **options):
        from mdm.models import OrgUnit, ReferenceValue
        from emissions.models import (
            EmissionFactor, ReportingPeriod, OrganizationalBoundary,
            SBTiTarget, InventorySource, InventorySourceStatus,
            CoverageGoal, CoverageAction,
        )

        with transaction.atomic():
            summary = {}

            # ── 0. Org-unit rename: "Giza Smart Village" -> "Smart Village" ──
            summary["OrgUnit rename"] = self._rename_smart_village(OrgUnit, ReferenceValue)

            # ── 1. Duplicate rule rename (period-scoped) ──────────────────
            summary["Rule rename"] = self._rename_duplicate_rules()

            # ── 2. Boundary fix: add Smart Village to FY 2025-26 ──────────
            summary["Boundary fix"] = self._fix_boundary(OrgUnit, OrganizationalBoundary)

            # ── 3. Factor hardening: country_code ─────────────────────────
            summary["Factor country_code"] = self._harden_factors(EmissionFactor)

            # ── 4. SBTi targets (policy, draft) ───────────────────────────
            summary["SBTi targets"] = self._sbti_targets(OrgUnit, SBTiTarget)

            # ── 5. Inventory coverage (declared universe) ─────────────────
            sources = self._inventory_sources(OrgUnit, InventorySource)
            summary["InventorySource"] = len(sources)
            summary["InventorySourceStatus"] = self._source_statuses(
                InventorySourceStatus, sources)

            # ── 6. Coverage goals ─────────────────────────────────────────
            summary["CoverageGoal"] = self._coverage_goals(OrgUnit, SBTiTarget, CoverageGoal)

            # ── 7. Coverage actions ───────────────────────────────────────
            summary["CoverageAction"] = self._coverage_actions(InventorySource, CoverageAction)

        self.stdout.write(self.style.SUCCESS("\nCarbon coverage seed complete."))
        for k, v in summary.items():
            self.stdout.write(f"  {k}: {v}")

    # ── 0 ────────────────────────────────────────────────────────────────
    def _rename_smart_village(self, OrgUnit, ReferenceValue):
        from mdm.models import ReferenceSet
        sv = OrgUnit.objects.filter(slug="aastmt-giza-smart-village").first()
        if not sv:
            return "not found (skip)"
        sv.name = "Smart Village"
        sv.slug = "aastmt-smart-village"
        sv.description = "Smart Village Branch"
        sv.save(update_fields=["name", "slug", "description"])
        # re-slug children so nothing references the old campus slug
        n = 0
        for child in sv.children.all():
            if "giza-smart-village" in child.slug:
                child.slug = child.slug.replace("giza-smart-village", "smart-village")
                child.save(update_fields=["slug"])
                n += 1
        # update the campuses ReferenceSet label (code "smart-village" already correct)
        try:
            rs = ReferenceSet.objects.get(name="campuses")
            rv = rs.values.get(code="smart-village")
            if rv.label == "Giza Smart Village":
                rv.label = "Smart Village"
                rv.save(update_fields=["label"])
        except (ReferenceSet.DoesNotExist, ReferenceValue.DoesNotExist):
            pass
        return f"campus + {n} dept slugs"

    # ── 1 ────────────────────────────────────────────────────────────────
    def _rename_duplicate_rules(self):
        from emissions.models import CalculationRule
        updated = 0
        for rule in CalculationRule.objects.filter(name="Electricity → CO2e"):
            period = rule.data_table.module.name.split("—")[0].strip()
            scope = rule.scope2_calculation_method
            if "Smart Village" in rule.data_table.module.name:
                rule.name = "Electricity → CO2e (Smart Village, FY 2023-24)"
            elif "Abu Qir" in rule.data_table.module.name:
                rule.name = "Electricity → CO2e (Abu Qir, FY 2025-26)"
            rule.save(update_fields=["name"])
            updated += 1
        return updated

    # ── 2 ────────────────────────────────────────────────────────────────
    def _fix_boundary(self, OrgUnit, OrganizationalBoundary):
        boundary = OrganizationalBoundary.objects.filter(
            name="AASTMT FY 2025-26 Operational Control").first()
        if not boundary:
            return "not found (skip)"
        sv = OrgUnit.objects.filter(slug="aastmt-smart-village").first()
        if sv:
            boundary.included_org_units.add(sv)
        return f"{boundary.included_org_units.count()} org units"

    # ── 3 ────────────────────────────────────────────────────────────────
    def _harden_factors(self, EmissionFactor):
        eg = {"EG_GRID_2024", "EG_WATER_2024", "CHILLED_WATER_COP3.5"}
        defra = {"DEFRA_DIESEL", "DEFRA_GASOLINE", "DEFRA_GASOLINE_95",
                 "DEFRA_NATURAL_GAS", "DEFRA_LPG"}
        n = 0
        for f in EmissionFactor.objects.all():
            cc = "EG" if f.code in eg else ("GB" if f.code in defra else None)
            if cc and f.country_code != cc:
                f.country_code = cc
                f.save(update_fields=["country_code"])
                n += 1
        return n

    # ── 4 ────────────────────────────────────────────────────────────────
    def _sbti_targets(self, OrgUnit, SBTiTarget):
        aastmt = OrgUnit.objects.filter(slug="aastmt").first()
        specs = [
            dict(name="AASTMT Scope 1+2 Reduction (SBTi 1.5°C)", scope="1+2",
                 target_year=2030, reduction_pct=Decimal("42.00"),
                 description="Absolute contraction aligned to SBTi 1.5°C and Egypt's "
                             "42% renewable-electricity-by-2030 goal."),
            dict(name="AASTMT Scope 3 Reduction (SBTi near-term)", scope="3",
                 target_year=2030, reduction_pct=Decimal("25.00"),
                 description="SBTi near-term Scope 3 floor (materiality-bounded)."),
            dict(name="AASTMT Net-Zero Anchor (long-term)", scope="1+2+3",
                 target_year=2050, reduction_pct=Decimal("90.00"),
                 description="Long-term net-zero anchor per SBTi corporate net-zero standard."),
        ]
        n = 0
        for s in specs:
            obj, created = SBTiTarget.objects.update_or_create(
                org_unit=aastmt, name=s["name"],
                defaults=dict(base_year=2024, target_year=s["target_year"],
                              target_type="absolute", scope=s["scope"],
                              reduction_pct=s["reduction_pct"],
                              status="draft", description=s["description"]),
            )
            n += 1
        return n

    # ── 5 ────────────────────────────────────────────────────────────────
    def _inventory_sources(self, OrgUnit, InventorySource):
        """Declared universe = present + pending sources only (accountable)."""
        sv = OrgUnit.objects.filter(slug="aastmt-smart-village").first()
        aq = OrgUnit.objects.filter(slug="aastmt-abu-qir").first()
        asw = OrgUnit.objects.filter(slug="aastmt-aswan-south-valley").first()

        # (org, scope, scope3_category, source_name)
        spec = [
            # ── Smart Village (FY 2023-24 inventory) ──
            (sv, 1, None, "Diesel generators (on-site power)"),
            (sv, 1, None, "Diesel vehicles (owned/controlled)"),
            (sv, 1, None, "Fire suppression (dry powder / CO2 / dry chemical)"),
            (sv, 1, None, "FM200 fire suppression"),
            (sv, 2, None, "Purchased electricity"),
            (sv, 2, None, "District chilled water (purchased cooling)"),
            (sv, 3, 1, "Consumables — paper / envelopes / folders"),
            (sv, 3, 1, "Consumables — printer cartridges / toner"),
            (sv, 3, 1, "Consumables — hygiene (soap / tissues)"),
            (sv, 3, 1, "Food consumption (meals)"),
            (sv, 3, 1, "Fertilizer (green areas)"),
            (sv, 3, 1, "Water consumption (purchased water)"),
            (sv, 3, 1, "Water waste / treatment"),
            (sv, 3, 2, "Capital goods (furniture / appliances)"),
            (sv, 3, 5, "Waste disposal"),
            (sv, 3, 7, "Student & employee commuting"),
            (sv, 3, 8, "Rented vehicles fuel (upstream leased assets)"),
            # ── Abu Qir (FY 2025-26 activity) ──
            (aq, 1, None, "Diesel (stationary + mobile)"),
            (aq, 1, None, "Gasoline 92 (mobile)"),
            (aq, 1, None, "Gasoline 95 (mobile)"),
            (aq, 1, None, "Refrigerants (R22 / R134a / R404A / R410A)"),
            (aq, 2, None, "Purchased electricity"),
            # ── Aswan South Valley (FY 2025-26 activity) ──
            (asw, 1, None, "Diesel generators (on-site)"),
            (asw, 1, None, "Gasoline vehicles"),
            (asw, 1, None, "Diesel vehicles"),
            (asw, 1, None, "R-404A fugitive (refrigeration)"),
            (asw, 1, None, "Other refrigerants (fugitive)"),
            (asw, 2, None, "Purchased electricity"),
            (asw, 3, 1, "Consumables — paper / envelopes / ink / toner / soap / tissues"),
            (asw, 3, 1, "Fertilizers"),
            (asw, 3, 1, "Water consumption"),
            (asw, 3, 2, "Capital goods (furniture / facilities)"),
            (asw, 3, 3, "Electricity T&D losses (fuel & energy related)"),
            (asw, 3, 4, "Upstream transportation (rental vehicles fuel)"),
            (asw, 3, 8, "Upstream leased assets (rented buildings elec / water)"),
        ]
        created = []
        for org, scope, cat, name in spec:
            obj, _ = InventorySource.objects.update_or_create(
                org_unit=org, scope=scope, scope3_category=cat, source_name=name,
                defaults={"is_active": True},
            )
            created.append(obj)
        return created

    # ── 5b ───────────────────────────────────────────────────────────────
    def _source_statuses(self, InventorySourceStatus, sources):
        """Mark covered (table + calc) vs declared for the relevant period.

        Rebuilds the status table from scratch — this command is the sole owner
        of InventorySourceStatus, so a clean rebuild guarantees no orphaned
        period-scoped rows survive a prior (incorrect) run.
        """
        from emissions.models import ReportingPeriod
        from dataschema.models import DataTable
        InventorySourceStatus.objects.all().delete()
        fy2324 = ReportingPeriod.objects.get(name="FY 2023-24")
        fy2526 = ReportingPeriod.objects.get(name="FY 2025-26")

        sv = {s.source_name: s for s in sources if s.org_unit.slug == "aastmt-smart-village"}
        aq = {s.source_name: s for s in sources if s.org_unit.slug == "aastmt-abu-qir"}
        asw = {s.source_name: s for s in sources if s.org_unit.slug == "aastmt-aswan-south-valley"}

        def table(module, name):
            return DataTable.objects.get(module__name=module, name=name)

        # (org_slug, source_name) -> (period, [linked tables], tier)
        covered_map = {
            ("aastmt-smart-village", "Purchased electricity"):
                (fy2324, [table("Smart Village — Carbon Footprint", "monthly_electricity")], 3),
            ("aastmt-smart-village", "District chilled water (purchased cooling)"):
                (fy2324, [table("Smart Village — Carbon Footprint", "monthly_chilled_water")], 3),
            ("aastmt-smart-village", "Water consumption (purchased water)"):
                (fy2324, [table("Smart Village — Carbon Footprint", "monthly_water")], 3),
            ("aastmt-abu-qir", "Purchased electricity"):
                (fy2526, [table("Abu Qir — Carbon Footprint", "monthly_electricity")], 3),
            ("aastmt-abu-qir", "Diesel (stationary + mobile)"):
                (fy2526, [table("Abu Qir — Carbon Footprint", "monthly_fuel")], 3),
            ("aastmt-abu-qir", "Gasoline 92 (mobile)"):
                (fy2526, [table("Abu Qir — Carbon Footprint", "monthly_fuel")], 3),
            ("aastmt-abu-qir", "Gasoline 95 (mobile)"):
                (fy2526, [table("Abu Qir — Carbon Footprint", "monthly_fuel")], 3),
            ("aastmt-aswan-south-valley", "Purchased electricity"):
                (fy2526, [table("South Valley — Carbon Footprint", "scope12_activity")], 3),
            ("aastmt-aswan-south-valley", "Diesel generators (on-site)"):
                (fy2526, [table("South Valley — Carbon Footprint", "scope12_activity")], 3),
            ("aastmt-aswan-south-valley", "Gasoline vehicles"):
                (fy2526, [table("South Valley — Carbon Footprint", "scope12_activity")], 3),
            ("aastmt-aswan-south-valley", "Diesel vehicles"):
                (fy2526, [table("South Valley — Carbon Footprint", "scope12_activity")], 3),
        }

        n = 0
        for src in sources:
            org = src.org_unit.slug
            period = fy2324 if org == "aastmt-smart-village" else fy2526
            key = (org, src.source_name)
            if key in covered_map:
                p, tables, tier = covered_map[key]
                st, _ = InventorySourceStatus.objects.update_or_create(
                    source=src, reporting_period=p,
                    defaults={"status": "covered", "data_quality_tier": tier},
                )
                st.linked_tables.set(tables)
            else:
                st, _ = InventorySourceStatus.objects.update_or_create(
                    source=src, reporting_period=period,
                    defaults={"status": "declared", "data_quality_tier": None},
                )
                st.linked_tables.clear()
            n += 1
        return n

    # ── 6 ────────────────────────────────────────────────────────────────
    def _coverage_goals(self, OrgUnit, SBTiTarget, CoverageGoal):
        aastmt = OrgUnit.objects.filter(slug="aastmt").first()
        t12 = SBTiTarget.objects.get(name="AASTMT Scope 1+2 Reduction (SBTi 1.5°C)")
        t3 = SBTiTarget.objects.get(name="AASTMT Scope 3 Reduction (SBTi near-term)")
        specs = [
            dict(name="Scope 1+2 Coverage", scope="1+2", pct=Decimal("100.00"),
                 tier=3, sbti=t12),
            dict(name="Scope 3 Coverage", scope="3", pct=Decimal("80.00"),
                 tier=4, sbti=t3),
        ]
        n = 0
        for s in specs:
            CoverageGoal.objects.update_or_create(
                org_unit=aastmt, name=s["name"],
                defaults=dict(scope=s["scope"], target_coverage_pct=s["pct"],
                              min_quality_tier=s["tier"],
                              completeness_definition="materiality_bounded",
                              target_year=2026, sbti_target=s["sbti"],
                              status="active"),
            )
            n += 1
        return n

    # ── 7 ────────────────────────────────────────────────────────────────
    def _coverage_actions(self, InventorySource, CoverageAction):
        def get(org_slug, source_name):
            return InventorySource.objects.get(org_unit__slug=org_slug, source_name=source_name)

        specs = [
            ("aastmt-abu-qir", "Refrigerants (R22 / R134a / R404A / R410A)",
             "improve_quality", "Wire GWP conversion (R-22=1810, R-404A=3922) into calculations."),
            ("aastmt-smart-village", "Diesel generators (on-site power)",
             "collect_data", "Collect monthly diesel generator consumption time-series."),
            ("aastmt-smart-village", "Diesel vehicles (owned/controlled)",
             "collect_data", "Collect monthly fleet diesel consumption time-series."),
            ("aastmt-smart-village", "Student & employee commuting",
             "collect_data", "Survey student + employee commuting (km / mode)."),
            ("aastmt-aswan-south-valley", "Purchased electricity",
             "collect_data", "Wire Aswan 700,000 kWh to EG_GRID_2024 calculation rule."),
            ("aastmt-aswan-south-valley", "Diesel vehicles",
             "collect_data", "Wire Aswan 125,500 L diesel to DEFRA_DIESEL calculation rule."),
            ("aastmt-smart-village", "FM200 fire suppression",
             "formalize_exclusion", "FM200 marked 'pending' in inventory — confirm or exclude."),
        ]
        n = 0
        for org, name, atype, notes in specs:
            src = get(org, name)
            CoverageAction.objects.get_or_create(
                source=src, action_type=atype, notes=notes,
                defaults={"status": "open"},
            )
            n += 1
        return n
