# TASK: Carbon Phase 1 — UI Terminology + Essential Workflows

**Status:** Ready for Worker Execution  
**Date:** 2026-07-25  
**Protocol:** Master-Worker (Zoo as Master, never codes)  
**Workers:** Worker 1 (raptor - backend), Worker 2 (mai-code flash - frontend)  
**Execution:** Parallel tracks with zero dependencies

---

## Master-Worker Protocol

### Master (Zoo) Responsibilities ✅
- ✅ Plan and create task specifications
- ✅ Define acceptance criteria
- ✅ Provide architecture guidance
- ✅ Review and validate worker deliverables
- ❌ **NEVER write code directly**

### Worker 1 (raptor) — Backend
- Execute all backend changes
- Run tests and verify functionality
- Report completion status to master

### Worker 2 (mai-code flash) — Frontend
- Execute all frontend changes
- Test UI in browser
- Report completion status to master

---

## Executive Summary

Based on enterprise carbon platform audit ([`plans/CARBON_UI_TERMINOLOGY_ENTERPRISE_AUDIT.md`](plans/CARBON_UI_TERMINOLOGY_ENTERPRISE_AUDIT.md:1-655)), implement:

1. **Backend (Worker 1):** Carbon reference data seeding + calculation validation layer
2. **Frontend (Worker 2):** Enterprise terminology fixes + workflow-based navigation

**Philosophy Confirmed:**
- ✅ Data Trust Platform: Generic `DataTable`/`DataRow` for ALL domains
- ✅ Carbon Domain: Specific config (`EmissionFactor`, `ReportingPeriod`) + business logic
- ✅ Separation: Platform admin at `/catalog/`, `/mdm/`, carbon at `/carbon/`

---

## Architecture Context

```
┌─────────────────────────────────────────────────────────────────┐
│              DATA TRUST PLATFORM (Generic Layer)                 │
│                                                                   │
│  URL: /catalog/, /mdm/, /dq/                                     │
│  Tables: DataTable → DataRow (stores activity data)             │
│  Services: Catalog, DQ Rules, Reference Data                     │
└─────────────────────────────────────────────────────────────────┘
                             ↑ uses
                             │
┌─────────────────────────────────────────────────────────────────┐
│                 CARBON DOMAIN (emissions/ app)                   │
│                                                                   │
│  URL: /carbon/*                                                  │
│  Config: EmissionFactor, ReportingPeriod, Calculation           │
│  Business Logic: CO2e calculation, monthly reporting             │
│  UI: Carbon Console, Activity Data Collection, Reports           │
└─────────────────────────────────────────────────────────────────┘
```

---

# WORKER 1 (raptor) — BACKEND TRACK

## Context for Worker 1

Current backend state:
- ✅ Models exist: [`EmissionFactor`](backend/emissions/models.py:96-215), [`ReportingPeriod`](backend/emissions/models.py:8-93), [`Calculation`](backend/emissions/models.py:285-471)
- ✅ Basic APIs: [`CalculateAPIView`](backend/emissions/views.py:624-697), [`ReportingPeriodViewSet`](backend/emissions/views.py:45-80)
- ⚠️ Missing: Scope-specific validation, reference data seed, calculation rules

**User Requirements (Confirmed):**
- Hybrid data entry: manual + CSV import
- Manual calculation trigger: users click button
- No approval workflow
- Monthly reporting cycles
- Scope 3 priorities: Categories 1, 3, 6, 7

---

## B1: Seed Carbon Reference Data

**Purpose:** Provide production-ready emission factors and scope configurations.

### B1.1: Create Management Command

**File:** `backend/emissions/management/commands/seed_carbon_reference_data.py` (NEW)

