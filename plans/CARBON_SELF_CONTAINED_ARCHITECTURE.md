# Carbon Domain — Self-Contained Architecture

**Status:** Architecture Design  
**Date:** 2026-07-25  
**Purpose:** Define a robust, self-contained carbon emissions management system  

---

## Core Principle: Carbon as a Domain-Specific App

The carbon system should be **fully self-contained** with its own:
1. **Configuration layer** — Scopes, categories, emission sources managed within carbon domain
2. **Data models** — Carbon-specific tables independent of generic `dataschema` app
3. **Business logic** — Calculation rules, validation, workflows entirely in `emissions/`
4. **UI namespace** — Dedicated `/carbon/` routes separate from `/catalog/` platform admin

**Key Decision:** Carbon does NOT rely on generic `Module`/`DataTable` for core workflows. Instead, carbon has its own **typed models** for activity data.

---

## Architecture: Platform Core vs. Carbon Domain

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLATFORM CORE (Reusable)                      │
│  - catalog: DataDomain, AssetProfile, Governance                 │
│  - mdm: OrgUnit, ReferenceSet (reusable master data)           │
│  - dq: DQRule, DQResult (reusable quality framework)           │
│  - accounts: User, ScopedRole (RBAC)                            │
│  - dataschema: DataTable, DataRow (OPTIONAL for generic data)  │
└─────────────────────────────────────────────────────────────────┘
                            ↑ leverages
                            │
┌─────────────────────────────────────────────────────────────────┐
│                   CARBON DOMAIN APP (emissions/)                 │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Configuration Layer (Carbon-Specific Metadata)           │  │
│  │ - EmissionScope: Scope 1/2/3 definitions                │  │
│  │ - EmissionCategory: Stationary, mobile, electricity      │  │
│  │ - Scope3Category: 15 GHG Protocol categories             │  │
│  │ - EmissionSource: Physical assets (vehicles, buildings)  │  │
│  │ - EmissionFactor: Conversion coefficients                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ↓ used by                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Data Models (Typed Carbon Data)                          │  │
│  │ - ActivityData: Fuel consumption, electricity, travel     │  │
│  │ - Calculation: CO2e results linked to activity           │  │
│  │ - ReportingPeriod: Monthly/quarterly cycles              │  │
│  │ - CalculationRule: Auto-calculation triggers             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ↓ processed by                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Business Logic (Carbon Workflows)                        │  │
│  │ - Data validation by scope                               │  │
│  │ - Emission calculations (activity × factor → CO2e)       │  │
│  │ - Reporting period workflow (draft → verified → closed)  │  │
│  │ - Materiality assessment (Scope 3 prioritization)        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ↓ consumed by                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Reporting & Analytics                                    │  │
│  │ - GHG Protocol reports (by scope/category)               │  │
│  │ - Trend analysis (YoY comparison)                        │  │
│  │ - Data owner dashboards (scoped to org units)            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Carbon Configuration Models (New)

### 1. EmissionScope (Metadata Table)

```python
# backend/emissions/models.py

class EmissionScope(models.Model):
    """
    GHG Protocol scope definitions (Scope 1/2/3).
    Self-contained carbon configuration.
    """
    scope_number = models.PositiveSmallIntegerField(
        unique=True,
        choices=[(1, '1'), (2, '2'), (3, '3')]
    )
    name = models.CharField(max_length=100)  # "Scope 1 - Direct Emissions"
    description = models.TextField()
    ghg_protocol_reference = models.URLField(blank=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    requires_source_asset = models.BooleanField(
        default=False,
        help_text="Does this scope require linking to a physical asset (vehicle, building)?"
    )
    required_fields = models.JSONField(
        default=list,
        help_text="List of mandatory field names for this scope, e.g., ['fuel_type', 'combustion_source']"
    )
    
    # UI Configuration
    icon = models.CharField(max_length=50, default='factory')  # MUI icon name
    color = models.CharField(max_length=7, default='#10b981')  # Hex color
    
    class Meta:
        ordering = ['scope_number']
    
    def __str__(self):
        return f"Scope {self.scope_number}: {self.name}"


# Seed data via migration:
# Scope 1: Direct emissions (vehicles, boilers, owned assets)
# Scope 2: Indirect energy (purchased electricity, steam, cooling)
# Scope 3: Value chain (business travel, commuting, purchased goods)
```

