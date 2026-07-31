#!/usr/bin/env python
"""
Carbon Platform — Master Seed Script (2024–2026)
==================================================
Seeds ALL entities for a fully functional Carbon platform demo.
Idempotent — safe to run multiple times.

Usage:
  python seed_all.py              # seed everything (idempotent)
  python seed_all.py --reset      # delete all carbon data first, then re-seed
  python seed_all.py --years 2025 # seed only 2025
"""

import os, sys, random
from datetime import date
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django; django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.text import slugify
from accounts.models import ScopedRole
from core.models import Module
from mdm.models import OrgUnit
from catalog.models import AssetProfile
from dataschema.models import DataTable, DataField, DataRow
from emissions.models import (
    ReportingPeriod, EmissionFactor, GWP,
    CalculationRule, SBTiTarget, Calculation,
)
from dq.services import profile_table, run_dq

User = get_user_model()

# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════

DEFAULT_YEARS = (2024, 2025, 2026)

def banner(text):
    print(f"\n{'='*70}\n  {text}\n{'='*70}")

# ══════════════════════════════════════════
# SEED DATA CONSTANTS (values are fixed — do not change)
# ══════════════════════════════════════════

ORG_UNIT_TREE = {
    'AASTMT': {
        'Smart Village': {
            'Buildings': None,
            'Transport': None,
            'Facilities': None,
        },
        'Alexandria': None,
        'Port Said': None,
    }
}

MODULE_SPEC = {
    'name': 'Carbon Footprint',
    'description': 'GHG emissions tracking -- AASTMT Smart Village campus',
    'org_unit_name': 'Smart Village',
    'scope': 1,
}
TABLE_SPECS = [
    {
        'name': 'electricity_consumption', 'title': 'Electricity Consumption',
        'description': 'Monthly electricity (kWh) -- Buildings 401 + 2401',
        'fields': [
            ('kwh', 'kWh', 'number', True),
            ('period_month', 'Month', 'date', True),
            ('meter_id', 'Meter ID', 'string', False),
            ('notes', 'Notes', 'text', False),
        ],
    },
    {
        'name': 'water_consumption', 'title': 'Water Consumption',
        'description': 'Monthly water consumption (m3)',
        'fields': [
            ('m3', 'm3', 'number', True),
            ('period_month', 'Month', 'date', True),
            ('notes', 'Notes', 'text', False),
        ],
    },
    {
        'name': 'chilled_water', 'title': 'Chilled Water',
        'description': 'Monthly chilled water (TR-hours)',
        'fields': [
            ('tr_hours', 'TR-hours', 'number', True),
            ('period_month', 'Month', 'date', True),
            ('notes', 'Notes', 'text', False),
        ],
    },
    {
        'name': 'fuel_consumption', 'title': 'Fuel Consumption',
        'description': 'Monthly fuel -- generators & fleet',
        'fields': [
            ('diesel_liters', 'Diesel (L)', 'number', False),
            ('gasoline_liters', 'Gasoline (L)', 'number', False),
            ('natural_gas_m3', 'Natural Gas (m3)', 'number', False),
            ('period_month', 'Month', 'date', True),
            ('source', 'Source', 'string', False),
        ],
    },
    {
        'name': 'refrigerant_usage', 'title': 'Refrigerant Usage',
        'description': 'Annual refrigerant leakage (kg)',
        'fields': [
            ('r134a_kg', 'R-134a (kg)', 'number', False),
            ('r410a_kg', 'R-410A (kg)', 'number', False),
            ('r407c_kg', 'R-407C (kg)', 'number', False),
            ('period_month', 'Month', 'date', True),
            ('notes', 'Notes', 'text', False),
        ],
    },
    {
        'name': 'employee_commute', 'title': 'Employee Commute',
        'description': 'Monthly employee commute data (Scope 3)',
        'fields': [
            ('car_km', 'Car (km)', 'number', False),
            ('bus_km', 'Bus (km)', 'number', False),
            ('employees_count', 'Employees', 'number', False),
            ('period_month', 'Month', 'date', True),
        ],
    },
]