```python
"""
Seed production carbon reference data:
- Emission factors for common fuel types (Scope 1)
- Electricity factors (Scope 2)
- Business travel factors (Scope 3)
- Scope 3 category definitions
"""
from django.core.management.base import BaseCommand
from emissions.models import EmissionFactor, GWP
from mdm.models import ReferenceSet, ReferenceValue
from core.models import Module
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed carbon reference data for production use'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Seeding carbon reference data...')
        
        # 1. Seed GWP values (AR6 default)
        self._seed_gwp()
        
        # 2. Seed Scope 1 emission factors
        self._seed_scope1_factors()
        
        # 3. Seed Scope 2 emission factors
        self._seed_scope2_factors()
        
        # 4. Seed Scope 3 categories (1, 3, 6, 7)
        self._seed_scope3_categories()
        
        # 5. Seed activity units reference set
        self._seed_activity_units()
        
        self.stdout.write(self.style.SUCCESS('✅ Carbon reference data seeded'))

    def _seed_gwp(self):
        """Seed Global Warming Potential values from IPCC AR6."""
        gwp_data = [
            ('CO2', 'Carbon Dioxide', 1, 1, 1),
            ('CH4', 'Methane', 29.8, 82.5, 27.9),  # AR6 100yr, 20yr, fossil
            ('N2O', 'Nitrous Oxide', 273, 273, 273),
        ]
        
        for gas, name, ar6_100, ar6_20, fossil in gwp_data:
            GWP.objects.update_or_create(
                gas=gas,
                defaults={
                    'gas_name': name,
                    'ar6_gwp_100': ar6_100,
                    'ar6_gwp_20': ar6_20,
                    'ar5_gwp_100': ar6_100,  # Simplified
                    'ar4_gwp_100': ar6_100,
                }
            )
        self.stdout.write('  ✓ GWP values seeded')

    def _seed_scope1_factors(self):
        """Seed Scope 1 emission factors (stationary combustion)."""
        # Get or create Scope 1 modules
        from dataschema.models import DataTable
        
        factors = [
            # Natural Gas
            {
                'name': 'Natural Gas - Stationary Combustion',
                'scope': 1,
                'category': 'Stationary Combustion',
                'fuel_type': 'Natural Gas',
                'region': 'Global',
                'factor': 0.0539,  # kg CO2e per kWh
                'unit': 'kWh',
                'source': 'UK DEFRA 2024',
            },
            # Diesel
            {
                'name': 'Diesel - Mobile Combustion',
                'scope': 1,
                'category': 'Mobile Combustion',
                'fuel_type': 'Diesel',
                'region': 'Global',
                'factor': 2.687,  # kg CO2e per liter
                'unit': 'liters',
                'source': 'EPA 2024',
            },
            # Gasoline
            {
                'name': 'Gasoline - Mobile Combustion',
                'scope': 1,
                'category': 'Mobile Combustion',
                'fuel_type': 'Gasoline',
                'region': 'Global',
                'factor': 2.296,  # kg CO2e per liter
                'unit': 'liters',
                'source': 'EPA 2024',
            },
        ]
        
        for data in factors:
            EmissionFactor.objects.update_or_create(
                name=data['name'],
                defaults={
                    'scope': data['scope'],
                    'category': data['category'],
                    'fuel_type': data['fuel_type'],
                    'region': data['region'],
                    'factor': data['factor'],
                    'unit': data['unit'],
                    'source': data['source'],
                    'is_active': True,
                }
            )
        self.stdout.write(f'  ✓ {len(factors)} Scope 1 factors seeded')

    def _seed_scope2_factors(self):
        """Seed Scope 2 emission factors (purchased electricity)."""
        factors = [
            {
                'name': 'Electricity - Egypt Grid Average',
                'scope': 2,
                'category': 'Purchased Electricity',
                'fuel_type': 'Grid Electricity',
                'region': 'Egypt',
                'factor': 0.551,  # kg CO2e per kWh (IEA 2023)
                'unit': 'kWh',
                'source': 'IEA 2023',
            },
            {
                'name': 'Electricity - MENA Regional Average',
                'scope': 2,
                'category': 'Purchased Electricity',
                'fuel_type': 'Grid Electricity',
                'region': 'MENA',
                'factor': 0.623,  # kg CO2e per kWh
                'unit': 'kWh',
                'source': 'IEA 2023',
            },
        ]
        
        for data in factors:
            EmissionFactor.objects.update_or_create(
                name=data['name'],
                defaults={
                    'scope': data['scope'],
                    'category': data['category'],
                    'fuel_type': data['fuel_type'],
                    'region': data['region'],
                    'factor': data['factor'],
                    'unit': data['unit'],
                    'source': data['source'],
                    'is_active': True,
                }
            )
        self.stdout.write(f'  ✓ {len(factors)} Scope 2 factors seeded')

    def _seed_scope3_categories(self):
        """Seed Scope 3 categories (priorities: 1, 3, 6, 7)."""
        factors = [
            # Category 1: Purchased Goods and Services
            {
                'name': 'Paper Products - Scope 3 Category 1',
                'scope': 3,
                'category': 'Category 1: Purchased Goods',
                'fuel_type': 'Office Paper',
                'region': 'Global',
                'factor': 0.937,  # kg CO2e per kg
                'unit': 'kg',
                'source': 'EPA EEIO 2024',
            },
            # Category 3: Fuel and Energy Related (not in Scope 1/2)
            {
                'name': 'Transmission & Distribution Losses - Egypt',
                'scope': 3,
                'category': 'Category 3: Fuel & Energy Related',
                'fuel_type': 'T&D Losses',
                'region': 'Egypt',
                'factor': 0.055,  # kg CO2e per kWh (10% of grid factor)
                'unit': 'kWh',
                'source': 'GHG Protocol Scope 3 Guidance',
            },
            # Category 6: Business Travel
            {
                'name': 'Air Travel - Short Haul Economy',
                'scope': 3,
                'category': 'Category 6: Business Travel',
                'fuel_type': 'Aviation - Domestic',
                'region': 'Global',
                'factor': 0.154,  # kg CO2e per passenger-km
                'unit': 'passenger-km',
                'source': 'UK DEFRA 2024',
            },
            {
                'name': 'Hotel Stay - Average',
                'scope': 3,
                'category': 'Category 6: Business Travel',
                'fuel_type': 'Accommodation',
                'region': 'Global',
                'factor': 12.5,  # kg CO2e per night
                'unit': 'nights',
                'source': 'Hotel Carbon Measurement Initiative',
            },
            # Category 7: Employee Commuting
            {
                'name': 'Employee Commute - Bus',
                'scope': 3,
                'category': 'Category 7: Employee Commuting',
                'fuel_type': 'Public Bus',
                'region': 'Egypt',
                'factor': 0.089,  # kg CO2e per passenger-km
                'unit': 'passenger-km',
                'source': 'UK DEFRA 2024 (adjusted)',
            },
            {
                'name': 'Employee Commute - Private Car',
                'scope': 3,
                'category': 'Category 7: Employee Commuting',
                'fuel_type': 'Passenger Car',
                'region': 'Egypt',
                'factor': 0.171,  # kg CO2e per km
                'unit': 'km',
                'source': 'EPA 2024',
            },
        ]
        
        for data in factors:
            EmissionFactor.objects.update_or_create(
                name=data['name'],
                defaults={
                    'scope': data['scope'],
                    'category': data['category'],
                    'fuel_type': data['fuel_type'],
                    'region': data['region'],
                    'factor': data['factor'],
                    'unit': data['unit'],
                    'source': data['source'],
                    'is_active': True,
                }
            )
        self.stdout.write(f'  ✓ {len(factors)} Scope 3 factors seeded')

    def _seed_activity_units(self):
        """Seed reference set for activity data units."""
        ref_set, created = ReferenceSet.objects.get_or_create(
            code='CARBON_ACTIVITY_UNITS',
            defaults={
                'name': 'Carbon Activity Data Units',
                'description': 'Standard units for carbon activity data entry',
                'lifecycle_state': 'published',
                'is_active': True,
            }
        )
        
        units = [
            ('kWh', 'Kilowatt Hours', 'Energy consumption'),
            ('liters', 'Liters', 'Liquid fuel volume'),
            ('kg', 'Kilograms', 'Mass'),
            ('km', 'Kilometers', 'Distance'),
            ('passenger-km', 'Passenger-Kilometers', 'Travel distance per person'),
            ('nights', 'Nights', 'Hotel accommodation'),
            ('m3', 'Cubic Meters', 'Gas volume'),
        ]
        
        for code, label, desc in units:
            ReferenceValue.objects.update_or_create(
                reference_set=ref_set,
                code=code,
                defaults={
                    'label': label,
                    'description': desc,
                    'is_active': True,
                }
            )
        
        self.stdout.write(f'  ✓ Activity units reference set created')
```

