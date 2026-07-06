# emissions/management/commands/setup_carbon_app.py
# Carbon (emissions) APP self-setup: seeds emission factors, binds calculation
# rules to the platform's trusted data tables, and computes CO2e.
# The emissions app MAY import platform core; core never imports this app.
# Idempotent + additive. NO model/schema changes.
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from dataschema.models import DataTable, DataField
from emissions.models import EmissionFactor, CalculationRule


# Emission factors this app uses (Egypt context). Values are documented, editable later.
FACTORS = [
    # code, name, category, scope, factor_value, activity_unit, source
    ("EG_GRID_2024", "Egypt National Grid (Electricity)", "electricity", 2, "0.4584", "kWh",
     "Egypt national grid average (IFI/IEA-based)"),
    ("EG_WATER_2024", "Water Supply + Treatment (Egypt)", "water", 3, "0.3440", "m3",
     "Water supply + treatment (DEFRA-based proxy)"),
]

# Which table's activity field maps to which factor.
# (table_name, activity_field_name, date_field_name, factor_code, rule_name)
RULE_BINDINGS = [
    ("monthly_electricity", "total_kwh", "month", "EG_GRID_2024", "Electricity → CO2e"),
    ("monthly_water",       "total_m3",  "month", "EG_WATER_2024", "Water → CO2e"),
    # NOTE: monthly_chilled_water (TR) is intentionally NOT wired yet — the CO2e
    # methodology for district chilled water (TR) needs to be decided separately.
]


class Command(BaseCommand):
    help = "Carbon app setup: seed emission factors, bind calculation rules to trusted tables, compute CO2e."

    def add_arguments(self, parser):
        parser.add_argument('--recalculate', action='store_true',
                            help='Delete existing calculations for these rules and recompute.')

    def handle(self, *args, **options):
        # 1. Emission factors
        for code, name, category, scope, value, unit, source in FACTORS:
            ef, created = EmissionFactor.objects.get_or_create(
                code=code,
                defaults={
                    'name': name, 'category': category, 'scope': scope,
                    'factor_value': Decimal(value), 'factor_unit': 'kg CO2e',
                    'activity_unit': unit, 'source': source,
                    'valid_from': date(2023, 1, 1), 'is_active': True,
                },
            )
            self.stdout.write(f"  Factor {code}: {'created' if created else 'exists'} "
                              f"({value} kg CO2e/{unit}, scope {scope})")

        # 2. Calculation rules bound to the trusted data tables
        total_created = 0
        for table_name, activity_name, date_name, factor_code, rule_name in RULE_BINDINGS:
            table = DataTable.objects.filter(name=table_name, is_archived=False).first()
            if not table:
                self.stdout.write(self.style.WARNING(f"  SKIP: table '{table_name}' not found"))
                continue
            activity_field = DataField.objects.filter(data_table=table, name=activity_name).first()
            date_field = DataField.objects.filter(data_table=table, name=date_name).first()
            factor = EmissionFactor.objects.filter(code=factor_code).first()
            if not (activity_field and factor):
                self.stdout.write(self.style.WARNING(
                    f"  SKIP: missing field/factor for '{table_name}'"))
                continue

            rule, _ = CalculationRule.objects.get_or_create(
                data_table=table, activity_field=activity_field, emission_factor=factor,
                defaults={
                    'name': rule_name, 'date_field': date_field,
                    'rule_type': 'direct', 'is_active': True, 'auto_calculate': True,
                },
            )
            if rule.date_field_id != (date_field.id if date_field else None):
                rule.date_field = date_field
                rule.save(update_fields=['date_field'])

            created, skipped, errors = rule.calculate_for_table(
                recalculate=options['recalculate']
            )
            total_created += created
            self.stdout.write(f"  Rule '{rule_name}': created={created} skipped={skipped} errors={errors}")

        # 3. Summary
        from emissions.models import Calculation
        total = Calculation.objects.count()
        tonnes = sum(float(c.co2e_kg) for c in Calculation.objects.all()) / 1000.0
        self.stdout.write(self.style.SUCCESS(
            f"\nCarbon app ready. Calculations in system: {total}. "
            f"Total ≈ {tonnes:,.1f} tonnes CO2e (created {total_created} this run)."
        ))
