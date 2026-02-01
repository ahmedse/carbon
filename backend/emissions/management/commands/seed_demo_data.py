"""
Seed demonstration data for Carbon Management Platform showcase.

Creates a complete demo scenario:
- Demo Tenant: "Acme Corporation"
- Demo Project: "FY 2025 Carbon Footprint"
- Reporting Period: Jan 1, 2025 - Dec 31, 2025
- Modules: Scope 1, 2, 3 with realistic data tables and rows
- Calculation Rules linked to emission factors
- Pre-calculated emissions for dashboard visualization

Usage:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --clear  # Clear and recreate
    python manage.py seed_demo_data --dry-run  # Preview only
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import random
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Seeds comprehensive demo data for Carbon Management Platform showcase'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo data before seeding'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be created without making changes'
        )
    
    def handle(self, *args, **options):
        self.dry_run = options.get('dry_run', False)
        self.clear = options.get('clear', False)
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        with transaction.atomic():
            if self.clear:
                self._clear_demo_data()
            
            self._seed_all()
        
        self.stdout.write(self.style.SUCCESS('✅ Demo data seeding complete!'))
    
    def _clear_demo_data(self):
        """Remove existing demo data."""
        from accounts.models import Tenant
        from emissions.models import ReportingPeriod, Calculation, CalculationRule
        
        if self.dry_run:
            self.stdout.write('Would clear demo tenant and related data...')
            return
        
        # First delete calculations that reference the demo tenant
        demo_tenant = Tenant.objects.filter(name='Acme Corporation').first()
        if demo_tenant:
            # Delete calculations first (they have PROTECT on project/module)
            Calculation.objects.filter(project__tenant=demo_tenant).delete()
            # Delete calculation rules
            CalculationRule.objects.filter(data_table__module__project__tenant=demo_tenant).delete()
            # Delete reporting periods
            ReportingPeriod.objects.filter(tenant=demo_tenant).delete()
        
        # Now we can safely delete the tenant (cascades to projects, modules, etc.)
        Tenant.objects.filter(name__icontains='Acme').delete()
        Tenant.objects.filter(name__icontains='Demo').delete()
        
        self.stdout.write(self.style.WARNING('Cleared existing demo data'))
    
    def _seed_all(self):
        """Seed all demo data in order."""
        tenant = self._create_tenant()
        admin_user = self._create_demo_user(tenant)
        project = self._create_project(tenant, admin_user)
        reporting_period = self._create_reporting_period(tenant, project, admin_user)
        
        # Create modules with data tables
        modules = self._create_modules(project, admin_user)
        
        # Create data tables, fields, and rows for each module
        tables_data = {}
        for module in modules:
            tables_data[module.name] = self._create_tables_for_module(module, admin_user)
        
        # Create calculation rules linking data to emission factors
        self._create_calculation_rules(tables_data, admin_user)
        
        # Run calculations to populate the Calculation table
        self._run_calculations(reporting_period, admin_user)
        
        self._print_summary()
    
    def _create_tenant(self):
        """Create Acme Corporation tenant."""
        from accounts.models import Tenant
        
        if self.dry_run:
            self.stdout.write('Would create tenant: Acme Corporation')
            return None
        
        tenant, created = Tenant.objects.get_or_create(
            name='Acme Corporation',
        )
        
        action = 'Created' if created else 'Found existing'
        self.stdout.write(f'  {action} tenant: {tenant.name}')
        return tenant
    
    def _create_demo_user(self, tenant):
        """Create or get demo admin user."""
        from accounts.models import User
        from django.contrib.auth.models import Group
        
        if self.dry_run:
            self.stdout.write('Would create demo user: demo_admin@acme.com')
            return None
        
        user, created = User.objects.get_or_create(
            email='demo_admin@acme.com',
            tenant=tenant,
            defaults={
                'username': 'demo_admin',
                'first_name': 'Demo',
                'last_name': 'Administrator',
                'is_staff': False,
                'is_active': True,
            }
        )
        
        if created:
            user.set_password('demo123!')
            user.save()
        
        # Add admin role if available
        admin_group = Group.objects.filter(name='admin').first()
        if admin_group:
            from accounts.models import ScopedRole
            ScopedRole.objects.get_or_create(
                user=user,
                group=admin_group,
                tenant=tenant,
                defaults={'is_active': True}
            )
        
        action = 'Created' if created else 'Found existing'
        self.stdout.write(f'  {action} user: {user.email}')
        return user
    
    def _create_project(self, tenant, user):
        """Create FY 2025 Carbon Footprint project."""
        from core.models import Project
        
        if self.dry_run:
            self.stdout.write('Would create project: FY 2025 Carbon Footprint')
            return None
        
        project, created = Project.objects.get_or_create(
            tenant=tenant,
            name='FY 2025 Carbon Footprint',
        )
        
        action = 'Created' if created else 'Found existing'
        self.stdout.write(f'  {action} project: {project.name}')
        return project
    
    def _create_reporting_period(self, tenant, project, user):
        """Create FY 2025 reporting period."""
        from emissions.models import ReportingPeriod
        
        if self.dry_run:
            self.stdout.write('Would create reporting period: FY 2025')
            return None
        
        period, created = ReportingPeriod.objects.get_or_create(
            tenant=tenant,
            name='FY 2025',
            defaults={
                'project': project,
                'start_date': date(2025, 1, 1),
                'end_date': date(2025, 12, 31),
                'period_type': 'annual',
                'status': 'open',
                'description': 'Fiscal Year 2025 carbon emissions reporting cycle',
                'is_baseline': True,
                'created_by': user,
            }
        )
        
        action = 'Created' if created else 'Found existing'
        self.stdout.write(f'  {action} reporting period: {period.name}')
        return period
    
    def _create_modules(self, project, user):
        """Create GHG Protocol scope modules."""
        from core.models import Module
        
        modules_config = [
            {
                'name': 'Scope 1 - Direct Emissions',
                'scope': 1,
            },
            {
                'name': 'Scope 2 - Indirect Energy',
                'scope': 2,
            },
            {
                'name': 'Scope 3 - Value Chain',
                'scope': 3,
            },
        ]
        
        if self.dry_run:
            for cfg in modules_config:
                self.stdout.write(f"Would create module: {cfg['name']}")
            return []
        
        modules = []
        for cfg in modules_config:
            module, created = Module.objects.get_or_create(
                project=project,
                name=cfg['name'],
                defaults={
                    'scope': cfg['scope'],
                }
            )
            modules.append(module)
            action = 'Created' if created else 'Found existing'
            self.stdout.write(f"  {action} module: {module.name}")
        
        return modules
    
    def _create_tables_for_module(self, module, user):
        """Create data tables with fields and sample rows for a module."""
        from dataschema.models import DataTable, DataField, DataRow
        
        if self.dry_run:
            self.stdout.write(f'Would create tables for module: {module.name}')
            return {}
        
        tables = {}
        
        if module.scope == 1:
            # Scope 1: Natural Gas, Fleet Vehicles, Refrigerants
            tables['Natural Gas Consumption'] = self._create_natural_gas_table(module, user)
            tables['Fleet Vehicles'] = self._create_fleet_table(module, user)
        
        elif module.scope == 2:
            # Scope 2: Electricity
            tables['Electricity Consumption'] = self._create_electricity_table(module, user)
        
        elif module.scope == 3:
            # Scope 3: Business Travel, Employee Commuting
            tables['Business Travel'] = self._create_business_travel_table(module, user)
            tables['Employee Commuting'] = self._create_commuting_table(module, user)
        
        return tables
    
    def _create_natural_gas_table(self, module, user):
        """Create Natural Gas consumption table with monthly data."""
        from dataschema.models import DataTable, DataField, DataRow
        
        table, _ = DataTable.objects.get_or_create(
            module=module,
            name='natural_gas_consumption',
            defaults={
                'title': 'Natural Gas Consumption',
                'description': 'Monthly natural gas usage for heating and operations',
                'created_by': user,
            }
        )
        
        # Create fields
        fields_config = [
            {'name': 'facility', 'label': 'Facility', 'type': 'select', 
             'options': {'choices': ['HQ Building', 'Warehouse A', 'Manufacturing Plant', 'Data Center']}},
            {'name': 'month', 'label': 'Month', 'type': 'select',
             'options': {'choices': ['January', 'February', 'March', 'April', 'May', 'June', 
                                      'July', 'August', 'September', 'October', 'November', 'December']}},
            {'name': 'consumption_therms', 'label': 'Consumption (therms)', 'type': 'number', 'required': True},
            {'name': 'cost_usd', 'label': 'Cost ($)', 'type': 'number'},
            {'name': 'co2e_emissions', 'label': 'CO2e (kg)', 'type': 'number'},
            {'name': 'reporting_year', 'label': 'Reporting Year', 'type': 'number'},
            {'name': 'reporting_month', 'label': 'Reporting Month', 'type': 'string'},
        ]
        
        fields = {}
        for i, fc in enumerate(fields_config):
            field, _ = DataField.objects.get_or_create(
                data_table=table,
                name=fc['name'],
                defaults={
                    'label': fc['label'],
                    'type': fc['type'],
                    'required': fc.get('required', False),
                    'options': fc.get('options'),
                    'order': i,
                    'created_by': user,
                }
            )
            fields[fc['name']] = field
        
        # Create 12 months of sample data for each facility
        facilities = ['HQ Building', 'Warehouse A', 'Manufacturing Plant', 'Data Center']
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        
        # Natural gas usage varies by season (higher in winter)
        seasonal_factors = [1.8, 1.7, 1.3, 0.8, 0.5, 0.3, 0.3, 0.3, 0.5, 0.9, 1.4, 1.7]
        base_usage = {'HQ Building': 2000, 'Warehouse A': 1500, 'Manufacturing Plant': 5000, 'Data Center': 800}
        
        for facility in facilities:
            for i, month in enumerate(months):
                usage = int(base_usage[facility] * seasonal_factors[i] * (0.9 + random.random() * 0.2))
                cost = round(usage * 1.05, 2)  # ~$1.05 per therm
                
                # Natural gas EF: 5.3 kg CO2e per therm
                co2e = round(usage * 5.3, 2)
                
                DataRow.objects.get_or_create(
                    data_table=table,
                    values={
                        'facility': facility,
                        'month': month,
                        'consumption_therms': usage,
                        'cost_usd': cost,
                        'co2e_emissions': co2e,
                        'reporting_year': 2025,
                        'reporting_month': month,
                    },
                    defaults={'created_by': user}
                )
        
        row_count = DataRow.objects.filter(data_table=table).count()
        self.stdout.write(f'    Created table: {table.title} ({row_count} rows)')
        return {'table': table, 'fields': fields}
    
    def _create_fleet_table(self, module, user):
        """Create Fleet Vehicles table."""
        from dataschema.models import DataTable, DataField, DataRow
        
        table, _ = DataTable.objects.get_or_create(
            module=module,
            name='fleet_vehicles',
            defaults={
                'title': 'Fleet Vehicles',
                'description': 'Company vehicle fuel consumption',
                'created_by': user,
            }
        )
        
        fields_config = [
            {'name': 'vehicle_id', 'label': 'Vehicle ID', 'type': 'string'},
            {'name': 'vehicle_type', 'label': 'Vehicle Type', 'type': 'select',
             'options': {'choices': ['Sedan', 'SUV', 'Pickup Truck', 'Van', 'Light Truck']}},
            {'name': 'fuel_type', 'label': 'Fuel Type', 'type': 'select',
             'options': {'choices': ['Gasoline', 'Diesel', 'Hybrid', 'Electric']}},
            {'name': 'fuel_liters', 'label': 'Fuel (liters)', 'type': 'number', 'required': True},
            {'name': 'distance_km', 'label': 'Distance (km)', 'type': 'number'},
            {'name': 'month', 'label': 'Month', 'type': 'string'},
            {'name': 'co2e_emissions', 'label': 'CO2e (kg)', 'type': 'number'},
            {'name': 'reporting_year', 'label': 'Reporting Year', 'type': 'number'},
            {'name': 'reporting_month', 'label': 'Reporting Month', 'type': 'string'},
        ]
        
        fields = {}
        for i, fc in enumerate(fields_config):
            field, _ = DataField.objects.get_or_create(
                data_table=table,
                name=fc['name'],
                defaults={
                    'label': fc['label'],
                    'type': fc['type'],
                    'required': fc.get('required', False),
                    'options': fc.get('options'),
                    'order': i,
                    'created_by': user,
                }
            )
            fields[fc['name']] = field
        
        # Fleet data: 15 vehicles tracked monthly
        vehicles = [
            ('VH-001', 'Sedan', 'Gasoline', 120),
            ('VH-002', 'SUV', 'Gasoline', 180),
            ('VH-003', 'Pickup Truck', 'Diesel', 250),
            ('VH-004', 'Van', 'Diesel', 300),
            ('VH-005', 'Sedan', 'Hybrid', 60),
            ('VH-006', 'Light Truck', 'Diesel', 350),
            ('VH-007', 'SUV', 'Gasoline', 200),
            ('VH-008', 'Sedan', 'Gasoline', 100),
            ('VH-009', 'Van', 'Diesel', 280),
            ('VH-010', 'Pickup Truck', 'Gasoline', 220),
        ]
        
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        
        # Emission factors: kg CO2e per liter
        ef_map = {'Gasoline': 2.31, 'Diesel': 2.68, 'Hybrid': 1.15, 'Electric': 0}
        
        for vid, vtype, fuel, base_liters in vehicles:
            for month in months:
                # Vary fuel usage slightly by month
                liters = int(base_liters * (0.85 + random.random() * 0.3))
                distance = int(liters * 10)  # ~10 km per liter average
                co2e = round(liters * ef_map[fuel], 2)
                
                DataRow.objects.get_or_create(
                    data_table=table,
                    values={
                        'vehicle_id': vid,
                        'vehicle_type': vtype,
                        'fuel_type': fuel,
                        'fuel_liters': liters,
                        'distance_km': distance,
                        'month': month,
                        'co2e_emissions': co2e,
                        'reporting_year': 2025,
                        'reporting_month': month,
                    },
                    defaults={'created_by': user}
                )
        
        row_count = DataRow.objects.filter(data_table=table).count()
        self.stdout.write(f'    Created table: {table.title} ({row_count} rows)')
        return {'table': table, 'fields': fields}
    
    def _create_electricity_table(self, module, user):
        """Create Electricity consumption table."""
        from dataschema.models import DataTable, DataField, DataRow
        
        table, _ = DataTable.objects.get_or_create(
            module=module,
            name='electricity_consumption',
            defaults={
                'title': 'Electricity Consumption',
                'description': 'Monthly electricity usage by facility',
                'created_by': user,
            }
        )
        
        fields_config = [
            {'name': 'facility', 'label': 'Facility', 'type': 'select',
             'options': {'choices': ['HQ Building', 'Warehouse A', 'Manufacturing Plant', 'Data Center']}},
            {'name': 'month', 'label': 'Month', 'type': 'string'},
            {'name': 'consumption_kwh', 'label': 'Consumption (kWh)', 'type': 'number', 'required': True},
            {'name': 'renewable_kwh', 'label': 'Renewable (kWh)', 'type': 'number'},
            {'name': 'grid_kwh', 'label': 'Grid (kWh)', 'type': 'number'},
            {'name': 'cost_usd', 'label': 'Cost ($)', 'type': 'number'},
            {'name': 'co2e_emissions', 'label': 'CO2e (kg)', 'type': 'number'},
            {'name': 'reporting_year', 'label': 'Reporting Year', 'type': 'number'},
            {'name': 'reporting_month', 'label': 'Reporting Month', 'type': 'string'},
        ]
        
        fields = {}
        for i, fc in enumerate(fields_config):
            field, _ = DataField.objects.get_or_create(
                data_table=table,
                name=fc['name'],
                defaults={
                    'label': fc['label'],
                    'type': fc['type'],
                    'required': fc.get('required', False),
                    'options': fc.get('options'),
                    'order': i,
                    'created_by': user,
                }
            )
            fields[fc['name']] = field
        
        facilities = ['HQ Building', 'Warehouse A', 'Manufacturing Plant', 'Data Center']
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        
        # Electricity usage - higher in summer for AC
        seasonal_factors = [0.9, 0.85, 0.9, 1.0, 1.1, 1.3, 1.4, 1.4, 1.2, 1.0, 0.9, 0.95]
        base_kwh = {'HQ Building': 50000, 'Warehouse A': 30000, 'Manufacturing Plant': 150000, 'Data Center': 200000}
        renewable_pct = {'HQ Building': 0.2, 'Warehouse A': 0.1, 'Manufacturing Plant': 0.05, 'Data Center': 0.3}
        
        for facility in facilities:
            for i, month in enumerate(months):
                total_kwh = int(base_kwh[facility] * seasonal_factors[i] * (0.95 + random.random() * 0.1))
                renewable = int(total_kwh * renewable_pct[facility])
                grid = total_kwh - renewable
                cost = round(total_kwh * 0.12, 2)  # $0.12 per kWh
                
                # US Grid Average: 0.417 kg CO2e per kWh (grid only, renewable is zero)
                co2e = round(grid * 0.417, 2)
                
                DataRow.objects.get_or_create(
                    data_table=table,
                    values={
                        'facility': facility,
                        'month': month,
                        'consumption_kwh': total_kwh,
                        'renewable_kwh': renewable,
                        'grid_kwh': grid,
                        'cost_usd': cost,
                        'co2e_emissions': co2e,
                        'reporting_year': 2025,
                        'reporting_month': month,
                    },
                    defaults={'created_by': user}
                )
        
        row_count = DataRow.objects.filter(data_table=table).count()
        self.stdout.write(f'    Created table: {table.title} ({row_count} rows)')
        return {'table': table, 'fields': fields}
    
    def _create_business_travel_table(self, module, user):
        """Create Business Travel table."""
        from dataschema.models import DataTable, DataField, DataRow
        
        table, _ = DataTable.objects.get_or_create(
            module=module,
            name='business_travel',
            defaults={
                'title': 'Business Travel',
                'description': 'Air travel and ground transportation',
                'created_by': user,
            }
        )
        
        fields_config = [
            {'name': 'traveler', 'label': 'Traveler', 'type': 'string'},
            {'name': 'trip_type', 'label': 'Trip Type', 'type': 'select',
             'options': {'choices': ['Domestic Flight', 'International Flight', 'Rail', 'Rental Car']}},
            {'name': 'origin', 'label': 'Origin', 'type': 'string'},
            {'name': 'destination', 'label': 'Destination', 'type': 'string'},
            {'name': 'distance_km', 'label': 'Distance (km)', 'type': 'number', 'required': True},
            {'name': 'flight_class', 'label': 'Flight Class', 'type': 'select',
             'options': {'choices': ['Economy', 'Business', 'First']}},
            {'name': 'travel_date', 'label': 'Travel Date', 'type': 'date'},
            {'name': 'co2e_emissions', 'label': 'CO2e (kg)', 'type': 'number'},
            {'name': 'reporting_year', 'label': 'Reporting Year', 'type': 'number'},
            {'name': 'reporting_month', 'label': 'Reporting Month', 'type': 'string'},
        ]
        
        fields = {}
        for i, fc in enumerate(fields_config):
            field, _ = DataField.objects.get_or_create(
                data_table=table,
                name=fc['name'],
                defaults={
                    'label': fc['label'],
                    'type': fc['type'],
                    'required': fc.get('required', False),
                    'options': fc.get('options'),
                    'order': i,
                    'created_by': user,
                }
            )
            fields[fc['name']] = field
        
        # Sample business trips
        trips = [
            ('John Smith', 'Domestic Flight', 'New York', 'Los Angeles', 3950, 'Economy', 'January'),
            ('Jane Doe', 'International Flight', 'New York', 'London', 5580, 'Business', 'February'),
            ('Bob Johnson', 'Domestic Flight', 'Chicago', 'Miami', 1980, 'Economy', 'March'),
            ('Alice Williams', 'Rail', 'Boston', 'New York', 350, 'Economy', 'March'),
            ('John Smith', 'Rental Car', 'Los Angeles', 'San Francisco', 615, 'Economy', 'April'),
            ('Jane Doe', 'Domestic Flight', 'San Francisco', 'Seattle', 1100, 'Economy', 'May'),
            ('Bob Johnson', 'International Flight', 'Chicago', 'Tokyo', 10150, 'Business', 'June'),
            ('Charlie Brown', 'Domestic Flight', 'Dallas', 'Denver', 1030, 'Economy', 'July'),
            ('Diana Prince', 'Rail', 'Washington DC', 'Philadelphia', 220, 'Economy', 'August'),
            ('Edward Norton', 'Domestic Flight', 'Miami', 'Atlanta', 1050, 'Economy', 'September'),
            ('Frank Castle', 'International Flight', 'New York', 'Paris', 5840, 'First', 'October'),
            ('Grace Kelly', 'Rental Car', 'Denver', 'Salt Lake City', 830, 'Economy', 'November'),
            ('Henry Ford', 'Domestic Flight', 'Detroit', 'Houston', 1950, 'Economy', 'December'),
        ]
        
        # Emission factors (kg CO2e per passenger-km)
        ef_map = {
            ('Domestic Flight', 'Economy'): 0.255,
            ('Domestic Flight', 'Business'): 0.382,
            ('Domestic Flight', 'First'): 0.765,
            ('International Flight', 'Economy'): 0.195,
            ('International Flight', 'Business'): 0.566,
            ('International Flight', 'First'): 0.780,
            ('Rail', 'Economy'): 0.041,
            ('Rental Car', 'Economy'): 0.171,
        }
        
        months_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
            'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
        }
        
        for traveler, trip_type, origin, dest, dist, flight_class, month in trips:
            ef_key = (trip_type, flight_class) if trip_type in ['Domestic Flight', 'International Flight'] else (trip_type, 'Economy')
            co2e = round(dist * ef_map.get(ef_key, 0.2), 2)
            travel_date = date(2025, months_map[month], random.randint(1, 28))
            
            DataRow.objects.get_or_create(
                data_table=table,
                values={
                    'traveler': traveler,
                    'trip_type': trip_type,
                    'origin': origin,
                    'destination': dest,
                    'distance_km': dist,
                    'flight_class': flight_class,
                    'travel_date': travel_date.isoformat(),
                    'co2e_emissions': co2e,
                    'reporting_year': 2025,
                    'reporting_month': month,
                },
                defaults={'created_by': user}
            )
        
        row_count = DataRow.objects.filter(data_table=table).count()
        self.stdout.write(f'    Created table: {table.title} ({row_count} rows)')
        return {'table': table, 'fields': fields}
    
    def _create_commuting_table(self, module, user):
        """Create Employee Commuting table."""
        from dataschema.models import DataTable, DataField, DataRow
        
        table, _ = DataTable.objects.get_or_create(
            module=module,
            name='employee_commuting',
            defaults={
                'title': 'Employee Commuting',
                'description': 'Employee commute patterns and emissions',
                'created_by': user,
            }
        )
        
        fields_config = [
            {'name': 'department', 'label': 'Department', 'type': 'select',
             'options': {'choices': ['Engineering', 'Sales', 'Operations', 'Finance', 'HR', 'Marketing']}},
            {'name': 'commute_mode', 'label': 'Commute Mode', 'type': 'select',
             'options': {'choices': ['Car (Solo)', 'Carpool', 'Public Transit', 'Bicycle', 'Remote']}},
            {'name': 'employees', 'label': 'Employee Count', 'type': 'number', 'required': True},
            {'name': 'avg_distance_km', 'label': 'Avg Distance (km one-way)', 'type': 'number', 'required': True},
            {'name': 'working_days', 'label': 'Working Days/Month', 'type': 'number'},
            {'name': 'month', 'label': 'Month', 'type': 'string'},
            {'name': 'co2e_emissions', 'label': 'CO2e (kg)', 'type': 'number'},
            {'name': 'reporting_year', 'label': 'Reporting Year', 'type': 'number'},
            {'name': 'reporting_month', 'label': 'Reporting Month', 'type': 'string'},
        ]
        
        fields = {}
        for i, fc in enumerate(fields_config):
            field, _ = DataField.objects.get_or_create(
                data_table=table,
                name=fc['name'],
                defaults={
                    'label': fc['label'],
                    'type': fc['type'],
                    'required': fc.get('required', False),
                    'options': fc.get('options'),
                    'order': i,
                    'created_by': user,
                }
            )
            fields[fc['name']] = field
        
        departments = ['Engineering', 'Sales', 'Operations', 'Finance', 'HR', 'Marketing']
        modes = ['Car (Solo)', 'Carpool', 'Public Transit', 'Bicycle', 'Remote']
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        
        # Emission factors (kg CO2e per km)
        ef_map = {'Car (Solo)': 0.171, 'Carpool': 0.086, 'Public Transit': 0.089, 'Bicycle': 0, 'Remote': 0}
        
        # Employee distribution by department and mode
        dept_sizes = {'Engineering': 80, 'Sales': 40, 'Operations': 60, 'Finance': 25, 'HR': 15, 'Marketing': 30}
        mode_pct = {'Car (Solo)': 0.45, 'Carpool': 0.15, 'Public Transit': 0.20, 'Bicycle': 0.05, 'Remote': 0.15}
        
        for dept in departments:
            for mode in modes:
                employees = int(dept_sizes[dept] * mode_pct[mode])
                if employees == 0:
                    continue
                    
                avg_dist = random.randint(10, 30)  # 10-30 km one-way
                
                for month in months:
                    working_days = 22 if month not in ['December'] else 18
                    # Total km = employees * 2 (round trip) * avg_dist * working_days
                    total_km = employees * 2 * avg_dist * working_days
                    co2e = round(total_km * ef_map[mode], 2)
                    
                    DataRow.objects.get_or_create(
                        data_table=table,
                        values={
                            'department': dept,
                            'commute_mode': mode,
                            'employees': employees,
                            'avg_distance_km': avg_dist,
                            'working_days': working_days,
                            'month': month,
                            'co2e_emissions': co2e,
                            'reporting_year': 2025,
                            'reporting_month': month,
                        },
                        defaults={'created_by': user}
                    )
        
        row_count = DataRow.objects.filter(data_table=table).count()
        self.stdout.write(f'    Created table: {table.title} ({row_count} rows)')
        return {'table': table, 'fields': fields}
    
    def _create_calculation_rules(self, tables_data, user):
        """Create calculation rules linking data fields to emission factors."""
        from emissions.models import CalculationRule, EmissionFactor
        
        if self.dry_run:
            self.stdout.write('Would create calculation rules...')
            return
        
        rules_config = []
        
        # Natural Gas rule
        if 'Natural Gas Consumption' in tables_data.get('Scope 1 - Direct Emissions', {}):
            tbl_data = tables_data['Scope 1 - Direct Emissions']['Natural Gas Consumption']
            ef = EmissionFactor.objects.filter(code='FUEL_NAT_GAS_THERM').first()
            if ef and 'consumption_therms' in tbl_data['fields']:
                rules_config.append({
                    'name': 'Natural Gas → CO2e',
                    'data_table': tbl_data['table'],
                    'activity_field': tbl_data['fields']['consumption_therms'],
                    'output_field': tbl_data['fields'].get('co2e_emissions'),
                    'emission_factor': ef,
                })
        
        # Fleet Vehicles rule (gasoline)
        if 'Fleet Vehicles' in tables_data.get('Scope 1 - Direct Emissions', {}):
            tbl_data = tables_data['Scope 1 - Direct Emissions']['Fleet Vehicles']
            ef = EmissionFactor.objects.filter(code='FUEL_PETROL_L').first()
            if ef and 'fuel_liters' in tbl_data['fields']:
                rules_config.append({
                    'name': 'Fleet Fuel → CO2e',
                    'data_table': tbl_data['table'],
                    'activity_field': tbl_data['fields']['fuel_liters'],
                    'output_field': tbl_data['fields'].get('co2e_emissions'),
                    'emission_factor': ef,
                    'factor_selector_field': tbl_data['fields'].get('fuel_type'),
                    'factor_selector_mapping': {
                        'Gasoline': 'FUEL_PETROL_L',
                        'Diesel': 'FUEL_DIESEL_L',
                        'Hybrid': 'FUEL_PETROL_L',  # Use gasoline but with lower consumption
                    }
                })
        
        # Electricity rule
        if 'Electricity Consumption' in tables_data.get('Scope 2 - Indirect Energy', {}):
            tbl_data = tables_data['Scope 2 - Indirect Energy']['Electricity Consumption']
            ef = EmissionFactor.objects.filter(code='US_GRID_AVG').first()
            if ef and 'grid_kwh' in tbl_data['fields']:
                rules_config.append({
                    'name': 'Electricity (Grid) → CO2e',
                    'data_table': tbl_data['table'],
                    'activity_field': tbl_data['fields']['grid_kwh'],
                    'output_field': tbl_data['fields'].get('co2e_emissions'),
                    'emission_factor': ef,
                })
        
        # Business Travel rule
        if 'Business Travel' in tables_data.get('Scope 3 - Value Chain', {}):
            tbl_data = tables_data['Scope 3 - Value Chain']['Business Travel']
            ef = EmissionFactor.objects.filter(code='FLIGHT_SHORT_ECO').first()
            if ef and 'distance_km' in tbl_data['fields']:
                rules_config.append({
                    'name': 'Business Travel → CO2e',
                    'data_table': tbl_data['table'],
                    'activity_field': tbl_data['fields']['distance_km'],
                    'output_field': tbl_data['fields'].get('co2e_emissions'),
                    'emission_factor': ef,
                })
        
        for cfg in rules_config:
            rule, created = CalculationRule.objects.get_or_create(
                data_table=cfg['data_table'],
                activity_field=cfg['activity_field'],
                emission_factor=cfg['emission_factor'],
                defaults={
                    'name': cfg['name'],
                    'output_field': cfg.get('output_field'),
                    'factor_selector_field': cfg.get('factor_selector_field'),
                    'factor_selector_mapping': cfg.get('factor_selector_mapping'),
                    'is_active': True,
                    'auto_calculate': True,
                    'created_by': user,
                }
            )
            action = 'Created' if created else 'Found existing'
            self.stdout.write(f'  {action} rule: {rule.name}')
    
    def _run_calculations(self, reporting_period, user):
        """Execute calculations for all data rows."""
        from emissions.models import CalculationRule, Calculation
        from dataschema.models import DataRow
        
        if self.dry_run:
            self.stdout.write('Would run calculations...')
            return
        
        # Clear existing calculations for clean demo
        Calculation.objects.all().delete()
        
        # Get all rules
        rules = CalculationRule.objects.filter(is_active=True)
        
        total_created = 0
        for rule in rules:
            created, skipped, errors = rule.calculate_for_table(
                reporting_period=reporting_period,
                user=user,
                recalculate=True
            )
            total_created += created
            self.stdout.write(f'  Rule "{rule.name}": {created} calculations created')
        
        self.stdout.write(f'\n  Total calculations created: {total_created}')
    
    def _print_summary(self):
        """Print summary of created data."""
        from accounts.models import Tenant
        from core.models import Project, Module
        from dataschema.models import DataTable, DataRow
        from emissions.models import ReportingPeriod, Calculation, CalculationRule
        
        if self.dry_run:
            return
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('DEMO DATA SUMMARY'))
        self.stdout.write('='*60)
        
        tenant = Tenant.objects.filter(name='Acme Corporation').first()
        if tenant:
            self.stdout.write(f'\nTenant: {tenant.name}')
            
            projects = Project.objects.filter(tenant=tenant)
            for project in projects:
                self.stdout.write(f'\n  Project: {project.name}')
                
                modules = Module.objects.filter(project=project)
                for module in modules:
                    self.stdout.write(f'\n    Module: {module.name} (Scope {module.scope})')
                    
                    tables = DataTable.objects.filter(module=module)
                    for table in tables:
                        row_count = DataRow.objects.filter(data_table=table).count()
                        self.stdout.write(f'      - {table.title}: {row_count} rows')
        
        # Emission totals
        calcs = Calculation.objects.all()
        scope_totals = {}
        for calc in calcs:
            scope = calc.scope
            scope_totals[scope] = scope_totals.get(scope, Decimal('0')) + calc.co2e_kg
        
        self.stdout.write('\n' + '-'*60)
        self.stdout.write(self.style.SUCCESS('EMISSION TOTALS (FY 2025)'))
        self.stdout.write('-'*60)
        
        grand_total = Decimal('0')
        for scope in [1, 2, 3]:
            total = scope_totals.get(scope, Decimal('0'))
            tonnes = total / 1000
            grand_total += total
            self.stdout.write(f'  Scope {scope}: {tonnes:,.2f} tonnes CO2e')
        
        self.stdout.write(f'\n  TOTAL: {grand_total/1000:,.2f} tonnes CO2e')
        self.stdout.write('='*60 + '\n')
        
        # Login credentials
        self.stdout.write(self.style.SUCCESS('\nDEMO LOGIN:'))
        self.stdout.write('  Email: demo_admin@acme.com')
        self.stdout.write('  Password: demo123!')
        self.stdout.write('')