### 2. EmissionCategory (Hierarchical)

```python
class EmissionCategory(models.Model):
    """
    Emission categories within each scope.
    Examples:
    - Scope 1: Stationary Combustion, Mobile Combustion, Fugitive
    - Scope 2: Purchased Electricity, Purchased Steam
    - Scope 3: Cat 1 (Purchased Goods), Cat 6 (Business Travel), etc.
    """
    scope = models.ForeignKey(
        EmissionScope,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    
    # Identity
    code = models.CharField(max_length=50, unique=True)  # "S1_MOBILE_COMB"
    name = models.CharField(max_length=200)  # "Mobile Combustion"
    description = models.TextField(blank=True)
    
    # Hierarchy (for Scope 3 subcategories)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    
    # Configuration
    is_active = models.BooleanField(default=True)
    is_material = models.BooleanField(
        default=False,
        help_text="Has materiality assessment identified this as >5% of total emissions?"
    )
    tracking_method = models.CharField(
        max_length=20,
        choices=[
            ('detailed', 'Detailed Data Collection'),
            ('estimated', 'Industry Average Estimate'),
            ('excluded', 'Not Applicable'),
        ],
        default='detailed'
    )
    
    # GHG Protocol Reference (for Scope 3)
    ghg_category_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="GHG Protocol Scope 3 category number (1-15)"
    )
    
    # UI
    icon = models.CharField(max_length=50, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    
    class Meta:
        ordering = ['scope', 'sort_order', 'name']
        verbose_name_plural = "Emission Categories"
    
    def __str__(self):
        return f"{self.scope.name} → {self.name}"


# Seed data examples:
# Scope 1 Categories:
# - S1_STATIONARY: Stationary Combustion (boilers, generators)
# - S1_MOBILE: Mobile Combustion (vehicles, equipment)
# - S1_FUGITIVE: Fugitive Emissions (refrigerants, gas leaks)
# - S1_PROCESS: Process Emissions (chemical reactions)

# Scope 2 Categories:
# - S2_ELECTRICITY: Purchased Electricity
# - S2_STEAM: Purchased Steam
# - S2_HEATING: Purchased Heating
# - S2_COOLING: Purchased Cooling

# Scope 3 Categories (GHG Protocol 15 categories):
# - S3_CAT1: Purchased Goods and Services
# - S3_CAT3: Fuel and Energy Related Activities
# - S3_CAT6: Business Travel
# - S3_CAT7: Employee Commuting
# ... etc.
```

### 3. EmissionSource (Physical Assets)

```python
class EmissionSource(models.Model):
    """
    Physical emission-generating assets (vehicles, buildings, equipment).
    Links carbon data to real-world sources.
    """
    # Identity
    code = models.CharField(max_length=50, unique=True)  # "VEHICLE_BUS001"
    name = models.CharField(max_length=200)  # "Campus Bus #001"
    source_type = models.CharField(
        max_length=50,
        choices=[
            ('vehicle', 'Vehicle'),
            ('building', 'Building'),
            ('equipment', 'Equipment'),
            ('facility', 'Facility'),
            ('asset', 'Other Asset'),
        ]
    )
    
    # Classification
    scope = models.ForeignKey(
        EmissionScope,
        on_delete=models.PROTECT,
        related_name='sources'
    )
    category = models.ForeignKey(
        EmissionCategory,
        on_delete=models.PROTECT,
        related_name='sources'
    )
    
    # Organizational Scoping
    org_unit = models.ForeignKey(
        'mdm.OrgUnit',
        on_delete=models.CASCADE,
        related_name='emission_sources',
        help_text="Which org unit owns/operates this source"
    )
    
    # Metadata
    description = models.TextField(blank=True)
    manufacturer = models.CharField(max_length=200, blank=True)
    model = models.CharField(max_length=200, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    installation_date = models.DateField(null=True, blank=True)
    
    # Activity Data Hints (for data entry guidance)
    typical_activity_unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., 'liters', 'kWh', 'km'"
    )
    typical_emission_factor = models.ForeignKey(
        'EmissionFactor',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='typical_sources',
        help_text="Default emission factor for this source"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    decommissioned_date = models.DateField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_sources'
    )
    
    class Meta:
        ordering = ['org_unit', 'source_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.source_type})"


# Example sources:
# - "Campus Bus #001" (vehicle, mobile combustion, Scope 1)
# - "Main Building HVAC" (equipment, stationary combustion, Scope 1)
# - "Engineering Lab 5" (building, purchased electricity, Scope 2)
```

