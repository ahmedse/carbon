# TASK: Data Trust Core — Reference Data Governance (Track D)

> **Master:** Zoo (Architect Mode)  
> **Worker:** Code Mode  
> **Priority:** TEMPORAL VALIDITY & LIFECYCLE — Complete the reference data management tier  
> **Reference:** [`plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md`](plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md) Track D  
> **Depends On:** Track A (DQ Execution) ✅, Track B (Governance Audit Trail) ✅

---

## Mission Brief

You are implementing **Track D (Reference Data Governance)** of the Data Trust Core backend completion. This adds **temporal validity enforcement** and **lifecycle management** to complete the reference data management (RDM) tier.

### Current State
- ✅ [`ReferenceSet`](backend/mdm/models.py:8) and [`ReferenceValue`](backend/mdm/models.py:42) models exist
- ✅ [`valid_from`](backend/mdm/models.py:49) / [`valid_to`](backend/mdm/models.py:50) fields exist but not enforced
- ✅ Basic CRUD endpoints work: [`backend/mdm/views.py`](backend/mdm/views.py:1)
- ✅ Audit trail wired (Track B)
- ⚠️ No temporal query layer (can't ask "what values were valid on 2025-01-15?")
- ❌ No lifecycle states (draft → active → deprecated → archived)
- ❌ No field binding management (bulk bind/unbind with safety)

### Your Job
Implement **3 deliverables**:

1. **D1: Temporal Validity Query Layer** — Time-travel queries for reference values
2. **D2: Reference Set Lifecycle** — State machine (draft → active → deprecated → archived)
3. **D3: Field Binding Management** — Bulk bind/unbind DataFields to reference sets

---

## Deliverable D1: Temporal Validity Query Layer

### Context
[`ReferenceValue.valid_from`](backend/mdm/models.py:49) and [`valid_to`](backend/mdm/models.py:50) fields exist but are not used. Users need:
- "Show me values that were valid on 2025-12-31" (time-travel for compliance)
- "Hide expired values from dropdowns" (UX + data quality)
- "List all time-bound values" (reporting)

### Requirements

#### D1.1: Temporal Query Action on ReferenceSetViewSet
- **Location:** [`backend/mdm/views.py`](backend/mdm/views.py:19)
- **Action:** `@action(detail=True, methods=['get'])`
- **Endpoint:** `GET /mdm/reference-sets/{id}/values/?date=<ISO-date>`
- **Logic:**
  ```python
  @action(detail=True, methods=['get'])
  def values(self, request, pk=None):
      """
      GET /mdm/reference-sets/{id}/values/?date=2025-01-15&active=true
      Returns values valid at the specified date.
      
      Temporal logic:
      - If date provided: filter where date >= valid_from (or valid_from is null)
                          AND date <= valid_to (or valid_to is null)
      - If no date: return all values (existing behavior)
      - If active=true: filter is_active=True
      """
      ref_set = self.get_object()
      qs = ReferenceValue.objects.filter(reference_set=ref_set)
      
      # Active filter (existing)
      if request.query_params.get('active') in ('1', 'true', 'True'):
          qs = qs.filter(is_active=True)
      
      # Temporal filter (NEW)
      date_str = request.query_params.get('date')
      if date_str:
          from datetime.date import fromisoformat
          target_date = fromisoformat(date_str)
          qs = qs.filter(
              models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=target_date)
          ).filter(
              models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=target_date)
          )
      
      return Response(ReferenceValueSerializer(qs, many=True).data)
  ```

#### D1.2: Current Values Helper Method
- **Location:** [`backend/mdm/models.py`](backend/mdm/models.py:8) on `ReferenceSet` model
- **Method:**
  ```python
  def get_current_values(self, as_of=None):
      """
      Return values that are valid as of a specific date.
      If as_of is None, uses today's date.
      """
      from django.utils import timezone
      from django.db.models import Q
      
      target_date = as_of or timezone.now().date()
      return self.values.filter(
          is_active=True
      ).filter(
          Q(valid_from__isnull=True) | Q(valid_from__lte=target_date)
      ).filter(
          Q(valid_to__isnull=True) | Q(valid_to__gte=target_date)
      )
  ```

#### D1.3: Temporal Validity Enforcement in DQ Rules
- **Context:** Track A added `reference_integrity` rule type
- **Enhancement:** When rule validates against a reference set, use current values only
- **Location:** [`backend/dq/services.py`](backend/dq/services.py:1) in `_evaluate_rule()` for `reference_integrity`
- **Change:**
  ```python
  elif rule.rule_type == 'reference_integrity':
      rs_id = rule.params.get('reference_set')
      if rs_id:
          # OLD: allowed = set(ReferenceValue.objects.filter(reference_set_id=rs_id, is_active=True).values_list('code', flat=True))
          # NEW: Use temporal validity
          from mdm.models import ReferenceSet
          ref_set = ReferenceSet.objects.get(id=rs_id)
          allowed = set(ref_set.get_current_values().values_list('code', flat=True))
      # ... rest of logic
  ```

#### D1.4: API Documentation for Temporal Queries
- **Response Example:**
  ```json
  GET /mdm/reference-sets/5/values/?date=2025-01-15&active=true
  
  [
    {
      "id": 12,
      "reference_set": 5,
      "code": "SCOPE1",
      "label": "Direct Emissions",
      "valid_from": "2024-01-01",
      "valid_to": null,
      "is_active": true
    },
    {
      "id": 13,
      "code": "SCOPE2",
      "label": "Indirect Emissions",
      "valid_from": "2024-01-01",
      "valid_to": "2025-12-31",
      "is_active": true
    }
  ]
  ```

### Acceptance Criteria
- [ ] `GET /reference-sets/{id}/values/?date=2025-01-15` returns only values valid on that date
- [ ] Values with `valid_from > date` are excluded
- [ ] Values with `valid_to < date` are excluded
- [ ] Values with null `valid_from`/`valid_to` are included (永久有效)
- [ ] `get_current_values()` method works with today's date by default
- [ ] DQ `reference_integrity` rule uses temporal validity
- [ ] Test: `test_temporal_validity.py` with ≥80% coverage

---

## Deliverable D2: Reference Set Lifecycle Management

### Context
Reference sets need formal lifecycle states to prevent accidental changes to active production sets. States:
- **draft** — Being built; not ready for use
- **active** — In production; used by data entry forms
- **deprecated** — Phasing out; read-only; no new bindings
- **archived** — Historical; read-only; hidden from lists

### Requirements

#### D2.1: Add Lifecycle State Field
- **Location:** [`backend/mdm/models.py`](backend/mdm/models.py:8)
- **Migration:**
  ```python
  # Add to ReferenceSet model
  LIFECYCLE_STATES = [
      ('draft', 'Draft'),
      ('active', 'Active'),
      ('deprecated', 'Deprecated'),
      ('archived', 'Archived'),
  ]
  
  lifecycle_state = models.CharField(
      max_length=20,
      choices=LIFECYCLE_STATES,
      default='draft',
      help_text="Lifecycle state of this reference set"
  )
  ```
- **Run Migration:**
  ```bash
  python manage.py makemigrations mdm
  python manage.py migrate mdm
  ```

#### D2.2: State Transition Validation
- **Location:** [`backend/mdm/models.py`](backend/mdm/models.py:8)
- **Method:**
  ```python
  VALID_TRANSITIONS = {
      'draft': ['active'],
      'active': ['deprecated'],
      'deprecated': ['archived', 'active'],  # Can reactivate
      'archived': [],  # Cannot transition out
  }
  
  def can_transition_to(self, new_state):
      """Check if transition from current state to new_state is valid."""
      return new_state in self.VALID_TRANSITIONS.get(self.lifecycle_state, [])
  
  def transition_to(self, new_state, user=None):
      """Transition to new state with validation and audit."""
      if not self.can_transition_to(new_state):
          raise ValueError(
              f"Invalid transition: {self.lifecycle_state} → {new_state}"
          )
      old_state = self.lifecycle_state
      self.lifecycle_state = new_state
      self.save(update_fields=['lifecycle_state'])
      
      # Emit governance event
      if user:
          from catalog.audit_utils import emit_governance_event
          emit_governance_event(
              entity_type='ReferenceSet',
              entity_id=self.id,
              action='update',
              before={'lifecycle_state': old_state},
              after={'lifecycle_state': new_state},
              user=user
          )
  ```

#### D2.3: Lifecycle Transition Action
- **Location:** [`backend/mdm/views.py`](backend/mdm/views.py:19)
- **Action:**
  ```python
  @action(detail=True, methods=['post'])
  def transition(self, request, pk=None):
      """
      POST /mdm/reference-sets/{id}/transition/
      Body: {"state": "active"}
      
      Transitions the reference set to a new lifecycle state.
      """
      ref_set = self.get_object()
      new_state = request.data.get('state')
      
      if not new_state:
          return Response(
              {'error': 'state is required'},
              status=status.HTTP_400_BAD_REQUEST
          )
      
      try:
          ref_set.transition_to(new_state, user=request.user)
          return Response({
              'id': ref_set.id,
              'name': ref_set.name,
              'lifecycle_state': ref_set.lifecycle_state,
              'message': f'Transitioned to {new_state}'
          })
      except ValueError as e:
          return Response(
              {'error': str(e)},
              status=status.HTTP_400_BAD_REQUEST
          )
  ```

#### D2.4: Lifecycle-Based Filtering
- **Location:** [`backend/mdm/views.py`](backend/mdm/views.py:40) in `get_queryset()`
- **Change:**
  ```python
  def get_queryset(self):
      qs = ReferenceSet.objects.filter(is_active=True)
      
      # Filter by lifecycle state
      state = self.request.query_params.get('lifecycle_state')
      if state:
          qs = qs.filter(lifecycle_state=state)
      
      # Hide archived sets by default in list views
      if self.action == 'list' and not state:
          qs = qs.exclude(lifecycle_state='archived')
      
      # ... existing RBAC filtering
      return qs
  ```

#### D2.5: Deprecation Enforcement
- **Rules:**
  - **deprecated** sets: Read-only; cannot add/edit values (except reactivation)
  - **deprecated** sets: Cannot bind new DataFields
  - **archived** sets: Fully read-only; hidden from default lists

- **Location:** [`backend/mdm/views.py`](backend/mdm/views.py:94) in `perform_update()`
- **Validation:**
  ```python
  def perform_update(self, serializer):
      obj = self.get_object()
      
      # Block updates to deprecated/archived sets (except lifecycle transition)
      if obj.lifecycle_state in ['deprecated', 'archived']:
          # Allow lifecycle_state changes only
          if set(serializer.validated_data.keys()) != {'lifecycle_state'}:
              raise PermissionDenied(
                  f"Cannot modify {obj.lifecycle_state} reference set"
              )
      
      # ... existing steward check and audit logic
  ```

### Acceptance Criteria
- [ ] `lifecycle_state` field added to ReferenceSet model
- [ ] Valid transitions enforced: draft→active, active→deprecated, deprecated→archived
- [ ] Invalid transitions rejected (e.g., draft→archived)
- [ ] `POST /reference-sets/{id}/transition/` API works
- [ ] Governance event emitted on state change
- [ ] Deprecated sets are read-only (except reactivation)
- [ ] Archived sets hidden from default lists
- [ ] Test: `test_lifecycle.py` with ≥80% coverage

---

## Deliverable D3: Field Binding Management

### Context
[`DataField.reference_set`](backend/dataschema/models.py:52) FK exists (additive from Phase 0) but no bulk management or safety checks. Users need:
- "Bind all 'Scope' fields to the Emission Scopes reference set"
- "Unbind a deprecated set safely (check for data first)"
- "List all fields bound to a reference set"

### Requirements

#### D3.1: List Bound Fields Action
- **Location:** [`backend/mdm/views.py`](backend/mdm/views.py:19)
- **Action:**
  ```python
  @action(detail=True, methods=['get'])
  def bound_fields(self, request, pk=None):
      """
      GET /mdm/reference-sets/{id}/bound-fields/
      Returns all DataFields bound to this reference set.
      """
      ref_set = self.get_object()
      from dataschema.models import DataField
      fields = DataField.objects.filter(
          reference_set=ref_set,
          is_active=True,
          is_archived=False
      ).select_related('data_table')
      
      return Response([
          {
              'id': f.id,
              'name': f.name,
              'table_id': f.data_table_id,
              'table_name': f.data_table.name,
              'type': f.type
          }
          for f in fields
      ])
  ```

#### D3.2: Bulk Bind Fields Action
- **Endpoint:** `POST /mdm/reference-sets/{id}/bind-fields/`
- **Request Body:**
  ```json
  {
    "field_ids": [12, 34, 56]
  }
  ```
- **Logic:**
  ```python
  @action(detail=True, methods=['post'])
  def bind_fields(self, request, pk=None):
      """
      POST /mdm/reference-sets/{id}/bind-fields/
      Body: {"field_ids": [12, 34, 56]}
      
      Binds multiple DataFields to this reference set.
      Validates:
      - All fields are type='reference'
      - Reference set is active (not deprecated/archived)
      """
      ref_set = self.get_object()
      field_ids = request.data.get('field_ids', [])
      
      if not field_ids:
          return Response(
              {'error': 'field_ids is required'},
              status=status.HTTP_400_BAD_REQUEST
          )
      
      # Validate lifecycle state
      if ref_set.lifecycle_state in ['deprecated', 'archived']:
          return Response(
              {'error': f'Cannot bind to {ref_set.lifecycle_state} reference set'},
              status=status.HTTP_400_BAD_REQUEST
          )
      
      # Fetch fields
      from dataschema.models import DataField
      fields = DataField.objects.filter(id__in=field_ids)
      
      # Validate type
      invalid = [f for f in fields if f.type != 'reference']
      if invalid:
          return Response(
              {'error': f'Fields must be type=reference: {[f.id for f in invalid]}'},
              status=status.HTTP_400_BAD_REQUEST
          )
      
      # Bind
      bound = []
      for field in fields:
          field.reference_set = ref_set
          field.save(update_fields=['reference_set'])
          bound.append(field.id)
      
      return Response({
          'reference_set': ref_set.id,
          'bound_fields': bound,
          'message': f'Bound {len(bound)} fields'
      })
  ```

#### D3.3: Bulk Unbind Fields Action
- **Endpoint:** `POST /mdm/reference-sets/{id}/unbind-fields/`
- **Request Body:**
  ```json
  {
    "field_ids": [12, 34],
    "force": false
  }
  ```
- **Safety Check:** Before unbinding, check if existing data would violate the unbind
  - If `force=true`, unbind anyway (admin override)
  - If `force=false`, reject if data exists
- **Logic:**
  ```python
  @action(detail=True, methods=['post'])
  def unbind_fields(self, request, pk=None):
      """
      POST /mdm/reference-sets/{id}/unbind-fields/
      Body: {"field_ids": [12, 34], "force": false}
      
      Unbinds fields from this reference set.
      Safety: Checks if existing DataRows would violate rules if unbound.
      """
      ref_set = self.get_object()
      field_ids = request.data.get('field_ids', [])
      force = request.data.get('force', False)
      
      if not field_ids:
          return Response(
              {'error': 'field_ids is required'},
              status=status.HTTP_400_BAD_REQUEST
          )
      
      from dataschema.models import DataField, DataRow
      fields = DataField.objects.filter(id__in=field_ids, reference_set=ref_set)
      
      # Safety check (unless force=true)
      if not force:
          for field in fields:
              # Check if any rows have data in this field
              rows_with_data = DataRow.objects.filter(
                  data_table=field.data_table,
                  is_archived=False
              ).exclude(
                  values__has_key=field.name
              ).count()
              
              if rows_with_data > 0:
                  return Response(
                      {
                          'error': f'Field {field.id} ({field.name}) has {rows_with_data} rows with data. Use force=true to override.'
                      },
                      status=status.HTTP_400_BAD_REQUEST
                  )
      
      # Unbind
      unbound = []
      for field in fields:
          field.reference_set = None
          field.save(update_fields=['reference_set'])
          unbound.append(field.id)
      
      return Response({
          'reference_set': ref_set.id,
          'unbound_fields': unbound,
          'message': f'Unbound {len(unbound)} fields'
      })
  ```

#### D3.4: Single Field Bind/Unbind via DataFieldViewSet
- **Alternative:** Allow binding via `PATCH /dataschema/data-fields/{id}/`
- **Serializer:** [`backend/dataschema/serializers.py`](backend/dataschema/serializers.py:1)
- **Add Field:**
  ```python
  class DataFieldSerializer(serializers.ModelSerializer):
      reference_set = serializers.PrimaryKeyRelatedField(
          queryset=ReferenceSet.objects.filter(is_active=True),
          required=False,
          allow_null=True
      )
      
      class Meta:
          model = DataField
          fields = [..., 'reference_set']
  ```

### Acceptance Criteria
- [ ] `GET /reference-sets/{id}/bound-fields/` lists all bound DataFields
- [ ] `POST /reference-sets/{id}/bind-fields/` bulk binds fields with validation
- [ ] Cannot bind to deprecated/archived reference sets
- [ ] `POST /reference-sets/{id}/unbind-fields/` with safety check (rejects if data exists)
- [ ] `force=true` overrides safety check
- [ ] Single field bind via `PATCH /data-fields/{id}/` works
- [ ] Test: `test_field_binding.py` with ≥80% coverage

---

## Implementation Guidelines

### File Structure
```
backend/mdm/
  models.py          # MODIFY: Add lifecycle_state, get_current_values(), transition_to()
  views.py           # MODIFY: Add temporal query, lifecycle actions, field binding actions
  serializers.py     # MODIFY: Add lifecycle_state to ReferenceSetSerializer
  urls.py            # AUTO: Routes registered by ViewSet actions
  migrations/
    000X_add_lifecycle_state.py  # CREATE: Add lifecycle_state field
  tests/
    test_temporal_validity.py    # CREATE: Temporal query tests
    test_lifecycle.py             # CREATE: Lifecycle transition tests
    test_field_binding.py         # CREATE: Field binding tests

backend/dataschema/
  models.py          # VERIFY: reference_set FK exists on DataField
  serializers.py     # MODIFY: Add reference_set to DataFieldSerializer
  
backend/dq/
  services.py        # MODIFY: Use get_current_values() in reference_integrity rule
```

### Technology Stack
- **Django Migrations** (add lifecycle_state field)
- **Django ORM** (Q objects for temporal queries)
- **Python datetime** (parse ISO dates)
- NO new dependencies

### Code Style
- Follow existing patterns in [`backend/mdm/views.py`](backend/mdm/views.py:19)
- Use Django `@action` decorator for custom endpoints
- Type hints: Use where helpful
- Error handling: Return clear error messages (400/403/404)

### Testing Protocol
1. Write tests FIRST for each deliverable
2. Test temporal queries with various date ranges
3. Test lifecycle transitions (valid + invalid)
4. Test field binding with safety checks
5. Run: `pytest backend/mdm/tests/ -v --cov=backend/mdm`

### Temporal Query Pattern (Reusable)
```python
from django.db.models import Q
from datetime import date

def get_values_at_date(reference_set, target_date):
    """Return values valid at a specific date."""
    return ReferenceValue.objects.filter(
        reference_set=reference_set,
        is_active=True
    ).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=target_date)
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=target_date)
    )
```

---

## Acceptance Testing

### Manual API Testing Checklist

1. **Temporal query:**
   ```bash
   curl "http://localhost:8000/carbon-api/mdm/reference-sets/1/values/?date=2025-01-15&active=true" \
     -H "Authorization: Token <token>"
   ```
   Expected: Only values valid on 2025-01-15

2. **Lifecycle transition:**
   ```bash
   curl -X POST http://localhost:8000/carbon-api/mdm/reference-sets/1/transition/ \
     -H "Authorization: Token <token>" \
     -d '{"state": "active"}'
   ```
   Expected: 200 OK, state changed to active

3. **Invalid transition:**
   ```bash
   curl -X POST http://localhost:8000/carbon-api/mdm/reference-sets/1/transition/ \
     -H "Authorization: Token <token>" \
     -d '{"state": "archived"}'
   ```
   Expected: 400 Bad Request (invalid transition draft→archived)

4. **Bind fields:**
   ```bash
   curl -X POST http://localhost:8000/carbon-api/mdm/reference-sets/1/bind-fields/ \
     -H "Authorization: Token <token>" \
     -d '{"field_ids": [12, 34]}'
   ```
   Expected: 200 OK, fields bound

5. **Unbind with safety check:**
   ```bash
   curl -X POST http://localhost:8000/carbon-api/mdm/reference-sets/1/unbind-fields/ \
     -H "Authorization: Token <token>" \
     -d '{"field_ids": [12], "force": false}'
   ```
   Expected: 400 if data exists, 200 if no data

### Pytest Test Suite
```bash
# Run all Track D tests
pytest backend/mdm/tests/test_temporal_validity.py \
       backend/mdm/tests/test_lifecycle.py \
       backend/mdm/tests/test_field_binding.py \
       -v --cov=backend/mdm --cov-report=term-missing

# Expected output:
# test_temporal_query_with_date PASSED
# test_temporal_query_no_date PASSED
# test_get_current_values PASSED
# test_lifecycle_transition_valid PASSED
# test_lifecycle_transition_invalid PASSED
# test_deprecated_set_readonly PASSED
# test_bind_fields_bulk PASSED
# test_unbind_fields_with_safety PASSED
# test_unbind_fields_force PASSED
# Coverage: ≥80%
```

---

## Out of Scope (Do NOT implement)

- ❌ Reference set versioning (multi-version support) — Phase 2
- ❌ Reference set approval workflows — Phase 3
- ❌ Reference set export/import (CSV/JSON) — Phase 2
- ❌ Reference set merge/split operations — out of scope
- ❌ UI for lifecycle management — frontend work, separate task
- ❌ Email notifications on lifecycle transitions — Phase 3
- ❌ Automated deprecation (schedule deprecation date) — Phase 2

---

## Deliverable Checklist

Use this checklist to track completion. Mark each item when acceptance criteria pass.

### D1: Temporal Validity Query Layer
- [ ] `GET /reference-sets/{id}/values/?date=<ISO>` returns temporally filtered values
- [ ] `get_current_values()` method on ReferenceSet model
- [ ] DQ `reference_integrity` rule uses temporal validity
- [ ] Values with null valid_from/valid_to handled correctly
- [ ] Test: `test_temporal_validity.py` passes with ≥80% coverage

### D2: Reference Set Lifecycle
- [ ] `lifecycle_state` field added to ReferenceSet model (migration applied)
- [ ] Valid transitions enforced (draft→active, active→deprecated, etc.)
- [ ] `transition_to()` method with validation and audit
- [ ] `POST /reference-sets/{id}/transition/` API endpoint
- [ ] Deprecated sets are read-only (except reactivation)
- [ ] Archived sets hidden from default lists
- [ ] Test: `test_lifecycle.py` passes with ≥80% coverage

### D3: Field Binding Management
- [ ] `GET /reference-sets/{id}/bound-fields/` lists bound DataFields
- [ ] `POST /reference-sets/{id}/bind-fields/` bulk binds with validation
- [ ] `POST /reference-sets/{id}/unbind-fields/` with safety check
- [ ] Cannot bind to deprecated/archived sets
- [ ] `force=true` overrides safety check
- [ ] `PATCH /data-fields/{id}/` allows single field bind/unbind
- [ ] Test: `test_field_binding.py` passes with ≥80% coverage

---

## Success Criteria (Track D Complete)

**This task is DONE when:**
1. ✅ All 3 deliverables pass acceptance criteria
2. ✅ Pytest suite passes with ≥80% coverage for temporal validity + lifecycle + binding
3. ✅ Manual API testing checklist completes without errors
4. ✅ Temporal queries return correct results for various date ranges
5. ✅ Lifecycle transitions validated and audited
6. ✅ Field binding safety checks prevent data integrity issues
7. ✅ Code reviewed by master (Zoo) and approved

---

## Deliverable Format

When complete, write [`TASK-RESULT-REFERENCE-DATA-GOVERNANCE.md`](TASK-RESULT-REFERENCE-DATA-GOVERNANCE.md) with:

1. **Summary:** What was implemented
2. **Files Modified:** List of changed files with line counts
3. **API Endpoints:** New endpoints with example requests/responses
4. **Test Results:** Pytest output showing coverage
5. **Manual Testing:** Evidence of successful API calls
6. **Known Issues:** Any limitations or bugs to address later
7. **Master Prompt:** Your message back to Ahmed/Zoo

### Master Prompt Template
```
Master (Ahmed/Zoo),

I've completed Track D (Reference Data Governance). Here's what's done:

✅ Deliverable D1: Temporal Validity - Time-travel queries; get_current_values(); DQ integration
✅ Deliverable D2: Lifecycle Management - State machine (draft→active→deprecated→archived); transition validation; read-only enforcement
✅ Deliverable D3: Field Binding - Bulk bind/unbind; safety checks; bound fields listing

Test Coverage: 82% (target: 80%)
API Testing: All 5 manual tests passed
Temporal Queries: Validated with historical data
Lifecycle: 12 valid transitions tested; 8 invalid rejected

Files Modified:
- backend/mdm/models.py (+80 lines)
- backend/mdm/views.py (+200 lines)
- backend/mdm/serializers.py (+15 lines)
- backend/mdm/migrations/000X_add_lifecycle_state.py (+20 lines, new)
- backend/dq/services.py (+5 lines)
- backend/mdm/tests/test_temporal_validity.py (+150 lines, new)
- backend/mdm/tests/test_lifecycle.py (+180 lines, new)
- backend/mdm/tests/test_field_binding.py (+200 lines, new)

Known Issues:
- Unbind safety check uses naive row count (could be optimized with sampling in Phase 2)
- Lifecycle state change doesn't cascade to values (future: auto-deprecate values when set is deprecated)
- No UI for lifecycle visualization (frontend task)

Ready for:
- Track C (API Documentation) — Swagger/OpenAPI integration
- Or Track E (Operational Excellence) — Logging + performance optimization
- Or frontend work — Lifecycle management UI

Worker ready for next task.
```

---

## Questions for Master (Before Starting)

If anything is unclear, ask Ahmed/Zoo:

1. Should deprecated reference sets allow emergency updates, or strictly read-only?
2. For unbind safety check, should we sample data or check all rows?
3. Should lifecycle transitions trigger notifications (email/Slack)?
4. Should archived sets be soft-deleted (is_active=False) or kept as archived state?
5. For temporal queries, should we support date ranges (e.g., `date_from` & `date_to`)?

**My recommendations:**
1. Strictly read-only (except reactivation) — safer for production
2. Check all rows for Phase 1; optimize in Phase 2 if performance issue
3. No notifications in Phase 1; add in Phase 3
4. Keep as archived state (is_active=True but lifecycle_state='archived') — better audit trail
5. Single date only for Phase 1; add ranges in Phase 2 if needed

Proceed only after master confirms the task is clear.

---

**Master (Zoo) — ready to hand this off to the worker?**
