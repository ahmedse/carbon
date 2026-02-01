"""
Management command to seed emission factors and GWP values.

Usage:
    python manage.py seed_emission_factors
    python manage.py seed_emission_factors --category=electricity
    python manage.py seed_emission_factors --clear
    python manage.py seed_emission_factors --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from emissions.models import EmissionFactor, GWP
from datetime import date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seeds the database with emission factors and GWP values'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            type=str,
            help='Seed only a specific category (electricity, stationary_combustion, mobile_combustion, transport, fugitive, waste, water)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )

    def handle(self, *args, **options):
        self.dry_run = options.get('dry_run', False)
        self.verbosity = options.get('verbosity', 1)
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        if options.get('clear') and not self.dry_run:
            self.stdout.write('Clearing existing data...')
            EmissionFactor.objects.all().delete()
            GWP.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared all emission factors and GWP values'))
        
        category_filter = options.get('category')
        
        try:
            with transaction.atomic():
                # Seed GWP values first (no category filter applies)
                if not category_filter:
                    gwp_count = self._seed_gwp()
                    self.stdout.write(self.style.SUCCESS(f'Seeded {gwp_count} GWP values'))
                
                # Seed emission factors by category
                total_ef = 0
                
                categories = {
                    'electricity': self._seed_electricity_factors,
                    'stationary_combustion': self._seed_stationary_combustion_factors,
                    'mobile_combustion': self._seed_mobile_combustion_factors,
                    'transport': self._seed_transport_factors,
                    'fugitive': self._seed_fugitive_factors,
                    'waste': self._seed_waste_factors,
                    'water': self._seed_water_factors,
                }
                
                if category_filter:
                    if category_filter in categories:
                        count = categories[category_filter]()
                        total_ef += count
                        self.stdout.write(self.style.SUCCESS(f'Seeded {count} {category_filter} factors'))
                    else:
                        self.stdout.write(self.style.ERROR(f'Unknown category: {category_filter}'))
                        self.stdout.write(f'Available: {", ".join(categories.keys())}')
                        return
                else:
                    for cat_name, seed_func in categories.items():
                        count = seed_func()
                        total_ef += count
                        self.stdout.write(f'  {cat_name}: {count} factors')
                
                if self.dry_run:
                    raise Exception('Dry run - rolling back')
                    
        except Exception as e:
            if 'Dry run' in str(e):
                self.stdout.write(self.style.WARNING(f'Would have seeded {total_ef} emission factors'))
            else:
                raise
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully seeded {total_ef} emission factors'))

    def _create_factor(self, **kwargs):
        """Create or update an emission factor."""
        code = kwargs.get('code')
        defaults = {k: v for k, v in kwargs.items() if k != 'code'}
        
        # Ensure factor_value is Decimal
        if 'factor_value' in defaults:
            defaults['factor_value'] = Decimal(str(defaults['factor_value']))
        
        # Set defaults
        defaults.setdefault('factor_unit', 'kg CO2e')
        defaults.setdefault('valid_from', date(2024, 1, 1))
        defaults.setdefault('is_active', True)
        defaults.setdefault('tags', [])
        
        if self.dry_run:
            return 1
        
        obj, created = EmissionFactor.objects.update_or_create(
            code=code,
            defaults=defaults
        )
        return 1

    def _seed_gwp(self):
        """Seed Global Warming Potential values."""
        gwp_data = [
            {'gas_name': 'Carbon Dioxide', 'gas_formula': 'CO2', 'gwp_ar5_100yr': 1, 'gwp_ar6_100yr': 1, 'gwp_ar5_20yr': 1, 'gwp_ar6_20yr': 1, 'cas_number': '124-38-9'},
            {'gas_name': 'Methane (Fossil)', 'gas_formula': 'CH4', 'gwp_ar5_100yr': 30, 'gwp_ar6_100yr': 29.8, 'gwp_ar5_20yr': 85, 'gwp_ar6_20yr': 82.5, 'cas_number': '74-82-8'},
            {'gas_name': 'Methane (Biogenic)', 'gas_formula': 'CH4_BIO', 'gwp_ar5_100yr': 28, 'gwp_ar6_100yr': 27.2, 'gwp_ar5_20yr': 84, 'gwp_ar6_20yr': 80.8, 'cas_number': '74-82-8'},
            {'gas_name': 'Nitrous Oxide', 'gas_formula': 'N2O', 'gwp_ar5_100yr': 265, 'gwp_ar6_100yr': 273, 'gwp_ar5_20yr': 264, 'gwp_ar6_20yr': 273, 'cas_number': '10024-97-2'},
            {'gas_name': 'Sulfur Hexafluoride', 'gas_formula': 'SF6', 'gwp_ar5_100yr': 23500, 'gwp_ar6_100yr': 25200, 'gwp_ar5_20yr': 17500, 'gwp_ar6_20yr': 18300, 'cas_number': '2551-62-4'},
            {'gas_name': 'Nitrogen Trifluoride', 'gas_formula': 'NF3', 'gwp_ar5_100yr': 16100, 'gwp_ar6_100yr': 17400, 'gwp_ar5_20yr': 12800, 'gwp_ar6_20yr': 13400, 'cas_number': '7783-54-2'},
            {'gas_name': 'HFC-23', 'gas_formula': 'CHF3', 'gwp_ar5_100yr': 12400, 'gwp_ar6_100yr': 14600, 'gwp_ar5_20yr': 10800, 'gwp_ar6_20yr': 12400, 'cas_number': '75-46-7'},
            {'gas_name': 'HFC-32', 'gas_formula': 'CH2F2', 'gwp_ar5_100yr': 677, 'gwp_ar6_100yr': 771, 'gwp_ar5_20yr': 2430, 'gwp_ar6_20yr': 2693, 'cas_number': '75-10-5'},
            {'gas_name': 'HFC-125', 'gas_formula': 'CHF2CF3', 'gwp_ar5_100yr': 3170, 'gwp_ar6_100yr': 3740, 'gwp_ar5_20yr': 6090, 'gwp_ar6_20yr': 6740, 'cas_number': '354-33-6'},
            {'gas_name': 'HFC-134a', 'gas_formula': 'CH2FCF3', 'gwp_ar5_100yr': 1300, 'gwp_ar6_100yr': 1530, 'gwp_ar5_20yr': 3790, 'gwp_ar6_20yr': 4144, 'cas_number': '811-97-2'},
            {'gas_name': 'HFC-143a', 'gas_formula': 'CH3CF3', 'gwp_ar5_100yr': 4800, 'gwp_ar6_100yr': 5810, 'gwp_ar5_20yr': 6940, 'gwp_ar6_20yr': 7840, 'cas_number': '420-46-2'},
            {'gas_name': 'HFC-152a', 'gas_formula': 'CH3CHF2', 'gwp_ar5_100yr': 138, 'gwp_ar6_100yr': 164, 'gwp_ar5_20yr': 506, 'gwp_ar6_20yr': 591, 'cas_number': '75-37-6'},
            {'gas_name': 'PFC-14 (CF4)', 'gas_formula': 'CF4', 'gwp_ar5_100yr': 6630, 'gwp_ar6_100yr': 7380, 'gwp_ar5_20yr': 4880, 'gwp_ar6_20yr': 5300, 'cas_number': '75-73-0'},
            {'gas_name': 'PFC-116 (C2F6)', 'gas_formula': 'C2F6', 'gwp_ar5_100yr': 11100, 'gwp_ar6_100yr': 12400, 'gwp_ar5_20yr': 8210, 'gwp_ar6_20yr': 8940, 'cas_number': '76-16-4'},
        ]
        
        count = 0
        for data in gwp_data:
            if self.dry_run:
                count += 1
                continue
            
            GWP.objects.update_or_create(
                gas_formula=data['gas_formula'],
                defaults={
                    'gas_name': data['gas_name'],
                    'gwp_ar5_100yr': Decimal(str(data['gwp_ar5_100yr'])),
                    'gwp_ar6_100yr': Decimal(str(data['gwp_ar6_100yr'])),
                    'gwp_ar5_20yr': Decimal(str(data['gwp_ar5_20yr'])),
                    'gwp_ar6_20yr': Decimal(str(data['gwp_ar6_20yr'])),
                    'cas_number': data.get('cas_number', ''),
                }
            )
            count += 1
        
        return count

    def _seed_electricity_factors(self):
        """Seed electricity grid emission factors - 50+ countries."""
        electricity_data = [
            # Americas
            {'code': 'US_GRID_AVG', 'name': 'United States Grid Average', 'factor_value': 0.417, 'country': 'United States', 'country_code': 'USA', 'source': 'EPA eGRID 2024', 'tags': ['electricity', 'grid', 'power', 'kwh', 'usa', 'us', 'america']},
            {'code': 'US_GRID_CA', 'name': 'United States - California', 'factor_value': 0.225, 'country': 'United States', 'country_code': 'USA', 'region': 'California', 'source': 'EPA eGRID 2024', 'tags': ['electricity', 'grid', 'california', 'ca']},
            {'code': 'US_GRID_TX', 'name': 'United States - Texas', 'factor_value': 0.401, 'country': 'United States', 'country_code': 'USA', 'region': 'Texas', 'source': 'EPA eGRID 2024', 'tags': ['electricity', 'grid', 'texas', 'tx']},
            {'code': 'US_GRID_NY', 'name': 'United States - New York', 'factor_value': 0.245, 'country': 'United States', 'country_code': 'USA', 'region': 'New York', 'source': 'EPA eGRID 2024', 'tags': ['electricity', 'grid', 'new york', 'ny']},
            {'code': 'CA_GRID', 'name': 'Canada Grid Average', 'factor_value': 0.110, 'country': 'Canada', 'country_code': 'CAN', 'source': 'CER 2024', 'tags': ['electricity', 'grid', 'canada']},
            {'code': 'MX_GRID', 'name': 'Mexico Grid Average', 'factor_value': 0.435, 'country': 'Mexico', 'country_code': 'MEX', 'source': 'CFE 2024', 'tags': ['electricity', 'grid', 'mexico']},
            {'code': 'BR_GRID', 'name': 'Brazil Grid Average', 'factor_value': 0.074, 'country': 'Brazil', 'country_code': 'BRA', 'source': 'MCTI 2024', 'tags': ['electricity', 'grid', 'brazil']},
            {'code': 'AR_GRID', 'name': 'Argentina Grid Average', 'factor_value': 0.350, 'country': 'Argentina', 'country_code': 'ARG', 'source': 'CAMMESA 2024', 'tags': ['electricity', 'grid', 'argentina']},
            {'code': 'CL_GRID', 'name': 'Chile Grid Average', 'factor_value': 0.370, 'country': 'Chile', 'country_code': 'CHL', 'source': 'CNE 2024', 'tags': ['electricity', 'grid', 'chile']},
            {'code': 'CO_GRID', 'name': 'Colombia Grid Average', 'factor_value': 0.180, 'country': 'Colombia', 'country_code': 'COL', 'source': 'XM 2024', 'tags': ['electricity', 'grid', 'colombia']},
            {'code': 'PE_GRID', 'name': 'Peru Grid Average', 'factor_value': 0.250, 'country': 'Peru', 'country_code': 'PER', 'source': 'MINEM 2024', 'tags': ['electricity', 'grid', 'peru']},
            # Europe
            {'code': 'GB_GRID', 'name': 'United Kingdom Grid', 'factor_value': 0.207, 'country': 'United Kingdom', 'country_code': 'GBR', 'source': 'UK DEFRA 2024', 'tags': ['electricity', 'grid', 'uk', 'britain', 'england']},
            {'code': 'DE_GRID', 'name': 'Germany Grid', 'factor_value': 0.366, 'country': 'Germany', 'country_code': 'DEU', 'source': 'UBA 2024', 'tags': ['electricity', 'grid', 'germany', 'deutschland']},
            {'code': 'FR_GRID', 'name': 'France Grid', 'factor_value': 0.052, 'country': 'France', 'country_code': 'FRA', 'source': 'RTE 2024', 'tags': ['electricity', 'grid', 'france']},
            {'code': 'IT_GRID', 'name': 'Italy Grid', 'factor_value': 0.256, 'country': 'Italy', 'country_code': 'ITA', 'source': 'ISPRA 2024', 'tags': ['electricity', 'grid', 'italy']},
            {'code': 'ES_GRID', 'name': 'Spain Grid', 'factor_value': 0.160, 'country': 'Spain', 'country_code': 'ESP', 'source': 'REE 2024', 'tags': ['electricity', 'grid', 'spain']},
            {'code': 'PT_GRID', 'name': 'Portugal Grid', 'factor_value': 0.180, 'country': 'Portugal', 'country_code': 'PRT', 'source': 'REN 2024', 'tags': ['electricity', 'grid', 'portugal']},
            {'code': 'NL_GRID', 'name': 'Netherlands Grid', 'factor_value': 0.328, 'country': 'Netherlands', 'country_code': 'NLD', 'source': 'CBS 2024', 'tags': ['electricity', 'grid', 'netherlands', 'holland']},
            {'code': 'BE_GRID', 'name': 'Belgium Grid', 'factor_value': 0.170, 'country': 'Belgium', 'country_code': 'BEL', 'source': 'Elia 2024', 'tags': ['electricity', 'grid', 'belgium']},
            {'code': 'AT_GRID', 'name': 'Austria Grid', 'factor_value': 0.087, 'country': 'Austria', 'country_code': 'AUT', 'source': 'E-Control 2024', 'tags': ['electricity', 'grid', 'austria']},
            {'code': 'CH_GRID', 'name': 'Switzerland Grid', 'factor_value': 0.015, 'country': 'Switzerland', 'country_code': 'CHE', 'source': 'BFE 2024', 'tags': ['electricity', 'grid', 'switzerland']},
            {'code': 'PL_GRID', 'name': 'Poland Grid', 'factor_value': 0.670, 'country': 'Poland', 'country_code': 'POL', 'source': 'URE 2024', 'tags': ['electricity', 'grid', 'poland']},
            {'code': 'CZ_GRID', 'name': 'Czech Republic Grid', 'factor_value': 0.395, 'country': 'Czech Republic', 'country_code': 'CZE', 'source': 'ERU 2024', 'tags': ['electricity', 'grid', 'czech']},
            {'code': 'HU_GRID', 'name': 'Hungary Grid', 'factor_value': 0.230, 'country': 'Hungary', 'country_code': 'HUN', 'source': 'MEKH 2024', 'tags': ['electricity', 'grid', 'hungary']},
            {'code': 'RO_GRID', 'name': 'Romania Grid', 'factor_value': 0.270, 'country': 'Romania', 'country_code': 'ROU', 'source': 'ANRE 2024', 'tags': ['electricity', 'grid', 'romania']},
            {'code': 'GR_GRID', 'name': 'Greece Grid', 'factor_value': 0.400, 'country': 'Greece', 'country_code': 'GRC', 'source': 'ADMIE 2024', 'tags': ['electricity', 'grid', 'greece']},
            {'code': 'IE_GRID', 'name': 'Ireland Grid', 'factor_value': 0.296, 'country': 'Ireland', 'country_code': 'IRL', 'source': 'SEAI 2024', 'tags': ['electricity', 'grid', 'ireland']},
            {'code': 'DK_GRID', 'name': 'Denmark Grid', 'factor_value': 0.095, 'country': 'Denmark', 'country_code': 'DNK', 'source': 'Energinet 2024', 'tags': ['electricity', 'grid', 'denmark']},
            {'code': 'SE_GRID', 'name': 'Sweden Grid', 'factor_value': 0.013, 'country': 'Sweden', 'country_code': 'SWE', 'source': 'SCB 2024', 'tags': ['electricity', 'grid', 'sweden']},
            {'code': 'NO_GRID', 'name': 'Norway Grid', 'factor_value': 0.008, 'country': 'Norway', 'country_code': 'NOR', 'source': 'NVE 2024', 'tags': ['electricity', 'grid', 'norway']},
            {'code': 'FI_GRID', 'name': 'Finland Grid', 'factor_value': 0.069, 'country': 'Finland', 'country_code': 'FIN', 'source': 'Statistics Finland 2024', 'tags': ['electricity', 'grid', 'finland']},
            # Asia-Pacific
            {'code': 'CN_GRID', 'name': 'China Grid (National)', 'factor_value': 0.555, 'country': 'China', 'country_code': 'CHN', 'source': 'MEE China 2024', 'tags': ['electricity', 'grid', 'china']},
            {'code': 'IN_GRID', 'name': 'India Grid', 'factor_value': 0.708, 'country': 'India', 'country_code': 'IND', 'source': 'CEA India 2024', 'tags': ['electricity', 'grid', 'india']},
            {'code': 'JP_GRID', 'name': 'Japan Grid', 'factor_value': 0.457, 'country': 'Japan', 'country_code': 'JPN', 'source': 'MOE Japan 2024', 'tags': ['electricity', 'grid', 'japan']},
            {'code': 'KR_GRID', 'name': 'South Korea Grid', 'factor_value': 0.460, 'country': 'South Korea', 'country_code': 'KOR', 'source': 'KEEI 2024', 'tags': ['electricity', 'grid', 'korea', 'south korea']},
            {'code': 'AU_GRID', 'name': 'Australia Grid (National)', 'factor_value': 0.656, 'country': 'Australia', 'country_code': 'AUS', 'source': 'DISER 2024', 'tags': ['electricity', 'grid', 'australia']},
            {'code': 'NZ_GRID', 'name': 'New Zealand Grid', 'factor_value': 0.084, 'country': 'New Zealand', 'country_code': 'NZL', 'source': 'MBIE 2024', 'tags': ['electricity', 'grid', 'new zealand']},
            {'code': 'SG_GRID', 'name': 'Singapore Grid', 'factor_value': 0.408, 'country': 'Singapore', 'country_code': 'SGP', 'source': 'EMA 2024', 'tags': ['electricity', 'grid', 'singapore']},
            {'code': 'MY_GRID', 'name': 'Malaysia Grid', 'factor_value': 0.585, 'country': 'Malaysia', 'country_code': 'MYS', 'source': 'ST 2024', 'tags': ['electricity', 'grid', 'malaysia']},
            {'code': 'TH_GRID', 'name': 'Thailand Grid', 'factor_value': 0.510, 'country': 'Thailand', 'country_code': 'THA', 'source': 'EPPO 2024', 'tags': ['electricity', 'grid', 'thailand']},
            {'code': 'ID_GRID', 'name': 'Indonesia Grid', 'factor_value': 0.770, 'country': 'Indonesia', 'country_code': 'IDN', 'source': 'MEMR 2024', 'tags': ['electricity', 'grid', 'indonesia']},
            {'code': 'VN_GRID', 'name': 'Vietnam Grid', 'factor_value': 0.656, 'country': 'Vietnam', 'country_code': 'VNM', 'source': 'EVN 2024', 'tags': ['electricity', 'grid', 'vietnam']},
            {'code': 'PH_GRID', 'name': 'Philippines Grid', 'factor_value': 0.505, 'country': 'Philippines', 'country_code': 'PHL', 'source': 'DOE 2024', 'tags': ['electricity', 'grid', 'philippines']},
            # Middle East & Africa
            {'code': 'SA_GRID', 'name': 'Saudi Arabia Grid', 'factor_value': 0.590, 'country': 'Saudi Arabia', 'country_code': 'SAU', 'source': 'ECRA 2024', 'tags': ['electricity', 'grid', 'saudi arabia', 'ksa']},
            {'code': 'AE_GRID', 'name': 'UAE Grid', 'factor_value': 0.470, 'country': 'United Arab Emirates', 'country_code': 'ARE', 'source': 'EAD 2024', 'tags': ['electricity', 'grid', 'uae', 'emirates', 'dubai']},
            {'code': 'EG_GRID', 'name': 'Egypt Grid', 'factor_value': 0.475, 'country': 'Egypt', 'country_code': 'EGY', 'source': 'EEHC 2024', 'tags': ['electricity', 'grid', 'egypt']},
            {'code': 'ZA_GRID', 'name': 'South Africa Grid', 'factor_value': 0.928, 'country': 'South Africa', 'country_code': 'ZAF', 'source': 'Eskom 2024', 'tags': ['electricity', 'grid', 'south africa']},
            {'code': 'NG_GRID', 'name': 'Nigeria Grid', 'factor_value': 0.430, 'country': 'Nigeria', 'country_code': 'NGA', 'source': 'NERC 2024', 'tags': ['electricity', 'grid', 'nigeria']},
            {'code': 'IL_GRID', 'name': 'Israel Grid', 'factor_value': 0.530, 'country': 'Israel', 'country_code': 'ISR', 'source': 'IEC 2024', 'tags': ['electricity', 'grid', 'israel']},
            {'code': 'TR_GRID', 'name': 'Turkey Grid', 'factor_value': 0.470, 'country': 'Turkey', 'country_code': 'TUR', 'source': 'EPDK 2024', 'tags': ['electricity', 'grid', 'turkey']},
        ]
        
        count = 0
        for data in electricity_data:
            data['scope'] = 2  # Scope 2 - Indirect (Energy)
            data['category'] = 'electricity'
            data['activity_unit'] = 'kWh'
            data['subcategory'] = 'Grid Electricity'
            count += self._create_factor(**data)
        
        return count

    def _seed_stationary_combustion_factors(self):
        """Seed stationary combustion (fuels) emission factors."""
        fuels_data = [
            # Natural Gas
            {'code': 'FUEL_NAT_GAS', 'name': 'Natural Gas (kWh)', 'factor_value': 0.18387, 'activity_unit': 'kWh', 'subcategory': 'Natural Gas', 'source': 'IPCC 2006', 'tags': ['natural gas', 'gas', 'heating', 'combustion']},
            {'code': 'FUEL_NAT_GAS_M3', 'name': 'Natural Gas (m³)', 'factor_value': 1.939, 'activity_unit': 'm³', 'subcategory': 'Natural Gas', 'source': 'IPCC 2006', 'tags': ['natural gas', 'gas', 'cubic meter']},
            {'code': 'FUEL_NAT_GAS_THERM', 'name': 'Natural Gas (therm)', 'factor_value': 5.31, 'activity_unit': 'therm', 'subcategory': 'Natural Gas', 'source': 'EPA 2024', 'tags': ['natural gas', 'gas', 'therm']},
            # Diesel/Oil
            {'code': 'FUEL_DIESEL_STAT', 'name': 'Diesel (Stationary)', 'factor_value': 2.68, 'activity_unit': 'liter', 'subcategory': 'Diesel', 'source': 'DEFRA 2024', 'tags': ['diesel', 'oil', 'generator', 'stationary']},
            {'code': 'FUEL_DIESEL_STAT_GAL', 'name': 'Diesel (Stationary, US Gallon)', 'factor_value': 10.16, 'activity_unit': 'gallon', 'subcategory': 'Diesel', 'source': 'EPA 2024', 'tags': ['diesel', 'oil', 'gallon']},
            {'code': 'FUEL_HFO', 'name': 'Heavy Fuel Oil', 'factor_value': 3.11, 'activity_unit': 'liter', 'subcategory': 'Fuel Oil', 'source': 'DEFRA 2024', 'tags': ['heavy fuel oil', 'hfo', 'bunker']},
            {'code': 'FUEL_LFO', 'name': 'Light Fuel Oil', 'factor_value': 2.96, 'activity_unit': 'liter', 'subcategory': 'Fuel Oil', 'source': 'DEFRA 2024', 'tags': ['light fuel oil', 'lfo']},
            {'code': 'FUEL_KEROSENE', 'name': 'Kerosene', 'factor_value': 2.52, 'activity_unit': 'liter', 'subcategory': 'Kerosene', 'source': 'DEFRA 2024', 'tags': ['kerosene', 'paraffin', 'heating oil']},
            # LPG
            {'code': 'FUEL_LPG', 'name': 'LPG (Propane)', 'factor_value': 1.51, 'activity_unit': 'liter', 'subcategory': 'LPG', 'source': 'DEFRA 2024', 'tags': ['lpg', 'propane', 'gas']},
            {'code': 'FUEL_BUTANE', 'name': 'LPG (Butane)', 'factor_value': 1.78, 'activity_unit': 'liter', 'subcategory': 'LPG', 'source': 'DEFRA 2024', 'tags': ['lpg', 'butane', 'gas']},
            # Coal
            {'code': 'FUEL_COAL_ANTH', 'name': 'Coal (Anthracite)', 'factor_value': 2.86, 'activity_unit': 'kg', 'subcategory': 'Coal', 'source': 'IPCC 2006', 'tags': ['coal', 'anthracite', 'solid fuel']},
            {'code': 'FUEL_COAL_BIT', 'name': 'Coal (Bituminous)', 'factor_value': 2.42, 'activity_unit': 'kg', 'subcategory': 'Coal', 'source': 'IPCC 2006', 'tags': ['coal', 'bituminous', 'solid fuel']},
            {'code': 'FUEL_COAL_LIG', 'name': 'Coal (Lignite)', 'factor_value': 1.16, 'activity_unit': 'kg', 'subcategory': 'Coal', 'source': 'IPCC 2006', 'tags': ['coal', 'lignite', 'brown coal']},
            # Biomass
            {'code': 'FUEL_WOOD_PELLET', 'name': 'Wood Pellets', 'factor_value': 0.024, 'activity_unit': 'kg', 'subcategory': 'Biomass', 'source': 'DEFRA 2024', 'tags': ['wood', 'pellet', 'biomass', 'renewable']},
            {'code': 'FUEL_WOOD_CHIPS', 'name': 'Wood Chips', 'factor_value': 0.015, 'activity_unit': 'kg', 'subcategory': 'Biomass', 'source': 'DEFRA 2024', 'tags': ['wood', 'chips', 'biomass', 'renewable']},
            {'code': 'FUEL_BIOGAS', 'name': 'Biogas', 'factor_value': 0.00022, 'activity_unit': 'kWh', 'subcategory': 'Biogas', 'source': 'DEFRA 2024', 'tags': ['biogas', 'renewable', 'anaerobic']},
            {'code': 'FUEL_BIOMETHANE', 'name': 'Biomethane', 'factor_value': 0.00034, 'activity_unit': 'kWh', 'subcategory': 'Biogas', 'source': 'DEFRA 2024', 'tags': ['biomethane', 'renewable', 'green gas']},
            # Hydrogen
            {'code': 'FUEL_H2_GREY', 'name': 'Hydrogen (Grey)', 'factor_value': 9.00, 'activity_unit': 'kg', 'subcategory': 'Hydrogen', 'source': 'IEA 2024', 'tags': ['hydrogen', 'grey hydrogen', 'h2']},
            {'code': 'FUEL_H2_BLUE', 'name': 'Hydrogen (Blue)', 'factor_value': 2.00, 'activity_unit': 'kg', 'subcategory': 'Hydrogen', 'source': 'IEA 2024', 'tags': ['hydrogen', 'blue hydrogen', 'h2', 'ccs']},
            {'code': 'FUEL_H2_GREEN', 'name': 'Hydrogen (Green)', 'factor_value': 0.00, 'activity_unit': 'kg', 'subcategory': 'Hydrogen', 'source': 'IEA 2024', 'tags': ['hydrogen', 'green hydrogen', 'h2', 'renewable']},
        ]
        
        count = 0
        for data in fuels_data:
            data['scope'] = 1  # Scope 1 - Direct
            data['category'] = 'stationary_combustion'
            count += self._create_factor(**data)
        
        return count

    def _seed_mobile_combustion_factors(self):
        """Seed mobile combustion (vehicles) emission factors."""
        vehicles_data = [
            # Passenger Cars - Petrol
            {'code': 'VEH_CAR_PETROL_S', 'name': 'Petrol Car (Small <1.4L)', 'factor_value': 0.14207, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'petrol', 'gasoline', 'small', 'vehicle']},
            {'code': 'VEH_CAR_PETROL_M', 'name': 'Petrol Car (Medium 1.4-2.0L)', 'factor_value': 0.17487, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'petrol', 'gasoline', 'medium', 'vehicle']},
            {'code': 'VEH_CAR_PETROL_L', 'name': 'Petrol Car (Large >2.0L)', 'factor_value': 0.22295, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'petrol', 'gasoline', 'large', 'vehicle']},
            # Passenger Cars - Diesel
            {'code': 'VEH_CAR_DIESEL_S', 'name': 'Diesel Car (Small)', 'factor_value': 0.13870, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'diesel', 'small', 'vehicle']},
            {'code': 'VEH_CAR_DIESEL_M', 'name': 'Diesel Car (Medium)', 'factor_value': 0.16524, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'diesel', 'medium', 'vehicle']},
            {'code': 'VEH_CAR_DIESEL_L', 'name': 'Diesel Car (Large)', 'factor_value': 0.20514, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'diesel', 'large', 'vehicle']},
            # Passenger Cars - Electric/Hybrid
            {'code': 'VEH_CAR_HYBRID_M', 'name': 'Hybrid Car (Medium)', 'factor_value': 0.11529, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'hybrid', 'vehicle']},
            {'code': 'VEH_CAR_EV', 'name': 'Electric Car (Average)', 'factor_value': 0.04692, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'electric', 'ev', 'bev', 'vehicle']},
            {'code': 'VEH_CAR_PHEV_M', 'name': 'Plug-in Hybrid (Medium)', 'factor_value': 0.07028, 'activity_unit': 'km', 'subcategory': 'Passenger Car', 'source': 'DEFRA 2024', 'tags': ['car', 'plugin', 'phev', 'hybrid', 'vehicle']},
            # Vans
            {'code': 'VEH_VAN_PETROL_S', 'name': 'Van (Petrol, Small)', 'factor_value': 0.18976, 'activity_unit': 'km', 'subcategory': 'Van', 'source': 'DEFRA 2024', 'tags': ['van', 'petrol', 'small', 'lcv']},
            {'code': 'VEH_VAN_DIESEL_S', 'name': 'Van (Diesel, Small)', 'factor_value': 0.17098, 'activity_unit': 'km', 'subcategory': 'Van', 'source': 'DEFRA 2024', 'tags': ['van', 'diesel', 'small', 'lcv']},
            {'code': 'VEH_VAN_DIESEL_M', 'name': 'Van (Diesel, Medium)', 'factor_value': 0.20935, 'activity_unit': 'km', 'subcategory': 'Van', 'source': 'DEFRA 2024', 'tags': ['van', 'diesel', 'medium', 'lcv']},
            {'code': 'VEH_VAN_DIESEL_L', 'name': 'Van (Diesel, Large)', 'factor_value': 0.25976, 'activity_unit': 'km', 'subcategory': 'Van', 'source': 'DEFRA 2024', 'tags': ['van', 'diesel', 'large', 'lcv']},
            {'code': 'VEH_VAN_EV', 'name': 'Van (Electric)', 'factor_value': 0.06153, 'activity_unit': 'km', 'subcategory': 'Van', 'source': 'DEFRA 2024', 'tags': ['van', 'electric', 'ev', 'lcv']},
            # HGVs
            {'code': 'VEH_HGV_RIG_S', 'name': 'HGV Rigid (<7.5t)', 'factor_value': 0.46133, 'activity_unit': 'km', 'subcategory': 'HGV', 'source': 'DEFRA 2024', 'tags': ['hgv', 'truck', 'lorry', 'rigid', 'small']},
            {'code': 'VEH_HGV_RIG_M', 'name': 'HGV Rigid (7.5-17t)', 'factor_value': 0.57916, 'activity_unit': 'km', 'subcategory': 'HGV', 'source': 'DEFRA 2024', 'tags': ['hgv', 'truck', 'lorry', 'rigid', 'medium']},
            {'code': 'VEH_HGV_RIG_L', 'name': 'HGV Rigid (>17t)', 'factor_value': 0.87088, 'activity_unit': 'km', 'subcategory': 'HGV', 'source': 'DEFRA 2024', 'tags': ['hgv', 'truck', 'lorry', 'rigid', 'large']},
            {'code': 'VEH_HGV_ART', 'name': 'HGV Articulated', 'factor_value': 0.92036, 'activity_unit': 'km', 'subcategory': 'HGV', 'source': 'DEFRA 2024', 'tags': ['hgv', 'truck', 'lorry', 'articulated', 'semi']},
            # Motorcycles
            {'code': 'VEH_MOTO_S', 'name': 'Motorcycle (Small <125cc)', 'factor_value': 0.08297, 'activity_unit': 'km', 'subcategory': 'Motorcycle', 'source': 'DEFRA 2024', 'tags': ['motorcycle', 'motorbike', 'small']},
            {'code': 'VEH_MOTO_M', 'name': 'Motorcycle (Medium 125-500cc)', 'factor_value': 0.10046, 'activity_unit': 'km', 'subcategory': 'Motorcycle', 'source': 'DEFRA 2024', 'tags': ['motorcycle', 'motorbike', 'medium']},
            {'code': 'VEH_MOTO_L', 'name': 'Motorcycle (Large >500cc)', 'factor_value': 0.13202, 'activity_unit': 'km', 'subcategory': 'Motorcycle', 'source': 'DEFRA 2024', 'tags': ['motorcycle', 'motorbike', 'large']},
            # Buses
            {'code': 'VEH_BUS_LOCAL', 'name': 'Local Bus', 'factor_value': 0.10187, 'activity_unit': 'passenger-km', 'subcategory': 'Bus', 'source': 'DEFRA 2024', 'tags': ['bus', 'local', 'public transport']},
            {'code': 'VEH_BUS_COACH', 'name': 'Coach', 'factor_value': 0.02610, 'activity_unit': 'passenger-km', 'subcategory': 'Bus', 'source': 'DEFRA 2024', 'tags': ['bus', 'coach', 'intercity']},
            # Fuel-based
            {'code': 'FUEL_PETROL_L', 'name': 'Petrol (per liter)', 'factor_value': 2.31, 'activity_unit': 'liter', 'subcategory': 'Vehicle Fuel', 'source': 'DEFRA 2024', 'tags': ['petrol', 'gasoline', 'fuel', 'liter']},
            {'code': 'FUEL_PETROL_GAL', 'name': 'Petrol (per US gallon)', 'factor_value': 8.78, 'activity_unit': 'gallon', 'subcategory': 'Vehicle Fuel', 'source': 'EPA 2024', 'tags': ['petrol', 'gasoline', 'fuel', 'gallon']},
            {'code': 'FUEL_DIESEL_L', 'name': 'Diesel (per liter)', 'factor_value': 2.68, 'activity_unit': 'liter', 'subcategory': 'Vehicle Fuel', 'source': 'DEFRA 2024', 'tags': ['diesel', 'fuel', 'liter']},
            {'code': 'FUEL_DIESEL_GAL', 'name': 'Diesel (per US gallon)', 'factor_value': 10.16, 'activity_unit': 'gallon', 'subcategory': 'Vehicle Fuel', 'source': 'EPA 2024', 'tags': ['diesel', 'fuel', 'gallon']},
        ]
        
        count = 0
        for data in vehicles_data:
            data['scope'] = 1  # Scope 1 - Direct (company vehicles)
            data['category'] = 'mobile_combustion'
            count += self._create_factor(**data)
        
        return count

    def _seed_transport_factors(self):
        """Seed business travel and freight transport emission factors."""
        transport_data = [
            # Flights - Passenger
            {'code': 'FLIGHT_DOM', 'name': 'Domestic Flight (<500km)', 'factor_value': 0.24587, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'domestic', 'air travel', 'aviation']},
            {'code': 'FLIGHT_SHORT_ECO', 'name': 'Short-Haul Flight Economy', 'factor_value': 0.15298, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'short haul', 'economy', 'aviation']},
            {'code': 'FLIGHT_SHORT_BUS', 'name': 'Short-Haul Flight Business', 'factor_value': 0.22947, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'short haul', 'business', 'aviation']},
            {'code': 'FLIGHT_LONG_ECO', 'name': 'Long-Haul Flight Economy', 'factor_value': 0.14615, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'long haul', 'economy', 'aviation']},
            {'code': 'FLIGHT_LONG_PREM', 'name': 'Long-Haul Flight Premium Economy', 'factor_value': 0.23384, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'long haul', 'premium economy', 'aviation']},
            {'code': 'FLIGHT_LONG_BUS', 'name': 'Long-Haul Flight Business', 'factor_value': 0.42386, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'long haul', 'business class', 'aviation']},
            {'code': 'FLIGHT_LONG_FIRST', 'name': 'Long-Haul Flight First Class', 'factor_value': 0.58461, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'long haul', 'first class', 'aviation']},
            {'code': 'FLIGHT_INTL_AVG', 'name': 'International Flight (Average)', 'factor_value': 0.17810, 'activity_unit': 'passenger-km', 'subcategory': 'Air Travel', 'source': 'DEFRA 2024', 'tags': ['flight', 'international', 'average', 'aviation']},
            # Rail
            {'code': 'RAIL_NATIONAL', 'name': 'National Rail (Average)', 'factor_value': 0.03549, 'activity_unit': 'passenger-km', 'subcategory': 'Rail', 'source': 'DEFRA 2024', 'tags': ['rail', 'train', 'national', 'public transport']},
            {'code': 'RAIL_INTL', 'name': 'International Rail', 'factor_value': 0.00446, 'activity_unit': 'passenger-km', 'subcategory': 'Rail', 'source': 'DEFRA 2024', 'tags': ['rail', 'train', 'international', 'eurostar']},
            {'code': 'RAIL_TRAM', 'name': 'Light Rail / Tram', 'factor_value': 0.02877, 'activity_unit': 'passenger-km', 'subcategory': 'Rail', 'source': 'DEFRA 2024', 'tags': ['rail', 'tram', 'light rail', 'public transport']},
            {'code': 'RAIL_METRO', 'name': 'Underground / Metro', 'factor_value': 0.02781, 'activity_unit': 'passenger-km', 'subcategory': 'Rail', 'source': 'DEFRA 2024', 'tags': ['rail', 'metro', 'underground', 'subway', 'public transport']},
            {'code': 'RAIL_HS', 'name': 'High-Speed Rail', 'factor_value': 0.00446, 'activity_unit': 'passenger-km', 'subcategory': 'Rail', 'source': 'DEFRA 2024', 'tags': ['rail', 'high speed', 'hsr', 'train']},
            # Taxi
            {'code': 'TAXI_REG', 'name': 'Taxi (Regular)', 'factor_value': 0.14827, 'activity_unit': 'km', 'subcategory': 'Taxi', 'source': 'DEFRA 2024', 'tags': ['taxi', 'cab', 'rideshare']},
            {'code': 'TAXI_BLACK', 'name': 'Taxi (Black Cab)', 'factor_value': 0.21001, 'activity_unit': 'km', 'subcategory': 'Taxi', 'source': 'DEFRA 2024', 'tags': ['taxi', 'black cab', 'london']},
            # Ferry
            {'code': 'FERRY_FOOT', 'name': 'Ferry (Foot Passenger)', 'factor_value': 0.01874, 'activity_unit': 'passenger-km', 'subcategory': 'Sea Travel', 'source': 'DEFRA 2024', 'tags': ['ferry', 'sea', 'boat', 'passenger']},
            {'code': 'FERRY_CAR', 'name': 'Ferry (Car Passenger)', 'factor_value': 0.12952, 'activity_unit': 'passenger-km', 'subcategory': 'Sea Travel', 'source': 'DEFRA 2024', 'tags': ['ferry', 'sea', 'boat', 'car', 'vehicle']},
            # Freight - Road
            {'code': 'FREIGHT_ROAD_HGV', 'name': 'Road Freight (HGV All)', 'factor_value': 0.10468, 'activity_unit': 'tonne-km', 'subcategory': 'Road Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'road', 'hgv', 'truck', 'logistics']},
            {'code': 'FREIGHT_ROAD_S', 'name': 'Road Freight (Rigid <7.5t)', 'factor_value': 0.43315, 'activity_unit': 'tonne-km', 'subcategory': 'Road Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'road', 'rigid', 'small']},
            {'code': 'FREIGHT_ROAD_M', 'name': 'Road Freight (Rigid 7.5-17t)', 'factor_value': 0.14952, 'activity_unit': 'tonne-km', 'subcategory': 'Road Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'road', 'rigid', 'medium']},
            {'code': 'FREIGHT_ROAD_ART', 'name': 'Road Freight (Articulated)', 'factor_value': 0.04894, 'activity_unit': 'tonne-km', 'subcategory': 'Road Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'road', 'articulated', 'semi']},
            {'code': 'FREIGHT_ROAD_VAN', 'name': 'Road Freight (Van)', 'factor_value': 0.58741, 'activity_unit': 'tonne-km', 'subcategory': 'Road Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'road', 'van', 'delivery']},
            # Freight - Rail
            {'code': 'FREIGHT_RAIL', 'name': 'Rail Freight', 'factor_value': 0.02443, 'activity_unit': 'tonne-km', 'subcategory': 'Rail Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'rail', 'train', 'logistics']},
            # Freight - Sea
            {'code': 'FREIGHT_SEA_CONT', 'name': 'Sea Freight (Container Ship)', 'factor_value': 0.01327, 'activity_unit': 'tonne-km', 'subcategory': 'Sea Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'sea', 'container', 'ship', 'maritime']},
            {'code': 'FREIGHT_SEA_BULK', 'name': 'Sea Freight (Bulk Carrier)', 'factor_value': 0.00308, 'activity_unit': 'tonne-km', 'subcategory': 'Sea Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'sea', 'bulk', 'ship', 'maritime']},
            {'code': 'FREIGHT_SEA_TANK', 'name': 'Sea Freight (Tanker)', 'factor_value': 0.00474, 'activity_unit': 'tonne-km', 'subcategory': 'Sea Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'sea', 'tanker', 'ship', 'oil']},
            # Freight - Air
            {'code': 'FREIGHT_AIR_LONG', 'name': 'Air Freight (Long-Haul)', 'factor_value': 0.60220, 'activity_unit': 'tonne-km', 'subcategory': 'Air Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'air', 'cargo', 'aviation', 'long haul']},
            {'code': 'FREIGHT_AIR_SHORT', 'name': 'Air Freight (Short-Haul)', 'factor_value': 1.13520, 'activity_unit': 'tonne-km', 'subcategory': 'Air Freight', 'source': 'DEFRA 2024', 'tags': ['freight', 'air', 'cargo', 'aviation', 'short haul']},
        ]
        
        count = 0
        for data in transport_data:
            data['scope'] = 3  # Scope 3 - Value Chain
            data['category'] = 'transport'
            count += self._create_factor(**data)
        
        return count

    def _seed_fugitive_factors(self):
        """Seed fugitive emissions (refrigerants) factors."""
        refrigerants_data = [
            {'code': 'REF_R22', 'name': 'R-22 (HCFC-22)', 'factor_value': 1960, 'activity_unit': 'kg', 'subcategory': 'HCFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r22', 'hcfc', 'ac', 'cooling']},
            {'code': 'REF_R32', 'name': 'R-32', 'factor_value': 771, 'activity_unit': 'kg', 'subcategory': 'HFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r32', 'hfc', 'ac', 'cooling']},
            {'code': 'REF_R134A', 'name': 'R-134a', 'factor_value': 1530, 'activity_unit': 'kg', 'subcategory': 'HFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r134a', 'hfc', 'ac', 'automotive']},
            {'code': 'REF_R404A', 'name': 'R-404A', 'factor_value': 4728, 'activity_unit': 'kg', 'subcategory': 'HFC Blend', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r404a', 'hfc', 'refrigeration']},
            {'code': 'REF_R407C', 'name': 'R-407C', 'factor_value': 1908, 'activity_unit': 'kg', 'subcategory': 'HFC Blend', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r407c', 'hfc', 'ac']},
            {'code': 'REF_R410A', 'name': 'R-410A', 'factor_value': 2256, 'activity_unit': 'kg', 'subcategory': 'HFC Blend', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r410a', 'hfc', 'ac', 'hvac']},
            {'code': 'REF_R507A', 'name': 'R-507A', 'factor_value': 4891, 'activity_unit': 'kg', 'subcategory': 'HFC Blend', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r507a', 'hfc', 'refrigeration']},
            {'code': 'REF_R1234YF', 'name': 'R-1234yf', 'factor_value': 1, 'activity_unit': 'kg', 'subcategory': 'HFO', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r1234yf', 'hfo', 'automotive', 'low gwp']},
            {'code': 'REF_R1234ZE', 'name': 'R-1234ze(E)', 'factor_value': 1, 'activity_unit': 'kg', 'subcategory': 'HFO', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'r1234ze', 'hfo', 'chiller', 'low gwp']},
            {'code': 'REF_SF6', 'name': 'SF6 (Sulfur Hexafluoride)', 'factor_value': 25200, 'activity_unit': 'kg', 'subcategory': 'Other', 'source': 'IPCC AR6', 'tags': ['sf6', 'sulfur hexafluoride', 'electrical', 'switchgear']},
            {'code': 'REF_CO2', 'name': 'CO2 (Refrigerant)', 'factor_value': 1, 'activity_unit': 'kg', 'subcategory': 'Natural', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'co2', 'r744', 'natural', 'low gwp']},
            {'code': 'REF_NH3', 'name': 'Ammonia (NH3)', 'factor_value': 0, 'activity_unit': 'kg', 'subcategory': 'Natural', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'ammonia', 'nh3', 'r717', 'natural']},
            {'code': 'REF_R290', 'name': 'Propane (R-290)', 'factor_value': 0.02, 'activity_unit': 'kg', 'subcategory': 'Natural', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'propane', 'r290', 'natural', 'low gwp']},
            {'code': 'REF_R600A', 'name': 'Isobutane (R-600a)', 'factor_value': 0.02, 'activity_unit': 'kg', 'subcategory': 'Natural', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'isobutane', 'r600a', 'natural', 'low gwp']},
            {'code': 'REF_NF3', 'name': 'NF3', 'factor_value': 17400, 'activity_unit': 'kg', 'subcategory': 'Other', 'source': 'IPCC AR6', 'tags': ['nf3', 'nitrogen trifluoride', 'semiconductor']},
            {'code': 'REF_HFC23', 'name': 'HFC-23', 'factor_value': 14600, 'activity_unit': 'kg', 'subcategory': 'HFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'hfc23', 'hfc']},
            {'code': 'REF_HFC125', 'name': 'HFC-125', 'factor_value': 3740, 'activity_unit': 'kg', 'subcategory': 'HFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'hfc125', 'hfc']},
            {'code': 'REF_HFC143A', 'name': 'HFC-143a', 'factor_value': 5810, 'activity_unit': 'kg', 'subcategory': 'HFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'hfc143a', 'hfc']},
            {'code': 'REF_HFC152A', 'name': 'HFC-152a', 'factor_value': 164, 'activity_unit': 'kg', 'subcategory': 'HFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'hfc152a', 'hfc', 'foam']},
            {'code': 'REF_HFC227EA', 'name': 'HFC-227ea', 'factor_value': 3600, 'activity_unit': 'kg', 'subcategory': 'HFC', 'source': 'IPCC AR6', 'tags': ['refrigerant', 'hfc227ea', 'hfc', 'fire suppression']},
        ]
        
        count = 0
        for data in refrigerants_data:
            data['scope'] = 1  # Scope 1 - Direct
            data['category'] = 'fugitive'
            count += self._create_factor(**data)
        
        return count

    def _seed_waste_factors(self):
        """Seed waste disposal emission factors."""
        waste_data = [
            {'code': 'WASTE_MUN_LANDFILL', 'name': 'Mixed Municipal Waste (Landfill)', 'factor_value': 0.446, 'activity_unit': 'kg', 'subcategory': 'Landfill', 'source': 'DEFRA 2024', 'tags': ['waste', 'municipal', 'landfill', 'disposal']},
            {'code': 'WASTE_MUN_INCIN', 'name': 'Mixed Municipal Waste (Incineration)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Incineration', 'source': 'DEFRA 2024', 'tags': ['waste', 'municipal', 'incineration', 'efw']},
            {'code': 'WASTE_PAPER_LAND', 'name': 'Paper (Landfill)', 'factor_value': 1.042, 'activity_unit': 'kg', 'subcategory': 'Landfill', 'source': 'DEFRA 2024', 'tags': ['waste', 'paper', 'landfill']},
            {'code': 'WASTE_PAPER_REC', 'name': 'Paper (Recycled)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Recycling', 'source': 'DEFRA 2024', 'tags': ['waste', 'paper', 'recycling', 'recycled']},
            {'code': 'WASTE_PAPER_INCIN', 'name': 'Paper (Incineration)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Incineration', 'source': 'DEFRA 2024', 'tags': ['waste', 'paper', 'incineration']},
            {'code': 'WASTE_PLASTIC_LAND', 'name': 'Plastic (Landfill)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Landfill', 'source': 'DEFRA 2024', 'tags': ['waste', 'plastic', 'landfill']},
            {'code': 'WASTE_PLASTIC_REC', 'name': 'Plastic (Recycled)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Recycling', 'source': 'DEFRA 2024', 'tags': ['waste', 'plastic', 'recycling', 'recycled']},
            {'code': 'WASTE_PLASTIC_INCIN', 'name': 'Plastic (Incineration)', 'factor_value': 2.100, 'activity_unit': 'kg', 'subcategory': 'Incineration', 'source': 'DEFRA 2024', 'tags': ['waste', 'plastic', 'incineration']},
            {'code': 'WASTE_GLASS_LAND', 'name': 'Glass (Landfill)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Landfill', 'source': 'DEFRA 2024', 'tags': ['waste', 'glass', 'landfill']},
            {'code': 'WASTE_GLASS_REC', 'name': 'Glass (Recycled)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Recycling', 'source': 'DEFRA 2024', 'tags': ['waste', 'glass', 'recycling', 'recycled']},
            {'code': 'WASTE_METAL_LAND', 'name': 'Metal (Landfill)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Landfill', 'source': 'DEFRA 2024', 'tags': ['waste', 'metal', 'landfill']},
            {'code': 'WASTE_METAL_REC', 'name': 'Metal (Recycled)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'Recycling', 'source': 'DEFRA 2024', 'tags': ['waste', 'metal', 'recycling', 'recycled']},
            {'code': 'WASTE_ORG_LAND', 'name': 'Organic Waste (Landfill)', 'factor_value': 0.550, 'activity_unit': 'kg', 'subcategory': 'Landfill', 'source': 'DEFRA 2024', 'tags': ['waste', 'organic', 'food', 'landfill']},
            {'code': 'WASTE_ORG_COMP', 'name': 'Organic Waste (Composted)', 'factor_value': 0.010, 'activity_unit': 'kg', 'subcategory': 'Composting', 'source': 'DEFRA 2024', 'tags': ['waste', 'organic', 'food', 'composting', 'compost']},
            {'code': 'WASTE_ORG_AD', 'name': 'Organic Waste (Anaerobic Digestion)', 'factor_value': 0.010, 'activity_unit': 'kg', 'subcategory': 'Anaerobic Digestion', 'source': 'DEFRA 2024', 'tags': ['waste', 'organic', 'food', 'anaerobic', 'biogas']},
            {'code': 'WASTE_CONST', 'name': 'Construction Waste', 'factor_value': 0.100, 'activity_unit': 'kg', 'subcategory': 'Construction', 'source': 'DEFRA 2024', 'tags': ['waste', 'construction', 'demolition', 'c&d']},
            {'code': 'WASTE_WEEE', 'name': 'Electrical Waste (WEEE)', 'factor_value': 0.021, 'activity_unit': 'kg', 'subcategory': 'WEEE', 'source': 'DEFRA 2024', 'tags': ['waste', 'electrical', 'electronic', 'weee', 'e-waste']},
        ]
        
        count = 0
        for data in waste_data:
            data['scope'] = 3  # Scope 3 - Value Chain
            data['category'] = 'waste'
            count += self._create_factor(**data)
        
        return count

    def _seed_water_factors(self):
        """Seed water supply and treatment emission factors."""
        water_data = [
            {'code': 'WATER_SUPPLY', 'name': 'Water Supply', 'factor_value': 0.149, 'activity_unit': 'm³', 'subcategory': 'Supply', 'source': 'DEFRA 2024', 'tags': ['water', 'supply', 'mains', 'utility']},
            {'code': 'WATER_TREAT', 'name': 'Water Treatment', 'factor_value': 0.272, 'activity_unit': 'm³', 'subcategory': 'Treatment', 'source': 'DEFRA 2024', 'tags': ['water', 'treatment', 'wastewater', 'sewage']},
            {'code': 'WATER_TOTAL', 'name': 'Water Supply + Treatment', 'factor_value': 0.421, 'activity_unit': 'm³', 'subcategory': 'Total', 'source': 'DEFRA 2024', 'tags': ['water', 'supply', 'treatment', 'total']},
        ]
        
        count = 0
        for data in water_data:
            data['scope'] = 3  # Scope 3 - Value Chain
            data['category'] = 'water'
            count += self._create_factor(**data)
        
        return count
