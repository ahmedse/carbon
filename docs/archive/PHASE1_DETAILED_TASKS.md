# PHASE 1: Stabilize Data Trust Platform Core — Detailed Task List

**Duration:** 2 weeks (10 working days)  
**Target Completion Date:** End of Week 2  
**Owner:** Backend + Frontend Teams

---

## Overview

Phase 1 stabilizes the data trust platform by completing four critical areas:
1. **MDM APIs** (Master Data Management) — reference data + org hierarchy
2. **DQ APIs** (Data Quality) — rules + profiling + results
3. **Lineage** (NEW) — track data upstream/downstream dependencies
4. **Governance Policies** (NEW) — define + enforce access control rules

All APIs must have:
- ✅ Serializers (DRF ModelSerializer)
- ✅ Views (Generic ViewSets with CRUD)
- ✅ URLs (registered in urls.py)
- ✅ Permissions (check user role + scope)
- ✅ Unit tests (model + serializer + view tests)
- ✅ Integration tests (RBAC enforcement, error handling)

---

## Task Breakdown by Component

### Component 1: MDM APIs (Master Data Management)

#### 1.1 Complete ReferenceSet/ReferenceValue API
**File:** `backend/mdm/serializers.py`  
**Time:** Day 1 (4 hours)

```python
# Tasks:
- [ ] Create ReferenceSetSerializer (nested ReferenceValueSerializer)
- [ ] Create ReferenceValueSerializer (code, label, is_active, sort_order, metadata)
- [ ] Add validation: code uniqueness per reference_set, label uniqueness per reference_set
- [ ] Add created_by default to current user
```

**File:** `backend/mdm/views.py`  
**Time:** Day 1 (4 hours)

```python
# Tasks:
- [ ] Create ReferenceSetViewSet (GenericViewSet + CRUD mixins)
  - GET /mdm/reference-sets/ (list, filterable by is_active)
  - POST /mdm/reference-sets/ (create, auto-assign created_by)
  - GET /mdm/reference-sets/{id}/ (detail, nested values)
  - PUT /mdm/reference-sets/{id}/ (update name/description/steward)
  - DELETE /mdm/reference-sets/{id}/ (soft delete: mark is_active=False)
- [ ] Create ReferenceValueViewSet
  - GET /mdm/reference-sets/{set_id}/values/ (list)
  - POST /mdm/reference-sets/{set_id}/values/ (add value to set)
  - PUT /mdm/reference-sets/{set_id}/values/{id}/ (update)
  - DELETE /mdm/reference-sets/{set_id}/values/{id}/ (delete)
- [ ] Add IsAuthenticated permission to all views
- [ ] Add ReferenceSet permission: only steward can edit (future: add IsObjectSteward)
```

**File:** `backend/mdm/permissions.py`  
**Time:** Day 1 (2 hours)

```python
# Tasks:
- [ ] Create IsReferenceSetSteward(permissions.BasePermission)
  - Check: request.user == object.steward or request.user.is_admin
- [ ] Create IsReferenceValueOwner(permissions.BasePermission)
  - Check: user can edit if steward of parent ReferenceSet
```

**File:** `backend/mdm/urls.py`  
**Time:** Day 1 (1 hour)

```python
# Tasks:
- [ ] Register ReferenceSetViewSet router
- [ ] Register ReferenceValueViewSet router
- [ ] Verify nested routes work: /mdm/reference-sets/{set_id}/values/
```

**File:** `backend/mdm/tests/test_reference_data.py`  
**Time:** Day 2 (6 hours)

```python
# Tasks:
- [ ] Create ReferenceSetSerializerTest (valid/invalid cases)
- [ ] Create ReferenceSetViewSetTest
  - Test list (unauthenticated → 401, authenticated → 200)
  - Test create (authenticated user becomes created_by)
  - Test update (only steward can update)
  - Test delete (soft delete, is_active=False)
  - Test filtering by is_active
- [ ] Create ReferenceValueViewSetTest
  - Test add value (validates uniqueness per set)
  - Test update value (only steward can)
  - Test delete value
- [ ] Test error handling: 403 Forbidden for non-steward edits
- [ ] Test performance: list 100 reference sets with values (should be <500ms)
```

---

#### 1.2 Complete OrgUnit API
**File:** `backend/mdm/serializers.py`  
**Time:** Day 2 (2 hours)

```python
# Tasks:
- [ ] Create OrgUnitSerializer
  - Include id, name, slug, code, org_type, parent, children (nested, read-only)
  - Add description, is_active
  - Add full_path property (serialized)
  - Add get_ancestor_ids method
```