### 4. Enhanced EmissionFactor (Already exists, add FK)

```python
# MODIFY existing EmissionFactor model:

class EmissionFactor(models.Model):
    # ... existing fields ...
    
    # ADD: Link to carbon configuration
    scope = models.ForeignKey(
        EmissionScope,
        on_delete=models.PROTECT,
        related_name='emission_factors'
    )
    category = models.ForeignKey(
        EmissionCategory,
        on_delete=models.PROTECT,
        related_name='emission_factors'
    )
    
    # ... rest of existing fields ...
```

---

## Carbon Data Models (Typed Activity Data)

### 1. ActivityData (Replaces generic DataRow for carbon)

```python
class ActivityData(models.Model):
    """
    Typed activity data for carbon emissions.
    Replaces generic dataschema.DataRow for carbon workflows.
    """
    # Link to configuration
    scope = models.ForeignKey(
        EmissionScope,
        on_delete=models.PROTECT,
        related_name='activity_data'
    )
    category = models.ForeignKey(
        EmissionCategory,
        on_delete=models.PROTECT,
        related_name='activity_data'
    )
    source = models.ForeignKey(
        EmissionSource,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activity_data',
        help_text="Physical asset that generated this emission (vehicle, building, etc.)"
    )
    
    # Activity Details
    activity_date = models.DateField(help_text="When did this activity occur?")
    activity_value = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Amount of activity (e.g., 100.5 liters, 250 kWh)"
    )
    activity_unit = models.CharField(
        max_length=50,
        help_text="Unit of measurement (e.g., 'liters', 'kWh', 'km')"
    )
    
    # Scope-Specific Fields (JSON for flexibility)
    scope_metadata = models.JSONField(
        default=dict,
        help_text="Scope-specific fields like fuel_type, grid_region, supplier_name"
    )
    # Example Scope 1: {"fuel_type": "diesel", "combustion_source": "generator"}
    # Example Scope 2: {"energy_type": "electricity", "grid_region": "EG_Cairo"}
    # Example Scope 3: {"supplier_name": "ABC Corp", "category_7_mode": "bus"}
    
    # Organizational Scoping
    org_unit = models.ForeignKey(
        'mdm.OrgUnit',
        on_delete=models.CASCADE,
        related_name='activity_data'
    )
    reporting_period = models.ForeignKey(
        'ReportingPeriod',
        on_delete=models.CASCADE,
        related_name='activity_data'
    )
    
    # Data Quality
    data_source = models.CharField(
        max_length=100,
        blank=True,
        help_text="Where did this data come from? (e.g., 'utility bill', 'fuel receipt')"
    )
    is_estimated = models.BooleanField(
        default=False,
        help_text="Is this an estimated value or actual measurement?"
    )
    notes = models.TextField(blank=True)
    
    # Calculation Status
    is_calculated = models.BooleanField(
        default=False,
        help_text="Has this been converted to CO2e?"
    )
    calculation_error = models.TextField(
        blank=True,
        help_text="Error message if calculation failed"
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_activity_data'
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['scope', 'category', 'activity_date']),
            models.Index(fields=['org_unit', 'reporting_period']),
            models.Index(fields=['is_calculated']),
        ]
    
    def __str__(self):
        return f"{self.scope.name} — {self.activity_value} {self.activity_unit} on {self.activity_date}"
    
    def clean(self):
        """Validate scope-specific required fields."""
        required = self.scope.required_fields
        missing = [f for f in required if f not in self.scope_metadata]
        if missing:
            raise ValidationError({
                'scope_metadata': f"Missing required fields for {self.scope.name}: {', '.join(missing)}"
            })
```

