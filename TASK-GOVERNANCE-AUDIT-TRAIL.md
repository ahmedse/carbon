# TASK: Data Trust Core — Governance Audit Trail (Track B)

> **Master:** Zoo (Architect Mode)  
> **Worker:** Code Mode  
> **Priority:** TRUST FOUNDATION — compliance layer for all governance-controlled entities  
> **Reference:** [`plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md`](plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md) Track B  
> **Depends On:** Track A (DQ Execution) — ✅ Complete

---

## Mission Brief

You are implementing **Track B (Governance Audit Trail)** of the Data Trust Core backend completion. This creates the **compliance foundation** — every change to governance-controlled entities must be audited and traceable.

### Current State
- ✅ `GovernanceEvent` model exists: [`backend/catalog/models.py`](backend/catalog/models.py:87)
- ✅ Track A already emits audit events for DQ-triggered catalog updates
- ⚠️ Manual CRUD on `AssetProfile`, `GlossaryTerm`, `DataDomain` not audited
- ❌ No audit trail for MDM changes (`ReferenceSet`, `ReferenceValue`, `OrgUnit`)
- ❌ No queryable audit API endpoint

### Your Job
Implement **3 deliverables**:

1. **B1: Wire GovernanceEvent Hooks** — Auto-audit catalog entity CRUD
2. **B2: Reference Data Change Tracking** — Audit MDM entity changes
3. **B3: Governance Event API** — Queryable audit trail with filters

---

## Deliverable B1: Wire GovernanceEvent Hooks (Catalog Entities)

### Context
When users update `AssetProfile.owner`, `GlossaryTerm.status`, or `DataDomain.description` via API, these changes must be captured in the [`GovernanceEvent`](backend/catalog/models.py:87) audit trail with before/after state.

Currently, only DQ-triggered updates (from Track A) are audited. Manual updates via `PATCH /catalog/assets/{id}/` are NOT audited.

### Requirements

#### B1.1: Create Audit Utility Function
- **Location:** Create [`backend/catalog/audit_utils.py`](backend/catalog/audit_utils.py)
- **Function Signature:**
  ```python
  def emit_governance_event(
      entity_type: str,
      entity_id: int,
      action: str,  # 'create', 'update', 'delete'
      before: dict,
      after: dict,
      user,
      asset_profile=None  # Optional FK to AssetProfile
  ):
      """Create a GovernanceEvent record with before/after state."""
      from catalog.models import GovernanceEvent
      GovernanceEvent.objects.create(
          entity_type=entity_type,
          entity_id=entity_id,
          action=action,
          before=before,
          after=after,
          user=user,
          asset=asset_profile
      )
  ```
- **Purpose:** Centralized audit emission for consistency

#### B1.2: Hook into ViewSet CRUD Operations
- **Targets:** [`backend/catalog/views.py`](backend/catalog/views.py:1)
  - `AssetProfileViewSet` (likely exists)
  - `GlossaryTermViewSet`
  - `DataDomainViewSet`
  - `TagViewSet` (optional — tags are lower priority)

- **Pattern:** Override `perform_create`, `perform_update`, `perform_destroy`
  ```python
  class AssetProfileViewSet(viewsets.ModelViewSet):
      def perform_update(self, serializer):
          instance = self.get_object()
          before = {
              'owner': instance.owner_id,
              'steward': instance.steward_id,
              'classification': instance.classification,
              'quality_status': instance.quality_status,
              # ... other auditable fields
          }
          instance = serializer.save(updated_by=self.request.user)
          after = {
              'owner': instance.owner_id,
              'steward': instance.steward_id,
              'classification': instance.classification,
              'quality_status': instance.quality_status,
          }
          emit_governance_event(
              entity_type='AssetProfile',
              entity_id=instance.id,
              action='update',
              before=before,
              after=after,
              user=self.request.user,
              asset_profile=instance
          )
  ```