EMISSION_FACTOR_SPECS = [
    # code, name, category, scope, factor_value, activity_unit, factor_unit, source
    # Scope 1 - Direct combustion
    ('NG_IPCC_2021', 'Natural Gas (IPCC 2021)', 'stationary_combustion', 1,
     Decimal('2.0'), 'm3', 'kg CO2e', 'IPCC 2021 Guidelines'),
    ('DIESEL_IPCC', 'Diesel (IPCC)', 'stationary_combustion', 1,
     Decimal('2.68'), 'L', 'kg CO2e', 'IPCC 2021'),
    ('GASOLINE_IPCC', 'Gasoline (IPCC)', 'mobile_combustion', 1,
     Decimal('2.31'), 'L', 'kg CO2e', 'IPCC 2021'),
    # Scope 1 - Refrigerants
    ('R134A_AR6', 'R-134a (AR6 GWP)', 'fugitive', 1,
     Decimal('1430'), 'kg', 'kg CO2e', 'IPCC AR6'),
    ('R410A_AR6', 'R-410A (AR6 GWP)', 'fugitive', 1,
     Decimal('2088'), 'kg', 'kg CO2e', 'IPCC AR6'),
    ('R407C_AR6', 'R-407C (AR6 GWP)', 'fugitive', 1,
     Decimal('1774'), 'kg', 'kg CO2e', 'IPCC AR6'),
    # Scope 2 - Purchased energy
    ('EG_GRID_2024', 'Egyptian Grid 2024', 'electricity', 2,
     Decimal('0.495'), 'kWh', 'kg CO2e', 'EEHC 2024 Annual Report'),
    ('EG_GRID_2025', 'Egyptian Grid 2025', 'electricity', 2,
     Decimal('0.477'), 'kWh', 'kg CO2e', 'EEHC 2025 Projection'),
    ('CHILLED_WATER', 'District Chilled Water', 'electricity', 2,
     Decimal('0.15'), 'TR-hr', 'kg CO2e', 'ASHRAE Guidelines'),
    # Scope 3 - Value chain
    ('WATER_EG', 'Water Supply & Treatment (Egypt)', 'water', 3,
     Decimal('0.344'), 'm3', 'kg CO2e', 'EEAA 2024'),
    ('COMMUTE_CAR', 'Employee Commute - Car', 'transport', 3,
     Decimal('0.21'), 'km', 'kg CO2e', 'DEFRA 2024'),
    ('COMMUTE_BUS', 'Employee Commute - Bus', 'transport', 3,
     Decimal('0.089'), 'km', 'kg CO2e', 'DEFRA 2024'),
]

GWP_SPECS = [
    ('Carbon Dioxide', 'CO2', 1, 1),
    ('Methane (fossil)', 'CH4', 28, Decimal('29.8')),
    ('Methane (biogenic)', 'CH4_biogenic', 25, Decimal('27.0')),
    ('Nitrous Oxide', 'N2O', 265, 273),
    ('HFC-134a', 'CH2FCF3', 1300, 1430),
    ('HFC-410A', 'R-410A', 1924, 2088),
    ('HFC-407C', 'R-407C', 1624, 1774),
    ('Sulfur Hexafluoride', 'SF6', 23500, 24300),
    ('Perfluoromethane', 'CF4', 6630, 7380),
]

# Actual AASTMT 2024 data where available; realistic projections for 2025-2026
ELECTRICITY_KWH = {
    2024: [232689, 199364, 194412, 183368, 160356, 213498, 306387, 245000, 255000, 260000, 235000, 230000],
    2025: [225000, 195000, 190000, 180000, 165000, 220000, 310000, 250000, 258000, 262000, 238000, 232000],
    2026: [220000, 190000, 185000, 175000, 160000, 215000, 305000, None, None, None, None, None],
}
WATER_M3 = {
    2024: [850, 850, 822, 824, 825, 826, 830, 840, 835, 845, 860, 870],
    2025: [840, 845, 820, 825, 830, 835, 845, 850, 840, 850, 865, 875],
    2026: [835, 840, 818, 822, 828, 832, 842, None, None, None, None, None],
}
CHILLED_WATER_TR = {
    2024: [58388, 56704, 68983, 116680, 188931, 234964, 313266, 280000, 240000, 200000, 120000, 65000],
    2025: [55000, 53000, 65000, 115000, 185000, 230000, 310000, 275000, 235000, 195000, 115000, 60000],
    2026: [52000, 50000, 62000, 110000, 180000, 228000, 305000, None, None, None, None, None],
}
FUEL_DIESEL_L = {
    2024: [800, 750, 820, 780, 760, 850, 900, 880, 860, 840, 810, 790],
    2025: [780, 740, 800, 760, 750, 840, 880, 860, 850, 830, 800, 780],
    2026: [770, 730, 790, 750, 740, 830, 870, None, None, None, None, None],
}
EMPLOYEES = {2024: 3200, 2025: 3350, 2026: 3450}