### 2. Enhanced Calculation Model

```python
# MODIFY existing Calculation model to link to ActivityData:

class Calculation(models.Model):
    # REPLACE data_row FK with:
    activity_data = models.ForeignKey(
        ActivityData,
        on_delete=models.CASCADE,
        related_name='calculations'
    )
    
    # ADD: Direct links to configuration
    scope = models.ForeignKey(
        EmissionScope,
        on_delete=models.PROTECT
    )
    category = models.ForeignKey(
        EmissionCategory,
        on_delete=models.PROTECT
    )
    source = models.ForeignKey(
        EmissionSource,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    
    # ... rest of existing Calculation fields ...
```

---

## Benefits of Self-Contained Architecture

### 1. Carbon Domain Independence
- ✅ Carbon workflows don't depend on generic `dataschema` app
- ✅ Scopes/categories managed within `emissions/` app
- ✅ Can export entire `emissions/` app to another Django project

### 2. Type Safety
- ✅ `ActivityData` model enforces carbon-specific validation
- ✅ No mixing of carbon data with generic platform data
- ✅ Clear schema: scope → category → source → activity → calculation

### 3. Configurability
- ✅ Admins can enable/disable Scope 3 categories via `EmissionCategory.is_active`
- ✅ Materiality thresholds stored in `EmissionCategory.is_material`
- ✅ Required fields per scope stored in `EmissionScope.required_fields`

### 4. Scalability
- ✅ Add new emission sources without touching platform core
- ✅ Add new Scope 3 categories via data migration
- ✅ Custom validation rules per category

### 5. UI Consistency
- ✅ All carbon UI metadata (icons, colors) stored in models
- ✅ Frontend queries `EmissionScope` API to render forms dynamically
- ✅ No hardcoded scope/category lists in frontend

---

## Integration with Platform Core

### What Carbon DOES Use from Platform

1. **RBAC (accounts/):** `User`, `ScopedRole` for org-unit access control
2. **MDM (mdm/):** `OrgUnit` for organizational scoping
3. **MDM (mdm/):** `ReferenceSet` for dropdown values (fuel types, grid regions)
4. **DQ (dq/):** Optional quality checks on `ActivityData` (completeness, outliers)
5. **Catalog (catalog/):** Optional `AssetProfile` for activity data governance

### What Carbon DOES NOT Use

1. ❌ **dataschema.DataTable** — Carbon has its own `ActivityData` model
2. ❌ **dataschema.DataRow** — Carbon doesn't store data in generic key-value rows
3. ❌ **core.Module** — Carbon uses `EmissionScope` + `EmissionCategory` instead

### Integration Points

```python
# backend/emissions/services.py

def sync_to_catalog(activity_data_id):
    """
    Optional: Create AssetProfile in catalog for governance tracking.
    """
    activity = ActivityData.objects.get(id=activity_data_id)
    AssetProfile.objects.update_or_create(
        # Link to carbon activity (custom field)
        carbon_activity_id=activity.id,
        defaults={
            'domain': DataDomain.objects.get(name='Carbon Emissions'),
            'owner': activity.created_by,
            'classification': 'internal',
        }
    )
```

---

## Migration Strategy: From Generic to Typed

### Current State (Using dataschema)
```
Module (scope=1) → DataTable → DataRow (key-value) → Calculation
```

### Target State (Self-Contained)
```
EmissionScope → EmissionCategory → ActivityData (typed) → Calculation
```

### Migration Plan

#### Phase 1: Create New Models (Week 1)
1. Create `EmissionScope`, `EmissionCategory`, `EmissionSource` models
2. Seed data migration with Scope 1/2/3 + categories
3. Keep existing `Calculation` model (backward compatible)

#### Phase 2: Add ActivityData (Week 2)
1. Create `ActivityData` model
2. Create dual-write system: save to both `DataRow` and `ActivityData`
3. Update frontend forms to use `ActivityData` API