**File:** `backend/mdm/views.py`  
**Time:** Day 2 (4 hours)

```python
# Tasks:
- [ ] Create OrgUnitViewSet
  - GET /mdm/orgunits/ (list, show tree structure, filterable by parent, is_active)
  - POST /mdm/orgunits/ (create under parent)
  - GET /mdm/orgunits/{id}/ (detail, include children)
  - PUT /mdm/orgunits/{id}/ (update name/description/parent)
  - DELETE /mdm/orgunits/{id}/ (cascade check: can't delete if has active children)
  - GET /mdm/orgunits/{id}/descendants/ (list all descendants + self)
  - GET /mdm/orgunits/{id}/ancestors/ (list all ancestors)
  - GET /mdm/orgunits/by-path/{path}/ (resolve full_path to org unit)
- [ ] Add permission: only admin can create/edit/delete OrgUnit (future: add org steward role)
- [ ] Add validation: parent must exist, no circular references
```

**File:** `backend/mdm/tests/test_orgunits.py`  
**Time:** Day 3 (4 hours)

```python
# Tasks:
- [ ] Create OrgUnitSerializerTest
  - Test full_path generation
  - Test nested children serialization
- [ ] Create OrgUnitViewSetTest
  - Test hierarchy: create root → add child → add grandchild
  - Test ancestors/descendants queries
  - Test path resolution
  - Test circular reference prevention (parent = self → error)
  - Test delete cascade: can't delete parent with active children
  - Test permission: non-admin → 403 on create/edit/delete
- [ ] Test tree listing performance (1000 orgunits, should load in <1s)
```

---

### Component 2: DQ APIs (Data Quality)

#### 2.1 Complete DQRule API
**File:** `backend/dq/serializers.py`  
**Time:** Day 3 (3 hours)

```python
# Tasks:
- [ ] Create DQRuleSerializer
  - Include id, scope (field/table), data_table, data_field, rule_type
  - Include params (JSONField), severity, is_active
  - Add validation: if scope='field', data_field must not be null
  - Add validation: if scope='table', data_table must not be null
- [ ] Create DQResultSerializer
  - Include id, rule (nested), run_at, passed, checked_count, failed_count
  - Include sample_failures (JSON), score (0-100)
```

**File:** `backend/dq/views.py`  
**Time:** Day 3 (4 hours)

```python
# Tasks:
- [ ] Create DQRuleViewSet
  - GET /dq/rules/ (list, filterable by scope/data_table/data_field/rule_type/is_active)
  - POST /dq/rules/ (create, validate params structure for rule_type)
  - GET /dq/rules/{id}/ (detail)
  - PUT /dq/rules/{id}/ (update)
  - DELETE /dq/rules/{id}/ (soft delete: is_active=False)
  - POST /dq/rules/{id}/execute/ (run rule against data, store result)
- [ ] Create DQResultViewSet
  - GET /dq/results/ (list, filterable by rule/run_at range/passed status)
  - GET /dq/results/{id}/ (detail)
- [ ] Add permission: only dataowner + admin can create/edit DQ rules
- [ ] Add validation for params structure by rule_type
  - not_null: params = {}
  - unique: params = {}
  - range: params = {min, max}
  - allowed_values: params = {values: []}
  - regex: params = {pattern: '...'}
```

**File:** `backend/dq/services.py`  
**Time:** Day 4 (8 hours) — CRITICAL

```python
# Tasks:
- [ ] Create DQRuleExecutor service
  - def execute_rule(rule, data_row_ids=None):
    - If no data_row_ids: execute on ALL rows in rule.data_table
    - Fetch rows from DataRow model
    - Apply rule logic based on rule_type
    - Collect failures (sample up to 10)
    - Calculate score: (checked_count - failed_count) / checked_count * 100
    - Return DQResult
  
  - def check_not_null(field, rows):
    - For each row in rows: check if row.values[field.name] is not None/empty
    - Count failures
    - Return failed_count

  - def check_unique(field, rows):
    - Collect all values for field
    - Count distinct vs total
    - Count failures: total - distinct
    - Return failed_count

  - def check_range(field, rows, min, max):
    - For each row: check value >= min AND value <= max
    - Count failures
    - Return failed_count

  - def check_allowed_values(field, rows, values):
    - For each row: check if value in values list
    - Count failures
    - Return failed_count

  - def check_regex(field, rows, pattern):
    - For each row: check if str(value) matches regex pattern
    - Count failures
    - Return failed_count

- [ ] Add error handling: skip null values gracefully, log format errors
- [ ] Add performance: batch process rows (1000 at a time to avoid memory spike)
- [ ] Add audit: log rule execution (user, timestamp, row count, result)
```

