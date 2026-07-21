# TASK: Data Trust Core — DQ Execution Foundation (Phase 1)

> **Master:** Zoo (Architect Mode)  
> **Worker:** Code Mode  
> **Priority:** CRITICAL PATH — blocks all downstream quality metrics, catalog integration, governance  
> **Reference:** [`plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md`](plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md) Track A

---

## Mission Brief

You are implementing **Track A (Profiling & DQ Execution)** of the Data Trust Core backend completion. This is the **critical path** — quality metrics are the foundation for catalog trust scores, governance workflows, and data observability.

### Current State
- ✅ Models exist: `FieldProfile`, `TableProfile`, `DQRule`, `DQResult` ([`backend/dq/models.py`](backend/dq/models.py:1))
- ✅ Service functions exist: `profile_table()`, `run_dq()` ([`backend/dq/services.py`](backend/dq/services.py:1))
- ✅ ViewSets exist but incomplete: [`backend/dq/views.py`](backend/dq/views.py:1) has read-only ViewSets
- ⚠️ Executor incomplete: [`backend/dq/executor.py`](backend/dq/executor.py) (if exists) has basic rules; missing `regex`, `reference_integrity`
- ❌ API endpoints not exposed: No `POST /dq/profile/`, `POST /dq/run/` actions
- ❌ Write-back missing: DQ results don't update [`AssetProfile.quality_status`](backend/catalog/models.py:72) or [`quality_score`](backend/catalog/models.py:73)

### Your Job
Implement **4 deliverables** in this order:

1. **A1: Complete DQ Rule Executor** — Add missing rule types + tests
2. **A2: Expose Profiling API** — Wire actions to trigger profiling and rule runs
3. **A3: Catalog Write-Back** — Auto-update asset quality from DQ results
4. **A4: DQ Results Query** — Queryable history with trends

---

## Deliverable A1: Complete DQ Rule Executor

### Context
The existing executor in [`backend/dq/services.py`](backend/dq/services.py:60) has basic rule evaluation (`not_null`, `unique`, `allowed_values`, `range`). You must add the missing rule types and make it production-ready.

### Requirements

#### A1.1: Add `regex` Rule Type
- **Location:** [`backend/dq/services.py`](backend/dq/services.py:1) in `_evaluate_rule()` function
- **Logic:**
  - Rule params: `{"pattern": "<regex_string>"}`
  - For each row, extract field value; skip if empty
  - Match against `re.compile(pattern)`; failure if no match
  - Collect failures: `{"row": <row_id>, "value": <failed_value>}`
- **Example:**
  ```python
  # Rule: email field must match email pattern
  # params = {"pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"}
  ```