#### Phase 3: Migrate Historical Data (Week 3)
1. Create data migration: `DataRow` → `ActivityData`
2. Update `Calculation.data_row` → `Calculation.activity_data`
3. Deprecate `DataRow` usage for carbon

#### Phase 4: Cleanup (Week 4)
1. Remove dual-write logic
2. Remove carbon-specific code from `dataschema` app
3. Archive old `Module` records

---

## API Architecture

### Configuration Endpoints (Read-Only for Users)

```python
# GET /carbon-api/config/scopes/
# Returns: [{"id": 1, "name": "Scope 1 - Direct", "required_fields": ["fuel_type"]}]

# GET /carbon-api/config/categories/?scope=1
# Returns: [{"id": 5, "code": "S1_MOBILE", "name": "Mobile Combustion"}]

# GET /carbon-api/config/sources/?org_unit=3&scope=1
# Returns: [{"id": 10, "name": "Campus Bus #001", "source_type": "vehicle"}]
```

### Activity Data CRUD

```python
# POST /carbon-api/activity-data/
# Body: {
#   "scope_id": 1,
#   "category_id": 5,
#   "source_id": 10,
#   "activity_date": "2025-12-01",
#   "activity_value": 100.5,
#   "activity_unit": "liters",
#   "scope_metadata": {"fuel_type": "diesel"},
#   "org_unit_id": 3,
#   "reporting_period_id": 2
# }

# GET /carbon-api/activity-data/?org_unit=3&period=2
# Returns paginated list with RBAC filtering

# PATCH /carbon-api/activity-data/{id}/
# Update single activity record

# DELETE /carbon-api/activity-data/{id}/
# Soft delete (set is_active=false)
```

### Calculation Trigger

```python
# POST /carbon-api/calculations/trigger/
# Body: {
#   "reporting_period_id": 2,
#   "org_unit_id": 3,  # Optional: specific org unit
#   "scope_id": 1,     # Optional: specific scope
#   "recalculate": false
# }
# Returns: {"calculations_created": 150, "total_co2e_tonnes": 45.2}
```

---

## Frontend Architecture

### Configuration-Driven Forms

```jsx
// carbon-frontend/src/pages/carbon/ActivityDataEntryPage.jsx

export default function ActivityDataEntryPage() {
  const [scopes, setScopes] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [selectedScope, setSelectedScope] = useState(null);
  
  // Load configuration from backend
  useEffect(() => {
    api.get('/carbon-api/config/scopes/').then(res => setScopes(res.data));
  }, []);
  
  useEffect(() => {
    if (selectedScope) {
      api.get(`/carbon-api/config/categories/?scope=${selectedScope.id}`)
        .then(res => setCategories(res.data));
      api.get(`/carbon-api/config/sources/?scope=${selectedScope.id}&org_unit=${user.org_unit_id}`)
        .then(res => setSources(res.data));
    }
  }, [selectedScope]);
  
  // Render form fields based on scope configuration
  const renderScopeSpecificFields = () => {
    if (!selectedScope) return null;
    
    return selectedScope.required_fields.map(field => (
      <TextField
        key={field}
        name={field}
        label={formatFieldLabel(field)}
        required
        helperText={`Required for ${selectedScope.name}`}
      />
    ));
  };
  
  return (
    <Form onSubmit={handleSubmit}>
      <Select
        label="Scope"
        value={selectedScope}
        onChange={(e) => setSelectedScope(scopes.find(s => s.id === e.target.value))}
      >
        {scopes.map(scope => (
          <MenuItem key={scope.id} value={scope.id}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Icon name={scope.icon} sx={{ color: scope.color }} />
              {scope.name}
            </Box>
          </MenuItem>
        ))}
      </Select>
      
      <Select label="Category" required>
        {categories.map(cat => (
          <MenuItem key={cat.id} value={cat.id}>{cat.name}</MenuItem>
        ))}
      </Select>
      
      <Select label="Emission Source" required>
        {sources.map(src => (
          <MenuItem key={src.id} value={src.id}>
            {src.name} ({src.source_type})
          </MenuItem>
        ))}
      </Select>
      
      <DatePicker label="Activity Date" required />
      <TextField label="Activity Value" type="number" required />
      <TextField label="Activity Unit" required />
      
      {renderScopeSpecificFields()}
      
      <Button type="submit">Save Activity Data</Button>
    </Form>
  );
}
```

