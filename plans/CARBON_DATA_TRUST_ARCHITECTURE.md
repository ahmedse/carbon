# Carbon Domain on Data Trust Platform — Correct Architecture

**Philosophy:** Carbon is a **domain app** built ON TOP of the generic Data Trust Platform (catalog, dataschema, MDM, DQ), not a replacement for it.

**Platform Core:** Generic tables (`DataTable`, `DataRow`, `Module`) host **all domains** — carbon is just one domain using the platform.

---

## Core Principle: Data Trust Platform

```
┌─────────────────────────────────────────────────────────────────┐
│            DATA TRUST PLATFORM (Generic Layer)                   │
│  Like Ataccama, Collibra — domain-agnostic data management      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ dataschema: DataTable, DataRow, DataField               │  │
│  │ - Generic storage for ANY domain's data                 │  │
│  │ - Carbon fuel data, HR data, finance data all here      │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ catalog: AssetProfile, DataDomain, GlossaryTerm         │  │
│  │ - Metadata for ANY table/field regardless of domain     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ dq: DQRule, DQResult, FieldProfile, TableProfile        │  │
│  │ - Quality checks on ANY table regardless of domain      │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ mdm: OrgUnit, ReferenceSet, ReferenceValue              │  │
│  │ - Master data for ANY domain (org structure + lookups)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ core: Module — top-level container for ANY domain       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ↑ uses
                            │
┌─────────────────────────────────────────────────────────────────┐
│                  CARBON DOMAIN APP (emissions/)                  │
│  Domain-specific business logic built ON the platform           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Carbon Configuration (Domain Metadata)                   │  │
│  │ - EmissionFactor: Conversion coefficients                │  │
│  │ - ReportingPeriod: Monthly/quarterly cycles              │  │
│  │ - CalculationRule: Auto-calculation triggers             │  │
│  │ - ReportConfig: Saved report templates                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Carbon Business Logic                                    │  │
│  │ - Calculation: Links DataRow → EmissionFactor → CO2e    │  │
│  │ - Services: profile_table(), calculate_emissions()       │  │
│  │ - Views: OwnerDashboard, ReportGenerator, Calculate API  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Corrected Architecture: Carbon Uses Platform Tables

### Platform Layer (Generic - Unchanged)

#### 1. Module (core.Module)
```python
# Already exists - generic container for ANY domain
class Module(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    scope = models.PositiveSmallIntegerField(  # Carbon-specific: 1/2/3
        choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')],
        null=True, blank=True  # NULL for non-carbon modules
    )
    org_unit = models.ForeignKey('mdm.OrgUnit', ...)
    
    # Examples:
    # - "Vehicle Fleet Data" (scope=1, carbon domain)
    # - "Employee Records" (scope=NULL, HR domain)
    # - "Purchase Orders" (scope=NULL, finance domain)
```

#### 2. DataTable (dataschema.DataTable)
```python
# Already exists - hosts data for ANY domain
class DataTable(models.Model):
    name = models.CharField(max_length=200)
    module = models.ForeignKey('core.Module', ...)
    
    # Examples:
    # - "Diesel Fuel Consumption" (module.scope=1)
    # - "Electricity Bills" (module.scope=2)
    # - "Business Travel Receipts" (module.scope=3)
    # - "Employee Training Records" (module.scope=NULL, HR domain)
```

#### 3. DataRow (dataschema.DataRow)
```python
# Already exists - stores actual data for ANY domain
class DataRow(models.Model):
    data_table = models.ForeignKey('dataschema.DataTable', ...)
    values = models.JSONField()  # {"fuel_type": "diesel", "liters": 100.5, "date": "2025-12-01"}
    
    # This same model stores:
    # - Carbon fuel data: {"fuel_type": "diesel", "liters": 100.5}
    # - HR data: {"employee_name": "Ahmed", "department": "IT"}
    # - Finance data: {"invoice_number": "INV-001", "amount": 5000}
```

### Carbon Domain Layer (emissions/)

#### 1. EmissionFactor (Domain Configuration)
```python
# Carbon-specific: conversion coefficients
class EmissionFactor(models.Model):
    name = models.CharField(max_length=200)  # "Egypt Grid 2025"
    scope = models.PositiveSmallIntegerField(choices=[(1,'1'),(2,'2'),(3,'3')])
    category = models.CharField(max_length=50)  # "electricity", "mobile_combustion"
    factor_value = models.DecimalField(...)  # 0.53 kg CO2e per kWh
    activity_unit = models.CharField(max_length=50)  # "kWh"
    
    # Lives in emissions/ app — carbon domain configuration
```

#### 2. Calculation (Domain Business Logic)
```python
# Carbon-specific: links platform data → emission factors → CO2e
class Calculation(models.Model):
    data_row = models.ForeignKey('dataschema.DataRow', ...)  # ← USES PLATFORM TABLE
    emission_factor = models.ForeignKey(EmissionFactor, ...)
    activity_value = models.DecimalField(...)
    co2e_kg = models.DecimalField(...)
    scope = models.PositiveSmallIntegerField(...)
    reporting_period = models.ForeignKey(ReportingPeriod, ...)
    
    # This is the BRIDGE between platform (DataRow) and carbon domain (EmissionFactor)
```

#### 3. ReportingPeriod (Domain Configuration)
```python
# Carbon-specific: monthly/quarterly reporting cycles
class ReportingPeriod(models.Model):
    name = models.CharField(max_length=100)  # "January 2025"
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(...)  # draft, open, locked, verified, closed
    
    # Lives in emissions/ app — carbon domain configuration
```

---

## How Carbon Workflows Use Platform Tables

### Workflow 1: Data Entry (Platform Generic)

```python
# Step 1: User navigates to carbon data entry
# URL: /carbon/data-entry/module/5  (Module with scope=1)

# Step 2: User sees tables in that module
tables = DataTable.objects.filter(module__scope=1, module__org_unit=user.org_unit)
# Returns: ["Diesel Fuel Consumption", "Natural Gas Usage", "Company Vehicles"]

# Step 3: User enters data into generic DataRow table
DataRow.objects.create(
    data_table=diesel_table,
    values={
        "date": "2025-12-01",
        "fuel_type": "diesel",
        "liters": 100.5,
        "vehicle_id": "BUS001",
        "odometer": 1234.5
    },
    org_unit=user.org_unit,
    created_by=user
)

# Platform handles:
# - ✅ RBAC scoping (via org_unit)
# - ✅ Data quality checks (via dq app)
# - ✅ Catalog metadata (via AssetProfile)
# - ✅ Audit trail (via GovernanceEvent)
```

### Workflow 2: Emission Calculation (Carbon Domain)

```python
# Step 1: User clicks "Calculate Emissions" button
# POST /carbon-api/emissions/calculate/

# Step 2: Carbon service finds relevant DataRows
rows = DataRow.objects.filter(
    data_table__module__scope=1,
    data_table__module__org_unit=user.org_unit,
    is_archived=False
)

# Step 3: For each row, find matching emission factor
for row in rows:
    fuel_type = row.values.get('fuel_type')  # "diesel"
    liters = row.values.get('liters')  # 100.5
    
    # Find emission factor for diesel
    ef = EmissionFactor.objects.get(
        scope=1,
        category='mobile_combustion',
        subcategory=fuel_type
    )
    
    # Calculate CO2e
    co2e_kg = Decimal(liters) * ef.factor_value
    
    # Store calculation (carbon domain)
    Calculation.objects.create(
        data_row=row,  # ← Links to platform DataRow
        emission_factor=ef,
        activity_value=liters,
        co2e_kg=co2e_kg,
        scope=1,
        reporting_period=current_period,
        org_unit=user.org_unit
    )

# Result: Platform DataRow + Carbon Calculation = Complete audit trail
```

### Workflow 3: Reporting (Carbon Domain)

```python
# Generate report for Scope 1 emissions
calculations = Calculation.objects.filter(
    reporting_period=period,
    scope=1,
    org_unit=user.org_unit
).select_related('data_row', 'emission_factor')

total_co2e = calculations.aggregate(Sum('co2e_kg'))['co2e_kg__sum']

# Drill down to source data
for calc in calculations:
    original_data = calc.data_row.values  # {"fuel_type": "diesel", "liters": 100.5}
    table_name = calc.data_row.data_table.name  # "Diesel Fuel Consumption"
    # Show in report...
```

---

## What Lives Where

### Platform Core (dataschema, catalog, dq, mdm, core)
| Model | Purpose | Domains |
|-------|---------|---------|
| `Module` | Top-level container | **ALL** (carbon, HR, finance, etc.) |
| `DataTable` | Table definition | **ALL** |
| `DataRow` | Actual data storage | **ALL** |
| `AssetProfile` | Metadata/governance | **ALL** |
| `DQRule` | Quality checks | **ALL** |
| `OrgUnit` | Organizational hierarchy | **ALL** |
| `ReferenceSet` | Dropdown values | **ALL** (fuel types, departments, etc.) |

### Carbon Domain (emissions/)
| Model | Purpose | Carbon-Specific |
|-------|---------|-----------------|
| `EmissionFactor` | Conversion coefficients | ✅ Yes |
| `Calculation` | CO2e results | ✅ Yes |
| `ReportingPeriod` | Monthly cycles | ✅ Yes |
| `CalculationRule` | Auto-calc triggers | ✅ Yes |
| `ReportConfig` | Saved reports | ✅ Yes |
| `GWP` | GHG gas potentials | ✅ Yes |

---

## Carbon Configuration: How to Make It "Robust"

Your concern was about "robust way for self-contained carbon system." Here's how we achieve that **while respecting platform philosophy**:

### 1. Carbon-Specific Validation (Domain Layer)

```python
# backend/emissions/validators.py

def validate_carbon_data_row(data_row):
    """
    Carbon domain validator for DataRow.
    Called by platform after generic validation passes.
    """
    module = data_row.data_table.module
    
    if module.scope is None:
        return  # Not a carbon module, skip
    
    # Scope-specific validation
    if module.scope == 1:
        required = ['fuel_type', 'combustion_source', 'activity_value']
    elif module.scope == 2:
        required = ['energy_type', 'grid_region', 'activity_value']
    elif module.scope == 3:
        required = ['category', 'supplier_name', 'activity_value']
    
    missing = [f for f in required if f not in data_row.values]
    if missing:
        raise ValidationError(
            f"Missing required fields for Scope {module.scope}: {', '.join(missing)}"
        )

# Register validator in platform
# backend/dataschema/views.py
from emissions.validators import validate_carbon_data_row

class DataRowViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        row = serializer.save()
        
        # Call domain validators
        if row.data_table.module.scope:  # If carbon module
            validate_carbon_data_row(row)
```

### 2. Carbon-Specific Reference Data (MDM Layer)

```python
# Use platform's ReferenceSet for carbon dropdown values
from mdm.models import ReferenceSet, ReferenceValue

# Seed data migration
fuel_types = ReferenceSet.objects.create(
    name="Carbon Fuel Types",
    code="CARBON_FUEL_TYPES",
    domain=DataDomain.objects.get(name="Carbon Emissions")
)

ReferenceValue.objects.bulk_create([
    ReferenceValue(reference_set=fuel_types, code="DIESEL", display_value="Diesel"),
    ReferenceValue(reference_set=fuel_types, code="PETROL", display_value="Petrol"),
    ReferenceValue(reference_set=fuel_types, code="NG", display_value="Natural Gas"),
])

# Use in frontend forms
# GET /mdm/field-options/?reference_set=CARBON_FUEL_TYPES
# Returns: [{"code": "DIESEL", "display_value": "Diesel"}, ...]
```

### 3. Carbon-Specific Catalog Metadata

```python
# Use platform's DataDomain for carbon classification
carbon_domain = DataDomain.objects.create(
    name="Carbon Emissions",
    description="GHG Protocol Scope 1/2/3 emissions data"
)

# Tag carbon tables
for table in DataTable.objects.filter(module__scope__isnull=False):
    AssetProfile.objects.update_or_create(
        data_table=table,
        defaults={
            'domain': carbon_domain,
            'classification': 'internal',
            'owner': table.module.org_unit.owner
        }
    )
```

### 4. Carbon-Specific DQ Rules

```python
# Use platform's DQRule for carbon quality checks
from dq.models import DQRule

# Rule: Fuel consumption must be positive
DQRule.objects.create(
    name="Positive Fuel Consumption",
    rule_type="range",
    data_table=diesel_table,
    field_name="liters",
    params={"min": 0.01, "max": 10000},
    severity="error"
)

# Rule: Scope 1 rows must have fuel type
DQRule.objects.create(
    name="Scope 1 Fuel Type Required",
    rule_type="not_null",
    data_table=diesel_table,
    field_name="fuel_type",
    params={},
    severity="critical"
)
```

---

## Carbon API Layer (Domain Service)

```python
# backend/emissions/views.py

class CalculateAPIView(APIView):
    """
    Carbon domain service built ON platform DataRow.
    """
    def post(self, request):
        table_id = request.data.get('table_id')
        period_id = request.data.get('reporting_period_id')
        
        # Get platform data
        table = DataTable.objects.get(id=table_id)
        rows = DataRow.objects.filter(
            data_table=table,
            is_archived=False
        )
        
        # Apply carbon business logic
        period = ReportingPeriod.objects.get(id=period_id)
        calculations = []
        
        for row in rows:
            # Extract activity data from generic DataRow
            fuel_type = row.values.get('fuel_type')
            liters = Decimal(row.values.get('liters', 0))
            
            # Find carbon emission factor
            ef = EmissionFactor.objects.filter(
                scope=table.module.scope,
                category='mobile_combustion',
                subcategory=fuel_type
            ).first()
            
            if not ef:
                continue  # Skip if no factor found
            
            # Create carbon calculation
            calc = Calculation.objects.create(
                data_row=row,
                emission_factor=ef,
                activity_value=liters,
                co2e_kg=liters * ef.factor_value,
                scope=table.module.scope,
                reporting_period=period,
                org_unit=row.org_unit
            )
            calculations.append(calc)
        
        return Response({
            'calculations_created': len(calculations),
            'total_co2e_tonnes': sum(c.co2e_kg for c in calculations) / 1000
        })
```

---

## Summary: Correct Architecture

### Platform Provides (Generic)
- ✅ `DataTable` / `DataRow` — stores carbon activity data
- ✅ `AssetProfile` — carbon table metadata
- ✅ `DQRule` — carbon quality checks
- ✅ `OrgUnit` — carbon org scoping
- ✅ `ReferenceSet` — carbon dropdown values

### Carbon Adds (Domain-Specific)
- ✅ `EmissionFactor` — carbon conversion coefficients
- ✅ `Calculation` — carbon CO2e results
- ✅ `ReportingPeriod` — carbon reporting cycles
- ✅ Validators — carbon scope validation
- ✅ Services — carbon calculation logic
- ✅ Views — carbon dashboards + reports

### Result
**Carbon is a domain app built ON TOP of the Data Trust Platform**, just like future HR or finance apps would be. The platform hosts ALL domains' data in generic tables, while domain apps (like carbon) add business logic and domain-specific configuration.

This respects the platform philosophy while providing robust carbon-specific workflows.

**Is this the correct understanding of how carbon should work with the platform?**