- **Fields to Audit (per entity):**
  - **AssetProfile:** `owner`, `steward`, `classification`, `domain`, `glossary_term`, `quality_status`, `quality_score`
  - **GlossaryTerm:** `term`, `definition`, `status`, `steward`, `domain`
  - **DataDomain:** `name`, `description`, `owner`, `parent`
  - **Tag:** `name`, `color` (optional)

#### B1.3: Handle Partial Updates (PATCH)
- **Issue:** DRF's `PATCH` only includes changed fields in `serializer.validated_data`
- **Solution:** Capture "before" state before `save()`, "after" state after
- **Only log changed fields:**
  ```python
  changed = {k: after[k] for k in before if before[k] != after.get(k)}
  if changed:
      emit_governance_event(...)  # Only if something changed
  ```

#### B1.4: Handle Deletions (Soft Delete Pattern)
- **Context:** Most models use soft delete (`is_archived=True` or `is_active=False`)
- **Pattern:**
  ```python
  def perform_destroy(self, instance):
      before = {'is_active': instance.is_active}
      instance.is_active = False
      instance.save()
      after = {'is_active': False}
      emit_governance_event(
          entity_type='GlossaryTerm',
          entity_id=instance.id,
          action='delete',  # Logical delete
          before=before,
          after=after,
          user=self.request.user
      )
  ```

### Acceptance Criteria
- [ ] Updating `AssetProfile.owner` via API creates `GovernanceEvent(action='update')`
- [ ] `before`/`after` JSON captures only changed fields
- [ ] `GovernanceEvent.user` is the authenticated user who made the change
- [ ] `GovernanceEvent.asset` is populated for AssetProfile changes
- [ ] Deleting a GlossaryTerm creates `GovernanceEvent(action='delete')`
- [ ] No events created when PATCH has no actual changes
- [ ] Test: `test_catalog_audit.py` with ≥80% coverage on audit hooks

---

## Deliverable B2: Reference Data Change Tracking

### Context
MDM entities (`ReferenceSet`, `ReferenceValue`, `OrgUnit`) are governance-controlled and must be audited. Currently, no audit trail exists for MDM CRUD.

### Requirements

#### B2.1: Audit MDM ViewSets
- **Targets:** [`backend/mdm/views.py`](backend/mdm/views.py:1)
  - `ReferenceSetViewSet`
  - `ReferenceValueViewSet`
  - `OrgUnitViewSet`

- **Pattern:** Same as B1.2 — override `perform_create`, `perform_update`, `perform_destroy`
- **Import:** Reuse `emit_governance_event` from `catalog.audit_utils`
- **Fields to Audit:**
  - **ReferenceSet:** `name`, `description`, `domain`, `steward`, `is_active`, `version`
  - **ReferenceValue:** `code`, `label`, `is_active`, `sort_order`, `valid_from`, `valid_to`
  - **OrgUnit:** `name`, `org_type`, `parent`, `is_active`

#### B2.2: Cross-App Audit (MDM → Catalog)
- **Issue:** `GovernanceEvent` is in `catalog` app; MDM is separate
- **Solution:** Import is fine (one-way dependency: `mdm → catalog` allowed)
- **Alternative:** Create `mdm.ChangeLog` model if full separation required
- **Decision:** Use `GovernanceEvent` for all governance changes (unified audit trail)

#### B2.3: Temporal Validity Change Tracking
- **Special Case:** `ReferenceValue.valid_from` / `valid_to` changes are high-impact (affect data quality)
- **Enhanced Logging:**
  ```python
  if 'valid_from' in changed or 'valid_to' in changed:
      emit_governance_event(
          entity_type='ReferenceValue',
          entity_id=instance.id,
          action='update',
          before={'valid_from': old_from, 'valid_to': old_to},
          after={'valid_from': new_from, 'valid_to': new_to},
          user=request.user
      )
  ```

