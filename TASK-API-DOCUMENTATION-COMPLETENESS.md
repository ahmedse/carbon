# TASK: Data Trust Core — API Documentation + Completeness (Track C)

**Status:** Ready for worker execution  
**Track:** C (API Completeness & Documentation)  
**Dependencies:** Tracks A (DQ Execution), B (Governance Audit), D (Reference Data Governance) complete  
**Estimated Scope:** Medium complexity, 3 deliverables

---

## Context

The Data Trust Core backend has three foundational apps (`catalog`, `mdm`, `dq`) with models and basic CRUD operations in place. Tracks A, B, and D added significant functionality:

- **Track A (DQ Execution):** Added 12+ new endpoints for profiling and rule execution (`POST /dq/profile/`, `/dq/run/`, `/dq/profile/bulk/`, `GET /dq/rules/{id}/history/`, `/dq/results/{id}/failures/`)
- **Track B (Governance Audit):** Added 2 endpoints (`GET /catalog/governance-events/`, `/catalog/governance/compliance/`)
- **Track D (Reference Data Governance):** Added 3 endpoints (temporal values query, lifecycle transitions, field binding)

**Current State:**
- ✅ Swagger/OpenAPI infrastructure exists (`drf_yasg` installed, `/api/swagger/` endpoint configured in `backend/config/urls.py`)
- ⚠️ **New endpoints from Tracks A/B/D not documented** — No `@swagger_auto_schema` decorators on custom actions
- ⚠️ **Soft-delete pattern inconsistent** — `Evidence` model uses `is_deleted`, `dataschema` models use `is_archived`, Data Trust Core apps have no soft-delete
- ⚠️ **Error handling inconsistent** — Some ViewSets have comprehensive error messages, others return generic 400/500
- ⚠️ **No bulk DELETE operations** — Individual delete only
- ⚠️ **Custom actions not fully documented** — Missing response examples and error scenarios

**User's Strategic Request:**
> "what next toward completing the data trust core modules? in backend first. deal with frontend after that"

This track focuses on **API polish and developer experience** — making all backend capabilities discoverable and usable via well-documented REST APIs.

---

## Objectives

1. **Complete API Coverage:** Implement missing soft-delete patterns, bulk operations, and custom actions across Data Trust Core apps
2. **Swagger Documentation:** Add `@swagger_auto_schema` decorators to all custom actions and bulk endpoints with request/response examples
3. **Standardized Error Handling:** Implement consistent error response format with actionable messages and field-level validation

---

## Deliverables

### **C1: Complete API Coverage**

**Goal:** Ensure all designed endpoints are functional, discoverable, and follow REST best practices.

#### Missing Endpoints to Implement

**Soft-Delete Pattern (Archive Instead of Hard Delete):**
- **Context:** `dataschema` app uses `is_archived` flag; Data Trust Core apps currently hard-delete
- **Requirement:** Override `destroy()` method in all Data Trust Core ViewSets to set archive/inactive flags instead of deleting records
- **Implementation:**
  ```python
  # catalog/views.py — DataDomainViewSet, GlossaryTermViewSet, TagViewSet
  def destroy(self, request, *args, **kwargs):
      instance = self.get_object()
      # Soft-delete pattern: set is_active=False instead of physical delete
      # Data Trust Core entities should preserve audit trail
      return Response(
          {"detail": "Hard delete not supported; use PATCH {is_active: false} to archive"},
          status=status.HTTP_405_METHOD_NOT_ALLOWED
      )
  
  # mdm/views.py — ReferenceSetViewSet already has soft-delete (is_active=False)
  # Audit: emit GovernanceEvent on archive operation
  ```

**Bulk Operations:**
- **`POST /catalog/assets/archive-bulk/`** — Archive multiple AssetProfiles (accepts list of IDs)
- **`POST /mdm/reference-sets/archive-bulk/`** — Archive multiple reference sets
- **`POST /mdm/reference-values/bulk-create/`** — Create multiple reference values in one request (for CSV import workflows)

**Custom Actions (Already Implemented but Need Documentation):**
- ✅ `GET /mdm/reference-sets/{id}/values/?date=YYYY-MM-DD` — Temporal values query (Track D)
- ✅ `POST /mdm/reference-sets/{id}/transition/` — Lifecycle state machine (Track D)
- ✅ `POST /mdm/bind-field/` — Field binding management (Track D)
- ✅ `GET /mdm/org-units/{id}/tree/` — Hierarchical tree view
- ✅ `GET /mdm/org-units/{id}/ancestors/` — Parent chain
- ✅ `POST /dq/rules/{id}/execute/` — Run single rule (Track A)
- ✅ `GET /dq/rules/{id}/history/` — Rule execution history (Track A)
- ✅ `GET /dq/results/{id}/failures/` — Sample failures (Track A)

