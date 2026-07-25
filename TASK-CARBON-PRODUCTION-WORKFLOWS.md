# TASK: Carbon Production Workflows — Data Trust Platform Integration

**Status:** Ready for Implementation  
**Date:** 2026-07-25  
**Philosophy:** Carbon is a domain app built ON TOP of the Data Trust Platform  

---

## Executive Summary

Build production-ready carbon accounting workflows that:
1. ✅ Use platform's generic tables (`DataTable`, `DataRow`) for activity data
2. ✅ Add carbon-specific configuration (`EmissionFactor`, `ReportingPeriod`)
3. ✅ Implement carbon business logic (calculations, validation, reporting)
4. ✅ Support monthly reporting cycles with workflow states
5. ✅ Enable data owners to submit carbon data within their org units

**User Requirements (Confirmed):**
- Hybrid data entry: manual forms + CSV bulk import
- Manual calculation trigger: users click "Calculate Emissions" button
- No approval workflow: data owners directly submit final emissions
- Monthly reporting frequency
- Scope 3 priorities: Categories 1, 3, 6, 7

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│              DATA TRUST PLATFORM (Generic Layer)                 │
│                                                                   │
│  dataschema.DataTable → DataRow (activity data storage)         │
│  catalog.AssetProfile (metadata)                                 │
│  dq.DQRule (quality checks)                                      │
│  mdm.OrgUnit + ReferenceSet (master data)                       │
└─────────────────────────────────────────────────────────────────┘
                            ↑ uses
                            │
┌─────────────────────────────────────────────────────────────────┐
│                 CARBON DOMAIN (emissions/ app)                   │
│                                                                   │
│  EmissionFactor → Calculation ← DataRow (bridge)                │
│  ReportingPeriod (monthly cycles)                                │
│  Validators (scope-specific validation)                          │
│  Services (calculation logic)                                    │
│  Views (dashboards, reports, calculate API)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Tracks

### Track 1: Carbon Configuration Layer (Backend)
**Deliverable:** Carbon-specific models and seed data

#### W1.1: Enhance ReportingPeriod Model
**File:** [`backend/emissions/models.py`](backend/emissions/models.py:8-93)

**Current state:** Model exists with workflow states (draft, open, locked, verified, closed)

**Add:**
```python
# Add to ReportingPeriod model
class ReportingPeriod(models.Model):
    # ... existing fields ...
    
    # NEW: Transition tracking
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        'accounts.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='locked_periods'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        'accounts.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_periods'
    )
    
    # NEW: Submission tracking
    def get_submission_status(self):
        """Returns completion % by org unit."""
        from dataschema.models import DataRow
        from mdm.models import OrgUnit
        
        org_units = OrgUnit.objects.filter(is_active=True)
        status_by_org = []
        
        for org_unit in org_units:
            rows_count = DataRow.objects.filter(
                data_table__module__scope__isnull=False,  # Carbon modules only
                org_unit=org_unit,
                created_at__gte=self.start_date,
                created_at__lte=self.end_date,
            ).count()
            
            calcs_count = Calculation.objects.filter(
                reporting_period=self,
                org_unit=org_unit,
            ).count()
            
            status_by_org.append({
                'org_unit_id': org_unit.id,
                'org_unit_name': org_unit.name,
                'rows_entered': rows_count,
                'calculations_done': calcs_count,
                'status': 'complete' if calcs_count > 0 else 'pending',
            })
        
        return status_by_org
```

**Migration:**
```bash
python manage.py makemigrations emissions
python manage.py migrate emissions
```

#### W1.2: Carbon Reference Data (Platform MDM)
**Files:** 
- Seed script: `backend/emissions/management/commands/seed_carbon_reference_data.py`
- Use platform's [`mdm.ReferenceSet`](backend/mdm/models.py:1-100)

