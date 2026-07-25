from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from emissions.models import EmissionFactor, GWP
from mdm.models import ReferenceSet, ReferenceValue


class Command(BaseCommand):
    help = 'Seeds Carbon reference data: emission factors, GWP values, and activity unit reference values.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing seeded carbon reference data before seeding.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes.',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.clear = options['clear']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no data will be created or modified'))

        if self.clear and not self.dry_run:
            self.stdout.write('Clearing existing carbon reference data...')
            EmissionFactor.objects.all().delete()
            GWP.objects.all().delete()
            ReferenceValue.objects.filter(reference_set__name='Emission Activity Units').delete()
            ReferenceSet.objects.filter(name='Emission Activity Units').delete()
            self.stdout.write(self.style.SUCCESS('Cleared carbon emission factors, GWP values, and activity units reference data.'))

        try:
            with transaction.atomic():
                gwp_count = self._seed_gwp()
                factors_count = self._seed_emission_factors()
                units_count = self._seed_activity_units()

                self.stdout.write(self.style.SUCCESS(f'Seeded {gwp_count} GWP values'))
                self.stdout.write(self.style.SUCCESS(f'Seeded {factors_count} emission factors'))
                self.stdout.write(self.style.SUCCESS(f'Seeded {units_count} activity unit reference values'))

                if self.dry_run:
                    raise RuntimeError('Dry run rollback')

        except RuntimeError as exc:
            if 'Dry run' in str(exc):
                self.stdout.write(self.style.WARNING('Dry run completed. No changes were saved.'))
            else:
                raise

    def _create_factor(self, data):
        if self.dry_run:
            return 1

        data = data.copy()
        data['factor_value'] = Decimal(str(data['factor_value']))
        data.setdefault('factor_unit', 'kg CO2e')
        data.setdefault('valid_from', date(2024, 1, 1))
        data.setdefault('is_active', True)
        data.setdefault('tags', [])

        EmissionFactor.objects.update_or_create(
            code=data['code'],
            defaults=data,
        )
        return 1

    def _seed_gwp(self):
        gwp_data = [
            {
                'gas_name': 'Carbon Dioxide',
                'gas_formula': 'CO2',
                'gwp_ar6_100yr': Decimal('1'),
                'gwp_ar6_20yr': Decimal('1'),
                'cas_number': '124-38-9',
            },
            {
                'gas_name': 'Methane',
                'gas_formula': 'CH4',
                'gwp_ar6_100yr': Decimal('27.2'),
                'gwp_ar6_20yr': Decimal('80.8'),
                'cas_number': '74-82-8',
            },
            {
                'gas_name': 'Nitrous Oxide',
                'gas_formula': 'N2O',
                'gwp_ar6_100yr': Decimal('273'),
                'gwp_ar6_20yr': Decimal('273'),
                'cas_number': '10024-97-2',
            },
        ]

        count = 0
        for item in gwp_data:
            if self.dry_run:
                count += 1
                continue

            GWP.objects.update_or_create(
                gas_formula=item['gas_formula'],
                defaults={
                    'gas_name': item['gas_name'],
                    'gwp_ar6_100yr': item['gwp_ar6_100yr'],
                    'gwp_ar6_20yr': item['gwp_ar6_20yr'],
                    'cas_number': item['cas_number'],
                },
            )
            count += 1
        return count

    def _seed_emission_factors(self):
        emission_factors = [
            # Scope 1: Direct emissions
            {'code': 'DIESEL_STATIONARY_L', 'name': 'Diesel (Stationary)', 'category': 'stationary_combustion', 'scope': 1, 'factor_value': '2.68', 'activity_unit': 'liter', 'source': 'DEFRA 2024', 'tags': ['diesel', 'stationary', 'fuel']},
            {'code': 'GASOLINE_STATIONARY_L', 'name': 'Gasoline (Stationary)', 'category': 'stationary_combustion', 'scope': 1, 'factor_value': '2.31', 'activity_unit': 'liter', 'source': 'DEFRA 2024', 'tags': ['gasoline', 'stationary', 'fuel']},
            {'code': 'NATURAL_GAS_M3', 'name': 'Natural Gas', 'category': 'stationary_combustion', 'scope': 1, 'factor_value': '1.94', 'activity_unit': 'm³', 'source': 'IPCC AR6', 'tags': ['natural gas', 'fuel', 'combustion']},
            {'code': 'LPG_L', 'name': 'LPG', 'category': 'stationary_combustion', 'scope': 1, 'factor_value': '1.51', 'activity_unit': 'liter', 'source': 'DEFRA 2024', 'tags': ['lpg', 'fuel', 'combustion']},
            {'code': 'FUEL_OIL_L', 'name': 'Fuel Oil', 'category': 'stationary_combustion', 'scope': 1, 'factor_value': '3.11', 'activity_unit': 'liter', 'source': 'DEFRA 2024', 'tags': ['fuel oil', 'combustion']},
            # Scope 2: Indirect energy emissions
            {'code': 'GRID_ELECTRICITY_KWH', 'name': 'Electricity Grid Average', 'category': 'electricity', 'scope': 2, 'factor_value': '0.417', 'activity_unit': 'kWh', 'source': 'EPA 2024', 'tags': ['electricity', 'grid', 'energy']},
            {'code': 'DISTRICT_HEAT_MWH', 'name': 'District Heating', 'category': 'electricity', 'scope': 2, 'factor_value': '0.200', 'activity_unit': 'MWh', 'source': 'IEA 2024', 'tags': ['district heating', 'energy', 'heat']},
            {'code': 'STEAM_TONNE', 'name': 'Steam', 'category': 'electricity', 'scope': 2, 'factor_value': '0.250', 'activity_unit': 'tonne', 'source': 'EPA 2024', 'tags': ['steam', 'energy']},
            # Scope 3: Value chain emissions
            {'code': 'FLIGHT_SHORT_PKM', 'name': 'Short-Haul Flight', 'category': 'transport', 'scope': 3, 'factor_value': '0.155', 'activity_unit': 'passenger-km', 'source': 'DEFRA 2024', 'tags': ['flight', 'air travel']},
            {'code': 'FLIGHT_LONG_PKM', 'name': 'Long-Haul Flight', 'category': 'transport', 'scope': 3, 'factor_value': '0.228', 'activity_unit': 'passenger-km', 'source': 'DEFRA 2024', 'tags': ['flight', 'air travel']},
            {'code': 'COMMUTE_CAR_KM', 'name': 'Commuting by Car', 'category': 'transport', 'scope': 3, 'factor_value': '0.192', 'activity_unit': 'km', 'source': 'DEFRA 2024', 'tags': ['commuting', 'car']},
            {'code': 'COMMUTE_TAXI_KM', 'name': 'Taxi Travel', 'category': 'transport', 'scope': 3, 'factor_value': '0.215', 'activity_unit': 'km', 'source': 'DEFRA 2024', 'tags': ['taxi', 'transport']},
            {'code': 'HOTEL_STAY_N', 'name': 'Hotel Stay', 'category': 'materials', 'scope': 3, 'factor_value': '31.0', 'activity_unit': 'nights', 'source': 'IEA 2024', 'tags': ['hotel', 'travel', 'accommodation']},
            {'code': 'BUS_TRANSIT_PKM', 'name': 'Bus Travel', 'category': 'transport', 'scope': 3, 'factor_value': '0.105', 'activity_unit': 'passenger-km', 'source': 'DEFRA 2024', 'tags': ['bus', 'transport']},
            {'code': 'RAIL_TRANSIT_PKM', 'name': 'Rail Travel', 'category': 'transport', 'scope': 3, 'factor_value': '0.045', 'activity_unit': 'passenger-km', 'source': 'DEFRA 2024', 'tags': ['rail', 'transport']},
            {'code': 'MEALS_KG', 'name': 'Food Consumption', 'category': 'materials', 'scope': 3, 'factor_value': '4.50', 'activity_unit': 'kg', 'source': 'IEA 2024', 'tags': ['food', 'meals']},
            {'code': 'WATER_USE_M3', 'name': 'Water Supply', 'category': 'water', 'scope': 3, 'factor_value': '0.272', 'activity_unit': 'm³', 'source': 'DEFRA 2024', 'tags': ['water', 'utility']},
        ]

        count = 0
        for factor in emission_factors:
            count += self._create_factor(factor)
        return count

    def _seed_activity_units(self):
        values = [
            {'code': 'kWh', 'label': 'kWh', 'description': 'Kilowatt-hours'},
            {'code': 'liters', 'label': 'Liters', 'description': 'Liters'},
            {'code': 'kg', 'label': 'Kilograms', 'description': 'Kilograms'},
            {'code': 'km', 'label': 'Kilometers', 'description': 'Kilometers'},
            {'code': 'passenger-km', 'label': 'Passenger-km', 'description': 'Passenger-kilometers'},
            {'code': 'nights', 'label': 'Nights', 'description': 'Hotel nights / overnight stays'},
        ]

        count = 0
        if self.dry_run:
            return len(values)

        ref_set, _ = ReferenceSet.objects.get_or_create(
            name='Emission Activity Units',
            defaults={'description': 'Standard activity units used by Carbon emission factors.'}
        )

        for index, value in enumerate(values, start=1):
            ReferenceValue.objects.update_or_create(
                reference_set=ref_set,
                code=value['code'],
                defaults={
                    'label': value['label'],
                    'description': value['description'],
                    'sort_order': index,
                    'is_active': True,
                },
            )
            count += 1

        return count