**Acceptance Criteria:**
- [ ] All Data Trust Core ViewSets (`catalog`, `mdm`, `dq`) reject hard `DELETE` with clear error message
- [ ] Bulk archive endpoints accept `{"ids": [1, 2, 3]}` and return per-item success/failure
- [ ] Bulk create endpoints validate all items before committing (atomic operation)
- [ ] All custom actions return HTTP 400 with field-specific errors for invalid params
- [ ] RBAC enforced: only org_unit owners can archive assets in their domain

---

### **C2: Swagger/OpenAPI Documentation**

**Goal:** Auto-generate interactive API docs at `/api/swagger/` with complete request/response examples.

#### Implementation Strategy

**Add `@swagger_auto_schema` to All Custom Actions:**

```python
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Example: Document temporal values query
@swagger_auto_schema(
    method='get',
    operation_description="Get reference values valid as of a specific date (time-travel query). "
                         "If date parameter is omitted, returns currently active values.",
    manual_parameters=[
        openapi.Parameter(
            'date',
            openapi.IN_QUERY,
            description="ISO 8601 date (YYYY-MM-DD) to query historical values",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE,
            required=False,
            example="2026-07-15"
        )
    ],
    responses={
        200: openapi.Response(
            description="List of reference values valid on the specified date",
            examples={
                "application/json": [
                    {
                        "id": 1,
                        "code": "scope1",
                        "display_value": "Scope 1 - Direct Emissions",
                        "valid_from": "2026-01-01",
                        "valid_to": None,
                        "is_active": True
                    }
                ]
            }
        ),
        400: "Invalid date format",
        404: "Reference set not found"
    }
)
@action(detail=True, methods=['get'])
def values(self, request, pk=None):
    # ... implementation
```

**Document All New Endpoints from Tracks A/B/D:**
1. **DQ Endpoints (11 total):**
   - `POST /dq/profile/` — Profile single table
   - `POST /dq/profile/bulk/` — Profile multiple tables
   - `POST /dq/run/` — Run rule(s) on table
   - `POST /dq/rules/{id}/execute/` — Execute specific rule
   - `GET /dq/rules/{id}/history/` — Last 10 runs with trend
   - `GET /dq/results/{id}/failures/` — Sample failed rows
   - `GET /dq/metrics/` — Org-scoped summary
   - `GET /dq/metrics/table/{id}/` — Table-level metrics
   - `GET /dq/metrics/field/{id}/` — Field-level metrics
   - `POST /dq/run-validation/` — Legacy alias for `/dq/run/`

2. **Governance Endpoints (2 total):**
   - `GET /catalog/governance-events/` — Audit trail with filters
   - `GET /catalog/governance/compliance/` — Compliance summary by entity type

3. **Reference Data Governance (3 total):**
   - `GET /mdm/reference-sets/{id}/values/?date=X` — Temporal query
   - `POST /mdm/reference-sets/{id}/transition/` — Lifecycle state change
   - `POST /mdm/bind-field/` — Bind/unbind fields to reference sets

**Update Swagger Schema Configuration:**
```python
# backend/config/urls.py
schema_view = get_schema_view(
    openapi.Info(
        title="Carbon Data Trust Core API",
        default_version='v1',
        description=(
            "**Data Trust Core Platform APIs**\n\n"
            "This API provides catalog, master data management (MDM), and data quality (DQ) services.\n\n"
            "### Key Modules:\n"
            "- **Catalog**: Asset profiling, governance events, glossary terms\n"
            "- **MDM**: Reference sets, org units, field binding\n"
            "- **DQ**: Data profiling, rule execution, quality metrics\n\n"
            "### Authentication:\n"
            "All endpoints require JWT authentication. Obtain token via `POST /api/v1/token/`.\n\n"
            "### RBAC:\n"
            "Access controlled via ScopedRole assignments (org_unit-based filtering)."
        ),
        contact=openapi.Contact(email="carbon@aast.edu"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(AllowAny,),
)
```

**Acceptance Criteria:**
- [ ] All 16+ new endpoints from Tracks A/B/D appear in Swagger UI at `/api/swagger/`
- [ ] Each custom action has:
  - Operation description (what it does, when to use it)
  - Request parameters (query params, path params, body schema)
  - Response examples (200 success + 400/404 error cases)
  - RBAC notes (which roles can call it)