**Create reference sets:**
```python
# backend/emissions/management/commands/seed_carbon_reference_data.py

from django.core.management.base import BaseCommand
from mdm.models import ReferenceSet, ReferenceValue
from catalog.models import DataDomain

class Command(BaseCommand):
    help = 'Seed carbon-specific reference data using platform MDM'
    
    def handle(self, *args, **options):
        # Get or create Carbon domain
        carbon_domain, _ = DataDomain.objects.get_or_create(
            name='Carbon Emissions',
            defaults={'description': 'GHG Protocol Scope 1/2/3 emissions data'}
        )
        
        # Scope 1: Fuel Types
        fuel_types, _ = ReferenceSet.objects.get_or_create(
            code='CARBON_FUEL_TYPES',
            defaults={
                'name': 'Carbon Fuel Types',
                'description': 'Types of fuel for Scope 1 combustion',
                'domain': carbon_domain
            }
        )
        
        fuels = [
            ('DIESEL', 'Diesel'),
            ('PETROL', 'Petrol/Gasoline'),
            ('NG', 'Natural Gas'),
            ('LPG', 'Liquefied Petroleum Gas'),
            ('COAL', 'Coal'),
            ('FUEL_OIL', 'Fuel Oil'),
        ]
        
        for code, display in fuels:
            ReferenceValue.objects.get_or_create(
                reference_set=fuel_types,
                code=code,
                defaults={'display_value': display, 'is_active': True}
            )
        
        # Scope 1: Combustion Sources
        sources, _ = ReferenceSet.objects.get_or_create(
            code='CARBON_COMBUSTION_SOURCES',
            defaults={
                'name': 'Combustion Sources',
                'description': 'Sources of combustion for Scope 1',
                'domain': carbon_domain
            }
        )
        
        source_types = [
            ('VEHICLE', 'Vehicle'),
            ('GENERATOR', 'Generator'),
            ('BOILER', 'Boiler'),
            ('FURNACE', 'Furnace'),
            ('OTHER', 'Other Equipment'),
        ]
        
        for code, display in source_types:
            ReferenceValue.objects.get_or_create(
                reference_set=sources,
                code=code,
                defaults={'display_value': display, 'is_active': True}
            )
        
        # Scope 2: Energy Types
        energy_types, _ = ReferenceSet.objects.get_or_create(
            code='CARBON_ENERGY_TYPES',
            defaults={
                'name': 'Energy Types',
                'description': 'Types of purchased energy for Scope 2',
                'domain': carbon_domain
            }
        )
        
        energies = [
            ('ELECTRICITY', 'Electricity'),
            ('STEAM', 'Steam'),
            ('HEATING', 'District Heating'),
            ('COOLING', 'District Cooling'),
        ]
        
        for code, display in energies:
            ReferenceValue.objects.get_or_create(
                reference_set=energy_types,
                code=code,
                defaults={'display_value': display, 'is_active': True}
            )
        
        # Scope 2: Grid Regions
        grid_regions, _ = ReferenceSet.objects.get_or_create(
            code='CARBON_GRID_REGIONS',
            defaults={
                'name': 'Grid Regions',
                'description': 'Electricity grid regions for emission factors',
                'domain': carbon_domain
            }
        )
        
        regions = [
            ('EG_CAIRO', 'Egypt - Cairo'),
            ('EG_ALEX', 'Egypt - Alexandria'),
            ('EG_NATIONAL', 'Egypt - National Grid Average'),
        ]
        
        for code, display in regions:
            ReferenceValue.objects.get_or_create(
                reference_set=grid_regions,
                code=code,
                defaults={'display_value': display, 'is_active': True}
            )
        
        # Scope 3: Categories (Priority: 1, 3, 6, 7)
        scope3_cats, _ = ReferenceSet.objects.get_or_create(
            code='CARBON_SCOPE3_CATEGORIES',
            defaults={
                'name': 'Scope 3 Categories',
                'description': 'GHG Protocol Scope 3 Categories (Priority subset)',
                'domain': carbon_domain
            }
        )
        
        categories = [
            ('S3_CAT1', 'Category 1: Purchased Goods and Services'),
            ('S3_CAT3', 'Category 3: Fuel- and Energy-Related Activities'),
            ('S3_CAT6', 'Category 6: Business Travel'),
            ('S3_CAT7', 'Category 7: Employee Commuting'),
        ]
        
        for code, display in categories:
            ReferenceValue.objects.get_or_create(
                reference_set=scope3_cats,
                code=code,
                defaults={'display_value': display, 'is_active': True}
            )
        
        self.stdout.write(self.style.SUCCESS('Carbon reference data seeded successfully'))
```