SBTI_SPECS = [
    ('AASTMT 50% by 2030', 2020, 2030, 'absolute', '1+2', Decimal('50'), 'committed',
     '50% absolute reduction in Scope 1+2 emissions by 2030 from 2020 baseline', 'AASTMT'),
    ('Smart Village Net Zero 2040', 2024, 2040, 'absolute', '1+2+3', Decimal('90'), 'draft',
     'Net zero for Smart Village campus', 'Smart Village'),
    ('Transport Fleet Electrification 2035', 2024, 2035, 'absolute', '1', Decimal('60'), 'draft',
     'Electrify 60% of fleet by 2035', 'Transport'),
    ('Grid Factor Decarbonization 2030', 2024, 2030, 'absolute', '2', Decimal('25'), 'committed',
     'Reduction driven by Egypt grid renewable mix improvement', 'Smart Village'),
]

# ══════════════════════════════════════════
# SeedBuilder — chainable seed orchestrator
# ══════════════════════════════════════════

class SeedBuilder:
    """
    Builder-pattern seed orchestrator.

    Every .with_*() step is chainable, idempotent, and auto-resolves its
    dependencies: e.g. .with_calculation_rules() will seed modules/tables and
    emission factors first if they have not been seeded yet.

    Usage:
        builder = SeedBuilder().with_org_units().with_users()
        builder.run()          # executes stacked steps in dependency order
        builder.print_summary()

        # or the standard full pipeline:
        builder = SeedBuilder.from_args()
        builder.run()
        builder.print_summary()
    """

    # step -> steps that must complete first (dependency order)
    _DEPENDENCIES = {
        'with_users': ('with_org_units',),
        'with_modules_and_tables': ('with_org_units',),
        'with_activity_data': ('with_modules_and_tables',),
        'with_calculation_rules': ('with_modules_and_tables', 'with_emission_factors'),
        'with_sbti_targets': ('with_org_units',),
        'with_calculations': ('with_calculation_rules',),
        'with_data_quality': ('with_modules_and_tables',),
    }

    # the full pipeline, in canonical order (used when no steps are stacked)
    _DEFAULT_STEPS = (
        'with_org_units',
        'with_users',
        'with_modules_and_tables',
        'with_periods',
        'with_emission_factors',
        'with_gwp',
        'with_activity_data',
        'with_calculation_rules',
        'with_sbti_targets',
        'with_calculations',
        'with_data_quality',
    )

    def __init__(self, years=DEFAULT_YEARS, reset=False):
        self.years = tuple(years)
        self.reset = reset
        # internal state (private — filled by the with_*() steps)
        self._org_units = {}
        self._users = []
        self._tables = {}
        self._periods = {}
        self._factors = {}
        # bookkeeping
        self._steps = []    # explicit chain accumulated via with_*() calls
        self._done = set()  # steps already executed (idempotency guard)

    # ──────────────────────────────────────────────
    # Foundation
    # ──────────────────────────────────────────────

    def with_org_units(self):
        """Seed the org unit tree. Returns self (chainable)."""
        if 'with_org_units' in self._done:
            return self
        banner("ORG UNITS")
        def _recurse(tree, parent=None):
            result = {}
            for name, children in tree.items():
                ou, created = OrgUnit.objects.get_or_create(
                    name=name,
                    defaults={'parent': parent, 'slug': slugify(name), 'is_active': True}
                )
                if not created and parent and not ou.parent:
                    ou.parent = parent; ou.save()
                result[name] = ou
                print(f"  {'+' if created else chr(183)} {ou.name}")
                if children:
                    result.update(_recurse(children, ou))
            return result
        self._org_units = _recurse(ORG_UNIT_TREE)
        print(f"  -> {len(self._org_units)} org units")
        self._steps.append('with_org_units')
        self._done.add('with_org_units')
        return self

    def with_users(self):
        """Seed users + scoped roles. Auto-resolves with_org_units()."""
        if 'with_users' in self._done:
            return self
        self.with_org_units()
        banner("USERS")
        USERS = [
            ('admin', 'admin123', 'admin@aastmt.edu.eg', True, True, 'admins_group', None),
            ('dataowner1', 'owner123', 'dataowner1@aastmt.edu.eg', False, False, 'dataowners_group', 'Smart Village'),
            ('analyst1', 'analyst123', 'analyst1@aastmt.edu.eg', False, False, 'analysts_group', None),
            ('viewer1', 'viewer123', 'viewer1@aastmt.edu.eg', False, False, 'viewers_group', None),
            ('transport_officer', 'transport123', 'transport@aastmt.edu.eg', False, False, 'dataowners_group', 'Smart Village'),
        ]
        for username, password, email, is_su, is_staff, role_name, ou_name in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'is_superuser': is_su, 'is_staff': is_staff}
            )
            user.email = email; user.is_superuser = is_su; user.is_staff = is_staff
            user.set_password(password); user.save()
            group, _ = Group.objects.get_or_create(name=role_name)
            org_unit = self._org_units.get(ou_name) if ou_name else None
            ScopedRole.objects.get_or_create(
                user=user, group=group, org_unit=org_unit, module=None,
                defaults={'is_active': True}
            )
            scope = f"({ou_name})" if ou_name else "(global)"
            print(f"  {'+' if created else chr(183)} {username:22} {role_name:18} {scope}")
        self._steps.append('with_users')
        self._done.add('with_users')
        return self

    def with_modules_and_tables(self):
        """Seed module + data tables. Auto-resolves with_org_units()."""
        if 'with_modules_and_tables' in self._done:
            return self
        self.with_org_units()
        banner("MODULES & DATA TABLES")
        ou = self._org_units.get(MODULE_SPEC['org_unit_name'])
        module, created = Module.objects.get_or_create(
            name=MODULE_SPEC['name'],
            defaults={
                'description': MODULE_SPEC['description'],
                'scope': MODULE_SPEC['scope'],
                'org_unit': ou,
            }
        )
        print(f"  {'+' if created else chr(183)} Module: {module.name} (Scope {module.scope})")

        tables = {}
        for ts in TABLE_SPECS:
            dt, created = DataTable.objects.get_or_create(
                module=module, name=ts['name'],
                defaults={'title': ts['title'], 'description': ts.get('description', '')}
            )
            fields = []
            for i, (fname, flabel, ftype, freq) in enumerate(ts['fields']):
                df, _ = DataField.objects.get_or_create(
                    data_table=dt, name=fname,
                    defaults={'label': flabel, 'type': ftype, 'required': freq, 'order': i}
                )
                fields.append(df)
            tables[ts['name']] = (dt, fields)
            print(f"    {'+' if created else chr(183)} Table: {ts['title']} ({len(fields)} fields)")
        self._tables = tables
        self._steps.append('with_modules_and_tables')
        self._done.add('with_modules_and_tables')
        return self

    # ──────────────────────────────────────────────
    # Reference data
    # ──────────────────────────────────────────────

    def with_periods(self):
        """Seed reporting periods for self.years."""
        if 'with_periods' in self._done:
            return self
        banner("REPORTING PERIODS")
        periods = {}
        for yr in self.years:
            p, created = ReportingPeriod.objects.get_or_create(
                name=str(yr),
                defaults={
                    'period_type': 'annual',
                    'start_date': date(yr, 1, 1),
                    'end_date': date(yr, 12, 31),
                    'status': 'verified' if yr < 2026 else 'open',
                }
            )
            periods[yr] = p
            print(f"  {'+' if created else chr(183)} {yr}: {p.get_status_display()} ({p.start_date} -> {p.end_date})")
        self._periods = periods
        self._steps.append('with_periods')
        self._done.add('with_periods')
        return self

    def with_emission_factors(self):
        """Seed emission factors from EMISSION_FACTOR_SPECS."""
        if 'with_emission_factors' in self._done:
            return self
        banner("EMISSION FACTORS")
        factors = {}
        for code, name, category, scope, fval, aunit, funit, source in EMISSION_FACTOR_SPECS:
            ef, created = EmissionFactor.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'category': category,
                    'scope': scope,
                    'factor_value': fval,
                    'activity_unit': aunit,
                    'factor_unit': funit,
                    'source': source,
                    'valid_from': date(2024, 1, 1),
                    'country': 'Egypt',
                    'country_code': 'EG',
                    'is_active': True,
                    'tags': [code.lower(), category],
                }
            )
            factors[code] = ef
            print(f"  {'+' if created else chr(183)} {code:18} scope={scope} {fval:10} {funit}/{aunit}")
        self._factors = factors
        self._steps.append('with_emission_factors')
        self._done.add('with_emission_factors')
        return self

    def with_gwp(self):
        """Seed GWP reference values from GWP_SPECS."""
        if 'with_gwp' in self._done:
            return self
        banner("GWP REFERENCE VALUES")
        for gas_name, formula, ar5, ar6 in GWP_SPECS:
            gwp, created = GWP.objects.get_or_create(
                gas_formula=formula,
                defaults={
                    'gas_name': gas_name,
                    'gwp_ar5_100yr': ar5,
                    'gwp_ar6_100yr': ar6,
                }
            )
            print(f"  {'+' if created else chr(183)} {formula:12} GWP(AR6)={ar6}")
        self._steps.append('with_gwp')
        self._done.add('with_gwp')
        return self

    # ──────────────────────────────────────────────
    # Activity data
    # ──────────────────────────────────────────────

    def with_activity_data(self):
        """Seed activity data rows. Auto-resolves with_modules_and_tables()."""
        if 'with_activity_data' in self._done:
            return self
        self.with_modules_and_tables()
        banner("ACTIVITY DATA")
        total_rows = 0
        for yr in self.years:
            yr_total = 0
            for month_idx in range(12):
                month_val = ELECTRICITY_KWH.get(yr, [None]*12)[month_idx]
                if month_val is None:
                    continue
                month_date = date(yr, month_idx + 1, 1)
                month_str = str(month_date)

                # Electricity
                vals = {'kwh': month_val, 'period_month': month_str}
                if not DataRow.objects.filter(data_table=self._tables['electricity_consumption'][0], values__period_month=month_str).exists():
                    DataRow.objects.create(data_table=self._tables['electricity_consumption'][0], values=vals)
                    yr_total += 1

                # Water
                water_val = WATER_M3.get(yr, [None]*12)[month_idx]
                if water_val is not None:
                    vals_w = {'m3': water_val, 'period_month': month_str}
                    if not DataRow.objects.filter(data_table=self._tables['water_consumption'][0], values__period_month=month_str).exists():
                        DataRow.objects.create(data_table=self._tables['water_consumption'][0], values=vals_w)
                        yr_total += 1

                # Chilled water
                chilled_val = CHILLED_WATER_TR.get(yr, [None]*12)[month_idx]
                if chilled_val is not None:
                    vals_c = {'tr_hours': chilled_val, 'period_month': month_str}
                    if not DataRow.objects.filter(data_table=self._tables['chilled_water'][0], values__period_month=month_str).exists():
                        DataRow.objects.create(data_table=self._tables['chilled_water'][0], values=vals_c)
                        yr_total += 1

                # Fuel
                diesel_val = FUEL_DIESEL_L.get(yr, [None]*12)[month_idx]
                if diesel_val:
                    vals_f = {
                        'diesel_liters': diesel_val,
                        'gasoline_liters': int(diesel_val * 0.25),
                        'natural_gas_m3': int(diesel_val * 0.15),
                        'period_month': month_str, 'source': 'generator'
                    }
                    if not DataRow.objects.filter(data_table=self._tables['fuel_consumption'][0], values__period_month=month_str).exists():
                        DataRow.objects.create(data_table=self._tables['fuel_consumption'][0], values=vals_f)
                        yr_total += 1

            # Yearly rows: refrigerants + commute
            yr_date = date(yr, 7, 1)
            yr_str = str(yr_date)
            vals_r = {'r134a_kg': random.randint(5, 15), 'r410a_kg': random.randint(3, 10),
                      'r407c_kg': random.randint(2, 8), 'period_month': yr_str}
            if not DataRow.objects.filter(data_table=self._tables['refrigerant_usage'][0], values__period_month=yr_str).exists():
                DataRow.objects.create(data_table=self._tables['refrigerant_usage'][0], values=vals_r)
                yr_total += 1

            emp = EMPLOYEES.get(yr, 3200)
            vals_c = {'car_km': int(emp * 15 * 22 * 0.6), 'bus_km': int(emp * 10 * 22 * 0.35),
                      'employees_count': emp, 'period_month': yr_str}
            if not DataRow.objects.filter(data_table=self._tables['employee_commute'][0], values__period_month=yr_str).exists():
                DataRow.objects.create(data_table=self._tables['employee_commute'][0], values=vals_c)
                yr_total += 1

            total_rows += yr_total
            print(f"  {yr}: {yr_total} rows")
        print(f"  -> {total_rows} total activity data rows")
        self._steps.append('with_activity_data')
        self._done.add('with_activity_data')
        return self

    # ──────────────────────────────────────────────
    # Rules / targets / calculations / DQ
    # ──────────────────────────────────────────────

    def with_calculation_rules(self):
        """Seed calculation rules. Auto-resolves modules/tables + factors."""
        if 'with_calculation_rules' in self._done:
            return self
        self.with_modules_and_tables()
        self.with_emission_factors()
        banner("CALCULATION RULES")
        rules_spec = [
            ('Electricity -> CO2 (Egypt Grid 2024)', 'electricity_consumption', 'kwh', 'EG_GRID_2024'),
            ('Electricity -> CO2 (Egypt Grid 2025)', 'electricity_consumption', 'kwh', 'EG_GRID_2025'),
            ('Water -> CO2', 'water_consumption', 'm3', 'WATER_EG'),
            ('Chilled Water -> CO2', 'chilled_water', 'tr_hours', 'CHILLED_WATER'),
            ('Diesel -> CO2', 'fuel_consumption', 'diesel_liters', 'DIESEL_IPCC'),
            ('Gasoline -> CO2', 'fuel_consumption', 'gasoline_liters', 'GASOLINE_IPCC'),
            ('Commute Car -> CO2', 'employee_commute', 'car_km', 'COMMUTE_CAR'),
        ]
        admin = User.objects.filter(username='admin').first()
        count = 0
        for name, tbl_name, field_name, factor_code in rules_spec:
            ef = self._factors.get(factor_code)
            if not ef:
                print(f"  WARNING Factor {factor_code} missing - skipping")
                continue
            dt, fields = self._tables[tbl_name]
            activity_field = next(f for f in fields if f.name == field_name)
            rule, created = CalculationRule.objects.get_or_create(
                data_table=dt, activity_field=activity_field, emission_factor=ef,
                defaults={
                    'name': name,
                    'rule_type': 'direct',
                    'is_active': True,
                    'auto_calculate': True,
                    'created_by': admin,
                }
            )
            count += 1
            print(f"  {'+' if created else chr(183)} {name}")
        print(f"  -> {count} calculation rules")
        self._steps.append('with_calculation_rules')
        self._done.add('with_calculation_rules')
        return self

    def with_sbti_targets(self):
        """Seed SBTi targets. Auto-resolves with_org_units()."""
        if 'with_sbti_targets' in self._done:
            return self
        self.with_org_units()
        banner("SBTi TARGETS")
        admin = User.objects.filter(username='admin').first()
        for name, base_yr, target_yr, ttype, scope, red_pct, status, desc, ou_name in SBTI_SPECS:
            ou = self._org_units.get(ou_name)
            target, created = SBTiTarget.objects.get_or_create(
                name=name, org_unit=ou,
                defaults={
                    'base_year': base_yr, 'target_year': target_yr,
                    'target_type': ttype, 'scope': scope,
                    'reduction_pct': red_pct, 'status': status,
                    'description': desc, 'created_by': admin,
                }
            )
            print(f"  {'+' if created else chr(183)} {name} ({base_yr}->{target_yr}, -{red_pct}%)")
        self._steps.append('with_sbti_targets')
        self._done.add('with_sbti_targets')
        return self

    def with_calculations(self):
        """Run calculations for all active rules. Auto-resolves rules."""
        if 'with_calculations' in self._done:
            return self
        self.with_calculation_rules()
        banner("RUNNING CALCULATIONS")
        admin = User.objects.filter(username='admin').first()
        rules = CalculationRule.objects.filter(is_active=True)
        total = 0
        for rule in rules:
            created, skipped, errors = rule.calculate_for_table(user=admin, recalculate=True)
            print(f"  {rule.name}: +{created} / {skipped} skipped / {errors} errors")
            total += created
        print(f"  -> {total} new calculations")
        self._steps.append('with_calculations')
        self._done.add('with_calculations')
        return self

    def with_data_quality(self):
        """Profile + run DQ on all tables. Auto-resolves modules/tables."""
        if 'with_data_quality' in self._done:
            return self
        self.with_modules_and_tables()
        banner("DATA QUALITY")
        for name, (dt, _) in self._tables.items():
            try:
                profile_table(dt.id)
                run_dq(dt.id)
                print(f"  OK {dt.title} - DQ profiled")
            except Exception as e:
                print(f"  WARNING {dt.title} - DQ failed: {e}")
        for name, (dt, _) in self._tables.items():
            ap, _ = AssetProfile.objects.get_or_create(data_table=dt, defaults={'quality_status': 'unknown'})
            ap.quality_status = 'passing'; ap.save()
        print(f"  -> Asset profiles updated")
        self._steps.append('with_data_quality')
        self._done.add('with_data_quality')
        return self

    # ──────────────────────────────────────────────
    # Terminal operations
    # ──────────────────────────────────────────────

    def _resolve_order(self, steps):
        """Topologically order steps so dependencies always run first."""
        ordered = []
        seen = set()
        def visit(step):
            if step in seen:
                return
            seen.add(step)
            for dep in self._DEPENDENCIES.get(step, ()):
                visit(dep)
            ordered.append(step)
        for step in steps:
            visit(step)
        return ordered

    def run(self):
        """Execute all stacked steps in dependency order (default: full pipeline)."""
        if self.reset:
            self._reset()
        self._print_header()
        steps = self._steps if self._steps else list(self._DEFAULT_STEPS)
        for step in self._resolve_order(steps):
            getattr(self, step)()
        return self

    def _reset(self):
        banner("RESET - Deleting all carbon data")
        Calculation.objects.all().delete()
        DataRow.objects.all().delete()
        SBTiTarget.objects.all().delete()
        CalculationRule.objects.all().delete()
        EmissionFactor.objects.all().delete()
        GWP.objects.all().delete()
        ReportingPeriod.objects.all().delete()
        DataField.objects.all().delete()
        DataTable.objects.all().delete()
        Module.objects.all().delete()
        AssetProfile.objects.all().delete()
        OrgUnit.objects.all().delete()
        ScopedRole.objects.all().delete()
        Group.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()
        print("  All carbon data deleted.")

    def _print_header(self):
        print(f"\n{'#'*70}")
        print(f"  CARBON MASTER SEED - {', '.join(str(y) for y in self.years)}")
        print(f"{'#'*70}")

    def print_summary(self):
        """Print the final summary table + login credentials."""
        banner("SEED COMPLETE")
        print(f"  Org Units:         {OrgUnit.objects.count()}")
        print(f"  Users:             {User.objects.count()}")
        print(f"  Groups:            {Group.objects.count()}")
        print(f"  ScopedRoles:       {ScopedRole.objects.count()}")
        print(f"  Modules:           {Module.objects.count()}")
        print(f"  DataTables:        {DataTable.objects.count()}")
        print(f"  DataRows:          {DataRow.objects.count()}")
        print(f"  ReportingPeriods:  {ReportingPeriod.objects.count()}")
        print(f"  EmissionFactors:   {EmissionFactor.objects.count()}")
        print(f"  GWPValues:         {GWP.objects.count()}")
        print(f"  CalculationRules:  {CalculationRule.objects.count()}")
        print(f"  Calculations:      {Calculation.objects.count()}")
        print(f"  SBTiTargets:       {SBTiTarget.objects.count()}")
        print()

        print("LOGIN CREDENTIALS:")
        print("-" * 50)
        creds = [
            ('admin', 'admin123', 'Superuser - full access'),
            ('dataowner1', 'owner123', 'Data Owner - Smart Village'),
            ('analyst1', 'analyst123', 'Analyst - read-only reports'),
            ('viewer1', 'viewer123', 'Viewer - minimal access'),
            ('transport_officer', 'transport123', 'Scoped Owner - Smart Village'),
        ]
        for u, p, desc in creds:
            print(f"  {u:22} / {p:16}  {desc}")
        print("-" * 50)

    @classmethod
    def from_args(cls):
        """Parse sys.argv and return a configured builder (same CLI as before)."""
        import argparse
        parser = argparse.ArgumentParser(description='Carbon Master Seed Script')
        parser.add_argument('--reset', action='store_true', help='Delete all carbon data first')
        parser.add_argument('--years', type=str, help='Comma-separated years (default: 2024,2025,2026)')
        args = parser.parse_args()
        years = tuple(int(y.strip()) for y in args.years.split(',')) if args.years else DEFAULT_YEARS
        return cls(years=years, reset=args.reset)


# ══════════════════════════════════════════
# MAIN — thin wrapper
# ══════════════════════════════════════════

def main():
    builder = SeedBuilder.from_args()
    builder.run()
    builder.print_summary()


if __name__ == '__main__':
    main()