**Acceptance Criteria:**
- Command runs without errors: `python manage.py seed_carbon_reference_data`
- Creates 15+ emission factors across Scopes 1/2/3
- Creates GWP values for CO2, CH4, N2O
- Creates activity units reference set
- All factors have `is_active=True`

---

## B2: Scope-Specific Validation Layer

**Purpose:** Validate activity data before calculation based on scope.

### B2.1: Add Validation to CalculateAPIView

**File:** [`backend/emissions/views.py`](backend/emissions/views.py:624-697)

**Current code at line 638:**
```python
def post(self, request):
    data_table_id = request.data.get('data_table_id')
    reporting_period_id = request.data.get('reporting_period_id')
    # ... directly proceeds to calculation
```

**Required changes:**

```python
# Add before line 638
from decimal import Decimal, InvalidOperation

def post(self, request):
    data_table_id = request.data.get('data_table_id')
    reporting_period_id = request.data.get('reporting_period_id')
    
    # 1. Validate inputs
    if not data_table_id:
        return Response(
            {'error': 'data_table_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # 2. Get table and check scope
    try:
        from dataschema.models import DataTable
        table = DataTable.objects.select_related('module').get(id=data_table_id)
    except DataTable.DoesNotExist:
        return Response(
            {'error': f'DataTable {data_table_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # 3. Validate scope is set (carbon tables have module.scope)
    if not table.module or table.module.scope is None:
        return Response(
            {
                'error': 'Invalid table for carbon calculations',
                'detail': 'Table must belong to a carbon module with scope (1, 2, or 3)',
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # 4. Get reporting period
    period = None
    if reporting_period_id:
        try:
            period = ReportingPeriod.objects.get(id=reporting_period_id)
            if period.status == 'closed':
                return Response(
                    {
                        'error': 'Reporting period is closed',
                        'detail': f'Period "{period.name}" was closed on {period.end_date}',
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ReportingPeriod.DoesNotExist:
            return Response(
                {'error': f'ReportingPeriod {reporting_period_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    # 5. Get activity data rows with validation
    from dataschema.models import DataRow
    rows = DataRow.objects.filter(data_table=table, is_active=True)
    
    if period:
        rows = rows.filter(
            created_at__gte=period.start_date,
            created_at__lte=period.end_date
        )
    
    if not rows.exists():
        return Response(
            {
                'warning': 'No activity data found',
                'detail': f'No active rows in table "{table.name}" for the specified period',
                'scope': table.module.scope,
                'period': period.name if period else 'all time',
            },
            status=status.HTTP_200_OK
        )
    
    # 6. Validate activity data completeness
    validation_errors = []
    for row in rows[:100]:  # Sample first 100 rows
        # Check for required fields based on scope
        values = row.values or {}
        
        if not values.get('activity_value'):
            validation_errors.append({
                'row_id': row.id,
                'error': 'Missing activity_value',
            })
        else:
            # Validate numeric
            try:
                Decimal(str(values['activity_value']))
            except (InvalidOperation, ValueError, TypeError):
                validation_errors.append({
                    'row_id': row.id,
                    'error': f'Invalid activity_value: {values.get("activity_value")}',
                })
        
        if not values.get('activity_unit'):
            validation_errors.append({
                'row_id': row.id,
                'error': 'Missing activity_unit',
            })
        
        if not values.get('emission_factor_id'):
            validation_errors.append({
                'row_id': row.id,
                'error': 'Missing emission_factor_id',
            })
    
    if validation_errors:
        return Response(
            {
                'error': 'Activity data validation failed',
                'validation_errors': validation_errors[:10],  # Return first 10
                'total_errors': len(validation_errors),
                'detail': 'Fix validation errors before calculating emissions',
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    
    # 7. Proceed with calculation (existing code continues)
    # ... rest of existing calculation logic
```

**Acceptance Criteria:**
- Returns HTTP 400 if `data_table_id` missing
- Returns HTTP 400 if table has no scope
- Returns HTTP 400 if reporting period is closed
- Returns HTTP 422 with validation errors if activity data incomplete
- Returns HTTP 200 with warning if no activity data found
- Existing calculation logic still works for valid data

---

## B3: Enhanced Calculation Tracking

**Purpose:** Track who triggered calculation and when.

### B3.1: Add Audit Fields to Calculation Model

**File:** [`backend/emissions/models.py`](backend/emissions/models.py:285-471)

**Add migration:**

Create file: `backend/emissions/migrations/0006_calculation_audit_fields.py`

```python
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('emissions', '0005_reportconfig'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='calculation',
            name='triggered_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='triggered_calculations',
                to='accounts.user'
            ),
        ),
        migrations.AddField(
            model_name='calculation',
            name='calculation_method',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual Trigger'),
                    ('auto', 'Automatic Rule'),
                    ('api', 'API Request'),
                    ('import', 'Bulk Import'),
                ],
                default='manual',
                max_length=20
            ),
        ),
    ]
```

### B3.2: Update Calculation Creation

**File:** [`backend/emissions/views.py`](backend/emissions/views.py:624-697)

In `CalculateAPIView.post()`, when creating calculations, add:

```python
# In the calculation creation loop (around line 670)
calculation = Calculation.objects.create(
    data_row=row,
    emission_factor=factor,
    activity_value=activity_value,
    activity_unit=activity_unit,
    co2e_kg=co2e_kg,
    reporting_period=period,
    # NEW FIELDS:
    triggered_by=request.user,
    calculation_method='manual',
)
```

**Acceptance Criteria:**
- Migration runs successfully
- New calculations have `triggered_by` set to current user
- New calculations have `calculation_method='manual'`
- Existing calculations remain unchanged (nullable fields)

---

## B4: Testing

### B4.1: Test Seed Command

```bash
cd backend
python manage.py seed_carbon_reference_data
python manage.py shell
```

```python
from emissions.models import EmissionFactor, GWP
from mdm.models import ReferenceSet

# Verify GWP
print(f"GWP count: {GWP.objects.count()}")  # Should be 3+

# Verify emission factors
scope1 = EmissionFactor.objects.filter(scope=1).count()
scope2 = EmissionFactor.objects.filter(scope=2).count()
scope3 = EmissionFactor.objects.filter(scope=3).count()
print(f"Scope 1: {scope1}, Scope 2: {scope2}, Scope 3: {scope3}")  # 3, 2, 6+

# Verify units
units = ReferenceSet.objects.get(code='CARBON_ACTIVITY_UNITS')
print(f"Activity units: {units.values.count()}")  # Should be 7+
```