#### B2.4: Bulk Operations Audit
- **Context:** Track A added `POST /dq/profile/bulk/` for batch operations
- **Requirement:** If MDM has bulk endpoints (e.g., `POST /mdm/reference-values/bulk-update/`), audit each individual change
- **Pattern:** Loop through items; emit one event per changed entity

### Acceptance Criteria
- [ ] Updating `ReferenceSet.steward` creates `GovernanceEvent`
- [ ] Deactivating a `ReferenceValue` (is_active → False) is audited
- [ ] Changing `valid_from` / `valid_to` creates audit event
- [ ] `OrgUnit` hierarchy changes (parent reassignment) are audited
- [ ] Bulk operations emit per-item events
- [ ] Test: `test_mdm_audit.py` with ≥80% coverage

---

## Deliverable B3: Governance Event API

### Context
Users (data stewards, compliance officers) need to query the audit trail to answer:
- "Who changed the owner of Asset #123?"
- "Show all classification changes in the last 30 days"
- "What did user Alice modify this week?"

### Requirements

#### B3.1: Governance Event ViewSet
- **Location:** [`backend/catalog/views.py`](backend/catalog/views.py:1)
- **ViewSet:** `GovernanceEventViewSet(viewsets.ReadOnlyModelViewSet)`
  ```python
  class GovernanceEventViewSet(viewsets.ReadOnlyModelViewSet):
      serializer_class = GovernanceEventSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [filters.SearchFilter, filters.OrderingFilter]
      ordering = ['-timestamp']
      ordering_fields = ['timestamp', 'entity_type', 'action']
  ```

- **Serializer:** [`backend/catalog/serializers.py`](backend/catalog/serializers.py:1)
  ```python
  class GovernanceEventSerializer(serializers.ModelSerializer):
      username = serializers.CharField(source='user.username', read_only=True)
      
      class Meta:
          model = GovernanceEvent
          fields = [
              'id', 'entity_type', 'entity_id', 'action',
              'before', 'after', 'user', 'username',
              'timestamp', 'asset'
          ]
          read_only_fields = ['id', 'timestamp']
  ```

#### B3.2: Query Filters
- **Filterable Fields:**
  - `entity_type` (exact match)
  - `entity_id` (exact match)
  - `action` (exact match: create/update/delete)
  - `user` (FK filter)
  - `timestamp__gte` / `timestamp__lte` (date range)
  - `asset` (FK filter — optional)

- **Implementation:** Use `django_filters.FilterSet`
  ```python
  from django_filters import rest_framework as filters
  
  class GovernanceEventFilter(filters.FilterSet):
      entity_type = filters.CharFilter()
      action = filters.CharFilter()
      user_id = filters.NumberFilter(field_name='user__id')
      start_date = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
      end_date = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
      
      class Meta:
          model = GovernanceEvent
          fields = ['entity_type', 'action', 'user_id', 'start_date', 'end_date']
  ```

- **Add to ViewSet:**
  ```python
  filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
  filterset_class = GovernanceEventFilter
  ```

#### B3.3: RBAC Filtering
- **Rule:** Users see only events for entities in their org_unit scope
- **Pattern:** Same as DQ views — filter by `ScopedRole`
  ```python
  def get_queryset(self):
      qs = GovernanceEvent.objects.all()
      user = self.request.user
      if user.is_superuser or user.is_staff:
          return qs
      
      user_org_units = ScopedRole.objects.filter(
          user=user, is_active=True
      ).values_list('org_unit_id', flat=True).distinct()
      
      if not user_org_units:
          return GovernanceEvent.objects.none()
      
      # Filter based on entity's org_unit
      # For AssetProfile, use asset__data_table__module__org_unit
      # For Domain/Glossary, allow all (global resources)
      # For ReferenceSet/OrgUnit, filter by org_unit
      
      # Simplified: Allow all for now; Phase 2 will tighten
      return qs
  ```