**Run:**
```bash
python manage.py seed_carbon_reference_data
```

#### W1.3: Carbon-Specific Validation
**File:** `backend/emissions/validators.py` (NEW)

```python
# backend/emissions/validators.py

from django.core.exceptions import ValidationError

def validate_carbon_data_row(data_row):
    """
    Validate that carbon data rows have required scope-specific fields.
    Called by platform after generic validation.
    """
    module = data_row.data_table.module
    
    # Skip if not a carbon module
    if module.scope is None:
        return
    
    values = data_row.values
    
    # Scope 1: Direct Emissions (combustion)
    if module.scope == 1:
        required = ['fuel_type', 'combustion_source', 'activity_value', 'activity_unit', 'activity_date']
        missing = [f for f in required if f not in values or not values[f]]
        
        if missing:
            raise ValidationError({
                'values': f"Missing required fields for Scope 1: {', '.join(missing)}. "
                         f"Required fields: fuel_type, combustion_source, activity_value, activity_unit, activity_date"
            })
        
        # Validate activity_value is positive
        try:
            activity_value = float(values.get('activity_value', 0))
            if activity_value <= 0:
                raise ValidationError({'values': 'activity_value must be greater than 0'})
        except (ValueError, TypeError):
            raise ValidationError({'values': 'activity_value must be a number'})
    
    # Scope 2: Indirect Energy Emissions
    elif module.scope == 2:
        required = ['energy_type', 'grid_region', 'activity_value', 'activity_unit', 'activity_date']
        missing = [f for f in required if f not in values or not values[f]]
        
        if missing:
            raise ValidationError({
                'values': f"Missing required fields for Scope 2: {', '.join(missing)}. "
                         f"Required fields: energy_type, grid_region, activity_value, activity_unit, activity_date"
            })
        
        # Validate activity_value is positive
        try:
            activity_value = float(values.get('activity_value', 0))
            if activity_value <= 0:
                raise ValidationError({'values': 'activity_value must be greater than 0'})
        except (ValueError, TypeError):
            raise ValidationError({'values': 'activity_value must be a number'})
    
    # Scope 3: Value Chain Emissions
    elif module.scope == 3:
        required = ['category', 'activity_value', 'activity_unit', 'activity_date']
        missing = [f for f in required if f not in values or not values[f]]
        
        if missing:
            raise ValidationError({
                'values': f"Missing required fields for Scope 3: {', '.join(missing)}. "
                         f"Required fields: category, activity_value, activity_unit, activity_date"
            })
        
        # Validate activity_value is positive
        try:
            activity_value = float(values.get('activity_value', 0))
            if activity_value <= 0:
                raise ValidationError({'values': 'activity_value must be greater than 0'})
        except (ValueError, TypeError):
            raise ValidationError({'values': 'activity_value must be a number'})
```

**Register validator in platform:**

**File:** [`backend/dataschema/views.py`](backend/dataschema/views.py:1-500)

```python
# In DataRowViewSet.perform_create()
from emissions.validators import validate_carbon_data_row

def perform_create(self, serializer):
    row = serializer.save(created_by=self.request.user)
    
    # Call carbon validator if this is a carbon module
    if row.data_table.module.scope:
        validate_carbon_data_row(row)
```

---

### Track 2: Carbon Calculation Service (Backend)

#### W2.1: Enhanced CalculateAPIView
**File:** [`backend/emissions/views.py`](backend/emissions/views.py:624-697)

**Current:** Basic calculation endpoint exists