### B4.2: Test Validation API

```bash
# Test missing data_table_id
curl -X POST http://localhost:8000/carbon-api/emissions/calculate/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# Expected: HTTP 400 with error "data_table_id is required"

# Test closed period
curl -X POST http://localhost:8000/carbon-api/emissions/calculate/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data_table_id": 1, "reporting_period_id": 999}'

# Expected: HTTP 400 if period closed, or proceeds if open
```

### B4.3: Write Unit Tests

**File:** `backend/emissions/tests/test_calculation_validation.py` (NEW)

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from emissions.models import EmissionFactor, ReportingPeriod
from dataschema.models import DataTable, DataRow, DataField
from core.models import Module
from mdm.models import OrgUnit, DataDomain

User = get_user_model()


class CalculationValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test_calculator',
            email='calc@test.com',
            password='test123',
            is_staff=True
        )
        self.client.force_authenticate(user=self.user)
        
        # Create org unit
        self.domain = DataDomain.objects.create(name='Carbon', code='CARBON')
        self.org_unit = OrgUnit.objects.create(
            name='Test Campus',
            org_type='campus',
            domain=self.domain
        )
        
        # Create carbon module with scope
        self.module = Module.objects.create(
            name='Vehicle Fleet',
            code='SCOPE1_VEHICLES',
            org_unit=self.org_unit,
            scope=1
        )
        
        # Create table
        self.table = DataTable.objects.create(
            name='Fleet Emissions',
            module=self.module,
            org_unit=self.org_unit
        )
        
        # Create emission factor
        self.factor = EmissionFactor.objects.create(
            name='Diesel',
            scope=1,
            category='Mobile Combustion',
            factor=2.687,
            unit='liters',
            is_active=True
        )
        
        # Create reporting period
        self.period = ReportingPeriod.objects.create(
            name='Jan 2026',
            start_date='2026-01-01',
            end_date='2026-01-31',
            status='open'
        )
    
    def test_calculate_missing_table_id(self):
        """Test validation: missing data_table_id."""
        response = self.client.post('/carbon-api/emissions/calculate/', {})
        self.assertEqual(response.status_code, 400)
        self.assertIn('data_table_id is required', response.data['error'])
    
    def test_calculate_table_without_scope(self):
        """Test validation: table without scope."""
        # Create table without scope
        module_no_scope = Module.objects.create(
            name='Generic Module',
            code='GENERIC',
            org_unit=self.org_unit,
            scope=None  # No scope
        )
        table_no_scope = DataTable.objects.create(
            name='Generic Table',
            module=module_no_scope,
            org_unit=self.org_unit
        )
        
        response = self.client.post('/carbon-api/emissions/calculate/', {
            'data_table_id': table_no_scope.id
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid table for carbon calculations', response.data['error'])
    
    def test_calculate_closed_period(self):
        """Test validation: closed reporting period."""
        closed_period = ReportingPeriod.objects.create(
            name='Dec 2025',
            start_date='2025-12-01',
            end_date='2025-12-31',
            status='closed'
        )
        
        response = self.client.post('/carbon-api/emissions/calculate/', {
            'data_table_id': self.table.id,
            'reporting_period_id': closed_period.id
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Reporting period is closed', response.data['error'])
    
    def test_calculate_no_activity_data(self):
        """Test warning: no activity data in period."""
        response = self.client.post('/carbon-api/emissions/calculate/', {
            'data_table_id': self.table.id,
            'reporting_period_id': self.period.id
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('No activity data found', response.data['warning'])
    
    def test_calculate_invalid_activity_value(self):
        """Test validation: invalid numeric activity_value."""
        # Create row with invalid activity_value
        row = DataRow.objects.create(
            data_table=self.table,
            org_unit=self.org_unit,
            values={
                'activity_value': 'invalid_number',
                'activity_unit': 'liters',
                'emission_factor_id': self.factor.id
            }
        )
        
        response = self.client.post('/carbon-api/emissions/calculate/', {
            'data_table_id': self.table.id
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn('validation failed', response.data['error'])
```

**Run tests:**
```bash
cd backend
python manage.py test emissions.tests.test_calculation_validation -v 2
```

---

## Worker 1 Deliverables

1. ✅ `backend/emissions/management/commands/seed_carbon_reference_data.py` created
2. ✅ Validation added to `CalculateAPIView.post()` in `backend/emissions/views.py`
3. ✅ Migration `0006_calculation_audit_fields.py` created and applied
4. ✅ Unit tests in `backend/emissions/tests/test_calculation_validation.py`
5. ✅ Seed command runs successfully: `python manage.py seed_carbon_reference_data`
6. ✅ Tests pass: `python manage.py test emissions.tests.test_calculation_validation`

---

# WORKER 2 (mai-code flash) — FRONTEND TRACK

## Context for Worker 2

Current frontend state:
- ✅ Sidebar with Scope 1/2/3 grouping: [`SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx:109-193)
- ✅ Existing pages: EmissionFactors, ReportGenerator, DataOwnerDashboard
- ⚠️ Terminology: Uses generic terms ("Data Entry", "Modules", "Tables")
- ⚠️ Missing: Carbon Console landing page, workflow navigation, tooltips

**Enterprise Audit Findings:**
- Leading platforms use: "Activity Data Collection", "Emission Sources", "Carbon Footprint Dashboard"
- Workflow-based navigation: Collect → Calculate → Report → Act
- Progress indicators: "65% complete, 3 of 8 facilities submitted"
- Contextual help with tooltips

---

## F1: Terminology Fixes (Quick Wins)

**Purpose:** Replace generic platform terms with carbon domain terminology.

### F1.1: Update Sidebar Labels

**File:** [`carbon-frontend/src/components/SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx:34-193)

**Changes needed:**

```jsx
// Around line 109 - Update scope headers
const scopeIcons = {
  1: { icon: LocalShipping, color: '#f44336', label: 'Scope 1: Direct Emissions' },
  2: { icon: Bolt, color: '#ff9800', label: 'Scope 2: Purchased Energy' },
  3: { icon: Flight, color: '#2196f3', label: 'Scope 3: Value Chain' },
};

// Around line 151 - Update "Modules" to "Emission Sources"
<Typography variant="caption" sx={{ opacity: 0.7, ml: 1 }}>
  Emission Sources
</Typography>

// Around line 24 - Update app menu labels
const carbonApps = [
  { label: 'Carbon Console', icon: Dashboard, path: '/carbon/console' },  // NEW
  { label: 'Activity Data', icon: TableChart, path: '/carbon/data-entry' },  // Changed from "Data Entry"
  { label: 'Emission Factors', icon: Calculate, path: '/carbon/emission-factors' },
  { label: 'Reports & Analytics', icon: Assessment, path: '/carbon/reports' },  // Changed from "Report Generator"
  { label: 'Settings', icon: Settings, path: '/carbon/settings' },  // NEW
];
```

**Acceptance Criteria:**
- Sidebar shows "Emission Sources" instead of "Modules"
- Scope labels include full descriptions (e.g., "Scope 1: Direct Emissions")
- App menu has "Activity Data" instead of "Data Entry"
- App menu has "Carbon Console" as first item

---

## F2: Carbon Console Landing Page

**Purpose:** Provide workflow-based navigation and high-level KPIs.

### F2.1: Create Carbon Console Page

**File:** `carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx` (NEW)

```jsx
import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Button,
  LinearProgress,
  Alert,
  Chip,
  Stack,
} from '@mui/material';
import {
  TrendingUp,
  Assignment,
  Calculate,
  Assessment,
  CheckCircle,
  Warning,
  ArrowForward,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { getOwnerSummary } from '../../api/emissions';
import { useNotification } from '../../contexts/NotificationContext';

const WorkflowCard = ({ title, description, status, progress, icon: Icon, actionLabel, actionPath, theme }) => {
  const navigate = useNavigate();
  
  const getStatusColor = () => {
    if (status === 'complete') return theme.palette.success.main;
    if (status === 'in-progress') return theme.palette.warning.main;
    return theme.palette.grey[400];
  };
  
  return (
    <Card sx={{ height: '100%', borderLeft: `4px solid ${getStatusColor()}` }}>
      <CardContent>
        <Stack direction="row" spacing={2} alignItems="flex-start">
          <Box
            sx={{
              p: 1.5,
              borderRadius: 2,
              bgcolor: `${getStatusColor()}15`,
              display: 'flex',
            }}
          >
            <Icon sx={{ color: getStatusColor(), fontSize: 32 }} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" gutterBottom>
              {title}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {description}
            </Typography>
            
            {progress !== null && (
              <Box sx={{ mb: 2 }}>
                <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    Progress
                  </Typography>
                  <Typography variant="caption" fontWeight="bold">
                    {progress}%
                  </Typography>
                </Stack>
                <LinearProgress
                  variant="determinate"
                  value={progress}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    bgcolor: theme.palette.grey[200],
                    '& .MuiLinearProgress-bar': {
                      bgcolor: getStatusColor(),
                    },
                  }}
                />
              </Box>
            )}
            
            <Button
              variant={status === 'in-progress' ? 'contained' : 'outlined'}
              size="small"
              endIcon={<ArrowForward />}
              onClick={() => navigate(actionPath)}
              sx={{ mt: 1 }}
            >
              {actionLabel}
            </Button>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
};

const MetricCard = ({ label, value, unit, trend, icon: Icon, color, theme }) => (
  <Card>
    <CardContent>
      <Stack direction="row" spacing={2} alignItems="center">
        <Box
          sx={{
            p: 1.5,
            borderRadius: 2,
            bgcolor: `${color}15`,
            display: 'flex',
          }}
        >
          <Icon sx={{ color, fontSize: 28 }} />
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="h5" fontWeight="bold">
            {value}
            {unit && (
              <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 0.5 }}>
                {unit}
              </Typography>
            )}
          </Typography>
          {trend && (
            <Typography variant="caption" color={trend > 0 ? 'error.main' : 'success.main'}>
              {trend > 0 ? '+' : ''}{trend}% vs last period
            </Typography>
          )}
        </Box>
      </Stack>
    </CardContent>
  </Card>
);

export default function CarbonConsolePage() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const { showNotification } = useNotification();
  const navigate = useNavigate();

  useEffect(() => {
    loadSummary();
  }, []);

  const loadSummary = async () => {
    try {
      const data = await getOwnerSummary();
      setSummary(data);
    } catch (error) {
      showNotification({
        message: 'Failed to load carbon console data',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <LinearProgress />
      </Box>
    );
  }

  // Calculate workflow progress
  const workflows = [
    {
      title: 'Collect Activity Data',
      description: 'Enter or import emissions data from your facilities',
      status: summary?.data_entry_progress > 80 ? 'complete' : 'in-progress',
      progress: summary?.data_entry_progress || 0,
      icon: Assignment,
      actionLabel: summary?.data_entry_progress > 0 ? 'Continue Entry' : 'Start Collecting',
      actionPath: '/carbon/data-entry',
    },
    {
      title: 'Calculate Emissions',
      description: 'Apply emission factors and compute CO2e totals',
      status: summary?.calculations_count > 0 ? 'complete' : 'pending',
      progress: summary?.calculations_count > 0 ? 100 : 0,
      icon: Calculate,
      actionLabel: 'Calculate Now',
      actionPath: '/carbon/calculate',
    },
    {
      title: 'Review & Report',
      description: 'Generate GHG inventory reports and disclosures',
      status: summary?.reports_count > 0 ? 'complete' : 'pending',
      progress: null,
      icon: Assessment,
      actionLabel: 'View Reports',
      actionPath: '/carbon/reports',
    },
    {
      title: 'Take Action',
      description: 'Track reduction initiatives and set targets',
      status: 'pending',
      progress: null,
      icon: TrendingUp,
      actionLabel: 'View Initiatives',
      actionPath: '/carbon/initiatives',
    },
  ];

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Carbon Management Console
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Manage your organization's greenhouse gas inventory and climate disclosures
        </Typography>
      </Box>

      {/* Alert if data quality issues */}
      {summary?.quality_score < 70 && (
        <Alert severity="warning" sx={{ mb: 3 }} icon={<Warning />}>
          Data quality score is {summary.quality_score}%. Review flagged records before generating reports.
        </Alert>
      )}

      {/* Key Metrics */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            label="Total Emissions (YTD)"
            value={summary?.total_emissions_ytd?.toLocaleString() || '0'}
            unit="kg CO₂e"
            trend={summary?.emissions_trend || null}
            icon={TrendingUp}
            color="#f44336"
            theme={{ palette: { grey: { 200: '#f5f5f5' } } }}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            label="Emission Sources"
            value={summary?.modules_count || '0'}
            unit="active"
            icon={Assignment}
            color="#ff9800"
            theme={{ palette: { grey: { 200: '#f5f5f5' } } }}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            label="Data Quality Score"
            value={summary?.quality_score || '0'}
            unit="%"
            icon={summary?.quality_score >= 70 ? CheckCircle : Warning}
            color={summary?.quality_score >= 70 ? '#4caf50' : '#ff9800'}
            theme={{ palette: { grey: { 200: '#f5f5f5' } } }}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            label="Reporting Period"
            value={summary?.current_period?.name || 'N/A'}
            icon={Assessment}
            color="#2196f3"
            theme={{ palette: { grey: { 200: '#f5f5f5' } } }}
          />
        </Grid>
      </Grid>

      {/* Workflow Steps */}
      <Typography variant="h5" gutterBottom sx={{ mb: 2 }}>
        Carbon Accounting Workflow
      </Typography>
      <Grid container spacing={3}>
        {workflows.map((workflow, index) => (
          <Grid item xs={12} md={6} key={index}>
            <WorkflowCard
              {...workflow}
              theme={{ palette: { success: { main: '#4caf50' }, warning: { main: '#ff9800' }, grey: { 200: '#f5f5f5', 400: '#bdbdbd' } } }}
            />
          </Grid>
        ))}
      </Grid>

      {/* Quick Actions */}
      <Box sx={{ mt: 4, p: 3, bgcolor: 'grey.50', borderRadius: 2 }}>
        <Typography variant="h6" gutterBottom>
          Quick Actions
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <Button
            variant="contained"
            startIcon={<Assignment />}
            onClick={() => navigate('/carbon/data-entry')}
          >
            Enter Activity Data
          </Button>
          <Button
            variant="outlined"
            startIcon={<Calculate />}
            onClick={() => navigate('/carbon/calculate')}
          >
            Calculate Emissions
          </Button>
          <Button
            variant="outlined"
            startIcon={<Assessment />}
            onClick={() => navigate('/carbon/reports')}
          >
            Generate Report
          </Button>
        </Stack>
      </Box>
    </Box>
  );
}
```

**Acceptance Criteria:**
- Page renders at `/carbon/console`
- Shows 4 workflow cards: Collect → Calculate → Report → Act
- Displays key metrics: total emissions, sources, quality score, period
- Progress bars update based on actual data
- Quick action buttons navigate correctly
- Responsive layout (mobile + desktop)

---

## F3: Breadcrumbs & Contextual Help

**Purpose:** Help users understand where they are in the workflow.

### F3.1: Add Breadcrumbs Component

**File:** `carbon-frontend/src/components/Breadcrumbs.jsx` (NEW)

```jsx
import React from 'react';
import { Breadcrumbs as MuiBreadcrumbs, Link, Typography } from '@mui/material';
import { NavigateNext, Home } from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

export default function Breadcrumbs() {
  const navigate = useNavigate();
  const location = useLocation();

  // Map routes to labels
  const routeLabels = {
    '/carbon': 'Carbon',
    '/carbon/console': 'Console',
    '/carbon/data-entry': 'Activity Data',
    '/carbon/emission-factors': 'Emission Factors',
    '/carbon/reports': 'Reports & Analytics',
    '/carbon/calculate': 'Calculate Emissions',
    '/carbon/settings': 'Settings',
    '/data-owner': 'Data Owner Portal',
    '/data-owner/dashboard': 'Dashboard',
    '/data-owner/assets': 'Assets',
  };

  // Build breadcrumb path
  const pathnames = location.pathname.split('/').filter(x => x);
  const breadcrumbs = pathnames.map((value, index) => {
    const to = `/${pathnames.slice(0, index + 1).join('/')}`;
    const label = routeLabels[to] || value.charAt(0).toUpperCase() + value.slice(1);
    const isLast = index === pathnames.length - 1;

    return isLast ? (
      <Typography key={to} color="text.primary" fontWeight="bold">
        {label}
      </Typography>
    ) : (
      <Link
        key={to}
        underline="hover"
        color="inherit"
        onClick={() => navigate(to)}
        sx={{ cursor: 'pointer' }}
      >
        {label}
      </Link>
    );
  });

  return (
    <MuiBreadcrumbs
      separator={<NavigateNext fontSize="small" />}
      sx={{ mb: 2 }}
    >
      <Link
        underline="hover"
        color="inherit"
        onClick={() => navigate('/')}
        sx={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}
      >
        <Home sx={{ mr: 0.5, fontSize: 20 }} />
        Home
      </Link>
      {breadcrumbs}
    </MuiBreadcrumbs>
  );
}
```

### F3.2: Add Breadcrumbs to Pages

Update each carbon page to include breadcrumbs:

**Files to update:**
- `carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx`
- `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx`
- `carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx`

**Pattern:**
```jsx
import Breadcrumbs from '../../components/Breadcrumbs';

export default function PageName() {
  return (
    <Box sx={{ p: 3 }}>
      <Breadcrumbs />  {/* Add this line */}
      {/* Rest of page content */}
    </Box>
  );
}
```

**Acceptance Criteria:**
- Breadcrumbs show current path (e.g., Home > Carbon > Console)
- Clicking breadcrumb navigates to that section
- Last item is non-clickable and bold
- Consistent across all carbon pages

---

## F4: Tooltips for Carbon Terminology

**Purpose:** Educate users about GHG Protocol terminology.

### F4.1: Create Tooltip Helper Component

**File:** `carbon-frontend/src/components/CarbonTooltip.jsx` (NEW)

```jsx
import React from 'react';
import { Tooltip, IconButton, Typography } from '@mui/material';
import { HelpOutline } from '@mui/icons-material';

const carbonGlossary = {
  'scope-1': 'Direct GHG emissions from sources owned or controlled by your organization (e.g., company vehicles, on-site fuel combustion)',
  'scope-2': 'Indirect GHG emissions from purchased electricity, steam, heating, and cooling',
  'scope-3': 'All other indirect emissions in your value chain (e.g., business travel, employee commuting, purchased goods)',
  'co2e': 'Carbon dioxide equivalent - a standard unit for measuring carbon footprints, expressing impact of different greenhouse gases in terms of CO2',
  'emission-factor': 'A coefficient that quantifies emissions per unit of activity (e.g., kg CO2e per liter of fuel)',
  'reporting-period': 'A defined time period for which emissions are calculated and reported, typically monthly or annually',
  'activity-data': 'Quantifiable measure of activity that results in GHG emissions (e.g., liters of fuel consumed, kWh electricity used)',
  'ghg-protocol': 'The most widely used international accounting standard for measuring and managing GHG emissions',
};

export default function CarbonTooltip({ term, children, placement = 'top' }) {
  const definition = carbonGlossary[term];
  
  if (!definition) {
    console.warn(`No definition found for term: ${term}`);
    return children || null;
  }

  return (
    <Tooltip
      title={
        <Typography variant="body2" sx={{ p: 1 }}>
          {definition}
        </Typography>
      }
      arrow
      placement={placement}
      enterDelay={300}
    >
      {children || (
        <IconButton size="small" sx={{ ml: 0.5 }}>
          <HelpOutline fontSize="small" sx={{ fontSize: 16, opacity: 0.6 }} />
        </IconButton>
      )}
    </Tooltip>
  );
}
```

### F4.2: Add Tooltips to Key Terms

**File:** [`carbon-frontend/src/components/SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx:151-193)

```jsx
import CarbonTooltip from './CarbonTooltip';

// Update scope headers (around line 151)
<Stack direction="row" alignItems="center" spacing={0.5}>
  <ScopeIcon sx={{ color: scopeColor, fontSize: 20 }} />
  <Typography variant="subtitle2" fontWeight="bold">
    {scopeLabel}
  </Typography>
  <CarbonTooltip term={`scope-${scope}`} />  {/* Add this */}
</Stack>
```

**File:** `carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx`

```jsx
import CarbonTooltip from '../../components/CarbonTooltip';

// Add to metric labels
<Stack direction="row" alignItems="center">
  <Typography variant="caption" color="text.secondary">
    Total Emissions (YTD)
  </Typography>
  <CarbonTooltip term="co2e" />
</Stack>
```

**Acceptance Criteria:**
- Tooltips appear on hover over help icons
- Definitions are clear and concise
- Tooltips added to: Scope 1/2/3 labels, CO2e, emission factors
- Consistent styling across app

---

## F5: Route Registration

**Purpose:** Register new Carbon Console page.

### F5.1: Update App Routes

**File:** [`carbon-frontend/src/App.jsx`](carbon-frontend/src/App.jsx:138-320)

Add import:
```jsx
import CarbonConsolePage from './pages/carbon/CarbonConsolePage';
```

Add route (around line 250, in the carbon section):
```jsx
<Route path="/carbon/console" element={<CarbonConsolePage />} />
```

### F5.2: Update Sidebar Navigation

**File:** [`carbon-frontend/src/components/SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx:24-46)

Ensure Carbon Console is first in app menu:
```jsx
const carbonApps = [
  { label: 'Carbon Console', icon: Dashboard, path: '/carbon/console' },
  { label: 'Activity Data', icon: TableChart, path: '/carbon/data-entry' },
  { label: 'Emission Factors', icon: Calculate, path: '/carbon/emission-factors' },
  { label: 'Reports & Analytics', icon: Assessment, path: '/carbon/reports' },
];
```

**Acceptance Criteria:**
- `/carbon/console` route works
- Sidebar shows "Carbon Console" as first menu item
- Clicking navigates correctly
- No console errors

---

## F6: Testing

### F6.1: Manual Browser Testing

```bash
cd carbon-frontend
npm start
```

**Test checklist:**
1. Navigate to `http://localhost:3000/carbon/console`
2. Verify page loads without errors
3. Check all 4 workflow cards render
4. Check metrics display (may show zeros if no data)
5. Click workflow action buttons → verify navigation
6. Click quick action buttons → verify navigation
7. Hover over scope tooltips → verify definitions appear
8. Check breadcrumbs → click each level
9. Test on mobile viewport (responsive layout)
10. Check sidebar → verify "Carbon Console" appears first

### F6.2: Terminology Audit

Verify updated terms appear in UI:
- ✅ "Emission Sources" (not "Modules")
- ✅ "Activity Data" (not "Data Entry")
- ✅ "Scope 1: Direct Emissions" (not just "Scope 1")
- ✅ "Carbon Console" (new landing page)
- ✅ "Reports & Analytics" (not "Report Generator")

---

## Worker 2 Deliverables

1. ✅ `carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx` created
2. ✅ `carbon-frontend/src/components/Breadcrumbs.jsx` created
3. ✅ `carbon-frontend/src/components/CarbonTooltip.jsx` created
4. ✅ Terminology updated in `SidebarMenu.jsx`
5. ✅ Breadcrumbs added to all carbon pages
6. ✅ Tooltips added to key terms
7. ✅ Routes registered in `App.jsx`
8. ✅ Manual browser testing completed
9. ✅ No console errors or warnings

---

# ACCEPTANCE CRITERIA (BOTH WORKERS)

## Backend (Worker 1)
- [ ] Seed command creates 15+ emission factors across Scopes 1/2/3
- [ ] Seed command creates GWP values for CO2, CH4, N2O
- [ ] Seed command creates activity units reference set
- [ ] Validation API returns HTTP 400 for missing `data_table_id`
- [ ] Validation API returns HTTP 400 for tables without scope
- [ ] Validation API returns HTTP 400 for closed reporting periods
- [ ] Validation API returns HTTP 422 for incomplete activity data
- [ ] Migration adds `triggered_by` and `calculation_method` to Calculation
- [ ] All unit tests pass: `python manage.py test emissions.tests.test_calculation_validation`

## Frontend (Worker 2)
- [ ] Carbon Console page renders at `/carbon/console`
- [ ] Sidebar shows "Emission Sources" instead of "Modules"
- [ ] Sidebar shows "Activity Data" instead of "Data Entry"
- [ ] Scope labels include full descriptions (e.g., "Scope 1: Direct Emissions")
- [ ] Breadcrumbs appear on all carbon pages
- [ ] Tooltips display on hover for Scope 1/2/3, CO2e, emission factors
- [ ] Carbon Console shows 4 workflow cards with progress
- [ ] Quick action buttons navigate correctly
- [ ] No console errors in browser
- [ ] Responsive layout works on mobile

## Integration Testing
- [ ] Backend seed data appears in frontend dropdowns (emission factors, units)
- [ ] Validation errors from backend display in frontend forms
- [ ] Carbon Console metrics reflect backend calculation results

---

# FILES MODIFIED/CREATED

## Worker 1 (Backend)

### Created
1. `backend/emissions/management/commands/seed_carbon_reference_data.py`
2. `backend/emissions/migrations/0006_calculation_audit_fields.py`
3. `backend/emissions/tests/test_calculation_validation.py`

### Modified
1. `backend/emissions/views.py` — Added validation to `CalculateAPIView.post()`
2. `backend/emissions/models.py` — (Migration adds fields, no manual edit needed)

## Worker 2 (Frontend)

### Created
1. `carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx`
2. `carbon-frontend/src/components/Breadcrumbs.jsx`
3. `carbon-frontend/src/components/CarbonTooltip.jsx`

### Modified
1. `carbon-frontend/src/components/SidebarMenu.jsx` — Updated labels and app menu
2. `carbon-frontend/src/App.jsx` — Added `/carbon/console` route
3. `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx` — Added breadcrumbs
4. `carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx` — Added breadcrumbs

---

# EXECUTION PROTOCOL

## Phase 1: Workers Execute Independently (Parallel)
1. Worker 1 (raptor) implements B1, B2, B3, B4
2. Worker 2 (mai-code flash) implements F1, F2, F3, F4, F5, F6
3. Workers report completion to master (Zoo)

## Phase 2: Master Reviews
1. Zoo reviews worker deliverables
2. Zoo validates acceptance criteria
3. Zoo identifies any gaps

## Phase 3: Integration Testing (If needed)
1. Run full stack (backend + frontend)
2. Test end-to-end workflows
3. Verify seed data → frontend dropdowns
4. Verify validation errors → frontend display

## Phase 4: Sign-Off
1. Workers confirm all deliverables completed
2. Master confirms all acceptance criteria met
3. Task marked as complete

---

# IMPORTANT NOTES

## For Worker 1 (raptor)
- You're extending existing models, NOT creating new tables
- Follow existing patterns in `backend/emissions/models.py`
- Use `update_or_create()` in seed command for idempotency
- Add logging to management command: `self.stdout.write()`

## For Worker 2 (mai-code flash)
- Match existing UI patterns from `EmissionFactorsPage.jsx`
- Use Material-UI components consistently
- Test responsive layout (xs, sm, md breakpoints)
- Keep API calls in `src/api/emissions.js`

## Architecture Constraints (Both Workers)
- ✅ Carbon uses platform's `DataTable`/`DataRow` for activity data storage
- ✅ Carbon adds domain-specific config (`EmissionFactor`, `ReportingPeriod`)
- ✅ Separation: Platform at `/catalog/`, `/mdm/`; Carbon at `/carbon/`
- ❌ Do NOT create new platform-level models
- ❌ Do NOT modify existing DQ/MDM/Catalog models

---

# SUCCESS CRITERIA

## Backend Success
```bash
# Seed command runs
python manage.py seed_carbon_reference_data
# Output: ✅ Carbon reference data seeded

# Check created data
python manage.py shell
>>> from emissions.models import EmissionFactor, GWP
>>> EmissionFactor.objects.filter(scope=1).count()  # 3+
>>> EmissionFactor.objects.filter(scope=2).count()  # 2+
>>> EmissionFactor.objects.filter(scope=3).count()  # 6+
>>> GWP.objects.count()  # 3+

# Tests pass
python manage.py test emissions.tests.test_calculation_validation
# Output: Ran 5 tests in X.XXXs OK
```

## Frontend Success
```bash
# Build runs without errors
cd carbon-frontend
npm start
# No compilation errors

# Browser console
# No errors or warnings
# Console shows: "Carbon Console loaded successfully"
```

## User Experience Success
- User lands on Carbon Console, sees clear workflow navigation
- User sees "Emission Sources" and understands these are carbon modules
- User hovers over "Scope 1" label, sees tooltip explaining direct emissions
- User clicks "Start Collecting", navigates to activity data entry
- User sees breadcrumbs: Home > Carbon > Activity Data

---

# REFERENCE DOCUMENTS

1. [`plans/CARBON_UI_TERMINOLOGY_ENTERPRISE_AUDIT.md`](plans/CARBON_UI_TERMINOLOGY_ENTERPRISE_AUDIT.md:1-655) — Enterprise benchmarking
2. [`TASK-CARBON-PRODUCTION-WORKFLOWS.md`](TASK-CARBON-PRODUCTION-WORKFLOWS.md:1-1085) — Carbon workflows spec
3. [`plans/CARBON_DATA_TRUST_ARCHITECTURE.md`](plans/CARBON_DATA_TRUST_ARCHITECTURE.md:1-489) — Architecture principles
4. [`TASK-CARBON-P1-SCOPED-OWNER-APPS.md`](TASK-CARBON-P1-SCOPED-OWNER-APPS.md:1-487) — Previous task (completed)
5. [`TASK-OPERATIONAL-EXCELLENCE.md`](TASK-OPERATIONAL-EXCELLENCE.md:1-816) — Track E (completed)

---

# DELIVERY ARTIFACT

Upon completion, create: **`TASK-RESULT-CARBON-PHASE1-UI-WORKFLOWS.md`**

Include:
1. ✅ Summary of changes (backend + frontend)
2. ✅ Test results (unit tests + browser tests)
3. ✅ Screenshots of Carbon Console page
4. ✅ Evidence of terminology updates (before/after)
5. ✅ Acceptance criteria checklist (all items checked)
6. ✅ Known issues or future improvements
7. ✅ Sign-off from both workers

---

**END OF TASK SPECIFICATION**

*Master (Zoo) — Never codes, only reviews and validates*  
*Worker 1 (raptor) — Backend implementation*  
*Worker 2 (mai-code flash) — Frontend implementation*