#### B3.4: Pagination
- **Default:** 50 results per page
- **Max:** 500 results per page
- **Implementation:** DRF `PageNumberPagination`
  ```python
  class GovernanceEventPagination(PageNumberPagination):
      page_size = 50
      page_size_query_param = 'page_size'
      max_page_size = 500
  ```

#### B3.5: Endpoint Examples
- `GET /carbon-api/catalog/governance-events/` — All events (paginated)
- `GET /catalog/governance-events/?entity_type=AssetProfile&action=update&limit=20` — Filtered
- `GET /catalog/governance-events/?user_id=5&start_date=2026-07-01T00:00:00Z` — User's changes
- `GET /catalog/governance-events/?entity_type=ReferenceValue&entity_id=42` — Specific entity history

### Acceptance Criteria
- [ ] `GET /catalog/governance-events/` returns paginated list
- [ ] Can filter by `entity_type`, `action`, `user_id`, date range
- [ ] Response includes `before`/`after` JSON with changed fields
- [ ] Ordering by `-timestamp` (newest first) works
- [ ] RBAC filters events (permissive for Phase 1: allow all)
- [ ] Test: `test_governance_api.py` with ≥80% coverage

---

## Implementation Guidelines

### File Structure
```
backend/catalog/
  models.py          # GovernanceEvent already exists
  audit_utils.py     # CREATE: emit_governance_event()
  views.py           # MODIFY: Add audit hooks + GovernanceEventViewSet
  serializers.py     # MODIFY: Add GovernanceEventSerializer
  urls.py            # UPDATE: Register governance-events/ endpoint
  filters.py         # CREATE: GovernanceEventFilter
  tests/
    test_catalog_audit.py  # CREATE: Audit hook tests
    test_governance_api.py # CREATE: API endpoint tests

backend/mdm/
  views.py           # MODIFY: Add audit hooks to ReferenceSet/Value/OrgUnit ViewSets
  tests/
    test_mdm_audit.py      # CREATE: MDM audit tests
```

### Technology Stack
- **Django Signals** (optional — use `perform_*` overrides instead for clarity)
- **django-filter** (add to requirements if not present)
- **Django REST Framework** (existing)
- NO new dependencies beyond `django-filter`

### Code Style
- Follow existing patterns in [`backend/dq/views.py`](backend/dq/views.py:1) for ViewSet overrides
- Reuse RBAC pattern from Track A
- Type hints: Use where helpful
- Error handling: Try-catch audit emission; never block CRUD on audit failure
  ```python
  try:
      emit_governance_event(...)
  except Exception as e:
      logger.error(f"Failed to emit governance event: {e}")
      # Continue with CRUD operation
  ```

