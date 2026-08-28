"""
core/management/commands/seed_carbon_raw.py

Seed the Carbon domain layer strictly from the 10 generated CSVs in raw/csv/
(see raw/SEED_SPEC.md). This is the reseed step after `flush_carbon.py`.

Scope rule (agreed, no fabrication):
  - Seed ONLY data present in the source CSVs.
  - `existence` == present            -> quantity seeded
  - `existence` == not_applicable     -> quantity empty
  - `existence` == pending            -> quantity empty
  - Blank months (e.g. Abu Qir Jun 2026) are already absent from the CSVs.

Idempotent: uses get_or_create / update_or_create throughout. Safe to re-run.
Does NOT touch Users/Groups or other apps.
"""
import csv
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

CSV_DIR = Path(settings.BASE_DIR).parent / "raw" / "csv"


def _row_hash(values):
    normalized = {str(k).lower(): v for k, v in (values or {}).items()}
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                   default=str).encode("utf-8")
    ).hexdigest()


class Command(BaseCommand):
    help = "Seed Carbon data from raw/csv (9 campuses, 3 data products, ~156 rows, factors, calcs)."

    def handle(self, *args, **options):
        from mdm.models import OrgUnit, ReferenceSet
        from core.models import Module
        from dataschema.models import DataTable, DataRow
        from emissions.models import (
            EmissionFactor, GWP, ReportingPeriod,
            OrganizationalBoundary, BaseYear, CalculationRule,
        )

        with transaction.atomic():
            summary = {}

            # ── 1. OrgUnits ──────────────────────────────────────────────
            root = self._org(OrgUnit, "AASTMT", "university", None)
            campuses = {}
            for row in self._csv("campuses.csv"):
                c = self._org(OrgUnit, row["name"], "campus", root,
                              code=row["slug"], description=row["full_name"])
                campuses[row["name"]] = c
            sv = campuses["Giza Smart Village"]
            abu_qir = campuses["Abu Qir"]
            south_valley = campuses["Aswan South Valley"]

            # Smart Village departments (FY23-24 data owners)
            sv_depts = {}
            for d in ["Facilities & Utilities", "Energy / Utilities",
                      "Transportation / Fleet", "Procurement", "Campus Services"]:
                sv_depts[d] = self._org(OrgUnit, d, "department", sv)
            summary["OrgUnits"] = OrgUnit.objects.count()

            # ── 2. ReferenceSets + values ───────────────────────────────
            self._refset(ReferenceSet, "campuses",
                         [(r["slug"], r["name"], r["full_name"]) for r in self._csv("campuses.csv")])
            self._refset(ReferenceSet, "buildings", [("401", "Building 401", ""), ("2401", "Building 2401", "")])
            self._refset(ReferenceSet, "fuel_types",
                         [(c, c, "") for c in ["natural_gas", "diesel", "gasoline", "lpg", "r22", "r134a", "r404a", "r410a"]])
            self._refset(ReferenceSet, "refrigerants",
                         [(c, c, "") for c in ["R-134a", "R-410A", "R-407C", "R-404A", "R-22", "other"]])
            self._refset(ReferenceSet, "fire_suppressants",
                         [(c, l, "") for c, l in [
                             ("dry_powder", "طفاية بودرة"), ("co2", "طفاية CO2"),
                             ("dry_chemical", "مسحوق كيماوي جاف"), ("fm200", "FM200")]])
            self._refset(ReferenceSet, "ghg_categories",
                         [(c, c, "") for c in [
                             "stationary_combustion", "mobile_combustion", "fugitive",
                             "purchased_energy", "consumables", "capital_goods",
                             "fertilizers", "fuel_energy", "water_waste", "commuting",
                             "waste", "business_travel", "leased_assets"]])
            self._refset(ReferenceSet, "units",
                         [(c, c, "") for c in ["kwh", "m3", "tr", "l", "kg", "m2", "km", "ton", "unit", "tissue", "paper"]])
            self._refset(ReferenceSet, "existence",
                         [(c, c, "") for c in ["present", "not_applicable", "pending"]])

            # ── 3. Modules (Data Products) + Tables + Fields ────────────
            # A data product is an org-owned GROUPING of related tables (the
            # DB "schema/namespace" analog) — NOT one table per product. One
            # product per campus with data; each bundles that campus's
            # activity tables. Authoritative GHG scope comes from the emission
            # factor at calc time (Module.scope is advisory only).
            refsets = {s.name: s for s in ReferenceSet.objects.all()}
            self.M = Module; self.T = DataTable
            tables = {}

            # ── Smart Village — Carbon Footprint ──────────────────────────
            mod_sv = self._module(Module, "Smart Village — Carbon Footprint", 2, sv,
                                  description="Smart Village campus activity data: electricity, "
                                              "chilled water, water, and the FY 2023-24 GHG inventory "
                                              "(spans Scope 1/2/3).")
            tables["sv_electricity"] = self._table(
                DataTable, mod_sv, "monthly_electricity", "Monthly Electricity (kWh)",
                "Smart Village monthly electricity — buildings 401 + 2401.",
                [("month", "Month", "date", True, 1, None),
                 ("building_401_kwh", "Building 401 (kWh)", "number", False, 2, None),
                 ("building_2401_kwh", "Building 2401 (kWh)", "number", False, 3, None),
                 ("total_kwh", "Total (kWh)", "number", False, 4, None)])
            tables["sv_chilled"] = self._table(
                DataTable, mod_sv, "monthly_chilled_water", "Monthly Chilled Water (TR)",
                "Smart Village chilled water — meters 2401-1 + 2401-2.",
                [("month", "Month", "date", True, 1, None),
                 ("meter_2401_1_tr", "Meter 2401-1 (TR)", "number", False, 2, None),
                 ("meter_2401_2_tr", "Meter 2401-2 (TR)", "number", False, 3, None),
                 ("total_tr", "Total (TR)", "number", False, 4, None)])
            tables["sv_water"] = self._table(
                DataTable, mod_sv, "monthly_water", "Monthly Water (m³)",
                "Smart Village monthly water — buildings 401 + 2401.",
                [("month", "Month", "date", True, 1, None),
                 ("building_401_m3", "Building 401 (m³)", "number", False, 2, None),
                 ("building_2401_m3", "Building 2401 (m³)", "number", False, 3, None),
                 ("total_m3", "Total (m³)", "number", False, 4, None)])
            tables["sv_inventory"] = self._table(
                DataTable, mod_sv, "ghg_inventory", "GHG Inventory (FY 2023-24)",
                "Smart Village GHG inventory — all scopes, per existence status.",
                [("scope", "Scope", "string", True, 1, None),
                 ("category", "Category", "string", False, 2, None),
                 ("source_of_emission", "Source of Emission", "string", False, 3, None),
                 ("activity_data", "Activity Data", "string", False, 4, None),
                 ("description_ar", "Description (AR)", "text", False, 5, None),
                 ("existence", "Existence", "select", False, 6, "existence"),
                 ("unit", "Unit", "string", False, 7, None),
                 ("quantity", "Quantity", "number", False, 8, None)])

            # ── Abu Qir — Carbon Footprint ────────────────────────────────
            mod_aq = self._module(Module, "Abu Qir — Carbon Footprint", 2, abu_qir,
                                  description="Abu Qir campus activity data: electricity, fuel, "
                                              "and the refrigerant inventory (spans Scope 1/2).")
            tables["abuqir_electricity"] = self._table(
                DataTable, mod_aq, "monthly_electricity", "Monthly Electricity (kWh)",
                "Abu Qir monthly electricity (total campus).",
                [("month", "Month", "date", True, 1, None),
                 ("total_kwh", "Total (kWh)", "number", False, 2, None)])
            tables["abuqir_fuel"] = self._table(
                DataTable, mod_aq, "monthly_fuel", "Monthly Fuel (L)",
                "Abu Qir monthly fuel — gasoline 92/95 + diesel.",
                [("month", "Month", "date", True, 1, None),
                 ("gasoline_92_l", "Gasoline 92 (L)", "number", False, 2, None),
                 ("gasoline_95_l", "Gasoline 95 (L)", "number", False, 3, None),
                 ("diesel_l", "Diesel (L)", "number", False, 4, None)])
            tables["refrigerants"] = self._table(
                DataTable, mod_aq, "refrigerants", "Refrigerant Inventory (FY 2025-26)",
                "Abu Qir refrigerant cylinder inventory.",
                [("campus", "Campus", "select", True, 1, "campuses"),
                 ("refrigerant", "Refrigerant", "select", False, 2, "refrigerants"),
                 ("cylinders_count", "Cylinders Count", "number", False, 3, None),
                 ("notes", "Notes", "text", False, 4, None)])

            # ── South Valley — Carbon Footprint ───────────────────────────
            mod_av = self._module(Module, "South Valley — Carbon Footprint", 1, south_valley,
                                  description="Aswan South Valley campus activity data: Scope 1/2 "
                                              "and Scope 3 activity.")
            tables["sv_scope12"] = self._table(
                DataTable, mod_av, "scope12_activity", "Scope 1 & 2 Activity (FY 2025-26)",
                "Aswan South Valley scope 1 + 2 activity data.",
                [("scope", "Scope", "string", True, 1, None),
                 ("category", "Category", "string", False, 2, None),
                 ("source", "Source", "string", False, 3, None),
                 ("activity_data", "Activity Data", "string", False, 4, None),
                 ("unit", "Unit", "string", False, 5, None),
                 ("quantity", "Quantity", "number", False, 6, None)])
            tables["sv_scope3"] = self._table(
                DataTable, mod_av, "scope3_activity", "Scope 3 Activity (FY 2025-26)",
                "Aswan South Valley scope 3 activity data.",
                [("category", "Category", "string", True, 1, None),
                 ("activity_data", "Activity Data", "string", False, 2, None),
                 ("unit", "Unit", "string", False, 3, None),
                 ("quantity", "Quantity", "number", False, 4, None)])

            # ── 4. DataRows ─────────────────────────────────────────────
            row_total = 0
            row_total += self._ingest(tables["sv_electricity"], "smart_village_monthly_electricity.csv",
                                      num=["building_401_kwh", "building_2401_kwh", "total_kwh"])
            row_total += self._ingest(tables["sv_chilled"], "smart_village_monthly_chilled_water.csv",
                                      num=["meter_2401_1_tr", "meter_2401_2_tr", "total_tr"])
            row_total += self._ingest(tables["sv_water"], "smart_village_monthly_water.csv",
                                      num=["building_401_m3", "building_2401_m3", "total_m3"])
            row_total += self._ingest(tables["sv_inventory"], "smart_village_inventory_fy2324.csv",
                                      num=["quantity"])
            row_total += self._ingest(tables["abuqir_electricity"], "abu_qir_monthly_electricity_fy2526.csv",
                                      num=["total_kwh"])
            row_total += self._ingest(tables["abuqir_fuel"], "abu_qir_fuel_fy2526.csv",
                                      num=["gasoline_92_l", "gasoline_95_l", "diesel_l"])
            row_total += self._ingest(tables["sv_scope12"], "south_valley_scope12_fy2526.csv",
                                      num=["quantity"])
            row_total += self._ingest(tables["sv_scope3"], "south_valley_scope3_fy2526.csv",
                                      num=["quantity"])
            row_total += self._ingest(tables["refrigerants"], "refrigerants_fy2526.csv",
                                      num=["cylinders_count"], ints=["cylinders_count"])
            summary["DataRows"] = row_total

            # ── 5. EmissionFactors + GWP ────────────────────────────────
            self._factors(EmissionFactor)
            self._gwp(GWP)

            # ── 6. ReportingPeriods + boundaries + base year ────────────
            boundary_sv = self._boundary(OrganizationalBoundary,
                                         "Smart Village Operational Control",
                                         [sv] + list(sv_depts.values()))
            boundary_fy26 = self._boundary(OrganizationalBoundary,
                                           "AASTMT FY 2025-26 Operational Control",
                                           [abu_qir, south_valley])
            fy2324 = self._period(ReportingPeriod, "FY 2023-24",
                                  date(2023, 7, 1), date(2024, 6, 30),
                                  boundary_sv, is_baseline=True)
            fy2526 = self._period(ReportingPeriod, "FY 2025-26",
                                  date(2025, 7, 1), date(2026, 6, 30),
                                  boundary_fy26, is_baseline=False)
            BaseYear.objects.update_or_create(
                year=2024,
                defaults={"reporting_period": fy2324, "recalculation_policy": "significant_only",
                          "description": "Smart Village FY 2023-24 baseline."},
            )

            # ── 7. CalculationRules + compute ───────────────────────────
            calc_created = self._rules(CalculationRule, tables, fy2324, fy2526)
            summary["Calculations (new)"] = calc_created

        self.stdout.write(self.style.SUCCESS("\nCarbon raw seed complete."))
        for k, v in summary.items():
            self.stdout.write(f"  {k}: {v}")

    # ── helpers ──────────────────────────────────────────────────────────

    def _csv(self, name):
        # utf-8-sig strips the UTF-8 BOM that export_csv.py writes on every file.
        with open(CSV_DIR / name, newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def _org(model, name, org_type, parent, code="", description=""):
        # slug is globally unique on OrgUnit; build it hierarchically
        # (parent.slug + slugified name) to avoid empty-slug collisions.
        from django.utils.text import slugify
        slug = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
        obj, _ = model.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "org_type": org_type, "parent": parent,
                      "code": code or name, "description": description},
        )
        return obj

    @staticmethod
    def _refset(model, name, values):
        from mdm.models import ReferenceValue
        rs, _ = model.objects.get_or_create(
            name=name,
            defaults={"description": f"Seeded reference set: {name}",
                      "lifecycle_state": "active", "is_active": True},
        )
        for i, (code, label, desc) in enumerate(values):
            ReferenceValue.objects.update_or_create(
                reference_set=rs, code=code,
                defaults={"label": label or code, "description": desc, "sort_order": i, "is_active": True},
            )
        return rs

    @staticmethod
    def _module(model, name, scope, org, description=""):
        obj, _ = model.objects.get_or_create(
            name=name,
            defaults={"scope": scope, "org_unit": org, "description": description,
                      "domain_attributes": {"carbon": {"scope": scope}}},
        )
        return obj

    def _table(self, model, module, name, title, description, fields):
        from dataschema.models import DataField
        tbl, _ = model.objects.get_or_create(
            module=module, name=name,
            defaults={"title": title, "description": description},
        )
        for (fname, label, ftype, required, order, refset_name) in fields:
            kwargs = {"label": label, "type": ftype, "required": required, "order": order}
            if refset_name:
                from mdm.models import ReferenceSet
                kwargs["reference_set"] = ReferenceSet.objects.get(name=refset_name)
            DataField.objects.get_or_create(data_table=tbl, name=fname, defaults=kwargs)
        return tbl

    def _ingest(self, table, csv_name, num=(), ints=()):
        from dataschema.models import DataRow
        created = 0
        for row in self._csv(csv_name):
            values = {}
            for k, v in row.items():
                if k in num:
                    values[k] = float(v) if v not in ("", "-", " ") else None
                elif k in ints:
                    values[k] = int(float(v)) if v not in ("", "-", " ") else None
                else:
                    values[k] = "" if v == "-" else (v or "")
            # skip fully-empty rows (safety)
            if not any(v not in (None, "") for v in values.values()):
                continue
            DataRow.objects.create(data_table=table, values=values, row_hash=_row_hash(values))
            created += 1
        return created

    @staticmethod
    def _factors(model):
        from decimal import Decimal
        specs = [
            # code, name, category, scope, value, activity_unit, source, subcategory
            ("EG_GRID_2024", "Egypt National Grid (Electricity)", "electricity", 2, "0.4584", "kWh",
             "Egypt national grid average (IFI/IEA-based)", ""),
            ("EG_WATER_2024", "Water Supply + Treatment (Egypt)", "water", 3, "0.3440", "m3",
             "Water supply + treatment (DEFRA-based proxy)", ""),
            ("CHILLED_WATER_COP3.5", "District Chilled Water (COP 3.5)", "electricity", 2, "0.4606", "TR·h",
             "3.51685 / 3.5 * 0.4584 kg CO2e per TR·h", "District cooling"),
            ("DEFRA_DIESEL", "Diesel (DEFRA 2024)", "stationary_combustion", 1, "2.51", "L",
             "DEFRA 2024, diesel (100% mineral)", "Diesel"),
            ("DEFRA_GASOLINE", "Gasoline (DEFRA 2024)", "mobile_combustion", 1, "2.19", "L",
             "DEFRA 2024, petrol (100% mineral)", "Gasoline"),
            # Distinct code so gasoline-95 rows don't collide with gasoline-92 on the
            # (data_row, emission_factor) dedup in CalculationRule.calculate_for_table.
            ("DEFRA_GASOLINE_95", "Gasoline 95 (DEFRA 2024)", "mobile_combustion", 1, "2.19", "L",
             "DEFRA 2024, petrol 95 octane (100% mineral)", "Gasoline 95"),
            ("DEFRA_NATURAL_GAS", "Natural Gas (DEFRA 2024)", "stationary_combustion", 1, "2.02", "m3",
             "DEFRA 2024, natural gas (gross CV)", "Natural Gas"),
            ("DEFRA_LPG", "LPG (DEFRA 2024)", "stationary_combustion", 1, "1.52", "kg",
             "DEFRA 2024, LPG (gross CV)", "LPG"),
        ]
        for code, name, category, scope, value, unit, source, sub in specs:
            model.objects.update_or_create(
                code=code,
                defaults={
                    "name": name, "category": category, "scope": scope,
                    "factor_value": Decimal(value), "factor_unit": "kg CO2e",
                    "activity_unit": unit, "source": source, "subcategory": sub,
                    "valid_from": date(2023, 1, 1), "is_active": True,
                    "tags": [code.lower()],
                },
            )

    @staticmethod
    def _gwp(model):
        from decimal import Decimal
        gases = [
            ("Carbon Dioxide", "CO2", "1", "124-38-9"),
            ("R-22", "R-22", "1810", ""),
            ("R-134a", "R-134a", "1430", ""),
            ("R-404A", "R-404A", "3922", ""),
            ("R-410A", "R-410A", "2088", ""),
            ("R-407C", "R-407C", "1774", ""),
            ("Sulfur Hexafluoride", "SF6", "23500", ""),
            ("Nitrous Oxide", "N2O", "265", "10024-97-2"),
        ]
        for name, formula, gwp, cas in gases:
            model.objects.update_or_create(
                gas_formula=formula,
                defaults={"gas_name": name, "gwp_ar6_100yr": Decimal(gwp), "cas_number": cas},
            )

    @staticmethod
    def _boundary(model, name, org_units):
        obj, _ = model.objects.get_or_create(
            name=name,
            defaults={"consolidation_approach": "operational_control", "is_active": True},
        )
        obj.included_org_units.set(org_units)
        return obj

    @staticmethod
    def _period(model, name, start, end, boundary, is_baseline):
        obj, _ = model.objects.update_or_create(
            name=name,
            defaults={
                "start_date": start, "end_date": end, "period_type": "annual",
                "status": "open", "is_baseline": is_baseline,
                "organizational_boundary": boundary,
            },
        )
        return obj

    def _rules(self, rule_model, tables, fy2324, fy2526):
        from dataschema.models import DataField
        from emissions.models import EmissionFactor

        def field(table, name):
            return DataField.objects.get(data_table=table, name=name)

        def factor(code):
            return EmissionFactor.objects.get(code=code)

        bindings = [
            ("sv_electricity", "total_kwh", "month", "EG_GRID_2024", "Electricity → CO2e", fy2324),
            ("sv_water", "total_m3", "month", "EG_WATER_2024", "Water → CO2e", fy2324),
            ("sv_chilled", "total_tr", "month", "CHILLED_WATER_COP3.5", "Chilled Water (TR) → CO2e", fy2324),
            ("abuqir_electricity", "total_kwh", "month", "EG_GRID_2024", "Electricity → CO2e", fy2526),
            ("abuqir_fuel", "diesel_l", "month", "DEFRA_DIESEL", "Diesel → CO2e", fy2526),
            ("abuqir_fuel", "gasoline_92_l", "month", "DEFRA_GASOLINE", "Gasoline 92 → CO2e", fy2526),
            ("abuqir_fuel", "gasoline_95_l", "month", "DEFRA_GASOLINE_95", "Gasoline 95 → CO2e", fy2526),
        ]

        total_created = 0
        for key, activity, date_name, factor_code, rule_name, period in bindings:
            table = tables[key]
            rule, _ = rule_model.objects.get_or_create(
                data_table=table,
                activity_field=field(table, activity),
                emission_factor=factor(factor_code),
                defaults={
                    "name": rule_name,
                    "date_field": field(table, date_name),
                    "rule_type": "direct", "is_active": True, "auto_calculate": True,
                    "scope2_calculation_method": "location_based",
                },
            )
            created, skipped, errors = rule.calculate_for_table(reporting_period=period)
            total_created += created
            self.stdout.write(f"  Rule '{rule_name}': created={created} skipped={skipped} errors={errors}")

        # South Valley scope 1+2 is a DENORMALIZED table (single `quantity`
        # column + `activity_data` discriminator), so it needs one selector
        # rule instead of one-rule-per-fuel. Activities without a mapped
        # factor (R-404A / Other refrigerants) fall through to an INACTIVE
        # sentinel factor and are skipped — they stay `declared` until their
        # GWP factors are wired.
        if "sv_scope12" in tables:
            sv12 = tables["sv_scope12"]
            sentinel, _ = EmissionFactor.objects.get_or_create(
                code="UNMAPPED_NO_FACTOR",
                defaults=dict(
                    name="Unmapped activity — skip (no factor)",
                    category="stationary_combustion", scope=1,
                    factor_value=Decimal("0"), factor_unit="kg CO2e",
                    activity_unit="unit", source="internal",
                    valid_from=date(2020, 1, 1), is_active=False,
                ),
            )
            sv_rule, _ = rule_model.objects.get_or_create(
                data_table=sv12,
                activity_field=field(sv12, "quantity"),
                factor_selector_field=field(sv12, "activity_data"),
                defaults=dict(
                    name="Scope 1+2 activity → CO2e (South Valley, FY 2025-26)",
                    emission_factor=sentinel,
                    factor_selector_mapping={
                        "Electricity": "EG_GRID_2024",
                        "Gasoline": "DEFRA_GASOLINE",
                        "Diesel": "DEFRA_DIESEL",
                    },
                    rule_type="direct", unit_conversion_factor=Decimal("1"),
                    scope2_calculation_method="location_based",
                    data_quality_tier=3,
                    is_active=True, auto_calculate=True,
                ),
            )
            created, skipped, errors = sv_rule.calculate_for_table(reporting_period=fy2526)
            total_created += created
            self.stdout.write(
                f"  Rule 'Scope 1+2 activity → CO2e (South Valley)': "
                f"created={created} skipped={skipped} errors={errors}"
            )

        return total_created