- [ ] "Try it out" feature works for all documented endpoints (interactive testing)
- [ ] Swagger schema validates (no YAML/JSON errors)
- [ ] Documentation distinguishes between:
  - Read-only endpoints (GET)
  - Mutating endpoints (POST/PATCH/DELETE)
  - Admin-only endpoints (marked with lock icon)

---

### **C3: Standardized Error Handling**

**Goal:** Provide consistent, actionable error responses across all Data Trust Core endpoints.

#### Error Response Format

**Standard Structure:**
```json
{
  "error": "ValidationError",
  "message": "Invalid request parameters",
  "details": {
    "date": ["Invalid date format. Expected YYYY-MM-DD, received '2026/07/15'"],
    "state": ["Invalid lifecycle transition: cannot move from 'draft' to 'archived' (must be 'active' first)"]
  },
  "timestamp": "2026-07-21T13:15:00Z",
  "path": "/api/v1/mdm/reference-sets/42/transition/"
}
```

**Error Categories:**
1. **Validation Errors (400):** Field-level validation failures
2. **Not Found (404):** Resource does not exist or user lacks access
3. **Permission Denied (403):** User authenticated but not authorized
4. **Conflict (409):** State conflict (e.g., lifecycle transition violation)
5. **Server Error (500):** Unexpected errors (never expose stack traces)

#### Implementation

**Create Custom Exception Handler:**
```python
# backend/catalog/exceptions.py (or shared location)
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.utils import timezone

def data_trust_exception_handler(exc, context):
    # Call DRF's default handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Enhance with standardized format
        error_data = {
            "error": exc.__class__.__name__,
            "message": str(exc),
            "timestamp": timezone.now().isoformat(),
            "path": context['request'].path
        }
        
        # Add field-level details for validation errors
        if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
            error_data['details'] = exc.detail
        
        response.data = error_data
    
    return response

# backend/config/settings.py
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'catalog.exceptions.data_trust_exception_handler',
    # ... other settings
}
```

**Add Validation to Key Endpoints:**
```python
# Example: Lifecycle transition validation
@action(detail=True, methods=['post'])
def transition(self, request, pk=None):
    ref_set = self.get_object()
    new_state = request.data.get('state')
    
    # Validate state is provided
    if not new_state:
        raise ValidationError({"state": ["This field is required"]})
    
    # Validate state is valid
    valid_states = [s[0] for s in ReferenceSet.LIFECYCLE_STATES]
    if new_state not in valid_states:
        raise ValidationError({
            "state": [f"Invalid state '{new_state}'. Allowed: {', '.join(valid_states)}"]
        })
    
    # Validate transition is allowed
    try:
        ref_set.transition_to(new_state, user=request.user)
    except ValueError as e:
        # Convert model-level error to HTTP 409 Conflict
        raise ValidationError({"state": [str(e)]})
    
    return Response(ReferenceSetSerializer(ref_set).data)
```

**Bulk Operation Error Reporting:**
```python
# Example: Bulk archive with per-item results
@action(detail=False, methods=['post'], url_path='archive-bulk')
def archive_bulk(self, request):
    ids = request.data.get('ids', [])
    
    if not ids:
        raise ValidationError({"ids": ["This field is required and must be a non-empty list"]})
    
    results = {"success": [], "failed": []}
    
    for asset_id in ids:
        try:
            asset = AssetProfile.objects.get(pk=asset_id)
            # RBAC check
            if asset.org_unit not in get_user_org_units(request.user):
                results['failed'].append({
                    "id": asset_id,
                    "error": "Permission denied: asset not in your org_unit"
                })
                continue
            
            asset.is_active = False
            asset.save()
            emit_governance_event(...)
            results['success'].append(asset_id)
        except AssetProfile.DoesNotExist:
            results['failed'].append({
                "id": asset_id,
                "error": "Asset not found"
            })
    
    return Response(results, status=status.HTTP_200_OK)
```

