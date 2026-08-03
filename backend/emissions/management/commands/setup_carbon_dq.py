# emissions/management/commands/setup_carbon_dq.py
# Carbon (emissions) APP observability setup: profiles the app's trusted data tables,
# seeds sensible DQ rules, runs them, and rolls quality up into the catalog.
# The emissions app MAY import platform core (dataschema, dq, catalog); core never imports this app.
# Idempotent for rules (get_or_create). NO model/schema changes.
from django.core.management.base import BaseCommand

from dataschema.models import DataTable, DataField
from dq.models import DQRule, TableProfile
from dq.services import profile_table, run_dq
from catalog.models import AssetProfile


# (table_name, date_field, activity_field)
TABLES = [
    # AASTMT legacy tables (month/total_* field names)
    ("monthly_electricity", "month", "total_kwh"),
    ("monthly_water", "month", "total_m3"),
    ("monthly_chilled_water", "month", "total_tr"),
    # AASTMT 2026 variant tables (period_month/consumption_* field names)
    ("monthly_electricity", "period_month", "consumption_kwh"),
    ("monthly_chilled_water", "period_month", "consumption_tr"),
    ("monthly_water", "period_month", "consumption_m3"),
    # Comprehensive 2026 seed tables
    ("electricity_consumption", "period_month", "kwh"),
    ("water_consumption", "period_month", "m3"),
    ("chilled_water", "period_month", "tr_hours"),
    ("fuel_consumption", "period_month", "diesel_liters"),
    ("refrigerant_usage", "period_month", "r134a_kg"),
    ("employee_commute", "period_month", "car_km"),
    ("fleet_fuel_log", "period_month", "gasoline_liters"),
    ("generator_fuel_log", "period_month", "diesel_liters"),
    ("paper_consumption", "period_month", "paper_reams"),
    ("vessel_fuel_log", "period_month", "diesel_liters"),
]


class Command(BaseCommand):
    help = "Carbon app observability: profile trusted tables, seed + run DQ rules, roll up to catalog."

    def handle(self, *args, **options):
        for table_name, date_name, activity_name in TABLES:
            table = DataTable.objects.filter(name=table_name, is_archived=False).first()
            if not table:
                self.stdout.write(self.style.WARNING(f"  SKIP: table '{table_name}' not found"))
                continue
            date_field = DataField.objects.filter(data_table=table, name=date_name).first()
            activity_field = DataField.objects.filter(data_table=table, name=activity_name).first()

            # 1. Seed DQ rules (idempotent on data_field + rule_type)
            if date_field:
                DQRule.objects.get_or_create(
                    data_field=date_field, rule_type='not_null',
                    defaults={'scope': 'field', 'data_table': table, 'severity': 'error', 'is_active': True},
                )
            if activity_field:
                DQRule.objects.get_or_create(
                    data_field=activity_field, rule_type='not_null',
                    defaults={'scope': 'field', 'data_table': table, 'severity': 'error', 'is_active': True},
                )
                DQRule.objects.get_or_create(
                    data_field=activity_field, rule_type='range',
                    defaults={'scope': 'field', 'data_table': table, 'severity': 'warn',
                              'params': {'min': 0}, 'is_active': True},
                )

            # 2. Profile the table, then 3. run DQ (rolls quality into catalog AssetProfile)
            prof = profile_table(table.id)
            dq = run_dq(table.id)

            ap = AssetProfile.objects.filter(data_table=table).first()
            self.stdout.write(
                f"  {table_name}: completeness={prof['completeness_pct']}% "
                f"rules_run={dq['rules_run']} "
                f"quality={getattr(ap, 'quality_status', 'n/a')}/{getattr(ap, 'quality_score', 'n/a')}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nObservability ready. DQ rules: {DQRule.objects.count()}, "
            f"table profiles: {TableProfile.objects.count()}."
        ))
