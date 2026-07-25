# Carbon Architecture Decision: Generic vs. Typed Models

**Decision Point:** Should carbon data use generic `dataschema` tables (DataTable/DataRow) or dedicated typed models?

---

## Option A: Keep Using Generic Platform (Current State)

### Architecture
```
core.Module (scope=1/2/3)
  ↓ contains
dataschema.DataTable (name="Vehicle Fuel Consumption")
  ↓ contains
dataschema.DataRow (values={"fuel_type": "diesel", "liters": 100.5})
  ↓ calculates to
emissions.Calculation (co2e_kg=269.34)
```

### Pros ✅
1. **Already implemented**: Data entry works today at `/carbon/data-entry`
2. **Flexible**: Users can create any table structure without code changes
3. **Reuses platform**: Leverages existing DQ, catalog, import/export
4. **Low development cost**: No new models needed
5. **Uniform UI**: All data entry uses same `DataEntryPage` component

### Cons ❌
1. **No type safety**: Can't enforce "Scope 1 must have fuel_type field"
2. **Validation complexity**: Need JSONField queries to validate scope-specific rules
3. **Query performance**: Filtering on `DataRow.values->>'fuel_type'` is slower than native column
4. **Mixed data**: Carbon data mixed with other platform data in same tables
5. **Coupled to platform**: Can't extract carbon app to another project easily

### Example Data Entry
```python
# User creates table manually via UI
table = DataTable.objects.create(
    name="Vehicle Fuel Consumption",
    module=Module.objects.get(scope=1)
)

# User defines fields manually
DataField.objects.create(table=table, name="fuel_type", data_type="text")
DataField.objects.create(table=table, name="liters", data_type="decimal")

# User enters data via generic form
DataRow.objects.create(
    data_table=table,
    values={"fuel_type": "diesel", "liters": 100.5, "date": "2025-12-01"}
)
```

---

## Option B: Create Dedicated Typed Models (Proposed)

### Architecture
```
emissions.EmissionScope (scope_number=1, name="Scope 1 - Direct")
  ↓ has many
emissions.EmissionCategory (code="S1_MOBILE", name="Mobile Combustion")
  ↓ has many
emissions.EmissionSource (code="BUS001", name="Campus Bus #001")
  ↓ generates
emissions.ActivityData (activity_value=100.5, activity_unit="liters", scope_metadata={"fuel_type": "diesel"})
  ↓ calculates to
emissions.Calculation (co2e_kg=269.34)
```

### Pros ✅
1. **Type safety**: `ActivityData` model enforces field validation at database level
2. **Domain clarity**: Clear schema shows carbon-specific concepts
3. **Query performance**: Native columns indexed properly (no JSONField queries)
4. **Self-contained**: Entire carbon system lives in `emissions/` app
5. **Validation**: `scope.required_fields` checked in `ActivityData.clean()`
6. **Portability**: Can export `emissions/` app to another Django project
7. **UI consistency**: Frontend renders forms based on `EmissionScope.required_fields`

### Cons ❌
1. **Development cost**: Need to build new models + migrations + APIs
2. **Migration complexity**: Move existing DataRow → ActivityData
3. **Less flexible**: Adding new fields requires code changes
4. **Data duplication**: If we keep DataRow for other domains
5. **Learning curve**: Team needs to understand new carbon-specific models

### Example Data Entry
```python
# Configuration seeded via migration (admin configures once)
scope = EmissionScope.objects.get(scope_number=1)
category = EmissionCategory.objects.get(code="S1_MOBILE")
source = EmissionSource.objects.get(code="BUS001")

# User enters data via carbon-specific form
ActivityData.objects.create(
    scope=scope,
    category=category,
    source=source,
    activity_date="2025-12-01",
    activity_value=100.5,
    activity_unit="liters",
    scope_metadata={"fuel_type": "diesel"},  # Validated against scope.required_fields
    org_unit=user.org_unit,
    reporting_period=current_period,
)
```

---

## Option C: Hybrid Approach (Recommended)

### Architecture
```
emissions.EmissionScope + EmissionCategory (NEW - configuration only)
  ↓ configured in
core.Module (scope=1, carbon_category=EmissionCategory.id)
  ↓ contains
dataschema.DataTable (with scope-aware validation)
  ↓ contains
dataschema.DataRow (values validated against EmissionScope.required_fields)
  ↓ calculates to
emissions.Calculation (co2e_kg=269.34)
```

### Implementation
1. **Add configuration models**: `EmissionScope`, `EmissionCategory`, `EmissionSource` (metadata only)
2. **Keep using DataTable/DataRow**: For actual activity data storage
3. **Add validation layer**: Check `DataRow.values` against `EmissionScope.required_fields` before save
4. **Enhance UI**: Frontend queries `EmissionScope` API to render correct form fields

### Pros ✅
1. **Best of both worlds**: Type safety for configuration, flexibility for data
2. **Incremental migration**: Add typed models gradually without breaking existing system
3. **Reuse platform**: Keep using DQ, catalog, import/export on DataRow
4. **Low risk**: Configuration tables are small (dozens of rows), data tables stay same
5. **Self-documenting**: `EmissionScope.required_fields` clearly defines validation rules