**Acceptance Criteria:**
- [ ] All 400 responses include field-level `details` dictionary
- [ ] 404 responses distinguish "not found" from "no permission" (don't leak existence)
- [ ] 500 errors never expose Python stack traces in production
- [ ] Bulk operations return structured `{success: [...], failed: [{id, error}]}` format
- [ ] Lifecycle transition errors (409) include current state and valid next states
- [ ] All error responses include `timestamp` and `path` for debugging
- [ ] Error messages are **actionable** (tell user what to fix, not just what's wrong)

---

## Implementation Guidelines

### Technology Stack (No New Dependencies)
- `drf-yasg` (already installed) — Swagger/OpenAPI generation
- Django REST Framework exception handling (built-in)
- Existing ViewSets and serializers (extend, don't rewrite)

### Testing Protocol
1. **Unit Tests for Error Handling:**
   - Test invalid params return 400 with field details
   - Test missing resource returns 404
   - Test RBAC violations return 403
   - Test lifecycle transition violations return 409

2. **Integration Tests for Bulk Operations:**
   - Test all-success scenario
   - Test partial failure (some IDs valid, some invalid)
   - Test RBAC filtering (can't archive assets outside org_unit)

3. **Manual Swagger Testing:**
   - Load `/api/swagger/` in browser
   - Verify all 16+ new endpoints appear
   - Use "Try it out" for each custom action
   - Verify response examples match actual API behavior

4. **Coverage Target:** ≥80% for modified ViewSets and exception handler

### File Modification Checklist

**Files to Modify:**
- [ ] `backend/catalog/views.py` — Add soft-delete override, bulk archive action, Swagger decorators
- [ ] `backend/catalog/exceptions.py` (new) — Custom exception handler
- [ ] `backend/mdm/views.py` — Add Swagger decorators to custom actions (values, transition, bind-field)
- [ ] `backend/dq/views.py` — Add Swagger decorators to all custom actions
- [ ] `backend/config/settings.py` — Configure custom exception handler
- [ ] `backend/config/urls.py` — Update Swagger schema description
- [ ] `backend/catalog/tests/test_api_errors.py` (new) — Error handling tests
- [ ] `backend/catalog/tests/test_bulk_operations.py` (new) — Bulk operation tests
- [ ] `backend/mdm/tests/test_swagger_docs.py` (new) — Swagger schema validation tests

**No Changes Required:**
- Models (soft-delete flags already exist where needed)
- Serializers (error messages come from ViewSets)
- URL routing (endpoints already registered)

---

## Testing Acceptance Criteria

### Automated Tests (Pytest)
Run all tests with coverage:
```bash
cd backend
pytest catalog/tests/test_api_errors.py -v
pytest catalog/tests/test_bulk_operations.py -v
pytest mdm/tests/test_swagger_docs.py -v
pytest --cov=catalog --cov=mdm --cov=dq --cov-report=term-missing
```

**Expected Output:**
- All tests pass (0 failures, 0 errors)
- Coverage ≥80% for modified files
- No regressions in existing tests (Track A/B/D tests still pass)

### Manual Verification Checklist

**Swagger Documentation:**
1. [ ] Navigate to `http://localhost:8000/api/v1/swagger/`
2. [ ] Verify "Data Trust Core" description appears in header
3. [ ] Expand "catalog" section → verify `POST /catalog/assets/archive-bulk/` appears
4. [ ] Expand "mdm" section → verify `GET /reference-sets/{id}/values/` has `date` parameter documented
5. [ ] Expand "dq" section → verify all 11 endpoints from Track A appear
6. [ ] Click "Try it out" on `GET /dq/rules/{id}/history/` → verify example response matches actual API
7. [ ] Verify error responses (400/404/409) have example JSON in Swagger

**Error Handling:**
1. [ ] `POST /mdm/reference-sets/999/transition/` → 404 with "Reference set not found"
2. [ ] `POST /mdm/reference-sets/{id}/transition/ {"state": "invalid"}` → 400 with allowed states
3. [ ] `POST /catalog/assets/archive-bulk/ {"ids": [1, 999]}` → 200 with `{success: [1], failed: [{id: 999, error: "..."}]}`
4. [ ] `DELETE /catalog/domains/{id}/` → 405 with "Hard delete not supported; use PATCH {is_active: false}"

**Bulk Operations:**
1. [ ] `POST /catalog/assets/archive-bulk/ {"ids": [1, 2, 3]}` → all assets archived, GovernanceEvent emitted
2. [ ] `POST /mdm/reference-values/bulk-create/ [...]` → all values created atomically (rollback on any failure)
3. [ ] Verify RBAC: user can only archive assets in their org_unit

---

## Out of Scope (Deferred to Phase 2 or Future Tracks)

**Explicitly NOT part of this task:**
- ❌ Async API endpoints (Celery-based profiling) — Phase 2
- ❌ Webhook/callback support for long-running operations — Phase 2
- ❌ GraphQL API layer — Not planned
- ❌ API rate limiting beyond Django throttling — Operational concern, Track E
- ❌ API versioning (v2 endpoints) — No breaking changes planned
- ❌ Export Swagger schema to external tools (Postman, Insomnia) — User can download from `/api/swagger/?format=openapi`
- ❌ Frontend integration for new endpoints — Separate track (post-backend completion)

---

## Sequencing Within Track C

Execute deliverables in this order:

1. **C3 First (Error Handling):** Establish error format before documenting it in Swagger
2. **C1 Next (API Coverage):** Implement missing endpoints with proper error handling
3. **C2 Last (Documentation):** Document finalized API surface with all error cases

**Rationale:** Error handling is a cross-cutting concern that affects all endpoints. Documenting incomplete APIs wastes effort.

---

## Success Criteria

**Track C complete when:**
- [ ] All Data Trust Core ViewSets have soft-delete (reject hard DELETE with 405)
- [ ] Bulk archive endpoints work for `AssetProfile`, `ReferenceSet`, `ReferenceValue`
- [ ] All 16+ endpoints from Tracks A/B/D documented in Swagger with examples
- [ ] `/api/swagger/` UI loads without errors and "Try it out" works
- [ ] Custom exception handler returns standardized error format
- [ ] Field-level validation errors include actionable messages
- [ ] Bulk operations report per-item success/failure
- [ ] Lifecycle transition errors (409) include current state context
- [ ] All tests pass with ≥80% coverage
- [ ] No regressions in existing Track A/B/D functionality

---

## Notes for Worker

### Key Constraints
1. **Do NOT introduce breaking changes** — All existing endpoints must continue working
2. **Do NOT add new models** — This is purely API polish, not new features
3. **Use existing patterns** — Follow soft-delete approach from `dataschema` app (`is_archived` flag)
4. **Preserve audit trail** — Emit `GovernanceEvent` for all archive operations
5. **RBAC enforcement** — Filter by user's `org_unit` assignments

### Common Pitfalls to Avoid
- ❌ Forgetting to emit `GovernanceEvent` on archive operations
- ❌ Hard-coding error messages instead of using serializer validation
- ❌ Exposing stack traces in error responses
- ❌ Missing RBAC checks in bulk operations (security vulnerability)
- ❌ Non-atomic bulk creates (should rollback on any validation failure)

### Quality Checklist Before Completion
- [ ] Run full test suite: `pytest --cov=catalog --cov=mdm --cov=dq`
- [ ] Verify Swagger schema validates: `python manage.py spectacular --validate`
- [ ] Test all custom actions via Swagger "Try it out"
- [ ] Check RBAC: non-admin user cannot archive assets outside their org_unit
- [ ] Verify error messages are user-friendly (no technical jargon)
- [ ] Confirm no N+1 queries in bulk operations (use `select_related`, `prefetch_related`)

---

## Deliverable Artifacts

Upon completion, provide:

1. **TASK-RESULT-API-DOCUMENTATION-COMPLETENESS.md** — Completion report with:
   - Summary of implemented endpoints
   - Files modified (line counts)
   - Test results (pytest output + coverage)
   - Manual testing evidence (Swagger screenshots, error response examples)
   - Known issues or edge cases

2. **Code Changes:**
   - Modified ViewSets with soft-delete overrides and Swagger decorators
   - Custom exception handler
   - Bulk operation actions
   - Test files

3. **Testing Evidence:**
   - Pytest output showing all tests passing
   - Coverage report (≥80%)
   - Swagger UI screenshot showing documented endpoints
   - Example error response JSON (400, 404, 409)

---

## References

- [`plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md`](plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md) — Track C specification (lines 128-164)
- [`backend/config/urls.py`](backend/config/urls.py:10-11) — Existing Swagger configuration
- [`backend/dataschema/views.py`](backend/dataschema/views.py:118-168) — Soft-delete pattern reference
- [`backend/catalog/audit_utils.py`](backend/catalog/audit_utils.py) — `emit_governance_event()` utility
- [`TASK-RESULT-DQ-EXECUTION-PHASE1.md`](TASK-RESULT-DQ-EXECUTION-PHASE1.md) — Track A endpoints to document
- [`TASK-RESULT-GOVERNANCE-AUDIT-TRAIL.md`](TASK-RESULT-GOVERNANCE-AUDIT-TRAIL.md) — Track B endpoints to document
- [`TASK-RESULT-REFERENCE-DATA-GOVERNANCE.md`](TASK-RESULT-REFERENCE-DATA-GOVERNANCE.md) — Track D endpoints to document

---

**END OF TASK SPECIFICATION**
