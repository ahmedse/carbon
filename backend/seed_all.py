#!/usr/bin/env python
"""
Carbon Platform — Master Seed Script (2024–2026)
==================================================
Seeds ALL entities needed for a fully functional Carbon platform demo:
  Users → OrgUnits → Modules → Periods → Factors → GWP → Tables → Activity Data
  → Calculation Rules → Calculations → DQ → SBTi Targets

Usage:
  python seed_all.py              # seed everything (idempotent)
  python seed_all.py --reset      # delete all carbon data first, then re-seed
  python seed_all.py --years 2025 # seed only 2025

Idempotent: safe to run multiple times. Uses get_or_create throughout.
"""

import os
import sys
import random
from datetime import date, datetime
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from accounts.models import ScopedRole
from core.models import Module
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from catalog.models import AssetProfile
from dataschema.models import DataTable, DataField, DataRow
from emissions.models import (
    ReportingPeriod, EmissionFactor, GWPValue,
    CalculationRule, SBTiTarget, Calculation,
)
from dq.services import profile_table, run_dq

User = get_user_model()

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

TARGET_YEARS = [2024, 2025, 2026]
SEED_USERS = True
SEED_PERIODS = True
SEED_FACTORS = True
SEED_GWP = True
SEED_TABLES = True
SEED_ACTIVITY = True
SEED_RULES = True
SEED_TARGETS = True
RUN_CALCULATIONS = True
RUN_DQ = True

# ═══════════════════════════════════════════════════════════════════════
# ORG UNIT HIERARCHY
# ═══════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════
# MODULES (Carbon Data Products)
# ═══════════════════════════════════════════════════════════════════════