### Cons ⚠️
1. **Still some coupling**: Carbon data still mixed with platform data in DataRow
2. **JSONField queries**: Still need `values->>'fuel_type'` for filtering
3. **Partial type safety**: Configuration is typed, but data is still key-value

### Example Implementation
```python
# backend/emissions/models.py

class EmissionScope(models.Model):
    """Configuration for Scope 1/2/3 validation rules."""
    scope_number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=100)
    required_fields = models.JSONField(
        default=list,
        help_text="['fuel_type', 'combustion_source'] for Scope 1"
    )
    icon = models.CharField(max_length=50, default='factory')
    color = models.CharField(max_length=7, default='#10b981')

# backend/dataschema/views.py (enhance existing)

class DataRowViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        # Add scope validation
        row_data = serializer.validated_data['values']
        table = serializer.validated_data['data_table']
        
        if table.module.scope:  # If this is a carbon module
            scope = EmissionScope.objects.get(scope_number=table.module.scope)
            
            # Validate required fields
            missing = [f for f in scope.required_fields if f not in row_data]
            if missing:
                raise ValidationError({
                    'values': f"Missing required fields for {scope.name}: {', '.join(missing)}"
                })
        
        serializer.save()
```

---

## Comparison Matrix

| Criteria | Generic (A) | Typed (B) | Hybrid (C) |
|----------|-------------|-----------|------------|
| **Development effort** | ✅ Low (done) | ❌ High (3 weeks) | ⚠️ Medium (1 week) |
| **Type safety** | ❌ None | ✅ Full | ⚠️ Partial |
| **Query performance** | ❌ JSONField | ✅ Native columns | ❌ JSONField |
| **Flexibility** | ✅ Very high | ❌ Low | ✅ High |
| **Self-contained** | ❌ Coupled | ✅ Independent | ⚠️ Partial |
| **Risk of data loss** | ✅ Low | ❌ High (migration) | ✅ Low |
| **Platform reuse** | ✅ Full | ❌ None | ✅ Full |
| **Scope validation** | ❌ Manual | ✅ Automatic | ✅ Automatic |
| **Production readiness** | ✅ Today | ❌ 3+ weeks | ⚠️ 1 week |

---

## Recommendation

### Phase 1 (Week 1): Hybrid Approach ✅
**Implement Option C** to get carbon-specific configuration without breaking existing system:

1. **Create configuration models**:
   - `EmissionScope` (Scope 1/2/3 metadata)
   - `EmissionCategory` (stationary, mobile, electricity, etc.)
   - `EmissionSource` (vehicles, buildings, equipment)
   - Enhanced `EmissionFactor` (link to scope/category)

2. **Add validation layer**:
   - Enhance `DataRowViewSet.perform_create()` to validate against `EmissionScope.required_fields`
   - Add frontend API: `GET /carbon-api/config/scopes/` to render forms dynamically

3. **Keep using DataTable/DataRow**:
   - No data migration needed
   - DQ, catalog, import/export still work
   - Data entry at `/carbon/data-entry` keeps working

### Phase 2 (Future - If Needed): Migrate to Typed Models
**Only if** we hit performance/scalability issues with JSONField queries:

1. Create `ActivityData` model
2. Implement dual-write: save to both `DataRow` and `ActivityData`
3. Migrate historical data: `DataRow` → `ActivityData`
4. Switch frontend to use `ActivityData` API
5. Deprecate `DataRow` for carbon

---

## Decision Factors

### Choose **Option A (Generic)** if:
- ✅ You want carbon in production **this week**
- ✅ You prioritize flexibility over type safety
- ✅ You're okay with manual validation in business logic
- ✅ You want minimal development cost

### Choose **Option B (Typed)** if:
- ✅ You need **strong type safety** and database-level constraints
- ✅ You plan to **extract carbon to separate product** later
- ✅ You can afford **3-week development cycle** + migration risk
- ✅ You prioritize **query performance** over flexibility

### Choose **Option C (Hybrid)** if:
- ✅ You want **best of both worlds** (configuration + flexibility)
- ✅ You need carbon in production **within 1 week**
- ✅ You want **incremental migration path** to typed models later
- ✅ You prioritize **low risk** and **platform reuse**

---

## My Recommendation: **Option C (Hybrid)** 

**Reasoning:**
1. **Low risk**: No data migration, existing system keeps working
2. **Quick delivery**: 1 week to add configuration layer
3. **Type safety where it matters**: Scope validation enforced automatically
4. **Future-proof**: Can migrate to fully typed models (Option B) later if needed
5. **Self-contained configuration**: `EmissionScope`/`EmissionCategory` live in `emissions/` app

This gives you the **robust, self-contained carbon system** you requested, while keeping the **quick path to production** you need.

---

**Next Step:** Confirm which option you prefer, then I'll create detailed implementation tasks.