**File:** `backend/dq/tests/test_dq.py`  
**Time:** Day 5 (8 hours)

```python
# Tasks:
- [ ] Create DQRuleSerializerTest (validation tests)
  - Test invalid params for rule_type (e.g., range without min/max)
  - Test scope validation (field_scope requires data_field, etc.)

- [ ] Create DQRuleViewSetTest
  - Test list (filterable by scope/rule_type)
  - Test create (validate params)
  - Test execute endpoint: trigger rule, check DQResult created
  - Test permission: non-admin → 403 on create/edit
  - Test soft delete: is_active=False after DELETE

- [ ] Create DQRuleExecutorTest
  - Test NOT_NULL: 100 rows, 5 nulls → failed_count=5, score=95
  - Test UNIQUE: 100 rows, 10 duplicates → failed_count=10, score=90
  - Test RANGE: 100 rows, 20 out of range → failed_count=20, score=80
  - Test ALLOWED_VALUES: 100 rows, 30 invalid → failed_count=30, score=70
  - Test REGEX: 100 rows, 10 non-matching → failed_count=10, score=90
  - Test error handling: null values skipped gracefully
  - Test performance: 10k rows evaluated in <2 seconds

- [ ] Create DQResultSerializerTest (validate JSON structure)
- [ ] Create sample_failures truncation test (limit to 10 samples)
```

---

#### 2.2 Complete FieldProfile & TableProfile API
**File:** `backend/dq/serializers.py`  
**Time:** Day 2 (2 hours)

```python
# Tasks:
- [ ] Create FieldProfileSerializer (read-only, used in metrics endpoints)
  - Include all profile metrics (row_count, null_count, distinct_count, completeness_pct, etc.)
- [ ] Create TableProfileSerializer (read-only)
  - Include table row_count, completeness_pct, profiled_at
```

**File:** `backend/dq/views.py`  
**Time:** Day 2 (3 hours)

```python
# Tasks:
- [ ] Create FieldProfileViewSet (read-only, for metrics dashboard)
  - GET /dq/field-profiles/ (list, filterable by data_field/data_table)
  - GET /dq/field-profiles/{id}/ (detail)
  - GET /dq/field-profiles/by-table/{table_id}/ (profiles for all fields in table)

- [ ] Create TableProfileViewSet (read-only)
  - GET /dq/table-profiles/ (list)
  - GET /dq/table-profiles/{id}/ (detail)

- [ ] Create DQ Metrics endpoint (aggregate across rules + profiles)
  - GET /dq/metrics/table-quality/{table_id}/ (return avg quality score)
  - GET /dq/metrics/field-quality/{field_id}/ (return avg quality score)
  - GET /dq/metrics/recent-results/ (list last 10 rule executions)
  - GET /dq/metrics/trending/ (quality score over time for table/field)
```

**File:** `backend/dq/services.py`  
**Time:** Day 4 (3 hours)

```python
# Tasks:
- [ ] Create ProfileCalculator service
  - def profile_field(field, rows=None):
    - If no rows: fetch all from data_table
    - Calculate: row_count, null_count, distinct_count, completeness, uniqueness
    - Calculate: min_value, max_value, mean_value
    - Calculate: top_values (top 10 by frequency)
    - Create FieldProfile entry
    - Return profile

  - def profile_table(table):
    - Fetch all rows
    - Calculate: row_count, completeness (avg across fields)
    - Create TableProfile entry
    - Return profile

- [ ] Add scheduling (future): auto-profile on data changes (Django Celery task)
- [ ] Add performance: batch field profiling (all fields in table in one pass)
```

**File:** `backend/dq/tests/test_profiling.py`  
**Time:** Day 5 (4 hours)

```python
# Tasks:
- [ ] Create ProfileCalculatorTest
  - Test field profile: 100 rows, 10 nulls → null_count=10, completeness=90%
  - Test distinct count: 100 rows, 30 distinct → uniqueness=30%
  - Test min/max/mean: numeric fields only
  - Test top_values: return top 10 distinct values with counts
  - Test performance: profile 100-field table with 10k rows in <5 seconds

- [ ] Create TableProfileViewSetTest
  - Test list profiles
  - Test detail with metrics
  - Test trending endpoint (quality over 30 days)

- [ ] Create DQ Metrics EndpointTest
  - Test table_quality aggregation
  - Test field_quality aggregation
  - Test trending calculation
```