### Testing Protocol
1. Write tests FIRST for each deliverable
2. Test both happy path (successful audit) and edge cases (audit failure doesn't block CRUD)
3. Verify RBAC filtering on API endpoint
4. Run: `pytest backend/catalog/tests/ backend/mdm/tests/ -v --cov`

### Audit Emission Pattern (Reusable)
```python
def perform_update(self, serializer):
    instance = self.get_object()
    
    # Capture "before" state
    before = {
        'field1': getattr(instance, 'field1', None),
        'field2': getattr(instance, 'field2', None),
    }
    
    # Perform update
    instance = serializer.save(updated_by=self.request.user)
    
    # Capture "after" state
    after = {
        'field1': getattr(instance, 'field1', None),
        'field2': getattr(instance, 'field2', None),
    }
    
    # Detect changes
    changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
    
    # Emit event only if something changed
    if changed:
        try:
            emit_governance_event(
                entity_type=self.basename,  # or hard-code entity name
                entity_id=instance.id,
                action='update',
                before={k: before[k] for k in changed},  # Only changed fields
                after={k: after[k] for k in changed},
                user=self.request.user,
                asset_profile=getattr(instance, 'asset_profile', None)
            )
        except Exception as e:
            logger.error(f"Audit emission failed: {e}")
```

---

## Acceptance Testing

### Manual API Testing Checklist

1. **Update AssetProfile owner:**
   ```bash
   curl -X PATCH http://localhost:8000/carbon-api/catalog/assets/1/ \
     -H "Authorization: Token <token>" \
     -d '{"owner": 3}'
   ```
   Then query:
   ```bash
   curl http://localhost:8000/carbon-api/catalog/governance-events/?entity_type=AssetProfile&entity_id=1
   ```
   Expected: Event with `before: {owner: 2}`, `after: {owner: 3}`

2. **Deactivate ReferenceValue:**
   ```bash
   curl -X PATCH http://localhost:8000/carbon-api/mdm/reference-values/5/ \
     -H "Authorization: Token <token>" \
     -d '{"is_active": false}'
   ```
   Expected: `GovernanceEvent(action='update', entity_type='ReferenceValue')`

3. **Query user's changes:**
   ```bash
   curl http://localhost:8000/carbon-api/catalog/governance-events/?user_id=2&start_date=2026-07-20T00:00:00Z
   ```
   Expected: List of events by user ID 2 since July 20

4. **Test RBAC:**
   - As non-admin user, query events
   - Expected: 200 OK (permissive mode for Phase 1)

5. **Test soft delete:**
   ```bash
   curl -X DELETE http://localhost:8000/carbon-api/catalog/glossary/1/ \
     -H "Authorization: Token <token>"
   ```
   Expected: `GovernanceEvent(action='delete')`

### Pytest Test Suite
```bash
# Run all audit tests
pytest backend/catalog/tests/test_catalog_audit.py backend/mdm/tests/test_mdm_audit.py -v

# Run API tests
pytest backend/catalog/tests/test_governance_api.py -v

# Coverage
pytest backend/catalog/tests/ backend/mdm/tests/ --cov=backend/catalog --cov=backend/mdm --cov-report=term-missing
```

**Expected output:**
- test_asset_profile_update_emits_event PASSED
- test_glossary_term_delete_emits_event PASSED
- test_reference_value_validity_change_audited PASSED
- test_governance_events_api_filtering PASSED
- test_governance_events_rbac PASSED
- Coverage: ≥80% for audit utils, views with hooks, API endpoint

---

## Out of Scope (Do NOT implement)

- ❌ Audit event retention/archiving (Phase 2)
- ❌ Audit event export (CSV/JSON download) — Phase 2
- ❌ Real-time audit notifications (email/Slack) — Phase 3
- ❌ Audit dashboard UI (frontend work, separate task)
- ❌ Audit event rollback/undo feature — out of scope
- ❌ Fine-grained RBAC (org_unit filtering) — Phase 1 uses permissive mode
- ❌ Audit event signatures (cryptographic integrity) — Phase 3

---

## Deliverable Checklist

Use this checklist to track completion. Mark each item when acceptance criteria pass.

### B1: Wire GovernanceEvent Hooks (Catalog)
- [ ] `emit_governance_event()` utility created in `catalog/audit_utils.py`
- [ ] `AssetProfileViewSet` emits events on create/update/delete
- [ ] `GlossaryTermViewSet` emits events
- [ ] `DataDomainViewSet` emits events
- [ ] Only changed fields captured in before/after
- [ ] No events emitted when PATCH has no changes
- [ ] Test suite: `test_catalog_audit.py` passes with ≥80% coverage

### B2: Reference Data Change Tracking
- [ ] `ReferenceSetViewSet` emits governance events
- [ ] `ReferenceValueViewSet` emits events (including temporal validity changes)
- [ ] `OrgUnitViewSet` emits events
- [ ] Bulk operations emit per-item events
- [ ] Test suite: `test_mdm_audit.py` passes with ≥80% coverage

### B3: Governance Event API
- [ ] `GovernanceEventViewSet` created (read-only)
- [ ] `GovernanceEventSerializer` with username field
- [ ] Filters: entity_type, action, user_id, date range
- [ ] Pagination: 50 per page, max 500
- [ ] Ordering by `-timestamp` works
- [ ] RBAC filtering (permissive mode for Phase 1)
- [ ] Test suite: `test_governance_api.py` passes with ≥80% coverage

---

## Success Criteria (Track B Complete)

**This task is DONE when:**
1. ✅ All 3 deliverables pass acceptance criteria
2. ✅ Pytest suite passes with ≥80% coverage for audit utils + hooks + API
3. ✅ Manual API testing checklist completes without errors
4. ✅ No CRUD operations blocked by audit failures (graceful error handling)
5. ✅ `GovernanceEvent` trail queryable via API with filters
6. ✅ Before/after state captured for all governance-controlled entities
7. ✅ Code reviewed by master (Zoo) and approved

---

## Deliverable Format

When complete, write [`TASK-RESULT-GOVERNANCE-AUDIT-TRAIL.md`](TASK-RESULT-GOVERNANCE-AUDIT-TRAIL.md) with:

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

I've completed Track B (Governance Audit Trail). Here's what's done:

✅ Deliverable B1: Catalog Audit Hooks - AssetProfile/GlossaryTerm/DataDomain CRUD emits GovernanceEvent
✅ Deliverable B2: MDM Change Tracking - ReferenceSet/Value/OrgUnit audited; temporal validity changes logged
✅ Deliverable B3: Governance Event API - GET /catalog/governance-events/ with filters (entity_type, action, user, date)

Test Coverage: 82% (target: 80%)
API Testing: All 5 manual tests passed
Audit Events: 127 events emitted during test suite
RBAC: Permissive mode (all users see all events in Phase 1)

Files Modified:
- backend/catalog/audit_utils.py (+45 lines, new)
- backend/catalog/views.py (+120 lines — audit hooks + GovernanceEventViewSet)
- backend/catalog/serializers.py (+15 lines — GovernanceEventSerializer)
- backend/catalog/filters.py (+25 lines, new)
- backend/catalog/urls.py (+5 lines)
- backend/mdm/views.py (+80 lines — audit hooks)
- backend/catalog/tests/test_catalog_audit.py (+180 lines, new)
- backend/mdm/tests/test_mdm_audit.py (+120 lines, new)
- backend/catalog/tests/test_governance_api.py (+150 lines, new)

Known Issues:
- RBAC is permissive (all users see all events); Phase 2 will add org_unit filtering
- Bulk operations audit each item sequentially (could be optimized with bulk_create in Phase 2)
- Audit event retention not implemented (table will grow indefinitely; needs partitioning in Phase 2)

Ready for:
- Track D (Reference Data Governance) — temporal versioning, lifecycle management
- Or Track C (API Documentation) — Swagger/OpenAPI integration

Worker ready for next task.
```

---

## Questions for Master (Before Starting)

If anything is unclear, ask Ahmed/Zoo:

1. Should `TagViewSet` also be audited, or is it low priority?
2. For RBAC filtering on governance events, is permissive mode (all users see all) acceptable for Phase 1?
3. Should bulk operations emit one event per item, or one aggregate event?
4. Error handling: If audit emission fails, should we log and continue, or fail the CRUD operation?
5. Do we need to audit ManyToMany changes (e.g., `AssetProfile.tags.add()`)? If yes, use Django signals.

**My recommendations:**
1. Skip TagViewSet for now (low priority)
2. Yes — permissive mode for Phase 1; tighten in Phase 2
3. One event per item (more granular; easier to query)
4. Log and continue (audit should never block business operations)
5. Yes — use `m2m_changed` signal for tags; capture before/after tag IDs

Proceed only after master confirms the task is clear.

---

**Master (Zoo) — ready to hand this off to the worker?**
