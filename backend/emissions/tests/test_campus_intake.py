"""CR-INT-01. Quoted files, intake writes, and no invented kilogram."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from accounts.models import ScopedRole, User
from emissions.campus_intake import (
    apply_template,
    assurance_status,
    coverage_board,
    enter_activity,
    file_activity_rows,
    intake_catalogue,
    market_kg,
    open_period_inventory_kg,
    record_assurance,
    record_contractual_factor,
    store_discovered_activity,
)
from emissions.models import Calculation, EmissionFactor, ReportingPeriod
from emissions.onboarding_o1 import evaluate_o1
from mdm.models import OrgUnit


def _factor(**kwargs):
    defaults = {
        "code": "TEST-FACTOR",
        "name": "Test factor",
        "category": "stationary_combustion",
        "scope": 1,
        "factor_value": Decimal("2.5"),
        "activity_unit": "litre",
        "source": "test double, not an AASTMT inventory factor",
        "valid_from": date(2023, 7, 1),
        "is_active": True,
    }
    defaults.update(kwargs)
    return EmissionFactor.objects.create(**defaults)


class CatalogueTests(TestCase):
    def test_leaves_quote_files_and_store_no_kilogram(self):
        catalogue = intake_catalogue()
        by_id = {row["id"]: row for row in catalogue["leaves"]}
        self.assertEqual(set(by_id), {"O2", "O3", "O4", "O5", "S2MB", "P1"})
        for row in by_id.values():
            self.assertEqual(row["outcome"], "b")
            self.assertFalse(row["passed"])
            self.assertIsNone(row["kilograms"])
        o2 = by_id["O2"]
        quantities = {row["quantity"] for row in o2["activity_rows"]}
        self.assertIn("700000", quantities)
        self.assertIn("25000", quantities)
        self.assertIn("125500", quantities)
        self.assertIn("3680", quantities)
        self.assertEqual(o2["tonnes_co2e"], "0")
        self.assertFalse(o2["waiting"]["exists"])
        self.assertEqual(o2["waiting"]["file"], "south_valley_inventory.csv")
        self.assertIn("south_valley_scope12_fy2526.csv", o2["discovered_files"])
        both = next(row for row in o2["exclusions"] if row["code"] == "diesel_stream_both")
        self.assertEqual(both["generators_l"], "25000")
        self.assertEqual(both["mobile_l"], "125500")

        o3 = by_id["O3"]
        self.assertTrue(any(row["code"] == "month_blank" and row["month"] == "2026-06-01" for row in o3["exclusions"]))
        self.assertTrue(any(row["code"] == "diesel_stream_unlabelled" for row in o3["exclusions"]))
        self.assertNotIn("0", {row["quantity"] for row in o3["activity_rows"] if row["label"] == "2026-06-01"})
        self.assertEqual(o3["waiting"]["file"], "abu_qir_inventory.csv")
        self.assertFalse(o3["waiting"]["exists"])

        o4 = by_id["O4"]
        self.assertEqual(o4["activity_rows"], [])
        self.assertEqual(o4["waiting"]["file"], "new_alamein_inventory.csv")
        self.assertIn("campus", o4["waiting"]["columns"])
        self.assertEqual(o4["tonnes_co2e"], "0")

        o5 = by_id["O5"]
        self.assertEqual(o5["activity_rows"][0]["quantity"], "73.0")
        self.assertEqual(o5["activity_rows"][0]["unit"], "ton")
        self.assertEqual(o5["waiting"]["file"], "smart_village_waste_factor.csv")
        self.assertFalse(o5["waiting"]["exists"])
        self.assertIsNone(o5["kilograms"])

        self.assertEqual(by_id["S2MB"]["method"], "absent")
        self.assertIsNone(by_id["S2MB"]["tonnes_co2e"])
        self.assertFalse(by_id["P1"]["not_assured_met"])
        blob = str(catalogue)
        for banned in ("405271", "5269592", "1254223.105920", "19456.800000", "1239599.320800"):
            self.assertNotIn(banned, blob)

    def test_evaluate_o1_stays_unassured(self):
        result = evaluate_o1(
            periods=[{
                "id": 1, "name": "FY 2023-24", "status": "open",
                "start_date": "2023-07-01", "end_date": "2024-06-30",
                "period_type": "annual", "organizational_boundary": 1,
            }],
            boundaries=[{
                "id": 1, "name": "AASTMT", "consolidation_approach": "operational_control",
            }],
            sources=[],
            statuses=[],
            summary={
                "total_calculations": 1,
                "by_scope": {"2": {"total_co2e_kg": "1239599.320800", "scope2_method": "location-based"}},
            },
            factors=[],
            goals=[],
        )
        assured = next(row for row in result["checks"] if row["code"] == "not_assured")
        self.assertFalse(assured["met"])
        quoted = next(row for row in result["checks"] if row["code"] == "summary_kg")
        self.assertEqual(quoted["kg"], "1239599.320800")

    def test_file_rows_keep_blank_months_and_unlabelled_diesel(self):
        rows = file_activity_rows()
        electricity = next(row for row in rows if row["source_name"] == "South Valley electricity")
        self.assertEqual(electricity["quantity"], "700000")
        self.assertEqual(electricity["unit"], "kWh")
        self.assertEqual(electricity["source_file"], "south_valley_scope12_fy2526.csv")
        self.assertEqual(electricity["period_role"], "locked")
        diesel = [row for row in rows if row["source_name"] == "South Valley diesel"]
        self.assertEqual({row["quantity"] for row in diesel}, {"25000", "125500"})
        self.assertTrue(all(row["in_scope_total"] == "false" and row["reason"] == "diesel_stream_both" for row in diesel))
        self.assertFalse(any(
            row["month"] == "2026-06-01" and row["source_name"] == "Abu Qir electricity" for row in rows
        ))
        abu_diesel = [row for row in rows if row["source_name"] == "Abu Qir diesel"]
        self.assertGreater(len(abu_diesel), 0)
        self.assertTrue(all(row["stream"] == "" and row["reason"] == "diesel_stream_unlabelled" for row in abu_diesel))
        self.assertNotIn("0", {row["quantity"] for row in rows})
        waste = next(row for row in rows if row["source_name"] == "Smart Village waste disposal")
        self.assertEqual(waste["quantity"], "73.0")
        self.assertEqual(waste["unit"], "ton")
        self.assertEqual(waste["period_role"], "open")
        self.assertFalse(any(row["campus"] == "New Alamein" for row in rows))
        self.assertFalse(any("scope3_fy2526" in row["source_file"] for row in rows))


class MarketAndAssuranceTests(TestCase):
    def test_market_path_uses_a_test_double_and_rejects_a_grid_copy(self):
        self.assertIsNone(market_kg("10", "0.4584", "0.4584", source="Egypt grid", same_row=False))
        self.assertIsNone(market_kg("10", "0.1000", "0.4584", source="Egypt residual mix", same_row=False))
        self.assertIsNone(market_kg("10", "0.1000", "0.4584", source="test double", same_row=True))
        kg = market_kg("10", "0.1000", "0.4584", source="test double, not an AASTMT inventory factor", same_row=False)
        self.assertEqual(kg, Decimal("1.0000"))
        grid = _factor(code="EG-GRID-FIXTURE", scope=2, category="electricity", factor_value=Decimal("0.4584"), activity_unit="kWh", source="Test EG grid")
        copy = _factor(code="EG-GRID-COPY", scope=2, category="electricity", factor_value=Decimal("0.4584"), activity_unit="kWh", source="copy of grid")
        with self.assertRaises(ValidationError):
            record_contractual_factor(contractual=copy, grid=grid)
        residual = _factor(
            code="EG-RESIDUAL", scope=2, category="electricity",
            factor_value=Decimal("0.2"), activity_unit="kWh", source="Egypt residual mix",
        )
        with self.assertRaises(ValidationError):
            record_contractual_factor(contractual=residual, grid=grid)
        double = _factor(
            code="TEST_CONTRACT_DOUBLE", scope=2, category="electricity",
            factor_value=Decimal("0.1000"), activity_unit="kWh",
            source="test double, not an AASTMT inventory factor",
        )
        stored = record_contractual_factor(contractual=double, grid=grid)
        self.assertNotEqual(stored.emission_factor_id, stored.grid_factor_id)
        self.assertFalse(Calculation.objects.filter(scope2_method="market_based").exists())

    def test_p1_stays_unmet_until_five_fields(self):
        period = ReportingPeriod.objects.create(
            name="FY 2023-24", start_date=date(2023, 7, 1), end_date=date(2024, 6, 30),
            status="open", period_type="annual",
        )
        partial = record_assurance(reporting_period=period, fields={
            "assurer_name": "Example VVB",
            "engagement_type": "limited",
            "standard": "ISO 14064-3",
            "opinion_date": date(2024, 7, 1),
        })
        self.assertFalse(partial["not_assured_met"])
        self.assertIn("statement_id", partial["missing"])
        self.assertFalse(partial["passed"])
        complete = record_assurance(reporting_period=period, fields={
            "assurer_name": "Example VVB",
            "engagement_type": "limited",
            "standard": "ISO 14064-3",
            "opinion_date": date(2024, 7, 1),
            "statement_id": "STMT-1",
        })
        self.assertTrue(complete["not_assured_met"])
        self.assertFalse(complete["passed"])
        early = assurance_status({
            "assurer_name": "Example VVB",
            "engagement_type": "limited",
            "standard": "ISO 14064-3",
            "opinion_date": date(2024, 1, 1),
            "statement_id": "STMT-1",
        }, period.end_date)
        self.assertFalse(early["not_assured_met"])


@override_settings(EMISSIONS_AUTO_CALC=False)
class IntakeWriteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="ahmed", password="AdminPa_132")
        self.period = ReportingPeriod.objects.create(
            name="FY 2023-24", start_date=date(2023, 7, 1), end_date=date(2024, 6, 30),
            status="open", period_type="annual",
        )
        root = OrgUnit.objects.create(name="AASTMT intake", slug="intake-root", org_type="company")
        self.org = OrgUnit.objects.create(
            name="South Valley", slug="sv-intake", parent=root, org_type="department",
        )
        self.other = OrgUnit.objects.create(
            name="Abu Qir", slug="aq-intake", parent=root, org_type="department",
        )
        self.factor = _factor()

    def _row(self, **overrides):
        item = {
            "campus": "South Valley",
            "source_name": "South Valley diesel",
            "scope": "1",
            "activity_unit": "litre",
            "quantity": "10",
            "stream": "generators",
            "period_start": "2023-07-01",
            "period_end": "2024-06-30",
        }
        item.update(overrides)
        return item

    def test_open_period_row_calculates_from_the_fixture_factor(self):
        result = apply_template(leaf_id="O2", rows=[self._row()], user=self.user, factor=self.factor)
        self.assertTrue(result["written"], result)
        self.assertEqual(Decimal(result["kilograms"][0]), Decimal("25.0"))
        self.assertEqual(ReportingPeriod.objects.filter(status="open").count(), 1)
        calc = Calculation.objects.get()
        self.assertEqual(calc.emission_factor_id, self.factor.id)
        self.assertIn("test double", self.factor.source)

    def test_fy2526_upload_is_not_posted_onto_the_open_period(self):
        result = apply_template(
            leaf_id="O2",
            rows=[self._row(period_start="2025-07-01", period_end="2026-06-30", quantity="700000")],
            user=self.user,
            factor=self.factor,
        )
        self.assertFalse(result["written"])
        self.assertIsNone(result["kilograms"])
        self.assertEqual(result["exclusions"][0]["code"], "period_mismatch")
        self.assertFalse(Calculation.objects.exists())

    def test_restate_archives_and_appends(self):
        first = apply_template(leaf_id="O2", rows=[self._row(quantity="10")], user=self.user, factor=self.factor)
        second = apply_template(leaf_id="O2", rows=[self._row(quantity="12")], user=self.user, factor=self.factor)
        self.assertEqual(second["archived_ids"], [first["current"][0]["id"]])
        self.assertEqual(second["current"][0]["values"]["quantity"], "12")
        from dataschema.models import DataRow
        old = DataRow.objects.get(pk=first["current"][0]["id"])
        self.assertTrue(old.is_archived)
        self.assertEqual(old.values["quantity"], "10")

    def test_both_diesel_streams_do_not_calculate(self):
        result = apply_template(
            leaf_id="O2",
            rows=[self._row(stream="generators"), self._row(stream="fleet", quantity="4")],
            user=self.user,
            factor=self.factor,
        )
        self.assertFalse(result["written"])
        self.assertIsNone(result["kilograms"])

    def test_campus_owner_cannot_write_another_campus(self):
        group, _ = Group.objects.get_or_create(name="dataowners_group")
        owner = User.objects.create_user(username="data.southvalley", password="AASTcarbonPa_132")
        ScopedRole.objects.create(user=owner, group=group, org_unit=self.org, module=None, is_active=True)
        own = apply_template(leaf_id="O2", rows=[self._row()], user=owner, factor=self.factor)
        self.assertTrue(own["written"], own)
        other = apply_template(
            leaf_id="O3",
            rows=[self._row(campus="Abu Qir", source_name="Abu Qir diesel")],
            user=owner,
            factor=self.factor,
        )
        self.assertFalse(other["written"])
        self.assertIn("org scope", other["errors"])

    def test_waste_without_a_tonne_factor_stores_no_kilogram(self):
        kg_factor = _factor(
            code="WASTE-KG-DOUBLE", scope=3, category="waste",
            activity_unit="kg", factor_value=Decimal("0.446"),
        )
        rows = [{
            "source_name": "Smart Village waste disposal",
            "quantity_tonne": "73.0",
            "treatment": "unspecified",
            "period_start": "2023-07-01",
            "period_end": "2024-06-30",
        }]
        result = apply_template(leaf_id="O5", rows=rows, user=self.user, factor=kg_factor)
        self.assertTrue(result["written"])
        self.assertIsNone(result["kilograms"])
        tonne = _factor(
            code="WASTE-TONNE-DOUBLE", scope=3, category="waste",
            activity_unit="tonne", factor_value=Decimal("1.5"),
            source="test double, not an AASTMT inventory factor",
        )
        again = apply_template(leaf_id="O5", rows=rows, user=self.user, factor=tonne)
        self.assertEqual(Decimal(again["kilograms"][0]), Decimal("109.5"))

    def test_coverage_is_a_stream_list_and_not_a_percent(self):
        from django.conf import settings

        self.assertFalse(settings.EMISSIONS_AUTO_CALC)
        board = coverage_board(self.user)
        self.assertFalse(board["coverage_complete"])
        self.assertNotIn("pct", board)
        self.assertEqual(board["open_period"]["id"], self.period.id)
        by_name = {row["source_name"]: row for row in board["streams"]}
        self.assertIn("Smart Village electricity", by_name)
        self.assertIn("Smart Village diesel", by_name)
        self.assertIn("South Valley electricity", by_name)
        self.assertIn("South Valley diesel", by_name)
        self.assertIn("Abu Qir electricity", by_name)
        self.assertIn("Abu Qir diesel", by_name)
        self.assertIn("New Alamein electricity", by_name)
        self.assertIn("New Alamein diesel", by_name)
        self.assertIn("Smart Village waste disposal", by_name)
        self.assertNotIn("fleet 5161", str(board).lower())
        south = by_name["South Valley electricity"]
        self.assertEqual(south["status"], "missing")
        self.assertIsNone(south["inventory_kg"])
        self.assertIn("south_valley_scope12_fy2526.csv", south["later_year_files"])
        abu = by_name["Abu Qir electricity"]
        self.assertIn("abu_qir_monthly_electricity_fy2526.csv", abu["later_year_files"])
        self.assertEqual(by_name["New Alamein diesel"]["status"], "missing")
        self.assertIsNone(by_name["Smart Village waste disposal"]["inventory_kg"])
        blob = str(board)
        for banned in (
            "405271", "5269592", "1254223.105920", "19456.800000",
            "1239599.320800", "8040.000000", "700000",
        ):
            self.assertNotIn(banned, blob)

    def test_entered_stream_quotes_only_its_own_calculation(self):
        result = apply_template(leaf_id="O2", rows=[self._row()], user=self.user, factor=self.factor)
        self.assertTrue(result["written"], result)
        board = coverage_board(self.user)
        by_name = {row["source_name"]: row for row in board["streams"]}
        diesel = by_name["South Valley diesel"]
        self.assertEqual(diesel["status"], "entered")
        self.assertEqual(Decimal(diesel["inventory_kg"]), Decimal("25.000000"))
        self.assertEqual(by_name["South Valley electricity"]["status"], "missing")
        self.assertIsNone(by_name["South Valley electricity"]["inventory_kg"])
        from emissions.services import MyDataService
        from django.contrib.auth.models import Group
        from accounts.models import ScopedRole

        group, _ = Group.objects.get_or_create(name="dataowners_group")
        owner = User.objects.create_user(username="data.southvalley.board", password="AASTcarbonPa_132")
        ScopedRole.objects.create(user=owner, group=group, org_unit=self.org, module=None, is_active=True)
        mine = MyDataService.get_my_data(owner)
        self.assertIsNotNone(mine)
        self.assertIn("Campus intake South Valley diesel", [row["name"] for row in mine["modules"]])

    def test_waste_row_waits_for_a_factor_and_stores_no_kilogram(self):
        OrgUnit.objects.create(
            name="Smart Village", slug="sv-waste-intake", parent=self.org.parent, org_type="department",
        )
        result = enter_activity(
            user=self.user,
            fields={"source_name": "Smart Village waste disposal", "quantity": "73.0"},
        )
        self.assertTrue(result["written"], result)
        self.assertIsNone(result["kilograms"])
        self.assertEqual(result["exclusions"][0]["code"], "awaiting_factor")
        from dataschema.models import DataRow

        stored = DataRow.objects.get(is_archived=False)
        self.assertEqual(stored.values["quantity_tonne"], "73.0")
        self.assertFalse(Calculation.objects.filter(data_row=stored).exists())
        waste = next(row for row in coverage_board(self.user)["streams"] if row["source_name"] == "Smart Village waste disposal")
        self.assertEqual(waste["status"], "awaiting_factor")
        self.assertIsNone(waste["inventory_kg"])

    def test_market_method_without_a_contract_stays_out(self):
        result = enter_activity(
            user=self.user,
            fields={
                "source_name": "South Valley electricity",
                "quantity": "10",
                "method": "market_based",
            },
        )
        self.assertFalse(result["written"])
        self.assertIsNone(result["kilograms"])
        self.assertEqual(result["exclusions"][0]["code"], "market_absent")
        self.assertFalse(Calculation.objects.exists())

    def test_later_year_rows_do_not_change_open_period_o1_kilograms(self):
        from django.conf import settings
        from dataschema.models import DataRow

        self.assertFalse(settings.EMISSIONS_AUTO_CALC)
        OrgUnit.objects.create(
            name="Smart Village", slug="sv-o1-intake", parent=self.org.parent, org_type="department",
        )
        OrgUnit.objects.create(
            name="New Alamein", slug="na-intake", parent=self.org.parent, org_type="department",
        )
        locked = ReportingPeriod.objects.create(
            name="FY 2025-26", start_date=date(2025, 7, 1), end_date=date(2026, 6, 30),
            status="locked", period_type="annual",
        )
        electricity = _factor(
            code="EG-GRID-O1-DOUBLE", scope=2, category="electricity",
            factor_value=Decimal("0.4584"), activity_unit="kWh", source="Test EG grid",
        )
        diesel = _factor(
            code="DIESEL-O1-DOUBLE", scope=1, category="stationary_combustion",
            factor_value=Decimal("2.68"), activity_unit="litre",
            source="test double, not an AASTMT inventory factor",
        )
        power = apply_template(leaf_id="O1", rows=[{
            "campus": "Smart Village",
            "source_name": "Smart Village electricity",
            "scope": "2",
            "activity_unit": "kWh",
            "quantity": "2704187",
            "stream": "location-based",
            "period_start": "2023-07-01",
            "period_end": "2024-06-30",
        }], user=self.user, factor=electricity)
        fuel = apply_template(leaf_id="O1", rows=[{
            "campus": "Smart Village",
            "source_name": "Smart Village diesel",
            "scope": "1",
            "activity_unit": "litre",
            "quantity": "3000",
            "stream": "generators",
            "period_start": "2023-07-01",
            "period_end": "2024-06-30",
        }], user=self.user, factor=diesel)
        self.assertTrue(power["written"], power)
        self.assertTrue(fuel["written"], fuel)
        before = open_period_inventory_kg()
        self.assertEqual(Decimal(before["2"]), Decimal("1239599.320800"))
        self.assertEqual(Decimal(before["1"]), Decimal("8040.000000"))
        o1_values = {
            row.id: dict(row.values)
            for row in DataRow.objects.filter(
                is_archived=False,
                values__source_name__in=["Smart Village electricity", "Smart Village diesel"],
            )
        }
        calc_ids = set(Calculation.objects.values_list("id", flat=True))
        stored = store_discovered_activity(user=self.user)
        self.assertTrue(stored["written"], stored)
        self.assertIsNone(stored["kilograms"])
        self.assertFalse(Calculation.objects.filter(reporting_period=locked).exists())
        self.assertEqual(set(Calculation.objects.values_list("id", flat=True)), calc_ids)
        after = open_period_inventory_kg()
        self.assertEqual(after, before)
        locked.refresh_from_db()
        self.period.refresh_from_db()
        self.assertEqual(locked.status, "locked")
        self.assertEqual(self.period.status, "open")
        self.assertEqual(ReportingPeriod.objects.filter(status="open").count(), 1)
        for row_id, values in o1_values.items():
            current = DataRow.objects.get(pk=row_id)
            self.assertFalse(current.is_archived)
            self.assertEqual(current.values, values)
        self.assertFalse(DataRow.objects.filter(
            values__month="2026-06-01", values__source_name="Abu Qir electricity",
        ).exists())
        self.assertTrue(DataRow.objects.filter(
            values__month="2026-06-01", values__source_name="Abu Qir diesel",
        ).exists())
        self.assertFalse(DataRow.objects.filter(values__quantity="0").exists())
        abu_diesel = list(DataRow.objects.filter(is_archived=False, values__source_name="Abu Qir diesel"))
        self.assertGreater(len(abu_diesel), 0)
        self.assertTrue(all((row.values.get("stream") or "") == "" for row in abu_diesel))
        self.assertTrue(all(row.values.get("reason") == "diesel_stream_unlabelled" for row in abu_diesel))
        self.assertFalse(Calculation.objects.filter(data_row__in=abu_diesel).exists())
        south_power = DataRow.objects.get(is_archived=False, values__source_name="South Valley electricity")
        self.assertEqual(south_power.values["quantity"], "700000")
        self.assertEqual(south_power.values["unit"], "kWh")
        self.assertEqual(south_power.values["source_file"], "south_valley_scope12_fy2526.csv")
        self.assertEqual(south_power.values["period_start"], "2025-07-01")
        waste = DataRow.objects.get(is_archived=False, values__source_name="Smart Village waste disposal")
        self.assertEqual(waste.values["quantity"], "73.0")
        self.assertEqual(waste.values["unit"], "ton")
        self.assertEqual(waste.values["period_start"], "2023-07-01")
        self.assertFalse(Calculation.objects.filter(data_row=waste).exists())
        board = coverage_board(self.user)
        by_period = {row["role"]: row for row in board["periods"]}
        open_streams = {row["source_name"]: row for row in by_period["open"]["streams"]}
        locked_streams = {row["source_name"]: row for row in by_period["locked"]["streams"]}
        self.assertEqual(open_streams["South Valley electricity"]["status"], "missing")
        self.assertIsNone(open_streams["South Valley electricity"]["inventory_kg"])
        self.assertEqual(open_streams["Abu Qir electricity"]["status"], "missing")
        self.assertEqual(open_streams["Abu Qir diesel"]["status"], "missing")
        self.assertEqual(open_streams["New Alamein electricity"]["status"], "missing")
        self.assertEqual(open_streams["New Alamein diesel"]["status"], "missing")
        self.assertEqual(open_streams["Smart Village electricity"]["status"], "entered")
        self.assertEqual(Decimal(open_streams["Smart Village electricity"]["inventory_kg"]), Decimal("1239599.320800"))
        self.assertEqual(Decimal(open_streams["Smart Village diesel"]["inventory_kg"]), Decimal("8040.000000"))
        self.assertEqual(open_streams["Smart Village waste disposal"]["status"], "awaiting_factor")
        self.assertIsNone(open_streams["Smart Village waste disposal"]["inventory_kg"])
        self.assertEqual(locked_streams["South Valley electricity"]["status"], "entered")
        self.assertIsNone(locked_streams["South Valley electricity"]["inventory_kg"])
        self.assertFalse(locked_streams["South Valley electricity"]["in_scope_total"])
        self.assertEqual(locked_streams["South Valley diesel"]["status"], "entered")
        self.assertEqual(locked_streams["South Valley diesel"]["reason"], "diesel_stream_both")
        self.assertIsNone(locked_streams["South Valley diesel"]["inventory_kg"])
        self.assertEqual(locked_streams["Abu Qir electricity"]["status"], "entered")
        self.assertIsNone(locked_streams["Abu Qir electricity"]["inventory_kg"])
        self.assertEqual(locked_streams["Abu Qir diesel"]["status"], "entered")
        self.assertEqual(locked_streams["Abu Qir diesel"]["reason"], "diesel_stream_unlabelled")
        self.assertIsNone(locked_streams["Abu Qir diesel"]["inventory_kg"])
        self.assertEqual(locked_streams["New Alamein electricity"]["status"], "missing")
        self.assertEqual(locked_streams["New Alamein diesel"]["status"], "missing")
        self.assertEqual(locked_streams["Smart Village waste disposal"]["status"], "missing")
        row_count = DataRow.objects.count()
        again = store_discovered_activity(user=self.user)
        self.assertFalse(again["written"])
        self.assertEqual(DataRow.objects.count(), row_count)
        self.assertEqual(open_period_inventory_kg(), before)
        assured = evaluate_o1(
            periods=[{
                "id": self.period.id, "name": "FY 2023-24", "status": "open",
                "start_date": "2023-07-01", "end_date": "2024-06-30",
                "period_type": "annual", "organizational_boundary": 1,
            }],
            boundaries=[{
                "id": 1, "name": "AASTMT", "consolidation_approach": "operational_control",
            }],
            sources=[],
            statuses=[],
            summary={"total_calculations": 1, "by_scope": {"2": {"total_co2e_kg": "1239599.320800"}}},
            factors=[],
            goals=[],
        )
        self.assertFalse(next(row for row in assured["checks"] if row["code"] == "not_assured")["met"])

    def test_campus_owner_records_only_their_campus(self):
        from dataschema.models import DataRow

        ReportingPeriod.objects.create(
            name="FY 2025-26", start_date=date(2025, 7, 1), end_date=date(2026, 6, 30),
            status="locked", period_type="annual",
        )
        OrgUnit.objects.create(
            name="Smart Village", slug="sv-owner-intake", parent=self.org.parent, org_type="department",
        )
        group, _ = Group.objects.get_or_create(name="dataowners_group")
        owner = User.objects.create_user(username="data.southvalley.files", password="AASTcarbonPa_132")
        ScopedRole.objects.create(user=owner, group=group, org_unit=self.org, module=None, is_active=True)
        stored = store_discovered_activity(user=owner)
        campuses = {row["campus"] for row in stored["current"]}
        self.assertEqual(campuses, {"South Valley"})
        self.assertFalse(DataRow.objects.filter(values__campus="Abu Qir").exists())
        self.assertFalse(DataRow.objects.filter(values__source_name="Smart Village waste disposal").exists())
        self.assertIsNone(stored["kilograms"])
        self.assertEqual(ReportingPeriod.objects.get(name="FY 2025-26").status, "locked")