**Enhance:**
```python
class CalculateAPIView(APIView):
    """
    POST /carbon-api/emissions/calculate/
    Manual trigger for emission calculations.
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'table_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='DataTable ID to calculate'),
                'reporting_period_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Reporting period'),
                'recalculate': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False, description='Recalculate existing'),
            },
            required=['table_id', 'reporting_period_id']
        ),
        responses={
            200: openapi.Response(
                'Calculation successful',
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'calculations_created': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_co2e_tonnes': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'scope': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'unmatched_rows': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'warnings': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                    }
                )
            ),
            400: 'Invalid request',
            403: 'Access denied',
            404: 'Table or period not found',
        }
    )
    def post(self, request):
        from dataschema.models import DataTable, DataRow
        from decimal import Decimal, InvalidOperation
        import logging
        
        logger = logging.getLogger('emissions')
        
        table_id = request.data.get('table_id')
        period_id = request.data.get('reporting_period_id')
        recalculate = request.data.get('recalculate', False)
        
        # Validate inputs
        if not table_id or not period_id:
            return Response(
                {'error': 'table_id and reporting_period_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get table and check access
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response({'error': 'Table not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check RBAC
        user_org_units = get_visible_org_units(request.user)
        if table.module.org_unit not in user_org_units:
            return Response({'error': 'Access denied to this table'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get reporting period
        try:
            period = ReportingPeriod.objects.get(id=period_id)
        except ReportingPeriod.DoesNotExist:
            return Response({'error': 'Reporting period not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if period is open
        if period.status not in ['draft', 'open']:
            return Response(
                {
                    'error': 'PeriodClosed',
                    'message': f'Period "{period.name}" is {period.status}. Only draft/open periods accept new calculations.',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get scope
        scope = table.module.scope
        if not scope:
            return Response(
                {'error': 'NotCarbonTable', 'message': 'This table is not assigned to a carbon scope'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get data rows
        rows = DataRow.objects.filter(
            data_table=table,
            is_archived=False
        )
        
        if rows.count() == 0:
            return Response(
                {
                    'error': 'EmptyTable',
                    'message': f'Table "{table.name}" has no data rows to calculate',
                    'suggested_action': 'Add data rows via POST /dataschema/rows/ or bulk import',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate emissions
        calculations_created = 0
        unmatched_rows = 0
        warnings = []
        
        for row in rows:
            # Skip if already calculated (unless recalculate=True)
            if not recalculate and Calculation.objects.filter(data_row=row, reporting_period=period).exists():
                continue
            
            # Extract activity data
            try:
                activity_value = Decimal(str(row.values.get('activity_value', 0)))
                activity_unit = row.values.get('activity_unit', '')
                activity_date = row.values.get('activity_date')
                
                if activity_value <= 0:
                    warnings.append(f"Row {row.id}: activity_value must be > 0, skipping")
                    unmatched_rows += 1
                    continue
                
            except (ValueError, TypeError, InvalidOperation) as e:
                warnings.append(f"Row {row.id}: Invalid activity_value '{row.values.get('activity_value')}', skipping")
                unmatched_rows += 1
                continue
            
            # Find emission factor (scope-specific logic)
            ef = None
            
            if scope == 1:
                # Scope 1: Match by fuel_type
                fuel_type = row.values.get('fuel_type', '').lower()
                ef = EmissionFactor.objects.filter(
                    scope=1,
                    category='mobile_combustion',
                    subcategory__icontains=fuel_type,
                    is_active=True
                ).first()
            
            elif scope == 2:
                # Scope 2: Match by energy_type + grid_region
                energy_type = row.values.get('energy_type', '').lower()
                grid_region = row.values.get('grid_region', '').lower()
                ef = EmissionFactor.objects.filter(
                    scope=2,
                    category__icontains=energy_type,
                    country_code__icontains='EG',  # Egypt
                    is_active=True
                ).first()
            
            elif scope == 3:
                # Scope 3: Match by category
                category = row.values.get('category', '').lower()
                ef = EmissionFactor.objects.filter(
                    scope=3,
                    category__icontains=category,
                    is_active=True
                ).first()
            
            if not ef:
                warnings.append(f"Row {row.id}: No emission factor found for {row.values}, skipping")
                unmatched_rows += 1
                continue
            
            # Calculate CO2e
            co2e_kg = activity_value * ef.factor_value
            
            # Create or update calculation
            calc, created = Calculation.objects.update_or_create(
                data_row=row,
                reporting_period=period,
                defaults={
                    'emission_factor': ef,
                    'activity_value': activity_value,
                    'activity_unit': activity_unit,
                    'co2e_kg': co2e_kg,
                    'scope': scope,
                    'category': ef.category,
                    'reporting_year': period.start_date.year,
                    'activity_date': activity_date,
                    'org_unit': table.module.org_unit,
                    'calculated_by': request.user,
                }
            )
            
            if created or recalculate:
                calculations_created += 1
        
        # Summary
        total_co2e = Calculation.objects.filter(
            data_row__data_table=table,
            reporting_period=period
        ).aggregate(total=Sum('co2e_kg'))['total'] or 0
        
        total_co2e_tonnes = float(total_co2e) / 1000
        
        logger.info(
            f"Calculation complete: table={table.id}, period={period.id}, "
            f"created={calculations_created}, unmatched={unmatched_rows}, total={total_co2e_tonnes:.2f} tonnes"
        )
        
        return Response({
            'calculations_created': calculations_created,
            'total_co2e_tonnes': round(total_co2e_tonnes, 2),
            'scope': scope,
            'reporting_period': period.name,
            'table_name': table.name,
            'unmatched_rows': unmatched_rows,
            'warnings': warnings if warnings else None,
        })
```

