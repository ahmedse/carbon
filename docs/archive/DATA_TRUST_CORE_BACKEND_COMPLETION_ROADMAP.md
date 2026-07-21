# Data Trust Core — Backend Completion Roadmap

> **Strategic Context:** User explicitly requesting "what next toward completing the data trust core modules? in backend first."
> This plan focuses on **backend-first development** of core platform functionality, following DESIGN_DATA_TRUST_CORE.md and PLAN_DATA_TRUST_PHASES.md.

---

## Executive Summary

The **Data Trust Core** architecture exists with three foundational apps (`catalog`, `mdm`, `dq`) already scaffolded. Current state:

### ✅ What's Built (Phase 1 UI Complete)
- Frontend: `AssetsPage`, `MDMPage`, `ReferenceSetDetailPage` with unified MUI DataGrid + BaseDetailPage patterns
- Backend models: `catalog` (DataDomain, GlossaryTerm, AssetProfile), `mdm` (ReferenceSet, ReferenceValue, OrgUnit), `dq` (DQRule, FieldProfile, TableProfile)
- Basic RBAC filtering via `ScopedRole`
- API endpoints with ViewSets and serializers

### ❌ Critical Gaps (Backend Infrastructure)
1. **Profiling & DQ Execution** — Service functions exist but not fully integrated with API endpoints
2. **Rule Execution Framework** — Executor class exists but lacks comprehensive testing
3. **Governance Event Audit Trail** — Models exist but auditing hooks not wired in all CRUD operations
4. **Reference Integrity Rules** — DQ model supports it, but executor incomplete
5. **API Documentation** — No `drf_yasg` integration (Swagger/OpenAPI)
6. **Bulk Operations** — No batch profiling/rule-running endpoints
7. **Temporal Tracking** — No versioning/SCD for reference data changes
8. **Error Handling & Resilience** — Missing comprehensive error scenarios and recovery

---

## Current Backend State Analysis

### Phase 1 Completion Status: **70% done**

| Component | Status | Notes |
|-----------|--------|-------|
| **Models** | ✅ 100% | All entities defined per design; migrations applied |
| **ViewSets/Serializers** | ✅ 90% | Most CRUD implemented; some write-back logic missing |
| **RBAC Filtering** | ⚠️ 70% | Basic `ScopedRole` filtering works; permissive mode for MDM needs review |
| **DQ Service Layer** | ⚠️ 60% | Profiling & rule execution functions exist; not all rule types complete |
| **Audit/Governance** | ❌ 20% | Models exist; hooks not wired into CRUD operations |
| **API Integration** | ⚠️ 50% | ViewSets exist; some actions not exposed; no async support |
| **Error Handling** | ❌ 10% | Basic try-catch; no comprehensive error reporting |
| **Documentation** | ❌ 0% | No Swagger/OpenAPI docs |

---

## Backend Completion Roadmap (Phase 1 Completion)

### **Track A: Profiling & DQ Execution** (Critical Path)

**Goal:** Make profiling and rule execution stable, performant, and fully integrated.

#### A1. Complete DQ Rule Executor
- **Current:** Basic executor in `dq/executor.py` with 4 rule types (`not_null`, `unique`, `allowed_values`, `range`)
- **Missing:** `regex`, `reference_integrity`, rule batching, performance optimization
- **Deliverable:** Full executor with all 5 rule types + comprehensive test suite
- **Acceptance:**
  - All rule types execute on sample data without errors
  - `regex` rules correctly match patterns
  - `reference_integrity` validates FK relationships
  - Pytest coverage ≥ 80% for executor
  - Performance: 1000-row table profiled in <5s

#### A2. Expose Profiling via API
- **Current:** Service functions exist; not exposed via API endpoint
- **Missing:** `POST /dq/profile/` and `POST /dq/run/` action endpoints
- **Deliverable:** RESTful endpoints for triggering profiling and rule runs
- **Acceptance:**
  - `POST /dq/profile/?table_id=<id>` returns profile with ≥5 metrics per field
  - `POST /dq/run/?rule_id=<id>` returns DQResult with pass/fail + sample failures
  - Async tasks deferred (Phase 2); synchronous responses for now
  - RBAC enforced (data owners/admins can trigger)