#### A1.2: Add `reference_integrity` Rule Type
- **Logic:**
  - Rule params: `{"reference_set_id": <int>}` (optional; if missing, use field's `reference_set` FK)
  - Fetch active reference values from [`ReferenceValue`](backend/mdm/models.py:42) with `is_active=True`
  - For each row, check if field value exists in reference set codes
  - Failures: rows with values not in allowed reference set
- **Example:**
  ```python
  # Rule: Scope field must match Emission Scopes reference set
  # params = {"reference_set_id": 5}
  ```

#### A1.3: Performance Optimization
- **Chunked Processing:**
  - If table has >10,000 rows, process in batches of 5,000
  - Accumulate failures across batches
  - Return total checked + failed counts
- **DB Optimization:**
  - Use `select_related('data_field')` when fetching rules
  - Cache reference set values in memory during `allowed_values`/`reference_integrity` checks
  - Avoid N+1 queries

#### A1.4: Test Suite
- **Location:** Create [`backend/dq/tests/test_executor.py`](backend/dq/tests/test_executor.py)
- **Coverage:**
  - Test each rule type (not_null, unique, allowed_values, range, regex, reference_integrity)
  - Test edge cases: empty table, all nulls, duplicate values, invalid regex
  - Test performance: 1000-row table completes in <5s
- **Fixtures:**
  - Create test DataTable with 3 fields (text, number, reference)
  - Create test ReferenceSet with 5 values
  - Create 100 DataRows with known pass/fail patterns
- **Run:** `pytest backend/dq/tests/test_executor.py -v`

### Acceptance Criteria
- [ ] `regex` rule type executes without errors; matches/rejects based on pattern
- [ ] `reference_integrity` rule type validates against active reference values
- [ ] 1000-row table with 5 rules completes profiling in <5s
- [ ] Pytest suite passes with ≥80% coverage for executor logic
- [ ] No N+1 queries (verify with Django Debug Toolbar or query logging)

---

## Deliverable A2: Expose Profiling API

### Context
Service functions [`profile_table()`](backend/dq/services.py:19) and `run_dq()` exist but are not callable via REST API. You must create ViewSet actions to trigger them.

### Requirements

#### A2.1: Profile Action
- **Endpoint:** `POST /carbon-api/dq/profile/`
- **Request Body:**
  ```json
  {
    "data_table_id": 123
  }
  ```
- **Response:**
  ```json
  {
    "table_id": 123,
    "rows_profiled": 1024,
    "fields_profiled": 8,
    "completeness_pct": 87.5,
    "profiled_at": "2026-07-21T06:00:00Z",
    "field_profiles": [
      {
        "field_id": 45,
        "field_name": "emission_factor",
        "completeness_pct": 92.3,
        "distinct_count": 15,
        "top_values": [{"value": "0.233", "count": 200}]
      }
    ]
  }
  ```
- **Location:** Add action to [`backend/dq/views.py`](backend/dq/views.py:1) — create new `ProfileAPIView` or add action to existing ViewSet
- **RBAC:** Only data owners/admins can trigger profiling; check user has `ScopedRole` for table's `org_unit`
- **Error Handling:**
  - 404 if `data_table_id` doesn't exist
  - 403 if user doesn't have access to table
  - 500 with error message if profiling fails (log exception)

#### A2.2: Run DQ Action
- **Endpoint:** `POST /carbon-api/dq/run/`
- **Request Body:**
  ```json
  {
    "rule_id": 78
  }
  ```
  Or batch mode:
  ```json
  {
    "data_table_id": 123
  }
  ```
  (Runs all active rules for table)
- **Response:**
  ```json
  {
    "rule_id": 78,
    "rule_name": "Email format validation",
    "passed": false,
    "checked_count": 1024,
    "failed_count": 12,
    "score": 98,
    "sample_failures": [
      {"row": 5023, "value": "invalid-email"},
      {"row": 5089, "value": "user@"}
    ],
    "run_at": "2026-07-21T06:05:00Z"
  }
  ```
- **Location:** Add action to [`backend/dq/views.py`](backend/dq/views.py:1)
- **RBAC:** Same as profile action (data owners/admins only)

#### A2.3: Bulk Profile
- **Endpoint:** `POST /carbon-api/dq/profile/bulk/`
- **Request Body:**
  ```json
  {
    "data_table_ids": [101, 102, 103]
  }
  ```
- **Response:**
  ```json
  {
    "total": 3,
    "success": 2,
    "failed": 1,
    "results": [
      {"table_id": 101, "status": "success", "rows_profiled": 500},
      {"table_id": 102, "status": "success", "rows_profiled": 1200},
      {"table_id": 103, "status": "error", "error": "Table not found"}
    ]
  }
  ```
- **Logic:** Loop through tables; catch per-table errors; return summary

### Acceptance Criteria
- [ ] `POST /dq/profile/` returns profile with ≥5 metrics per field
- [ ] `POST /dq/run/` executes rule and returns DQResult
- [ ] Batch mode runs all active rules for a table
- [ ] Bulk profile endpoint processes multiple tables with per-item status
- [ ] RBAC enforced: non-owners get 403
- [ ] Errors return clear messages (404, 403, 500 with reason)

---

## Deliverable A3: Catalog Write-Back

### Context
When DQ rules run, the results should automatically update the catalog asset's quality status. Currently [`AssetProfile.quality_status`](backend/catalog/models.py:72) and [`quality_score`](backend/catalog/models.py:73) are not updated.

### Requirements

#### A3.1: Write-Back Trigger
- **Location:** [`backend/dq/services.py`](backend/dq/services.py:1) in `run_dq()` function
- **Logic:**
  1. After rule execution creates `DQResult`, compute aggregate quality for the data table
  2. Fetch all active rules for the table: `DQRule.objects.filter(data_table=table, is_active=True)`
  3. Fetch latest `DQResult` for each rule: `rule.results.order_by('-run_at').first()`
  4. Compute:
     - `passed_count` = number of rules with `passed=True`
     - `total_count` = total active rules
     - `quality_score` = `(passed_count / total_count) * 100` (0–100)
     - `quality_status`:
       - `"passing"` if score ≥ 90
       - `"warning"` if score 70–89
       - `"failing"` if score < 70
       - `"unknown"` if no rules or no results
  5. Update or create `AssetProfile` for the table:
     ```python
     profile, _ = AssetProfile.objects.get_or_create(data_table=table)
     profile.quality_status = status
     profile.quality_score = score
     profile.updated_by = request.user  # pass user from API
     profile.save()
     ```

#### A3.2: Governance Event Hook
- **Location:** Same as A3.1
- **Logic:**
  - After updating `AssetProfile`, create a [`GovernanceEvent`](backend/catalog/models.py:87)
  - Fields:
    - `asset`: the AssetProfile instance
    - `entity_type`: `"AssetProfile"`
    - `entity_id`: `profile.id`
    - `action`: `"update"`
    - `before`: `{"quality_status": old_status, "quality_score": old_score}`
    - `after`: `{"quality_status": new_status, "quality_score": new_score}`
    - `user`: request user
  - Capture "before" state before saving profile

#### A3.3: Field-Level Write-Back
- **Logic:**
  - If rule is field-level (`scope='field'`), also update or create `AssetProfile` for the `DataField`
  - Compute quality_score for the field based on its rules only
  - Same status thresholds (≥90 passing, 70–89 warning, <70 failing)

### Acceptance Criteria
- [ ] After running DQ rule, `AssetProfile.quality_status` updates to reflect pass/fail
- [ ] Quality score (0–100) computed correctly from rule results
- [ ] Field-level assets also get quality status updated
- [ ] `GovernanceEvent` created with before/after snapshot
- [ ] Catalog API (`GET /catalog/assets/`) shows updated quality status

---

## Deliverable A4: DQ Results Query

### Context
Users need to query historical DQ results to see trends, identify recurring failures, and debug data quality issues.

### Requirements

#### A4.1: Results List Endpoint
- **Endpoint:** `GET /carbon-api/dq/results/`
- **Query Params:**
  - `rule_id` (optional): Filter by rule
  - `data_table_id` (optional): Filter by table (get all rules for table)
  - `passed` (optional): Filter by pass/fail (`true`/`false`)
  - `limit` (default 10): Number of results to return
  - `ordering` (default `-run_at`): Sort by run_at desc
- **Response:**
  ```json
  {
    "count": 42,
    "results": [
      {
        "id": 501,
        "rule_id": 78,
        "rule_name": "Email format",
        "rule_type": "regex",
        "run_at": "2026-07-21T06:00:00Z",
        "passed": false,
        "checked_count": 1024,
        "failed_count": 12,
        "score": 98,
        "sample_failures": [{"row": 5023, "value": "invalid"}]
      }
    ]
  }
  ```
- **Location:** [`backend/dq/views.py`](backend/dq/views.py:1) — extend existing `DQResultViewSet` (likely already exists as ReadOnlyModelViewSet)
- **RBAC:** Filter by user's org_unit scope (same as profiles)

#### A4.2: Rule History Action
- **Endpoint:** `GET /carbon-api/dq/rules/{rule_id}/history/`
- **Response:**
  ```json
  {
    "rule_id": 78,
    "rule_name": "Email format",
    "runs": [
      {"run_at": "2026-07-21T06:00:00Z", "passed": false, "score": 98},
      {"run_at": "2026-07-20T06:00:00Z", "passed": true, "score": 100},
      {"run_at": "2026-07-19T06:00:00Z", "passed": false, "score": 95}
    ],
    "trend": "degrading"
  }
  ```
- **Logic:**
  - Fetch last 10 results for rule
  - Compute trend: "improving" if latest score > avg of previous 3, "degrading" if <, else "stable"
- **Location:** Add `@action(detail=True, methods=['get'])` to `DQRuleViewSet`

#### A4.3: Sample Failures Detail
- **Endpoint:** `GET /carbon-api/dq/results/{result_id}/failures/`
- **Response:**
  ```json
  {
    "result_id": 501,
    "rule_name": "Email format",
    "failed_count": 12,
    "sample_size": 5,
    "failures": [
      {
        "row_id": 5023,
        "row_display": "Row 5023",
        "field_name": "contact_email",
        "value": "invalid-email",
        "reason": "Pattern mismatch: expected email format"
      }
    ]
  }
  ```
- **Logic:**
  - Return first 100 failures from `DQResult.sample_failures` JSON
  - Enhance with row metadata (row display name, field name)

### Acceptance Criteria
- [ ] Can query last 10 results for a rule
- [ ] Can filter results by pass/fail status
- [ ] Rule history shows trend (improving/degrading/stable)
- [ ] Sample failures endpoint returns actionable details
- [ ] RBAC filters results by user's org_unit scope

---

## Implementation Guidelines

### File Structure
```
backend/dq/
  models.py          # Already complete
  serializers.py     # Already complete
  services.py        # MODIFY: Add regex, reference_integrity; wire write-back
  views.py           # MODIFY: Add profile/run actions
  urls.py            # UPDATE: Register new endpoints
  tests/
    test_executor.py # CREATE: Rule executor tests
    test_api.py      # CREATE: API endpoint tests
```

### Technology Stack
- **Django REST Framework** (existing)
- **PostgreSQL** (existing)
- **pytest** for tests (existing)
- **Django signals** (for audit hooks if needed)
- NO new dependencies; use existing libraries

### Code Style
- Follow existing patterns in [`backend/dq/services.py`](backend/dq/services.py:1)
- Use Django ORM; avoid raw SQL
- RBAC via `ScopedRole` (existing pattern in [`backend/dq/views.py`](backend/dq/views.py:30))
- Error handling: Try-catch with clear messages; log exceptions
- Type hints: Use Python 3.9+ type hints where helpful

### Testing Protocol
1. Write tests FIRST for each deliverable
2. Run tests: `pytest backend/dq/tests/ -v --cov=backend/dq`
3. Ensure ≥80% coverage before marking deliverable complete
4. Manual API testing with curl or Postman for happy path + error cases

### RBAC Enforcement Pattern
```python
def get_queryset(self):
    qs = DQResult.objects.all()
    user = self.request.user
    if user.is_superuser or user.is_staff:
        return qs
    user_org_units = ScopedRole.objects.filter(
        user=user, is_active=True
    ).values_list('org_unit_id', flat=True).distinct()
    if not user_org_units:
        return DQResult.objects.none()
    return qs.filter(
        rule__data_table__module__org_unit_id__in=user_org_units
    ).distinct()
```

### Write-Back Pattern
```python
def update_asset_quality(table, user):
    rules = DQRule.objects.filter(data_table=table, is_active=True)
    results = [r.results.order_by('-run_at').first() for r in rules]
    passed = sum(1 for r in results if r and r.passed)
    total = len(results)
    score = (passed / total * 100) if total else 0
    status = 'passing' if score >= 90 else 'warning' if score >= 70 else 'failing'
    
    profile, _ = AssetProfile.objects.get_or_create(data_table=table)
    old = {'quality_status': profile.quality_status, 'quality_score': profile.quality_score}
    profile.quality_status = status
    profile.quality_score = score
    profile.updated_by = user
    profile.save()
    
    GovernanceEvent.objects.create(
        asset=profile, entity_type='AssetProfile', entity_id=profile.id,
        action='update', before=old,
        after={'quality_status': status, 'quality_score': score},
        user=user
    )
```

---

## Acceptance Testing

### Manual API Testing Checklist
1. **Profile a table:**
   ```bash
   curl -X POST http://localhost:8000/carbon-api/dq/profile/ \
     -H "Authorization: Token <your_token>" \
     -H "Content-Type: application/json" \
     -d '{"data_table_id": 1}'
   ```
   Expected: 200 OK with profile metrics

2. **Run a rule:**
   ```bash
   curl -X POST http://localhost:8000/carbon-api/dq/run/ \
     -H "Authorization: Token <your_token>" \
     -d '{"rule_id": 1}'
   ```
   Expected: 200 OK with DQResult

3. **Check catalog update:**
   ```bash
   curl http://localhost:8000/carbon-api/catalog/assets/?data_table_id=1 \
     -H "Authorization: Token <your_token>"
   ```
   Expected: Asset shows `quality_status` and `quality_score`

4. **Query results:**
   ```bash
   curl http://localhost:8000/carbon-api/dq/results/?rule_id=1&limit=5 \
     -H "Authorization: Token <your_token>"
   ```
   Expected: List of historical results

5. **Test RBAC:**
   - As non-admin user, attempt to profile a table outside your org_unit
   - Expected: 403 Forbidden

### Pytest Test Suite
```bash
# Run all DQ tests
pytest backend/dq/tests/ -v --cov=backend/dq --cov-report=term-missing

# Expected output:
# test_executor.py::test_not_null_rule PASSED
# test_executor.py::test_unique_rule PASSED
# test_executor.py::test_regex_rule PASSED
# test_executor.py::test_reference_integrity_rule PASSED
# test_api.py::test_profile_endpoint PASSED
# test_api.py::test_run_endpoint PASSED
# test_api.py::test_write_back PASSED
# Coverage: 82%
```

---

## Out of Scope (Do NOT implement)

- ❌ Async profiling (Celery/Redis) — deferred to Phase 2
- ❌ Scheduled rule runs (cron/beat) — deferred to Phase 2
- ❌ DQ dashboards/UI — frontend work, separate task
- ❌ Data lineage — Phase 2
- ❌ Custom rule editor (Python code execution) — security risk, deferred
- ❌ Alert notifications (email/Slack) — Phase 2
- ❌ Profiling for unstructured data (PDFs, images) — out of scope

---

## Deliverable Checklist

Use this checklist to track completion. Mark each item when acceptance criteria pass.

### A1: Complete DQ Rule Executor
- [ ] `regex` rule type implemented and tested
- [ ] `reference_integrity` rule type implemented and tested
- [ ] Chunked processing for tables >10k rows
- [ ] Pytest suite with ≥80% coverage
- [ ] 1000-row table profiles in <5s

### A2: Expose Profiling API
- [ ] `POST /dq/profile/` endpoint functional
- [ ] `POST /dq/run/` endpoint functional
- [ ] Batch mode (all rules for table) works
- [ ] `POST /dq/profile/bulk/` endpoint functional
- [ ] RBAC enforced on all endpoints
- [ ] Error handling (404, 403, 500) with clear messages

### A3: Catalog Write-Back
- [ ] `AssetProfile.quality_status` updates after DQ run
- [ ] `AssetProfile.quality_score` computed correctly (0–100)
- [ ] Field-level assets also updated
- [ ] `GovernanceEvent` created with before/after state
- [ ] Verified via `GET /catalog/assets/` API

### A4: DQ Results Query
- [ ] `GET /dq/results/` with filters works
- [ ] `GET /dq/rules/{id}/history/` shows trend
- [ ] `GET /dq/results/{id}/failures/` returns samples
- [ ] RBAC filters results by org_unit

---

## Success Criteria (Phase 1 Complete)

**This task is DONE when:**
1. ✅ All 4 deliverables pass acceptance criteria
2. ✅ Pytest suite passes with ≥80% coverage
3. ✅ Manual API testing checklist completes without errors
4. ✅ RBAC enforced: data owners see only their data
5. ✅ Catalog assets show updated quality status after DQ runs
6. ✅ No N+1 queries (verify with Django Debug Toolbar)
7. ✅ Code reviewed by master (Zoo) and approved

---

## Deliverable Format

When complete, write [`TASK-RESULT-DQ-EXECUTION-PHASE1.md`](TASK-RESULT-DQ-EXECUTION-PHASE1.md) with:

1. **Summary:** What was implemented
2. **Files Modified:** List of changed files with line counts
3. **API Endpoints:** List new endpoints with example requests/responses
4. **Test Results:** Pytest output showing coverage
5. **Manual Testing:** Screenshots or curl output of successful API calls
6. **Known Issues:** Any limitations or bugs to address later
7. **Master Prompt:** Your message back to Ahmed/Zoo

### Master Prompt Template
```
Master (Ahmed/Zoo),

I've completed Track A (DQ Execution) Phase 1. Here's what's done:

✅ Deliverable A1: DQ Executor - Added regex + reference_integrity rules; 1000-row table profiles in 3.2s
✅ Deliverable A2: API Endpoints - POST /dq/profile/, /dq/run/, /dq/profile/bulk/ all functional
✅ Deliverable A3: Write-Back - AssetProfile quality status auto-updates; GovernanceEvent audit trail working
✅ Deliverable A4: Results Query - GET /dq/results/ with filters; trend analysis working

Test Coverage: 84% (target: 80%)
API Testing: All 5 manual tests passed
RBAC: Enforced on all endpoints

Files Modified:
- backend/dq/services.py (+150 lines)
- backend/dq/views.py (+200 lines)
- backend/dq/urls.py (+10 lines)
- backend/dq/tests/test_executor.py (+300 lines, new)
- backend/dq/tests/test_api.py (+200 lines, new)

Known Issues:
- Bulk profiling times out for tables >50k rows (need async in Phase 2)
- Reference integrity rule doesn't handle circular FK (rare edge case)

Ready for:
- Track B (Governance Audit Trail) next, or
- Frontend integration for DQ results visualization

Worker ready for next task.
```

---

## Questions for Master (Before Starting)

If anything is unclear, ask Ahmed/Zoo:

1. Should `regex` rule support case-insensitive matching? (Add `case_insensitive` param?)
2. For bulk operations, what's the timeout? (Should we fail fast or continue on errors?)
3. Quality score thresholds: Are 90/70 the right cutoffs, or should they be configurable?
4. Write-back: Should we update catalog on every rule run, or only on bulk runs?
5. RBAC: Should superusers/staff bypass org_unit filtering, or enforce strict isolation?

Proceed only after master confirms the task is clear.

---

**Master (Zoo) — ready to hand this off to the worker?**