---

### Track 3: Monthly Reporting Workflow (Backend)

#### W3.1: Reporting Period Transition API
**File:** [`backend/emissions/views.py`](backend/emissions/views.py:45-80)

**Add to ReportingPeriodViewSet:**
```python
@action(detail=True, methods=['post'])
@swagger_auto_schema(
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'new_status': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['draft', 'open', 'locked', 'verified', 'closed']
            ),
            'notify_owners': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False),
        },
        required=['new_status']
    ),
    responses={200: ReportingPeriodSerializer, 400: 'Invalid transition'}
)
def transition(self, request, pk=None):
    """
    POST /carbon-api/emissions/reporting-periods/{id}/transition/
    Transition period between workflow states.
    """
    period = self.get_object()
    new_status = request.data.get('new_status')
    notify_owners = request.data.get('notify_owners', False)
    
    # Validate transition
    allowed_transitions = {
        'draft': ['open'],
        'open': ['locked', 'draft'],  # Can reopen
        'locked': ['verified', 'open'],  # Can unlock
        'verified': ['closed', 'locked'],  # Can reverify
        'closed': ['draft'],  # Can reopen for corrections
    }
    
    if new_status not in allowed_transitions.get(period.status, []):
        return Response(
            {
                'error': f"Cannot transition from '{period.status}' to '{new_status}'",
                'allowed_transitions': allowed_transitions.get(period.status, []),
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update status
    old_status = period.status
    period.status = new_status
    
    # Track who/when
    if new_status == 'locked':
        period.locked_at = timezone.now()
        period.locked_by = request.user
    elif new_status == 'verified':
        period.verified_at = timezone.now()
        period.verified_by = request.user
    
    period.save()
    
    # Create governance event
    from catalog.models import GovernanceEvent
    GovernanceEvent.objects.create(
        entity_type='reporting_period',
        entity_id=period.id,
        event_type='status_change',
        description=f"Period '{period.name}' transitioned from {old_status} to {new_status}",
        user=request.user,
    )
    
    # TODO: Send email notifications if notify_owners=True
    # if notify_owners and new_status == 'open':
    #     send_period_open_notification(period)
    
    return Response(ReportingPeriodSerializer(period).data)


@action(detail=True, methods=['get'])
def submission_status(self, request, pk=None):
    """
    GET /carbon-api/emissions/reporting-periods/{id}/submission-status/
    Returns completion status per org unit.
    """
    period = self.get_object()
    status_by_org = period.get_submission_status()
    
    total_orgs = len(status_by_org)
    complete_orgs = sum(1 for s in status_by_org if s['status'] == 'complete')
    overall_completion = (complete_orgs / total_orgs * 100) if total_orgs > 0 else 0
    
    return Response({
        'period_name': period.name,
        'period_status': period.status,
        'start_date': period.start_date,
        'end_date': period.end_date,
        'org_units': status_by_org,
        'overall_completion': round(overall_completion, 1),
        'total_org_units': total_orgs,
        'complete_org_units': complete_orgs,
    })
```

---

### Track 4: Frontend Carbon Workflows

#### W4.1: Enhanced Data Entry Page
**File:** [`carbon-frontend/src/pages/dataschema/DataEntryPage.jsx`](carbon-frontend/src/pages/dataschema/DataEntryPage.jsx:1-300)