#### A3. Write-Back to Catalog
- **Current:** `AssetProfile` has `quality_status` and `quality_score` fields; not populated by DQ
- **Missing:** Automatic update of catalog metadata after DQ runs
- **Deliverable:** Trigger that updates `AssetProfile.quality_status` + `quality_score` based on latest DQ results
- **Acceptance:**
  - After rule run, asset's quality status reflects pass/fail
  - Quality score (0–100) computed as (passed rules / total rules * 100)
  - Catalog audit trail records the change

#### A4. DQ Results Query & History
- **Current:** `DQResult` model exists; no aggregation or trend queries
- **Missing:** Endpoints to query rule history, trends, sample failures
- **Deliverable:** `GET /dq/results/?rule_id=<id>&limit=10` returns ordered results with details
- **Acceptance:**
  - Can fetch last 10 results for a rule
  - Can filter results by pass/fail status
  - Sample failures JSON is parseable and actionable

---

### **Track B: Governance Audit Trail** (Trust Foundation)

**Goal:** Ensure every change to governance-controlled entities is audited and traceable.

#### B1. Wire GovernanceEvent Hooks
- **Current:** `GovernanceEvent` model exists; auditing not triggered from CRUD
- **Missing:** Signals/post-save hooks for `AssetProfile`, `GlossaryTerm`, `DataDomain` updates
- **Deliverable:** Automatic event logging on create/update/delete
- **Acceptance:**
  - Update to `AssetProfile.owner` creates `GovernanceEvent(action='update')`
  - `before`/`after` JSON captures changed fields
  - Event includes user, timestamp, entity type, action
  - Can query `/catalog/events/?entity_type=AssetProfile` for audit trail

#### B2. Reference Data Change Tracking
- **Current:** `ReferenceSet` and `ReferenceValue` have no version tracking
- **Missing:** Capture before/after state when values change
- **Deliverable:** Create `ReferenceValueChangeLog` or extend `GovernanceEvent` for MDM changes
- **Acceptance:**
  - Deactivating a `ReferenceValue` creates an event with the change reason
  - Can query history of a reference set's values
  - Supports compliance audits (who changed what, when)

#### B3. Governance Event API
- **Current:** No API endpoint for governance events
- **Missing:** Queryable audit trail endpoint
- **Deliverable:** `GET /catalog/governance-events/?entity_type=X&user_id=Y&action=Z&start_date=...&end_date=...`
- **Acceptance:**
  - Can filter by entity type, user, action, date range
  - Returns paginated results with details
  - RBAC ensures data owners see only their domain's events

---

### **Track C: API Completeness & Documentation** (Integration Layer)

**Goal:** Ensure all backend capabilities are exposed via well-documented APIs.

#### C1. Complete API Coverage
- **Current:** Most ViewSets exist; some actions missing
- **Missing:**
  - `DELETE` endpoints for soft deletion (archive instead of hard delete)
  - Bulk operations (`POST /dq/profile/bulk/` for multiple tables)
  - Custom actions: `reference-sets/{id}/values/`, `org-units/{id}/tree/`, `org-units/{id}/ancestors/`
- **Deliverable:** All designed API endpoints functional
- **Acceptance:**
  - Can CRUD all entities via REST
  - Soft-delete works (archived flag, audit trail)
  - Bulk operations complete in reasonable time
  - All custom actions return expected shapes

#### C2. Swagger/OpenAPI Documentation
- **Current:** No Swagger configured
- **Missing:** `drf_yasg` integration with endpoint documentation
- **Deliverable:** Auto-generated Swagger UI at `/api/docs/` showing all endpoints
- **Acceptance:**
  - All ViewSets documented with request/response shapes
  - RBAC requirements visible (which roles can write)
  - Examples for common operations
  - Interactive "Try it out" feature works

#### C3. Error Handling & Validation
- **Current:** Basic Django error responses (400, 500)
- **Missing:** Consistent error format, validation messages, partial failure handling
- **Deliverable:** Standardized error response shape with actionable messages
- **Acceptance:**
  - Invalid reference_set ID returns 404 with clear message
  - Validation errors list specific field + reason
  - Bulk operations report per-item success/failure
  - No stack traces exposed in production responses