---

### Component 3: Lineage (NEW APP)

#### 3.1 Create Lineage Models & Serializers
**File:** `backend/lineage/__init__.py`  
**Time:** Day 6 (1 hour)

```python
# Tasks:
- [ ] Create apps.py (register 'lineage' app in settings.INSTALLED_APPS)
- [ ] Create models.py with DataLineage + FieldLineage models
```

**File:** `backend/lineage/models.py`  
**Time:** Day 6 (3 hours)

```python
# Tasks:
- [ ] Create DataLineage model:
  ```python
  class DataLineage(models.Model):
      upstream_table = FK(DataTable, related_name='lineage_downstream')
      downstream_table = FK(DataTable, related_name='lineage_upstream')
      lineage_type = CharField(choices=['direct', 'transform', 'aggregate', 'join', 'union'])
      description = TextField(blank=True)
      created_by = FK(User, null=True)
      created_at = DateTimeField(auto_now_add=True)
      
      def __str__(self):
          return f"{self.upstream_table} → {self.downstream_table} ({self.lineage_type})"
  ```

- [ ] Create FieldLineage model:
  ```python
  class FieldLineage(models.Model):
      upstream_field = FK(DataField, related_name='lineage_downstream')
      downstream_field = FK(DataField, related_name='lineage_upstream')
      transform_rule = TextField(blank=True, help_text="e.g., 'SUM', 'CONCAT', 'FILTER'")
      created_by = FK(User, null=True)
      created_at = DateTimeField(auto_now_add=True)
      
      def __str__(self):
          return f"{self.upstream_field} → {self.downstream_field}"
  ```

- [ ] Add migrations: `python manage.py makemigrations lineage`
- [ ] Add to Django admin for manual lineage definition
```

**File:** `backend/lineage/serializers.py`  
**Time:** Day 6 (2 hours)

```python
# Tasks:
- [ ] Create DataLineageSerializer
  - Include nested upstream_table/downstream_table
  - Include lineage_type + description
  - Add validation: upstream != downstream (no self-loops)

- [ ] Create FieldLineageSerializer
  - Include nested upstream_field/downstream_field
  - Include transform_rule
  - Add validation: upstream.data_table != downstream.data_table (no direct field lineage)
```

**File:** `backend/lineage/views.py`  
**Time:** Day 6 (4 hours)

```python
# Tasks:
- [ ] Create DataLineageViewSet
  - GET /lineage/table-lineage/ (list all table lineages)
  - POST /lineage/table-lineage/ (create lineage)
  - GET /lineage/table-lineage/{id}/ (detail)
  - PUT /lineage/table-lineage/{id}/ (update description/type)
  - DELETE /lineage/table-lineage/{id}/ (delete)

- [ ] Create FieldLineageViewSet
  - GET /lineage/field-lineage/ (list)
  - POST /lineage/field-lineage/ (create)
  - PUT/DELETE endpoints

- [ ] Create TraceLineageViewSet
  - GET /lineage/trace/upstream/{table_id}/ (walk upstream tables, return path)
  - GET /lineage/trace/downstream/{table_id}/ (walk downstream tables)
  - GET /lineage/trace/impact/{table_id}/ (show all affected tables on change)
```

**File:** `backend/lineage/services.py`  
**Time:** Day 7 (4 hours)

```python
# Tasks:
- [ ] Create LineageTracer service
  - def get_upstream(table_id):
    - BFS/DFS walk all DataLineage edges pointing to table_id
    - Return list of upstream table IDs + lineage type

  - def get_downstream(table_id):
    - BFS/DFS walk all DataLineage edges coming from table_id
    - Return list of downstream table IDs

  - def get_impact_chain(table_id):
    - Walk downstream recursively
    - Return tree of all affected tables
    - Used for: "if we delete this field, which tables/reports break?"

  - def validate_no_cycles():
    - Check DataLineage for circular dependencies
    - Return list of cycles found

- [ ] Add caching (future): cache lineage graph, invalidate on change
```

**File:** `backend/lineage/urls.py`  
**Time:** Day 6 (1 hour)

```python
# Tasks:
- [ ] Register all ViewSet routers
- [ ] Add routes in config/urls.py for /api/v1/lineage/
```

**File:** `backend/lineage/tests/test_lineage.py`  
**Time:** Day 7 (6 hours)