**Add scope-specific form fields:**
```jsx
// In DataEntryPage, add scope detection
const [scopeFields, setScopeFields] = useState([]);

useEffect(() => {
  if (selectedTable) {
    // Detect scope from table's module
    const scope = selectedTable.module?.scope;
    
    if (scope === 1) {
      setScopeFields([
        { name: 'fuel_type', label: 'Fuel Type', type: 'select', reference_set: 'CARBON_FUEL_TYPES', required: true },
        { name: 'combustion_source', label: 'Combustion Source', type: 'select', reference_set: 'CARBON_COMBUSTION_SOURCES', required: true },
        { name: 'activity_value', label: 'Fuel Amount', type: 'number', required: true },
        { name: 'activity_unit', label: 'Unit', type: 'text', placeholder: 'e.g., liters', required: true },
        { name: 'activity_date', label: 'Activity Date', type: 'date', required: true },
      ]);
    } else if (scope === 2) {
      setScopeFields([
        { name: 'energy_type', label: 'Energy Type', type: 'select', reference_set: 'CARBON_ENERGY_TYPES', required: true },
        { name: 'grid_region', label: 'Grid Region', type: 'select', reference_set: 'CARBON_GRID_REGIONS', required: true },
        { name: 'activity_value', label: 'Energy Amount', type: 'number', required: true },
        { name: 'activity_unit', label: 'Unit', type: 'text', placeholder: 'e.g., kWh', required: true },
        { name: 'activity_date', label: 'Activity Date', type: 'date', required: true },
      ]);
    } else if (scope === 3) {
      setScopeFields([
        { name: 'category', label: 'Scope 3 Category', type: 'select', reference_set: 'CARBON_SCOPE3_CATEGORIES', required: true },
        { name: 'supplier_name', label: 'Supplier Name', type: 'text', required: false },
        { name: 'activity_value', label: 'Activity Amount', type: 'number', required: true },
        { name: 'activity_unit', label: 'Unit', type: 'text', placeholder: 'e.g., kg, km', required: true },
        { name: 'activity_date', label: 'Activity Date', type: 'date', required: true },
      ]);
    } else {
      setScopeFields([]);  // Not a carbon table
    }
  }
}, [selectedTable]);

// Render scope-specific fields
{scopeFields.map(field => (
  <FormField key={field.name} field={field} form={form} setForm={setForm} />
))}
```

#### W4.2: Calculate Emissions Button
**File:** `carbon-frontend/src/pages/dataschema/TableDetailPage.jsx` (NEW or enhance existing)

```jsx
import { Calculate as CalculateIcon } from '@mui/icons-material';
import { Button, CircularProgress, Alert } from '@mui/material';

function TableDetailPage() {
  const [calculating, setCalculating] = useState(false);
  const [calcResult, setCalcResult] = useState(null);
  const { tableId } = useParams();
  const { showNotification } = useNotification();
  const navigate = useNavigate();
  
  const handleCalculate = async () => {
    // Get current reporting period (or let user select)
    const currentPeriod = await api.get('/carbon-api/emissions/reporting-periods/active/');
    
    setCalculating(true);
    setCalcResult(null);
    
    try {
      const response = await api.post('/carbon-api/emissions/calculate/', {
        table_id: parseInt(tableId),
        reporting_period_id: currentPeriod.data.id,
        recalculate: false,
      });
      
      setCalcResult(response.data);
      
      showNotification({
        type: 'success',
        message: `Calculated ${response.data.calculations_created} emissions. Total: ${response.data.total_co2e_tonnes} tonnes CO₂e`,
      });
      
      // Optionally navigate to report page
      // navigate(`/carbon/reports?period=${currentPeriod.data.id}`);
      
    } catch (error) {
      showNotification({
        type: 'error',
        message: error.response?.data?.message || 'Calculation failed',
      });
    } finally {
      setCalculating(false);
    }
  };
  
  return (
    <Box>
      <Button
        variant="contained"
        color="primary"
        startIcon={calculating ? <CircularProgress size={20} /> : <CalculateIcon />}
        onClick={handleCalculate}
        disabled={calculating || rowCount === 0}
      >
        {calculating ? 'Calculating...' : 'Calculate Emissions'}
      </Button>
      
      {calcResult && (
        <Alert severity="success" sx={{ mt: 2 }}>
          <strong>Calculation Complete:</strong><br />
          • {calcResult.calculations_created} calculations created<br />
          • Total: {calcResult.total_co2e_tonnes} tonnes CO₂e<br />
          • Scope: {calcResult.scope}<br />
          {calcResult.unmatched_rows > 0 && (
            <span style={{ color: 'orange' }}>• {calcResult.unmatched_rows} rows could not be matched to emission factors</span>
          )}
        </Alert>
      )}
    </Box>
  );
}
```