---

## Admin Configuration UI

### Scope 3 Category Manager

```jsx
// carbon-frontend/src/pages/carbon/admin/Scope3ConfigPage.jsx

export default function Scope3ConfigPage() {
  const [categories, setCategories] = useState([]);
  
  const toggleCategory = async (categoryId, enabled) => {
    await api.patch(`/carbon-api/config/categories/${categoryId}/`, {
      is_active: enabled
    });
    loadCategories();
  };
  
  const setMaterial = async (categoryId, isMaterial) => {
    await api.patch(`/carbon-api/config/categories/${categoryId}/`, {
      is_material: isMaterial,
      tracking_method: isMaterial ? 'detailed' : 'estimated'
    });
    loadCategories();
  };
  
  return (
    <Card>
      <CardHeader title="Scope 3 Category Configuration" />
      <CardContent>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Category</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Enabled</TableCell>
              <TableCell>Material</TableCell>
              <TableCell>Tracking Method</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {categories.filter(c => c.scope.scope_number === 3).map(cat => (
              <TableRow key={cat.id}>
                <TableCell>
                  {cat.ghg_category_number
                    ? `Category ${cat.ghg_category_number}`
                    : cat.code}
                </TableCell>
                <TableCell>{cat.name}</TableCell>
                <TableCell>
                  <Switch
                    checked={cat.is_active}
                    onChange={(e) => toggleCategory(cat.id, e.target.checked)}
                  />
                </TableCell>
                <TableCell>
                  <Checkbox
                    checked={cat.is_material}
                    onChange={(e) => setMaterial(cat.id, e.target.checked)}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={cat.tracking_method}
                    color={cat.tracking_method === 'detailed' ? 'success' : 'default'}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
```

---

## Summary: Self-Contained Carbon System

### What Gets Built

1. **Configuration Layer** (4 new models):
   - `EmissionScope` — Scope 1/2/3 metadata
   - `EmissionCategory` — Hierarchical categories per scope
   - `EmissionSource` — Physical assets (vehicles, buildings)
   - Enhanced `EmissionFactor` — Links to scope/category

2. **Data Layer** (1 new model):
   - `ActivityData` — Typed carbon activity data (replaces generic DataRow)

3. **Business Logic**:
   - Scope-specific validation in `ActivityData.clean()`
   - Calculation service links `ActivityData` → `EmissionFactor` → `Calculation`
   - Reporting period workflow in `ReportingPeriod` transitions

4. **APIs** (8 new endpoints):
   - `GET /carbon-api/config/scopes/`
   - `GET /carbon-api/config/categories/`
   - `GET /carbon-api/config/sources/`
   - `CRUD /carbon-api/activity-data/`
   - `POST /carbon-api/calculations/trigger/`
   - `PATCH /carbon-api/config/categories/{id}/` (admin only)

5. **Frontend** (5 new pages):
   - `/carbon/activity-data/entry` — Configuration-driven data entry
   - `/carbon/activity-data/list` — View/edit activity data
   - `/carbon/activity-data/bulk-import` — CSV import
   - `/carbon/admin/scope3-config` — Enable/disable categories
   - `/carbon/admin/sources` — Manage emission sources

### What Does NOT Get Built

- ❌ No changes to `dataschema` app
- ❌ No changes to `core.Module` model
- ❌ No changes to platform catalog (except optional governance sync)

### Result

**A fully self-contained carbon emissions management system** that:
- Lives entirely in `emissions/` app
- Leverages platform RBAC + MDM for scoping
- Can be extracted and reused in other Django projects
- Provides robust, typed carbon accounting workflows

---

**Next Step:** User approval of this architecture before proceeding with implementation.