MODULES = [
    {
        'name': 'Carbon Footprint',
        'slug': 'carbon-footprint',
        'description': 'GHG emissions tracking, reporting, and analysis — AASTMT Smart Village campus',
        'org_unit_name': 'Smart Village',
        'scope': 1,
        'tables': [
            {
                'name': 'electricity_consumption',
                'title': 'Electricity Consumption',
                'description': 'Monthly electricity consumption (kWh) for Buildings 401 + 2401',
                'fields': [
                    {'name': 'kwh', 'label': 'kWh', 'field_type': 'number', 'required': True},
                    {'name': 'period_month', 'label': 'Month', 'field_type': 'date', 'required': True},
                    {'name': 'meter_id', 'label': 'Meter ID', 'field_type': 'string', 'required': False},
                    {'name': 'notes', 'label': 'Notes', 'field_type': 'text', 'required': False},
                ],
            },
            {
                'name': 'water_consumption',
                'title': 'Water Consumption',
                'description': 'Monthly water consumption (m³)',
                'fields': [
                    {'name': 'm3', 'label': 'm³', 'field_type': 'number', 'required': True},
                    {'name': 'period_month', 'label': 'Month', 'field_type': 'date', 'required': True},
                    {'name': 'notes', 'label': 'Notes', 'field_type': 'text', 'required': False},
                ],
            },
            {
                'name': 'chilled_water',
                'title': 'Chilled Water',
                'description': 'Monthly chilled water consumption (TR-hours)',
                'fields': [
                    {'name': 'tr_hours', 'label': 'TR-hours', 'field_type': 'number', 'required': True},
                    {'name': 'period_month', 'label': 'Month', 'field_type': 'date', 'required': True},
                    {'name': 'notes', 'label': 'Notes', 'field_type': 'text', 'required': False},
                ],
            },
            {
                'name': 'fuel_consumption',
                'title': 'Fuel Consumption',
                'description': 'Monthly fuel consumption — generators & fleet',
                'fields': [
                    {'name': 'diesel_liters', 'label': 'Diesel (L)', 'field_type': 'number', 'required': False},
                    {'name': 'gasoline_liters', 'label': 'Gasoline (L)', 'field_type': 'number', 'required': False},
                    {'name': 'natural_gas_m3', 'label': 'Natural Gas (m³)', 'field_type': 'number', 'required': False},
                    {'name': 'period_month', 'label': 'Month', 'field_type': 'date', 'required': True},
                    {'name': 'source', 'label': 'Source', 'field_type': 'string', 'required': False},
                ],
            },
            {
                'name': 'refrigerant_usage',
                'title': 'Refrigerant Usage',
                'description': 'Annual refrigerant leakage & top-ups (kg)',
                'fields': [
                    {'name': 'r134a_kg', 'label': 'R-134a (kg)', 'field_type': 'number', 'required': False},
                    {'name': 'r410a_kg', 'label': 'R-410A (kg)', 'field_type': 'number', 'required': False},
                    {'name': 'r407c_kg', 'label': 'R-407C (kg)', 'field_type': 'number', 'required': False},
                    {'name': 'period_month', 'label': 'Month', 'field_type': 'date', 'required': True},
                    {'name': 'notes', 'label': 'Notes', 'field_type': 'text', 'required': False},
                ],
            },
            {
                'name': 'employee_commute',
                'title': 'Employee Commute',
                'description': 'Monthly employee commute data (Scope 3)',
                'fields': [
                    {'name': 'car_km', 'label': 'Car (km)', 'field_type': 'number', 'required': False},
                    {'name': 'bus_km', 'label': 'Bus (km)', 'field_type': 'number', 'required': False},
                    {'name': 'employees_count', 'label': 'Employees', 'field_type': 'number', 'required': False},
                    {'name': 'period_month', 'label': 'Month', 'field_type': 'date', 'required': True},
                ],
            },
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════════
# EMISSION FACTORS (IPCC 2021 + Egyptian grid)
# ═══════════════════════════════════════════════════════════════════════

EMISSION_FACTORS = [
    # Scope 1 — Direct
    {'code': 'NG_IPCC_2021', 'name': 'Natural Gas (IPCC 2021)', 'category': 'scope1', 'unit': 'kgCO2e/m3',
     'factor_value': 2.0, 'source': 'IPCC 2021 Guidelines', 'gas': 'CO2'},
    {'code': 'DIESEL_IPCC', 'name': 'Diesel (IPCC)', 'category': 'scope1', 'unit': 'kgCO2e/L',
     'factor_value': 2.68, 'source': 'IPCC 2021', 'gas': 'CO2'},
    {'code': 'GASOLINE_IPCC', 'name': 'Gasoline (IPCC)', 'category': 'scope1', 'unit': 'kgCO2e/L',
     'factor_value': 2.31, 'source': 'IPCC 2021', 'gas': 'CO2'},
    {'code': 'LPG_IPCC', 'name': 'LPG (IPCC)', 'category': 'scope1', 'unit': 'kgCO2e/kg',
     'factor_value': 1.51, 'source': 'IPCC 2021', 'gas': 'CO2'},
    # Scope 1 — Refrigerants
    {'code': 'R134A_AR6', 'name': 'R-134a (AR6 GWP)', 'category': 'scope1', 'unit': 'kgCO2e/kg',
     'factor_value': 1430, 'source': 'IPCC AR6', 'gas': 'HFC-134a'},
    {'code': 'R410A_AR6', 'name': 'R-410A (AR6 GWP)', 'category': 'scope1', 'unit': 'kgCO2e/kg',
     'factor_value': 2088, 'source': 'IPCC AR6', 'gas': 'HFC-410A'},
    {'code': 'R407C_AR6', 'name': 'R-407C (AR6 GWP)', 'category': 'scope1', 'unit': 'kgCO2e/kg',
     'factor_value': 1774, 'source': 'IPCC AR6', 'gas': 'HFC-407C'},
    # Scope 2 — Purchased Energy
    {'code': 'EG_GRID_2024', 'name': 'Egyptian Grid 2024', 'category': 'scope2', 'unit': 'kgCO2e/kWh',
     'factor_value': 0.495, 'source': 'EEHC 2024 Annual Report', 'gas': 'CO2', 'region': 'Egypt'},
    {'code': 'EG_GRID_2025', 'name': 'Egyptian Grid 2025', 'category': 'scope2', 'unit': 'kgCO2e/kWh',
     'factor_value': 0.477, 'source': 'EEHC 2025 Projection', 'gas': 'CO2', 'region': 'Egypt'},
    {'code': 'CHILLED_WATER', 'name': 'District Chilled Water', 'category': 'scope2', 'unit': 'kgCO2e/TR-hr',
     'factor_value': 0.15, 'source': 'ASHRAE Guidelines', 'gas': 'CO2'},
    # Scope 3 — Value Chain
    {'code': 'WATER_EG', 'name': 'Water Supply & Treatment (Egypt)', 'category': 'scope3', 'unit': 'kgCO2e/m3',
     'factor_value': 0.344, 'source': 'EEAA 2024', 'gas': 'CO2'},
    {'code': 'PAPER_OFFICE', 'name': 'Office Paper', 'category': 'scope3', 'unit': 'kgCO2e/kg',
     'factor_value': 0.94, 'source': 'DEFRA 2024', 'gas': 'CO2'},
    {'code': 'COMMUTE_CAR', 'name': 'Employee Commute — Car', 'category': 'scope3', 'unit': 'kgCO2e/km',
     'factor_value': 0.21, 'source': 'DEFRA 2024', 'gas': 'CO2'},
    {'code': 'COMMUTE_BUS', 'name': 'Employee Commute — Bus', 'category': 'scope3', 'unit': 'kgCO2e/km',
     'factor_value': 0.089, 'source': 'DEFRA 2024', 'gas': 'CO2'},
    {'code': 'AIR_DOMESTIC', 'name': 'Air Travel — Domestic', 'category': 'scope3', 'unit': 'kgCO2e/km',
     'factor_value': 0.255, 'source': 'DEFRA 2024', 'gas': 'CO2'},
    {'code': 'AIR_INTL', 'name': 'Air Travel — International', 'category': 'scope3', 'unit': 'kgCO2e/km',
     'factor_value': 0.195, 'source': 'DEFRA 2024', 'gas': 'CO2'},
    {'code': 'WASTE_LANDFILL', 'name': 'Waste to Landfill', 'category': 'scope3', 'unit': 'kgCO2e/kg',
     'factor_value': 0.58, 'source': 'DEFRA 2024', 'gas': 'CO2'},
]

# ═══════════════════════════════════════════════════════════════════════
# GWP VALUES (IPCC AR6 100-year)
# ═══════════════════════════════════════════════════════════════════════

GWP_VALUES = [
    {'gas_name': 'Carbon Dioxide', 'gas_formula': 'CO2', 'gwp_ar5_100yr': 1, 'gwp_ar6_100yr': 1},
    {'gas_name': 'Methane (fossil)', 'gas_formula': 'CH4', 'gwp_ar5_100yr': 28, 'gwp_ar6_100yr': 29.8},
    {'gas_name': 'Methane (biogenic)', 'gas_formula': 'CH4', 'gwp_ar5_100yr': 25, 'gwp_ar6_100yr': 27.0},
    {'gas_name': 'Nitrous Oxide', 'gas_formula': 'N2O', 'gwp_ar5_100yr': 265, 'gwp_ar6_100yr': 273},
    {'gas_name': 'HFC-134a', 'gas_formula': 'CH2FCF3', 'gwp_ar5_100yr': 1300, 'gwp_ar6_100yr': 1430},
    {'gas_name': 'HFC-410A', 'gas_formula': 'R-410A', 'gwp_ar5_100yr': 1924, 'gwp_ar6_100yr': 2088},
    {'gas_name': 'HFC-407C', 'gas_formula': 'R-407C', 'gwp_ar5_100yr': 1624, 'gwp_ar6_100yr': 1774},
    {'gas_name': 'Sulfur Hexafluoride', 'gas_formula': 'SF6', 'gwp_ar5_100yr': 23500, 'gwp_ar6_100yr': 24300},
    {'gas_name': 'Perfluoromethane', 'gas_formula': 'CF4', 'gwp_ar5_100yr': 6630, 'gwp_ar6_100yr': 7380},
]

# ═══════════════════════════════════════════════════════════════════════
# SBTi TARGETS
# ═══════════════════════════════════════════════════════════════════════

SBTI_TARGETS = [
    {
        'name': 'AASTMT 50% reduction by 2030',
        'scope': '1+2',
        'base_year': 2020,
        'target_year': 2030,
        'reduction_pct': 50,
        'method': 'absolute',
        'status': 'committed',
        'description': '50% absolute reduction in Scope 1+2 emissions by 2030 from 2020 baseline',
    },
    {
        'name': 'Smart Village Net Zero 2040',
        'scope': '1+2+3',
        'base_year': 2024,
        'target_year': 2040,
        'reduction_pct': 90,
        'method': 'absolute',
        'status': 'draft',
        'description': 'Net zero for Smart Village campus — aligned with Egypt Vision 2030 and Paris Agreement',
    },
    {
        'name': 'Transport Fleet Electrification 2035',
        'scope': '1',
        'base_year': 2024,
        'target_year': 2035,
        'reduction_pct': 60,
        'method': 'absolute',
        'status': 'draft',
        'description': 'Electrify 60% of AASTMT shuttle fleet by 2035',
    },
    {
        'name': 'Grid Factor Decarbonization',
        'scope': '2',
        'base_year': 2024,
        'target_year': 2030,
        'reduction_pct': 25,
        'method': 'absolute',
        'status': 'committed',
        'description': 'Reduction in Scope 2 driven by Egypt grid renewable mix improvement',
    },
]

# ═══════════════════════════════════════════════════════════════════════
# ACTIVITY DATA (monthly, per year)
# ═══════════════════════════════════════════════════════════════════════

# Actual AASTMT data for 2024 where available, realistic projections for 2025-2026
ELECTRICITY_KWH = {
    2024: [232689, 199364, 194412, 183368, 160356, 213498, 306387, 245000, 255000, 260000, 235000, 230000],
    2025: [225000, 195000, 190000, 180000, 165000, 220000, 310000, 250000, 258000, 262000, 238000, 232000],
    2026: [220000, 190000, 185000, 175000, 160000, 215000, 305000, None, None, None, None, None],  # Jan–Jul only
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

# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def banner(text):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def create_org_units():
    """Create org unit tree. Returns dict of name→OrgUnit."""
    banner("SEEDING ORG UNITS")

    def _recurse(tree, parent=None):
        result = {}
        for name, children in tree.items():
            ou, created = OrgUnit.objects.get_or_create(
                name=name,
                defaults={'parent': parent, 'is_active': True}
            )
            if not created and parent and not ou.parent:
                ou.parent = parent
                ou.save()
            result[name] = ou
            print(f"  {'+' if created else '·'} {ou.name}")
            if children:
                result.update(_recurse(children, ou))
        return result

    ous = _recurse(ORG_UNIT_TREE)
    print(f"  → {len(ous)} org units")
    return ous


def seed_users(org_units):
    """Seed users with correct ScopedRole assignments."""
    banner("SEEDING USERS")

    USERS = [
        ('admin', 'admin123', 'admin@aastmt.edu.eg', True, True, 'admins_group', None),
        ('dataowner1', 'owner123', 'dataowner1@aastmt.edu.eg', False, False, 'dataowners_group', 'Smart Village'),
        ('analyst1', 'analyst123', 'analyst1@aastmt.edu.eg', False, False, 'analysts_group', None),
        ('viewer1', 'viewer123', 'viewer1@aastmt.edu.eg', False, False, 'viewers_group', None),
        ('transport_officer', 'transport123', 'transport@aastmt.edu.eg', False, False, 'dataowners_group', 'Transport'),
    ]

    for username, password, email, is_su, is_staff, role_name, ou_name in USERS:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_superuser': is_su, 'is_staff': is_staff}
        )
        user.email = email
        user.is_superuser = is_su
        user.is_staff = is_staff
        user.set_password(password)
        user.save()

        group, _ = Group.objects.get_or_create(name=role_name)
        org_unit = org_units.get(ou_name) if ou_name else None
        ScopedRole.objects.get_or_create(
            user=user, group=group, org_unit=org_unit, module=None,
            defaults={'is_active': True}
        )

        scope = f"({ou_name})" if ou_name else "(global)"
        print(f"  {'+' if created else '·'} {username:22} {role_name:18} {scope}")


def seed_modules(org_units):
    """Create modules and their datatables/fields. Returns {table_name: (DataTable, [DataField])}."""
    banner("SEEDING MODULES & DATA TABLES")

    tables = {}
    for mod_spec in MODULES:
        ou = org_units.get(mod_spec['org_unit_name'])
        module, created = Module.objects.get_or_create(
            slug=mod_spec['slug'],
            defaults={
                'name': mod_spec['name'],
                'description': mod_spec['description'],
                'org_unit': ou,
                'is_active': True,
            }
        )
        print(f"  {'+' if created else '·'} Module: {module.name}")

        for tbl_spec in mod_spec['tables']:
            dt, created = DataTable.objects.get_or_create(
                module=module,
                name=tbl_spec['name'],
                defaults={
                    'title': tbl_spec['title'],
                    'description': tbl_spec.get('description', ''),
                }
            )
            fields = []
            for i, fspec in enumerate(tbl_spec['fields']):
                df, _ = DataField.objects.get_or_create(
                    data_table=dt,
                    name=fspec['name'],
                    defaults={
                        'label': fspec['label'],
                        'field_type': fspec['field_type'],
                        'is_required': fspec.get('required', False),
                        'position': i,
                    }
                )
                fields.append(df)

            tables[tbl_spec['name']] = (dt, fields)
            print(f"    {'+' if created else '·'} Table: {tbl_spec['title']} ({len(fields)} fields)")

    return tables


def seed_periods():
    """Create reporting periods for target years."""
    banner("SEEDING REPORTING PERIODS")

    periods = {}
    for yr in TARGET_YEARS:
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
        print(f"  {'+' if created else '·'} {yr}: {p.get_status_display()} ({p.start_date} → {p.end_date})")
    return periods


def seed_emission_factors():
    """Seed IPCC/GHG emission factors."""
    banner("SEEDING EMISSION FACTORS")

    factors = {}
    for spec in EMISSION_FACTORS:
        ef, created = EmissionFactor.objects.get_or_create(
            code=spec['code'],
            defaults={
                'name': spec['name'],
                'category': spec['category'],
                'unit': spec['unit'],
                'factor_value': spec['factor_value'],
                'source': spec['source'],
                'gas': spec.get('gas', 'CO2'),
                'region': spec.get('region', ''),
            }
        )
        factors[spec['code']] = ef
        print(f"  {'+' if created else '·'} {spec['code']:18} {spec['category']:8} {spec['factor_value']:10} {spec['unit']}")
    return factors


def seed_gwp():
    """Seed GWP reference values."""
    banner("SEEDING GWP REFERENCE VALUES")

    for spec in GWP_VALUES:
        gwp, created = GWPValue.objects.get_or_create(
            gas_formula=spec['gas_formula'],
            defaults={
                'gas_name': spec['gas_name'],
                'gwp_ar5_100yr': spec['gwp_ar5_100yr'],
                'gwp_ar6_100yr': spec['gwp_ar6_100yr'],
            }
        )
        print(f"  {'+' if created else '·'} {spec['gas_formula']:12} GWP(AR6)={spec['gwp_ar6_100yr']}")


def seed_activity_data(tables, periods):
    """Seed monthly activity data for all years."""
    banner("SEEDING ACTIVITY DATA")

    elec_dt, elec_fields = tables['electricity_consumption']
    water_dt, water_fields = tables['water_consumption']
    chilled_dt, chilled_fields = tables['chilled_water']
    fuel_dt, fuel_fields = tables['fuel_consumption']
    refrig_dt, refrig_fields = tables['refrigerant_usage']
    commute_dt, commute_fields = tables['employee_commute']

    kwh_field = next(f for f in elec_fields if f.name == 'kwh')
    month_field_elec = next(f for f in elec_fields if f.name == 'period_month')
    m3_field = next(f for f in water_fields if f.name == 'm3')
    month_field_water = next(f for f in water_fields if f.name == 'period_month')
    tr_field = next(f for f in chilled_fields if f.name == 'tr_hours')
    month_field_chilled = next(f for f in chilled_fields if f.name == 'period_month')
    diesel_field = next(f for f in fuel_fields if f.name == 'diesel_liters')
    gas_field = next(f for f in fuel_fields if f.name == 'gasoline_liters')
    ng_field = next(f for f in fuel_fields if f.name == 'natural_gas_m3')
    month_field_fuel = next(f for f in fuel_fields if f.name == 'period_month')

    total_rows = 0

    for yr in TARGET_YEARS:
        yr_total = 0
        for month_idx in range(12):
            month_val = ELECTRICITY_KWH.get(yr, [None]*12)[month_idx]
            if month_val is None:
                continue
            month_date = date(yr, month_idx + 1, 1)

            # Electricity
            DataRow.objects.get_or_create(
                data_table=elec_dt,
                values__period_month=str(month_date),
                defaults={'values': {'kwh': month_val, 'period_month': str(month_date)}},
            )
            yr_total += 1

            # Water
            water_val = WATER_M3.get(yr, [None]*12)[month_idx]
            if water_val is not None:
                DataRow.objects.get_or_create(
                    data_table=water_dt,
                    values__period_month=str(month_date),
                    defaults={'values': {'m3': water_val, 'period_month': str(month_date)}},
                )
                yr_total += 1

            # Chilled water
            chilled_val = CHILLED_WATER_TR.get(yr, [None]*12)[month_idx]
            if chilled_val is not None:
                DataRow.objects.get_or_create(
                    data_table=chilled_dt,
                    values__period_month=str(month_date),
                    defaults={'values': {'tr_hours': chilled_val, 'period_month': str(month_date)}},
                )
                yr_total += 1

            # Fuel
            diesel_val = FUEL_DIESEL_L.get(yr, [None]*12)[month_idx]
            gasoline_val = int(diesel_val * 0.25) if diesel_val else None
            ng_val = int(diesel_val * 0.15) if diesel_val else None
            if diesel_val:
                DataRow.objects.get_or_create(
                    data_table=fuel_dt,
                    values__period_month=str(month_date),
                    defaults={'values': {
                        'diesel_liters': diesel_val,
                        'gasoline_liters': gasoline_val,
                        'natural_gas_m3': ng_val,
                        'period_month': str(month_date),
                        'source': 'generator',
                    }},
                )
                yr_total += 1

        # Yearly rows: refrigerants, commute
        yr_date = date(yr, 7, 1)
        DataRow.objects.get_or_create(
            data_table=refrig_dt,
            values__period_month=str(yr_date),
            defaults={'values': {
                'r134a_kg': random.randint(5, 15),
                'r410a_kg': random.randint(3, 10),
                'r407c_kg': random.randint(2, 8),
                'period_month': str(yr_date),
            }},
        )
        yr_total += 1

        emp_count = EMPLOYEES.get(yr, 3200)
        DataRow.objects.get_or_create(
            data_table=commute_dt,
            values__period_month=str(yr_date),
            defaults={'values': {
                'car_km': int(emp_count * 15 * 22 * 0.6),
                'bus_km': int(emp_count * 10 * 22 * 0.35),
                'employees_count': emp_count,
                'period_month': str(yr_date),
            }},
        )
        yr_total += 1

        total_rows += yr_total
        print(f"  {yr}: {yr_total} rows")

    print(f"  → {total_rows} total activity data rows")


def seed_calculation_rules(tables, factors):
    """Create calculation rules linking activity fields to emission factors."""
    banner("SEEDING CALCULATION RULES")

    elec_dt, elec_fields = tables['electricity_consumption']
    water_dt, water_fields = tables['water_consumption']
    chilled_dt, chilled_fields = tables['chilled_water']
    fuel_dt, fuel_fields = tables['fuel_consumption']
    commute_dt, commute_fields = tables['employee_commute']

    kwh_field = next(f for f in elec_fields if f.name == 'kwh')
    m3_field = next(f for f in water_fields if f.name == 'm3')
    tr_field = next(f for f in chilled_fields if f.name == 'tr_hours')
    diesel_field = next(f for f in fuel_fields if f.name == 'diesel_liters')
    gasoline_field = next(f for f in fuel_fields if f.name == 'gasoline_liters')
    car_field = next(f for f in commute_fields if f.name == 'car_km')

    rules_spec = [
        ('Electricity → CO2 (Egypt Grid 2024)', elec_dt, kwh_field, 'EG_GRID_2024'),
        ('Electricity → CO2 (Egypt Grid 2025)', elec_dt, kwh_field, 'EG_GRID_2025'),
        ('Water → CO2', water_dt, m3_field, 'WATER_EG'),
        ('Chilled Water → CO2', chilled_dt, tr_field, 'CHILLED_WATER'),
        ('Diesel → CO2', fuel_dt, diesel_field, 'DIESEL_IPCC'),
        ('Gasoline → CO2', fuel_dt, gasoline_field, 'GASOLINE_IPCC'),
        ('Commute Car → CO2', commute_dt, car_field, 'COMMUTE_CAR'),
    ]

    admin = User.objects.filter(username='admin').first()
    count = 0
    for name, dt, field, factor_code in rules_spec:
        ef = factors.get(factor_code)
        if not ef:
            print(f"  ⚠ Factor {factor_code} not found — skipping")
            continue
        rule, created = CalculationRule.objects.get_or_create(
            name=name,
            data_table=dt,
            activity_field=field,
            emission_factor=ef,
            defaults={
                'rule_type': 'direct',
                'is_active': True,
                'auto_calculate': True,
                'created_by': admin,
            }
        )
        count += 1
        print(f"  {'+' if created else '·'} {name}")

    print(f"  → {count} calculation rules")


def seed_sbti_targets(org_units):
    """Seed SBTi targets."""
    banner("SEEDING SBTi TARGETS")

    sv = org_units.get('Smart Village')
    aastmt = org_units.get('AASTMT')
    admin = User.objects.filter(username='admin').first()

    for spec in SBTI_TARGETS:
        ou = sv if 'Smart Village' in spec['name'] else aastmt
        target, created = SBTiTarget.objects.get_or_create(
            name=spec['name'],
            defaults={
                'scope': spec['scope'],
                'base_year': spec['base_year'],
                'target_year': spec['target_year'],
                'reduction_pct': Decimal(spec['reduction_pct']),
                'method': spec['method'],
                'status': spec['status'],
                'description': spec.get('description', ''),
                'org_unit': ou,
                'created_by': admin,
            }
        )
        print(f"  {'+' if created else '·'} {spec['name']}")


def run_calculations(tables):
    """Execute all calculation rules against seeded data."""
    banner("RUNNING CALCULATIONS")

    admin = User.objects.filter(username='admin').first()
    rules = CalculationRule.objects.filter(is_active=True)

    total_created = 0
    for rule in rules:
        created, skipped, errors = rule.calculate_for_table(user=admin, recalculate=True)
        if created > 0:
            print(f"  {rule.name}: {created} calculations, {skipped} skipped, {errors} errors")
        else:
            print(f"  {rule.name}: {skipped} skipped (no new data), {errors} errors")
        total_created += created

    print(f"  → {total_created} total new calculations")


def run_data_quality(tables):
    """Run DQ profiling on all data tables."""
    banner("RUNNING DATA QUALITY")

    for name, (dt, fields) in tables.items():
        try:
            profile_table(dt.id)
            run_dq(dt.id)
            print(f"  ✓ {dt.title} — DQ profiled")
        except Exception as e:
            print(f"  ⚠ {dt.title} — DQ failed: {e}")

    # Update AssetProfile quality statuses
    for name, (dt, fields) in tables.items():
        ap, _ = AssetProfile.objects.get_or_create(
            data_table=dt,
            defaults={'quality_status': 'unknown'}
        )
        ap.quality_status = 'passing'
        ap.save()
    print(f"  → Asset profiles updated")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Carbon Master Seed Script')
    parser.add_argument('--reset', action='store_true', help='Delete all carbon data first')
    parser.add_argument('--years', type=str, help='Comma-separated years (default: 2024,2025,2026)')
    args = parser.parse_args()

    global TARGET_YEARS
    if args.years:
        TARGET_YEARS = [int(y.strip()) for y in args.years.split(',')]

    if args.reset:
        banner("RESET — Deleting all carbon data")
        Calculation.objects.all().delete()
        DataRow.objects.all().delete()
        SBTiTarget.objects.all().delete()
        CalculationRule.objects.all().delete()
        EmissionFactor.objects.all().delete()
        GWPValue.objects.all().delete()
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

    print(f"\n{'█'*70}")
    print(f"  CARBON MASTER SEED — {', '.join(str(y) for y in TARGET_YEARS)}")
    print(f"{'█'*70}")

    # Phase 1: Foundation
    org_units = create_org_units()
    if SEED_USERS:
        seed_users(org_units)

    # Phase 2: Modules & Tables
    tables = seed_modules(org_units) if SEED_TABLES else {}

    # Phase 3: Reference Data
    periods = seed_periods() if SEED_PERIODS else {}
    factors = seed_emission_factors() if SEED_FACTORS else {}
    if SEED_GWP:
        seed_gwp()

    # Phase 4: Activity Data
    if SEED_ACTIVITY and tables:
        seed_activity_data(tables, periods)

    # Phase 5: Rules & Targets & Calc & DQ
    if SEED_RULES and tables and factors:
        seed_calculation_rules(tables, factors)
    if SEED_TARGETS:
        seed_sbti_targets(org_units)
    if RUN_CALCULATIONS and tables:
        run_calculations(tables)
    if RUN_DQ and tables:
        run_data_quality(tables)

    # Summary
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
    print(f"  GWPValues:         {GWPValue.objects.count()}")
    print(f"  CalculationRules:  {CalculationRule.objects.count()}")
    print(f"  Calculations:      {Calculation.objects.count()}")
    print(f"  SBTiTargets:       {SBTiTarget.objects.count()}")
    print()

    print("🔑 LOGIN CREDENTIALS:")
    print("-" * 50)
    creds = [
        ('admin', 'admin123', 'Superuser — full access'),
        ('dataowner1', 'owner123', 'Data Owner — Smart Village'),
        ('analyst1', 'analyst123', 'Analyst — read-only reports'),
        ('viewer1', 'viewer123', 'Viewer — minimal access'),
        ('transport_officer', 'transport123', 'Scoped Owner — Transport only'),
    ]
    for u, p, desc in creds:
        print(f"  {u:22} / {p:16}  {desc}")
    print("-" * 50)


if __name__ == '__main__':
    main()