---

### **Track D: Reference Data Governance** (MDM Depth)

**Goal:** Complete the governance layer for reference data (not master data yet).

#### D1. Reference Data Versioning (Temporal Validity)
- **Current:** `ReferenceValue` has `valid_from`/`valid_to` fields; not enforced
- **Missing:**
  - Automatic enforcement: only show active (current date within valid range) values
  - API query: `GET /reference-sets/{id}/values/?date=<ISO>` returns values valid on that date
  - Time-travel support for compliance
- **Deliverable:** Temporal query layer for reference data
- **Acceptance:**
  - Value with `valid_from=2026-08-01` is not returned before that date
  - Can query historical values as-of a specific date
  - DQ rule `allowed_values` respects validity dates

#### D2. Reference Set Lifecycle
- **Current:** Sets have `is_active` flag; no formal lifecycle
- **Missing:**
  - Lifecycle states: draft → active → deprecated → archived
  - Transition validation (e.g., can't transition draft→archived)
  - Communication layer (notify data owners when a set is deprecated)
- **Deliverable:** Formal lifecycle with state machine
- **Acceptance:**
  - Can transition set through valid states
  - Deprecated sets still readable; new bindings rejected
  - API shows lifecycle state clearly

#### D3. Reference Data Binding Management
- **Current:** `DataField.reference_set` FK exists; no enforcement
- **Missing:**
  - UI/API to bind/unbind fields to reference sets
  - Validation: can't unbind a set that has active rows violating the new constraint
  - Bulk rebinding (e.g., "bind all Scope fields to Emission Scopes set")
- **Deliverable:** Complete binding CRUD with safety checks
- **Acceptance:**
  - `PATCH /data-fields/{id}/` accepts `reference_set` parameter
  - Unbind rejected if data would violate rule
  - Can bulk-bind via `POST /reference-sets/{id}/bind-fields/`

---

### **Track E: Operational Excellence** (Reliability)

**Goal:** Ensure the platform is production-ready with observability and resilience.

#### E1. Logging & Observability
- **Current:** Basic Django logging; no structured logs
- **Missing:**
  - Structured JSON logs (action, user, entity, result, timing)
  - Request-scoped correlation IDs for tracing
  - Performance metrics (profiling duration, rule execution time)
- **Deliverable:** Structured logging infrastructure
- **Acceptance:**
  - All API operations logged with outcome (success/error)
  - Long operations (>5s) flagged with duration
  - Can trace a specific user's actions across requests

#### E2. Error Recovery & Retry Logic
- **Current:** No retry mechanism for failed profiling/rules
- **Missing:**
  - Transient error handling (DB connection timeout, memory spike)
  - Retry with exponential backoff for async tasks (Phase 2)
  - Partial failure reporting in bulk operations
- **Deliverable:** Resilient service layer
- **Acceptance:**
  - Profiling a 100k-row table doesn't crash on memory spike
  - Failed rule runs are logged with reason
  - Bulk operations report per-item outcome

#### E3. Performance Optimization
- **Current:** No profiling or indexing analysis
- **Missing:**
  - Database indices for common queries (org_unit, active status, dates)
  - Query optimization (select_related, prefetch_related)
  - Caching for immutable reference data
- **Deliverable:** Optimized queries and data access
- **Acceptance:**
  - `GET /reference-sets/?domain=X` completes in <500ms (even with 1000 sets)
  - Asset list with profiles loads in <2s
  - No N+1 queries in ViewSet list endpoints

---

## Implementation Sequence

Follow this order to maximize dependency resolution and minimize rework:

```
1. Track A: DQ Execution (A1, A2) — foundation for quality metrics
2. Track B: Audit Trail (B1, B2, B3) — enables compliance
3. Track A: Write-Back (A3, A4) — connects DQ to catalog
4. Track D: Versioning (D1) — Reference data governance
5. Track C: API Completeness (C1) — expose all capabilities
6. Track D: Lifecycle (D2, D3) — reference set workflows
7. Track C: Documentation (C2, C3) — user-facing clarity
8. Track E: Observability (E1, E2, E3) — production readiness
```

---

## Acceptance Criteria (Phase 1 Exit Gate)

### Functional
- [ ] All DQ rule types execute successfully on real data
- [ ] Profiling a 1000-row table completes in <5s with actionable metrics
- [ ] Catalog assets show quality status/score from DQ
- [ ] Reference data lifecycle (active/deprecated/archived) enforced
- [ ] All CRUD operations audited with GovernanceEvent trail
- [ ] API endpoints handle edge cases (missing IDs, invalid params) with clear errors

### Non-Functional
- [ ] RBAC enforced: data owners can only trigger profiling/rules on their data
- [ ] Swagger docs auto-generated and interactive
- [ ] No N+1 queries in list endpoints
- [ ] Structured JSON logs for all operations
- [ ] 100-row test suite for DQ executor, services, viewsets (pytest)

### Compliance & Audit
- [ ] Every governance-controlled entity change is logged
- [ ] Audit trail queryable by date range, entity type, user
- [ ] Reference data versioning enables time-travel queries
- [ ] No untracked mutations of sensitive entities

---

## Deliverables Per Track

### Track A (DQ Execution)
- [ ] Enhanced `DQRuleExecutor` with all rule types + tests
- [ ] API actions: `POST /dq/profile/`, `POST /dq/run/`
- [ ] Catalog write-back trigger
- [ ] DQ results query endpoint

### Track B (Governance)
- [ ] `GovernanceEvent` signal handlers + tests
- [ ] Reference data change log
- [ ] Governance event API endpoint

### Track C (API)
- [ ] Complete ViewSet actions (all CRUD + custom)
- [ ] Swagger integration with docs
- [ ] Consistent error response format

### Track D (Reference Data Governance)
- [ ] Temporal validity query layer
- [ ] Reference set lifecycle state machine
- [ ] Field binding CRUD + bulk operations

### Track E (Observability)
- [ ] Structured logging setup
- [ ] Error recovery/retry logic
- [ ] Query optimization + indexing

---

## Notes for Implementation

### Key Dependencies
- All tracks depend on **Track A** (DQ execution) for accurate quality metrics
- **Track B** (audit) must be wired during CRUD implementation in all tracks
- **Track C** documentation is generated after all APIs are finalized

### Technology Stack (No Changes)
- Django REST Framework (existing)
- PostgreSQL (existing)
- Redis (available, not required for Phase 1)
- drf-yasg (add for Swagger)
- Django Signals (for audit hooks)

### Testing Strategy
- Unit tests for service functions (DQ executor, profiling)
- Integration tests for ViewSet actions (API + DB)
- Pytest fixtures for test data (reference sets, profiles)
- No end-to-end tests in Phase 1 (frontend tested separately)

### Phase 2 Dependencies (Do NOT pull forward)
- Async profiling (Celery, Redis) — deferred to Phase 2
- Data lineage — Phase 2
- MDM golden records (matching/merge) — Phase 2
- Pulse integration contract — Phase 3

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| DQ on large tables times out | Implement chunked processing; Phase 2 → async queues |
| RBAC filters too restrictive | Start permissive (all org_units see global ref data); tighten after testing |
| Audit trail fills DB | Partition GovernanceEvent by date; archive old events |
| API documentation stale | Auto-generate from code via drf-yasg; enforce on CI |
| Reference data versioning breaks reports | Phase 1 uses current values only; Phase 2 adds historical queries |

---

## Success Metrics

**Backend Phase 1 Complete when:**
1. ✅ All 4 DQ rule types pass pytest (regex, reference_integrity included)
2. ✅ Profiling API endpoint responds in <2s for 1000-row table
3. ✅ Asset quality status automatically updated after DQ run
4. ✅ Audit trail captures all governance entity changes
5. ✅ Reference set lifecycle enforced (draft → active → deprecated → archived)
6. ✅ Swagger docs fully rendered at `/api/docs/`
7. ✅ RBAC filtering allows data owners to see only their domain assets
8. ✅ 90%+ test coverage for service layer + ViewSets
9. ✅ Production build successful; no runtime errors on real AASTMT data

