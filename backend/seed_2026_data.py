#!/usr/bin/env python
"""
Seed 2026 emissions data (January only, since we're in Feb 2026).
Continues the reduction trajectory from previous years.
"""
import os
import sys
import django
from decimal import Decimal
from datetime import date
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from emissions.models import ReportingPeriod, Calculation, EmissionFactor
from dataschema.models import DataRow, DataTable
from core.models import Module
from accounts.models import User

def seed_2026_data():
    """Seed 2026 emissions data for January (first month of year)."""
    
    print("=== Seeding 2026 Emissions Data ===\n")
    
    user = User.objects.first()
    
    # Check existing 2026 data
    existing_2026 = Calculation.objects.filter(reporting_year=2026).count()
    if existing_2026 > 0:
        print(f"Found {existing_2026} existing 2026 calculations. Deleting...")
        Calculation.objects.filter(reporting_year=2026).delete()
    
    # Get modules
    modules = {m.scope: m for m in Module.objects.all() if m.scope}
    if not modules:
        print("Error: No modules found.")
        return
    
    # Get emission factors
    electricity_ef = EmissionFactor.objects.filter(category='electricity').first()
    natural_gas_ef = EmissionFactor.objects.filter(category='stationary_combustion').first()
    transport_ef = EmissionFactor.objects.filter(category='transport').first()
    mobile_ef = EmissionFactor.objects.filter(category='mobile_combustion').first()
    
    if not electricity_ef:
        print("Error: No electricity emission factor found.")
        return
    
    # Get or create data table
    module = modules.get(1)
    data_table, _ = DataTable.objects.get_or_create(
        name='2026_emissions',
        module=module,
        defaults={
            'title': '2026 Emissions Data',
            'description': 'Emissions data for FY 2026',
            'version': 1,
            'created_by': user,
            'updated_by': user,
        }
    )
    
    # Create reporting period for 2026
    period, created = ReportingPeriod.objects.get_or_create(
        name='FY 2026',
        defaults={
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 12, 31),
            'period_type': 'annual',
            'status': 'open',  # Current year - still open
            'is_baseline': False,
        }
    )
    
    if created:
        print(f"Created reporting period: {period.name}")
    else:
        print(f"Using existing period: {period.name}")
    
    # Get 2025 baseline to calculate 2026 target
    from django.db.models import Sum
    total_2025 = Calculation.objects.filter(reporting_year=2025).aggregate(
        total=Sum('co2e_kg')
    )['total'] or 0
    total_2025_tonnes = float(total_2025) / 1000
    print(f"2025 emissions: {total_2025_tonnes:.2f} tonnes")
    
    # Target: 5% additional reduction from 2025 (SBTi trajectory)
    # Since it's only January, estimate monthly average
    # 2025 had ~2516 tonnes total, so ~210 tonnes/month
    # 2026 should be ~5% less = ~200 tonnes/month
    
    # January 2026 estimates (continuing reduction)
    reduction_factor = 0.95  # 5% reduction from 2025 monthly average
    january_seasonal = 1.15  # Winter higher usage
    
    calculations_created = 0
    total_co2e = Decimal('0')
    
    # Scope 1 - Stationary Combustion (Natural Gas)
    if natural_gas_ef and modules.get(1):
        activity_value = Decimal('18000') * Decimal(str(reduction_factor)) * Decimal(str(january_seasonal))
        co2e = activity_value * natural_gas_ef.factor_value
        
        data_row = DataRow.objects.create(
            data_table=data_table,
            values={'year': 2026, 'month': 1, 'category': 'stationary_combustion'},
            created_by=user,
            updated_by=user,
        )
        
        Calculation.objects.create(
            module=modules[1],
            emission_factor=natural_gas_ef,
            data_row=data_row,
            reporting_period=period,
            reporting_year=2026,
            activity_value=activity_value,
            activity_unit=natural_gas_ef.activity_unit or 'kWh',
            co2e_kg=co2e,
            scope=1,
            category='stationary_combustion',
            calculated_by=user,
        )
        calculations_created += 1
        total_co2e += co2e
    
    # Scope 1 - Mobile Combustion (Vehicles)
    if mobile_ef and modules.get(1):
        activity_value = Decimal('3500') * Decimal(str(reduction_factor))
        co2e = activity_value * mobile_ef.factor_value
        
        data_row = DataRow.objects.create(
            data_table=data_table,
            values={'year': 2026, 'month': 1, 'category': 'mobile_combustion'},
            created_by=user,
            updated_by=user,
        )
        
        Calculation.objects.create(
            module=modules[1],
            emission_factor=mobile_ef,
            data_row=data_row,
            reporting_period=period,
            reporting_year=2026,
            activity_value=activity_value,
            activity_unit=mobile_ef.activity_unit or 'liters',
            co2e_kg=co2e,
            scope=1,
            category='mobile_combustion',
            calculated_by=user,
        )
        calculations_created += 1
        total_co2e += co2e
    
    # Scope 2 - Electricity
    if electricity_ef and modules.get(2):
        activity_value = Decimal('350000') * Decimal(str(reduction_factor)) * Decimal(str(january_seasonal))
        co2e = activity_value * electricity_ef.factor_value
        
        data_row = DataRow.objects.create(
            data_table=data_table,
            values={'year': 2026, 'month': 1, 'category': 'electricity'},
            created_by=user,
            updated_by=user,
        )
        
        Calculation.objects.create(
            module=modules[2],
            emission_factor=electricity_ef,
            data_row=data_row,
            reporting_period=period,
            reporting_year=2026,
            activity_value=activity_value,
            activity_unit='kWh',
            co2e_kg=co2e,
            scope=2,
            category='electricity',
            calculated_by=user,
        )
        calculations_created += 1
        total_co2e += co2e
    
    # Scope 3 - Transport (limited in January due to holidays)
    if transport_ef and modules.get(3):
        activity_value = Decimal('800') * Decimal(str(reduction_factor))
        co2e = activity_value * transport_ef.factor_value
        
        data_row = DataRow.objects.create(
            data_table=data_table,
            values={'year': 2026, 'month': 1, 'category': 'transport'},
            created_by=user,
            updated_by=user,
        )
        
        Calculation.objects.create(
            module=modules[3],
            emission_factor=transport_ef,
            data_row=data_row,
            reporting_period=period,
            reporting_year=2026,
            activity_value=activity_value,
            activity_unit=transport_ef.activity_unit or 'km',
            co2e_kg=co2e,
            scope=3,
            category='transport',
            calculated_by=user,
        )
        calculations_created += 1
        total_co2e += co2e
    
    total_tonnes = float(total_co2e) / 1000
    
    print(f"\n=== 2026 Data Seeded ===")
    print(f"Calculations created: {calculations_created}")
    print(f"January 2026 emissions: {total_tonnes:.2f} tonnes CO₂e")
    print(f"Projected annual (x12): {total_tonnes * 12:.2f} tonnes CO₂e")
    
    # Show comparison
    baseline_2020 = Calculation.objects.filter(reporting_year=2020).aggregate(
        total=Sum('co2e_kg')
    )['total'] or 0
    baseline_tonnes = float(baseline_2020) / 1000
    
    if baseline_tonnes > 0:
        projected_annual = total_tonnes * 12
        reduction_pct = (1 - projected_annual / baseline_tonnes) * 100
        print(f"\nProjected reduction from 2020 baseline: {reduction_pct:.1f}%")
        print(f"(2020 baseline: {baseline_tonnes:.2f} tonnes)")

if __name__ == '__main__':
    seed_2026_data()