```python
# Tasks:
- [ ] Create DataLineageSerializerTest (validation, no self-loops)
- [ ] Create DataLineageViewSetTest (CRUD operations)
- [ ] Create LineageTracerTest
  - Test upstream tracing: A→B→C, upstream(C)=[A,B]
  - Test downstream tracing
  - Test circular dependency detection
  - Test impact chain (all affected tables on delete)
  - Test performance: 1000 tables with 500 lineages, trace in <500ms
- [ ] Create FieldLineageTest (similar to above)
```

---

### Component 4: Governance Policies (NEW)

#### 4.1 Add GovernancePolicy Model to Catalog
**File:** `backend/catalog/models.py`  
**Time:** Day 8 (3 hours)

```python
# Tasks:
- [ ] Extend models with GovernancePolicy:
  ```python
  class GovernancePolicy(models.Model):
      RULE_TYPES = [
          ('access_control', 'Access Control'),
          ('classification', 'Data Classification'),
          ('retention', 'Data Retention'),
      ]
      
      name = CharField(max_length=200, unique=True)
      description = TextField(blank=True)
      scope = CharField(max_length=20, choices=[
          ('field', 'Field-level'), ('table', 'Table-level'), ('module', 'Module-level')
      ])
      rule_type = CharField(max_length=20, choices=RULE_TYPES)
      
      # Conditions: {role: 'dataowner', org_unit: 'Engineering', scope: 1}
      conditions = JSONField(default=dict)
      
      # Actions: {can_edit: true, can_delete: false, can_export: false}
      actions = JSONField(default=dict)
      
      created_by = FK(User, null=True)
      created_at = DateTimeField(auto_now_add=True)
      updated_at = DateTimeField(auto_now=True)
  ```

- [ ] Add migration: `python manage.py makemigrations catalog`
- [ ] Add to Django admin
```

**File:** `backend/catalog/serializers.py`  
**Time:** Day 8 (2 hours)

```python
# Tasks:
- [ ] Create GovernancePolicySerializer
  - Include all fields
  - Add validation: conditions/actions are valid JSON, keys are from allowed list
  - Add read-only created_by field
```

**File:** `backend/catalog/views.py`  
**Time:** Day 8 (3 hours)

```python
# Tasks:
- [ ] Create GovernancePolicyViewSet
  - GET /catalog/policies/ (list, filterable by scope/rule_type)
  - POST /catalog/policies/ (create, admin only)
  - PUT /catalog/policies/{id}/ (update, admin only)
  - DELETE /catalog/policies/{id}/ (delete, admin only)
  - POST /catalog/policies/{id}/evaluate/ (test policy against action)

- [ ] Create PolicyEvaluator view helper
  - Input: policy, user, action, context (table_id/field_id/module_id)
  - Output: {allowed: bool, reason: str}
```

**File:** `backend/catalog/services.py`  
**Time:** Day 8 (4 hours)

```python
# Tasks:
- [ ] Create PolicyEvaluator service
  - def evaluate_policy(policy, user, action, context):
    - Parse policy conditions (role, org_unit, scope, etc.)
    - Check if user matches conditions
    - If match: return policy.actions
    - Else: return default (deny)
    - Return {allowed: bool, actions: {...}, reason: str}

  - def evaluate_all_policies(user, action, context):
    - Get all applicable policies (scope matches)
    - Evaluate each
    - Return combined result (most restrictive wins)

  - def enforce_on_datarow_write(user, data_row, context):
    - Called before DataRow update/create
    - Check if user allowed to edit this table for this scope
    - Raise PermissionDenied if not

- [ ] Add audit logging: log every policy evaluation (for compliance)
```

**File:** `backend/catalog/tests/test_governance.py`  
**Time:** Day 9 (6 hours)

```python
# Tasks:
- [ ] Create GovernancePolicySerializerTest (validation)
- [ ] Create GovernancePolicyViewSetTest (CRUD)
- [ ] Create PolicyEvaluatorTest
  - Test access_control policy: only 'dataowner' role can edit
  - Test classification policy: 'confidential' data needs approval
  - Test retention policy: 'pii' data auto-expires after 365 days
  - Test multiple policies: most restrictive wins
  - Test context matching (org_unit, module, scope)
  - Test audit logging

- [ ] Create enforce_on_datarow_write test
  - User without permission tries to edit → PermissionDenied raised
  - User with permission edits → succeeds
```

---

### Component 5: Test All APIs End-to-End

**Time:** Day 9-10 (8 hours)