#### W4.3: Reporting Period Dashboard
**File:** `carbon-frontend/src/pages/emissions/ReportingPeriodDashboard.jsx` (NEW)

```jsx
import { useState, useEffect } from 'react';
import {
  Box, Typography, Table, TableBody, TableCell, TableHead, TableRow,
  Button, Chip, LinearProgress, Card, CardContent
} from '@mui/material';
import api from '../../api';

export default function ReportingPeriodDashboard() {
  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState(null);
  const [submissionStatus, setSubmissionStatus] = useState(null);
  
  useEffect(() => {
    loadPeriods();
  }, []);
  
  const loadPeriods = async () => {
    const response = await api.get('/carbon-api/emissions/reporting-periods/');
    setPeriods(response.data.results || response.data);
  };
  
  const handleTransition = async (periodId, newStatus) => {
    try {
      await api.post(`/carbon-api/emissions/reporting-periods/${periodId}/transition/`, {
        new_status: newStatus,
        notify_owners: true,
      });
      loadPeriods();
      showNotification({ type: 'success', message: `Period transitioned to ${newStatus}` });
    } catch (error) {
      showNotification({ type: 'error', message: error.response?.data?.error || 'Transition failed' });
    }
  };
  
  const loadSubmissionStatus = async (periodId) => {
    const response = await api.get(`/carbon-api/emissions/reporting-periods/${periodId}/submission-status/`);
    setSubmissionStatus(response.data);
  };
  
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Monthly Reporting Cycles</Typography>
      
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Period</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Dates</TableCell>
            <TableCell>Completion</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {periods.map(period => (
            <TableRow key={period.id}>
              <TableCell>{period.name}</TableCell>
              <TableCell>
                <Chip
                  label={period.status}
                  color={
                    period.status === 'open' ? 'success' :
                    period.status === 'locked' ? 'warning' :
                    period.status === 'verified' ? 'info' :
                    'default'
                  }
                />
              </TableCell>
              <TableCell>{period.start_date} — {period.end_date}</TableCell>
              <TableCell>
                <Button size="small" onClick={() => loadSubmissionStatus(period.id)}>
                  View Progress
                </Button>
              </TableCell>
              <TableCell>
                {period.status === 'draft' && (
                  <Button onClick={() => handleTransition(period.id, 'open')}>
                    Open for Submissions
                  </Button>
                )}
                {period.status === 'open' && (
                  <Button onClick={() => handleTransition(period.id, 'locked')}>
                    Lock Period
                  </Button>
                )}
                {period.status === 'locked' && (
                  <Button onClick={() => handleTransition(period.id, 'verified')}>
                    Verify & Approve
                  </Button>
                )}
                {period.status === 'verified' && (
                  <Button onClick={() => handleTransition(period.id, 'closed')}>
                    Close Period
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      
      {submissionStatus && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6">Submission Status: {submissionStatus.period_name}</Typography>
            <Typography variant="h5" color="primary">
              Overall Completion: {submissionStatus.overall_completion}%
            </Typography>
            <LinearProgress variant="determinate" value={submissionStatus.overall_completion} sx={{ my: 2 }} />
            
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Org Unit</TableCell>
                  <TableCell>Rows Entered</TableCell>
                  <TableCell>Calculations</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {submissionStatus.org_units.map(org => (
                  <TableRow key={org.org_unit_id}>
                    <TableCell>{org.org_unit_name}</TableCell>
                    <TableCell>{org.rows_entered}</TableCell>
                    <TableCell>{org.calculations_done}</TableCell>
                    <TableCell>
                      <Chip
                        label={org.status}
                        color={org.status === 'complete' ? 'success' : 'warning'}
                        size="small"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
```

