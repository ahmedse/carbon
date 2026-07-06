#!/usr/bin/env python
"""
Seed historical emissions data for dashboard demonstration.
Creates realistic multi-year data to demonstrate:
- Year-over-year trends
- Target progress tracking
- Seasonal patterns
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

def seed_historical_data():
    """Seed multi-year historical emissions data."""
    
    print("=== Seeding Historical Emissions Data ===\n")
    
    user = User.objects.first()
    
    # Get modules
    modules = {m.scope: m for m in Module.objects.all() if m.scope}
    if not modules:
        print("Error: No modules found.")
        return
    
    # Get emission factors
    electricity_ef = EmissionFactor.objects.filter(category='electricity').first()
    natural_gas_ef = EmissionFactor.objects.filter(category='stationary_combustion').first()
    transport_ef = EmissionFactor.objects.filter(category='transport').first()
    
    if not electricity_ef:
        print("Error: No electricity emission factor found.")
        return
    
    # Get or create data table for historical data
    module = modules.get(1)  # Use first module
    data_table, created = DataTable.objects.get_or_create(
        name='historical_emissions',
        module=module,
        defaults={
            'title': 'Historical Emissions Data',
            'description': 'Auto-generated historical data for dashboards',
            'version': 1,
            'created_by': user,
            'updated_by': user,
        }
    )
    
    # Create reporting periods for historical years
    years_config = [
        {'year': 2020, 'is_baseline': True, 'status': 'closed', 'name': 'FY 2020 (Baseline)'},
        {'year': 2021, 'is_baseline': False, 'status': 'closed', 'name': 'FY 2021'},
        {'year': 2022, 'is_baseline': False, 'status': 'closed', 'name': 'FY 2022'},
        {'year': 2023, 'is_baseline': False, 'status': 'closed', 'name': 'FY 2023'},
        {'year': 2024, 'is_baseline': False, 'status': 'closed', 'name': 'FY 2024'},
    ]
    
    # Emission reduction trajectory (baseline = 100%, targeting 50% by 2030)
    reduction_trajectory = {
        2020: 1.00,  # Baseline
        2021: 0.97,  # -3%
        2022: 0.93,  # -7%
        2023: 0.88,  # -12%
        2024: 0.82,  # -18%
        2025: 0.75,  # -25% (already seeded)
    }
    
    # Baseline emissions in kg CO2e
    baseline_monthly = {
        'scope1_base': 80000,  # 80 tonnes/month baseline
        'scope2_base': 200000,  # 200 tonnes/month baseline  
        'scope3_base': 25000,  # 25 tonnes/month baseline
    }
    
    # Seasonal adjustment factors
    seasonal_factors = {
        1: 1.15, 2: 1.12, 3: 1.05, 4: 0.95, 5: 0.90, 6: 0.92,
        7: 1.00, 8: 1.02, 9: 0.95, 10: 0.98, 11: 1.05, 12: 1.12,
    }
    
    calculations_created = 0
    
    for config in years_config:
        year = config['year']
        
        # Skip if this year already has significant data
        existing = Calculation.objects.filter(reporting_year=year).count()
        if existing > 10:
            print(f"Year {year}: Already has {existing} calculations, skipping...")
            continue
        
        # Create or get reporting period
        period, created = ReportingPeriod.objects.get_or_create(
            name=config['name'],
            defaults={
                'start_date': date(year, 1, 1),
                'end_date': date(year, 12, 31),
                'period_type': 'annual',
                'status': config['status'],
                'is_baseline': config['is_baseline'],
            }
        )
        
        if created:
            print(f"Created reporting period: {period.name}")
        else:
            print(f"Using existing period: {period.name}")
        
        reduction_factor = reduction_trajectory.get(year, 1.0)
        
        # Generate monthly calculations for this year
        for month in range(1, 13):
            seasonal = seasonal_factors[month]
            random_variance = random.uniform(0.92, 1.08)
            
            # Create DataRow for this month's data
            data_row = DataRow.objects.create(
                data_table=data_table,
                values={'year': year, 'month': month, 'type': 'historical'},
                created_by=user,
                updated_by=user,
            )
            
            # Scope 1 - Stationary Combustion
            if natural_gas_ef and modules.get(1):
                scope1_kg = baseline_monthly['scope1_base'] * reduction_factor * seasonal * random_variance
                Calculation.objects.create(
                    data_row=data_row,
                    module=modules[1],
                    scope=1,
                    category='stationary_combustion',
                    reporting_year=year,
                    reporting_month=month,
                    reporting_period=period,
                    emission_factor=natural_gas_ef,
                    activity_value=Decimal(str(scope1_kg / float(natural_gas_ef.factor_value))),
                    activity_unit=natural_gas_ef.activity_unit or 'm3',
                    co2e_kg=Decimal(str(round(scope1_kg, 2))),
                    calculation_method='factor',
                )
                calculations_created += 1
            
            # Create another DataRow for Scope 2
            data_row2 = DataRow.objects.create(
                data_table=data_table,
                values={'year': year, 'month': month, 'type': 'electricity'},
                created_by=user,
                updated_by=user,
            )
            
            # Scope 2 - Electricity
            if electricity_ef and modules.get(2):
                scope2_kg = baseline_monthly['scope2_base'] * reduction_factor * seasonal * random_variance
                if year >= 2023:
                    scope2_kg *= 0.90  # Extra 10% from renewable energy
                
                Calculation.objects.create(
                    data_row=data_row2,
                    module=modules[2],
                    scope=2,
                    category='electricity',
                    reporting_year=year,
                    reporting_month=month,
                    reporting_period=period,
                    emission_factor=electricity_ef,
                    activity_value=Decimal(str(scope2_kg / float(electricity_ef.factor_value))),
                    activity_unit=electricity_ef.activity_unit or 'kWh',
                    co2e_kg=Decimal(str(round(scope2_kg, 2))),
                    calculation_method='factor',
                )
                calculations_created += 1
            
            # Scope 3 - Business Travel (only some months have data)
            if transport_ef and modules.get(3) and month in [1, 3, 5, 6, 9, 10, 11]:
                data_row3 = DataRow.objects.create(
                    data_table=data_table,
                    values={'year': year, 'month': month, 'type': 'transport'},
                    created_by=user,
                    updated_by=user,
                )
                
                scope3_kg = baseline_monthly['scope3_base'] * reduction_factor * random_variance
                if year in [2020, 2021]:
                    scope3_kg *= 0.40  # Pandemic reduction
                elif year == 2022:
                    scope3_kg *= 0.70
                
                Calculation.objects.create(
                    data_row=data_row3,
                    module=modules[3],
                    scope=3,
                    category='transport',
                    reporting_year=year,
                    reporting_month=month,
                    reporting_period=period,
                    emission_factor=transport_ef,
                    activity_value=Decimal(str(scope3_kg / float(transport_ef.factor_value))),
                    activity_unit=transport_ef.activity_unit or 'km',
                    co2e_kg=Decimal(str(round(scope3_kg, 2))),
                    calculation_method='factor',
                )
                calculations_created += 1
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Created {calculations_created} calculation records")
    
    # Show emissions by year
    from django.db.models import Sum
    print("\n=== Emissions by Year ===")
    yearly = Calculation.objects.values('reporting_year').annotate(
        total=Sum('co2e_kg')
    ).order_by('reporting_year')
    
    for y in yearly:
        tonnes = float(y['total']) / 1000
        print(f"  {y['reporting_year']}: {tonnes:,.0f} tonnes")
    
    # Show scope breakdown for current year
    print("\n=== Current Year (2025) Scope Breakdown ===")
    current = Calculation.objects.filter(reporting_year=2025).values('scope').annotate(
        total=Sum('co2e_kg')
    ).order_by('scope')
    
    for s in current:
        tonnes = float(s['total']) / 1000
        print(f"  Scope {s['scope']}: {tonnes:,.0f} tonnes")

if __name__ == '__main__':
    seed_historical_data()