#### 5.1 Integration Tests
```python
# File: backend/tests/test_integration_phase1.py

# Tasks:
- [ ] Test E2E: Create OrgUnit → Create ReferenceSet → Create DQRule → Execute → Check Result
- [ ] Test E2E: Define table lineage → Add field lineage → Trace upstream/downstream
- [ ] Test E2E: Create governance policy → Evaluate against user action → Audit log
- [ ] Test E2E: RBAC enforcement
  - Admin creates rule, dataowner can't delete, auditor can only view
  - Steward of ReferenceSet can edit, others can't
  - Policy blocks non-owner from editing Scope 1 data

- [ ] Test permission matrix (all 15 combinations):
  - admin: full access to all operations
  - dataowner: create/edit own scope data, can't cross scopes
  - auditor: read-only, can view audit logs
  - viewer: read-only, limited to own org_unit
  - None: 401 Unauthorized

- [ ] Test error handling:
  - 400: invalid request (bad JSON, missing required fields)
  - 403: forbidden (insufficient permissions)
  - 404: not found (resource doesn't exist)
  - 409: conflict (duplicate unique constraint)
  - 500: server error (shouldn't happen, log for debugging)

- [ ] Test performance:
  - List 1000 reference sets: <1s
  - Trace lineage with 10k tables: <2s
  - Profile 100-field table with 100k rows: <10s
  - Execute 50 DQ rules on 10k rows: <5s
```

#### 5.2 API Documentation Update
```python
# File: backend/config/urls.py + Swagger schema

# Tasks:
- [ ] Verify all new endpoints appear in Swagger UI (/api/v1/swagger/)
- [ ] Document all endpoints with examples
- [ ] Document error responses (400, 403, 404, 500)
- [ ] Document permission requirements per endpoint
- [ ] Document query parameters (filters, sorting, pagination)
```

---

## Daily Breakdown

| Day | Component | Tasks | Hours |
|-----|-----------|-------|-------|
| **Day 1** | MDM: ReferenceSet | Serializers, Views, Permissions, URLs | 11 |
| **Day 2** | MDM: OrgUnit | Serializers, Views, Tests | 6 |
| **Day 3** | DQ: DQRule | Serializers, Views, Permissions | 7 |
| **Day 4** | DQ: Rule Executor Service | Rule execution logic, batch processing, audit | 11 |
| **Day 5** | DQ: Testing | Unit tests, executor tests, performance | 12 |
| **Day 6** | Lineage: Models | Models, migrations, serializers, initial views | 11 |
| **Day 7** | Lineage: Trace Service | LineageTracer implementation, tests | 10 |
| **Day 8** | Governance: Policy Model | GovernancePolicy model, serializers, views | 8 |
| **Day 9** | Governance: Evaluator Service | PolicyEvaluator logic, tests, audit logging | 10 |
| **Day 10** | Integration & E2E | Full integration tests, performance tests, documentation | 8 |

**Total:** ~94 hours (distributed across 2 weeks, roughly 9-10 hours/day)

---

## Success Criteria (Definition of Done)

✅ **Backend**
- [ ] All MDM endpoints working (CRUD for RefSet, RefValue, OrgUnit)
- [ ] All DQ endpoints working (CRUD for rules, results, profiles, metrics)
- [ ] All Lineage endpoints working (CRUD + trace)
- [ ] All Governance endpoints working (CRUD + evaluate)
- [ ] All APIs return 401 for unauthenticated users
- [ ] All write operations check permissions (return 403 if denied)
- [ ] All tests passing (>95% coverage for Phase 1 code)
- [ ] No N+1 queries (check with Django Debug Toolbar)
- [ ] Performance benchmarks met (<1s list, <2s trace, <10s profile)

✅ **Frontend (Phase 1 Foundation)**
- [ ] Create API layers: mdm.js, dq.js, lineage.js, governance.js
- [ ] All CRUD operations callable from frontend
- [ ] Error handling: display 400/403/404/500 messages to user

✅ **Documentation**
- [ ] All endpoints documented in Swagger
- [ ] All models documented (field descriptions)
- [ ] RBAC matrix documented (who can do what)
- [ ] Deployment checklist updated

---

## Handoff to Phase 2

At end of Phase 1:
- ✅ All backend APIs complete + tested
- ✅ All data trust core features available via REST API
- ✅ RBAC foundation in place
- 🔨 Frontend pages can now be built on solid API foundation
- 🔨 Phase 2 team builds UI/UX on top of these APIs