---

## Acceptance Criteria

### Track 1: Configuration
- [ ] `ReportingPeriod` has `locked_by`, `verified_by`, `get_submission_status()` method
- [ ] Carbon reference data seeded: fuel types, combustion sources, energy types, grid regions, Scope 3 categories
- [ ] `validate_carbon_data_row()` enforces scope-specific required fields
- [ ] Platform `DataRowViewSet` calls carbon validator on create

### Track 2: Calculation
- [ ] `POST /carbon-api/emissions/calculate/` creates `Calculation` records from `DataRow`
- [ ] Calculation matches rows to emission factors by scope (fuel_type for S1, energy_type+grid for S2, category for S3)
- [ ] Returns summary: calculations_created, total_co2e_tonnes, unmatched_rows, warnings
- [ ] Handles empty tables with actionable error message
- [ ] Handles closed reporting periods with error

### Track 3: Reporting Workflow
- [ ] `POST /carbon-api/emissions/reporting-periods/{id}/transition/` validates state transitions
- [ ] Tracks who/when for lock and verify transitions
- [ ] Creates `GovernanceEvent` for each transition
- [ ] `GET /carbon-api/emissions/reporting-periods/{id}/submission-status/` returns org-unit completion %

### Track 4: Frontend
- [ ] Data entry page shows scope-specific fields (fuel_type for S1, energy_type for S2, category for S3)
- [ ] Calculate button triggers calculation and shows success/error message
- [ ] Reporting period dashboard shows periods with status chips
- [ ] Transition buttons enabled/disabled based on current status
- [ ] Submission status card shows completion % by org unit

---

## Testing Protocol

### Backend Tests
```bash
# Test validation
python manage.py shell
from emissions.validators import validate_carbon_data_row
from dataschema.models import DataRow
row = DataRow.objects.filter(data_table__module__scope=1).first()
validate_carbon_data_row(row)  # Should pass or raise ValidationError

# Test calculation
curl -X POST http://localhost:8000/carbon-api/emissions/calculate/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_id": 1, "reporting_period_id": 1}'

# Test period transition
curl -X POST http://localhost:8000/carbon-api/emissions/reporting-periods/1/transition/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_status": "open", "notify_owners": true}'
```

### Frontend Tests
1. Navigate to `/carbon/data-entry/module/1` (Scope 1 module)
2. Select a table → should show fuel_type, combustion_source fields
3. Enter data → should validate required fields
4. Click "Calculate Emissions" → should show success message with tonnes CO2e
5. Navigate to `/carbon/reporting-periods` → should show periods with status
6. Click "Open for Submissions" → status should change to "open"
7. Click "View Progress" → should show org-unit completion %

---

## Deployment Checklist

### Backend
- [ ] Run migrations: `python manage.py migrate emissions`
- [ ] Seed reference data: `python manage.py seed_carbon_reference_data`
- [ ] Create initial reporting period: `ReportingPeriod.objects.create(...)`
- [ ] Verify carbon validators registered in `dataschema/views.py`

### Frontend
- [ ] Add routes for `/carbon/reporting-periods`
- [ ] Add "Calculate Emissions" button to table detail pages
- [ ] Test scope-specific forms on data entry pages

### Production
- [ ] Monitor calculation API performance (should complete <10s for 1000 rows)
- [ ] Set up email notifications for period transitions (future enhancement)
- [ ] Configure backup schedule for `emissions_calculation` table
- [ ] Document user guide for data owners

---

## Next Steps After Completion

1. **Track G: Report Generator** — Enhanced reporting with saved configurations
2. **DQ Dashboard UI** — Integrate quality metrics into carbon dashboards
3. **Bulk CSV Import** — Enhanced template generator for scope-specific imports
4. **Materiality Assessment** — Automated Scope 3 category prioritization
5. **Workflow Automation** — Auto-create monthly reporting periods via cron job

---

**Implementation Priority:** Complete Tracks 1-4 sequentially over 2 weeks for production-ready carbon workflows.
