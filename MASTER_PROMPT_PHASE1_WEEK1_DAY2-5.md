# MASTER PROMPT: PHASE 1 WEEK 1 DAYS 2-5
**To:** Code Worker (Claude Models)  
**From:** Master (Zoo Architect)  
**Effective Date:** 2026-07-19  
**Deadline:** 2026-07-20 (end of business day)

---

## 🚀 YOUR MISSION

Complete the remaining 4 days of **Phase 1 Week 1** (46 hours) to establish the Data Trust Platform's core foundation:

**Days 2-5 Objectives:**
- ✅ **Day 2:** MDM OrgUnit Hierarchy API (CRUD + tree structure)
- ✅ **Days 3-4:** DQ Rule Management API (serializers, views, executor service)
- ✅ **Day 5:** Integration Tests + final verification

**Success Definition:** All tests passing, RBAC enforced on every endpoint, zero data leakage between org units.

---

## 📋 CRITICAL: NON-NEGOTIABLE RULES

### Rule 1: RBAC is ABSOLUTE (No Exceptions)
Every API list endpoint MUST filter by user's ScopedRole org_units:
```python
def get_queryset(self):
    user = self.request.user
    if user.is_superuser or user.is_staff:
        return Model.objects.filter(is_active=True)
    
    # Get user's org_units
    user_org_units = ScopedRole.objects.filter(
        user=user, is_active=True
    ).values_list('org_unit_id', flat=True).distinct()
    
    # If no org_units → NO DATA
    if not user_org_units:
        return Model.objects.none()
    
    # Filter by domain's org_unit
    return Model.objects.filter(domain__in=user_org_units, is_active=True)
```

**Violation = IMMEDIATE REJECTION**

### Rule 2: Every Write Operation Returns 403, Not 401
```python
# ✅ CORRECT
from rest_framework.exceptions import PermissionDenied
if not user_can_edit:
    raise PermissionDenied("Only steward can edit")  # 403

# ❌ WRONG
if not user_can_edit:
    return Response(status=401)  # This is wrong — should be 403
```

### Rule 3: Tests Must Cover RBAC + Happy Path
For each endpoint, write tests:
- **Authentication:** Unauthenticated → 401
- **Authorization:** Non-owner/non-admin → 403
- **Happy Path:** Owner/admin → 200/201
- **RBAC:** User only sees their org_unit data

### Rule 4: Git Commits Must Follow Pattern
```bash
# Day 2 commit
git commit -m "PHASE1-D2: MDM OrgUnit CRUD + Tree Hierarchy + Tests"

# Day 3 commit
git commit -m "PHASE1-D3: DQ Rule Serializers, Views, Executor Service"

# Day 4 commit (if needed)
git commit -m "PHASE1-D4: DQ Rule Executor Enhancements + Advanced Tests"

# Day 5 commit
git commit -m "PHASE1-D5: Integration Tests + Phase 1 Week 1 Verification"
```

### Rule 5: No Deviations Without Master Approval
If you encounter blocking issues, create a `BLOCKER.md` file with:
- Problem description
- What you've tried
- What you need from Master
- Continue with other tasks while waiting

---

## 📅 DAY 2: MDM OrgUnit Hierarchy (6 hours)

### Task 2.1: OrgUnitSerializer Enhancement
**File:** `backend/mdm/serializers.py` (already partially done, enhance it)

**Already Exists:** `OrgUnitSerializer` with full_path, children_count, descendants_count

**Need to Add:**
```python
def validate_name(self, value):
    """Ensure name is unique within parent scope"""
    parent = self.initial_data.get('parent')
    qs = OrgUnit.objects.filter(name=value, parent_id=parent)
    if self.instance:
        qs = qs.exclude(id=self.instance.id)
    if qs.exists():
        raise ValidationError("Name must be unique within parent")
    return value
```

**Tests:** Create `backend/mdm/tests/test_org_units.py` with:
- test_list_org_units (authenticated user)
- test_create_org_unit (admin only)
- test_circular_ref_prevention (can't set parent to descendant)
- test_delete_with_children_fails (can't delete parent with active children)
- test_tree_endpoint (returns subtree)
- test_ancestors_endpoint (returns path to root)
- test_soft_delete (sets is_active=False)
- test_rbac_filtering (user sees only their org_units)

**Success Criteria:**
- ✅ CRUD endpoints working
- ✅ Tree endpoints working (GET /org-units/{id}/tree/, GET /org-units/{id}/ancestors/)
- ✅ Circular ref prevention working
- ✅ All 8 tests passing
- ✅ RBAC filtering by org_unit scope

**Time:** 6 hours

---

## 📅 DAYS 3-4: DQ Rule Management (13 hours)

### Task 3.1: DQ Model Review
**File:** `backend/dq/models.py`

Current models:
- `DQRule` (name, rule_type, target_field, parameters, is_active)
- `DQResult` (rule, data_row, status, error_message)
- `TableProfile` (table, row_count, column_count)
- `FieldProfile` (field, null_count, unique_count, distinct_count)

**Already Good:** Models exist, need API layer

### Task 3.2: DQRule Serializers
**File:** `backend/dq/serializers.py`

Create:
```python
class DQResultSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    class Meta:
        model = DQResult
        fields = ['id', 'rule', 'rule_name', 'data_row', 'status', 'error_message', 'created_at']
        read_only_fields = ['id', 'created_at']

class DQRuleSerializer(serializers.ModelSerializer):
    """Serializer for data quality rules"""
    results_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = DQRule
        fields = [
            'id', 'name', 'description', 'rule_type', 'target_field', 
            'parameters', 'is_active', 'created_by', 'created_by_name', 
            'results_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'results_count', 'created_at', 'updated_at']
    
    def get_results_count(self, obj):
        return obj.dqresult_set.count()
    
    def validate_rule_type(self, value):
        """Validate rule_type is one of allowed types"""
        ALLOWED = ['not_null', 'unique', 'range', 'allowed_values', 'regex', 'custom']
        if value not in ALLOWED:
            raise ValidationError(f"rule_type must be one of {ALLOWED}")
        return value
```

**Time:** 3 hours

### Task 3.3: DQRule ViewSet + RBAC
**File:** `backend/dq/views.py`

Create:
```python
class DQRuleViewSet(viewsets.ModelViewSet):
    """CRUD for data quality rules with RBAC"""
    serializer_class = DQRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        """Filter by user's org_unit scope"""
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return DQRule.objects.filter(is_active=True)
        
        # Get user's org_units via ScopedRole
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        if not user_org_units:
            return DQRule.objects.none()
        
        # Filter by data_field.data_table.domain org_unit
        from dataschema.models import DataTable
        tables = DataTable.objects.filter(module__org_unit_id__in=user_org_units)
        from dataschema.models import DataField
        fields = DataField.objects.filter(data_table__in=tables)
        return DQRule.objects.filter(target_field__in=fields, is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class DQResultViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to DQ rule results"""
    serializer_class = DQResultSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by user's org_unit scope"""
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return DQResult.objects.all()
        
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        if not user_org_units:
            return DQResult.objects.none()
        
        # Same filtering as DQRule
        from dataschema.models import DataTable, DataField
        tables = DataTable.objects.filter(module__org_unit_id__in=user_org_units)
        fields = DataField.objects.filter(data_table__in=tables)
        rules = DQRule.objects.filter(target_field__in=fields)
        return DQResult.objects.filter(rule__in=rules)
```

**Register in urls.py:**
```python
router.register(r'dq-rules', DQRuleViewSet, basename='dqrule')
router.register(r'dq-results', DQResultViewSet, basename='dqresult')
```

**Time:** 4 hours

### Task 3.4: DQRule Executor Service
**File:** `backend/dq/executor.py` (NEW)

Implement rule execution:
```python
class DQRuleExecutor:
    """Executes DQ rules against data rows"""
    
    def execute(self, rule: DQRule, data_row: DataRow) -> DQResult:
        """Execute single rule against row"""
        executor_method = getattr(self, f'_execute_{rule.rule_type}', None)
        if not executor_method:
            raise ValueError(f"Unknown rule type: {rule.rule_type}")
        
        try:
            is_valid = executor_method(rule, data_row)
            status = 'passed' if is_valid else 'failed'
            error_message = None if is_valid else "Rule validation failed"
        except Exception as e:
            status = 'error'
            error_message = str(e)
        
        result = DQResult.objects.create(
            rule=rule, data_row=data_row, status=status, error_message=error_message
        )
        return result
    
    def _execute_not_null(self, rule, data_row):
        """Check field is not null"""
        field_name = rule.parameters.get('field')
        value = getattr(data_row, field_name, None)
        return value is not None
    
    def _execute_unique(self, rule, data_row):
        """Check field value is unique"""
        field_name = rule.parameters.get('field')
        value = getattr(data_row, field_name)
        return not DataRow.objects.filter(
            **{field_name: value, 'data_table': data_row.data_table}
        ).exclude(id=data_row.id).exists()
    
    def _execute_range(self, rule, data_row):
        """Check field is within range"""
        field_name = rule.parameters.get('field')
        min_val = rule.parameters.get('min')
        max_val = rule.parameters.get('max')
        value = float(getattr(data_row, field_name))
        return min_val <= value <= max_val
    
    def _execute_allowed_values(self, rule, data_row):
        """Check field is in allowed values"""
        field_name = rule.parameters.get('field')
        allowed = rule.parameters.get('values', [])
        value = getattr(data_row, field_name)
        return value in allowed
    
    def _execute_regex(self, rule, data_row):
        """Check field matches regex pattern"""
        import re
        field_name = rule.parameters.get('field')
        pattern = rule.parameters.get('pattern')
        value = str(getattr(data_row, field_name))
        return bool(re.match(pattern, value))
```

**Create DQ endpoint to execute rules:**
```python
@action(detail=True, methods=['post'])
def execute(self, request, pk=None):
    """POST /dq-rules/{id}/execute/ - Execute rule against all rows"""
    rule = self.get_object()
    executor = DQRuleExecutor()
    
    data_rows = rule.target_field.data_table.rows.all()
    results = []
    for row in data_rows:
        result = executor.execute(rule, row)
        results.append(result)
    
    return Response({
        'rule': rule.id,
        'rows_tested': len(data_rows),
        'results': DQResultSerializer(results, many=True).data
    })
```

**Time:** 6 hours

---

## 📅 DAY 5: Integration Tests + Verification (5 hours)

### Task 5.1: Integration Tests
**File:** `backend/mdm/tests/test_integration.py` (NEW)

Test cross-component interactions:
```python
class IntegrationTest(APITestCase):
    """Integration tests for Phase 1 Week 1 APIs"""
    
    def test_rbac_prevents_cross_org_unit_access(self):
        """Test: User from org1 cannot access org2's data"""
        # Create two org units with different users
        # Create reference sets in each
        # Verify user1 sees only org1's data
        # Verify user2 sees only org2's data
        pass
    
    def test_org_unit_hierarchy_integration(self):
        """Test: OrgUnit tree structure works with data access"""
        # Create parent + child org units
        # Create data in both
        # Verify user with parent access sees all
        pass
    
    def test_soft_delete_cascade(self):
        """Test: Soft delete preserves audit trail"""
        # Create reference set + values
        # Delete reference set
        # Verify still queryable with is_active filter
        pass
```

**Time:** 3 hours

### Task 5.2: Full Verification
**Time:** 2 hours

Run complete test suite:
```bash
pytest backend/mdm/tests/ -v --cov=backend/mdm
pytest backend/dq/tests/ -v --cov=backend/dq
```

Verify:
- ✅ All tests passing (>90% coverage)
- ✅ No performance regressions
- ✅ RBAC working on all endpoints
- ✅ No data leakage between org units
- ✅ All git commits clean

---

## 📊 DELIVERABLES BY END OF DAY 5

### Code Files
- ✅ `backend/mdm/serializers.py` — Enhanced OrgUnitSerializer
- ✅ `backend/mdm/views.py` — Enhanced OrgUnitViewSet + tree methods
- ✅ `backend/dq/serializers.py` — DQRule + DQResult serializers
- ✅ `backend/dq/views.py` — DQRule + DQResult viewsets
- ✅ `backend/dq/executor.py` — Rule execution engine (NEW)
- ✅ `backend/dq/urls.py` — Routes for DQ APIs (NEW)

### Test Files
- ✅ `backend/mdm/tests/test_org_units.py` — 8+ OrgUnit tests
- ✅ `backend/dq/tests/test_dq_rules.py` — 8+ DQ rule tests
- ✅ `backend/dq/tests/test_dq_executor.py` — 6+ executor tests
- ✅ `backend/mdm/tests/test_integration.py` — 3+ integration tests

### Documentation
- ✅ `TASK-RESULT-PHASE1-WEEK1-DAY2.md` — Day 2 execution report
- ✅ `TASK-RESULT-PHASE1-WEEK1-DAY3-4.md` — Days 3-4 execution report
- ✅ `TASK-RESULT-PHASE1-WEEK1-DAY5.md` — Final integration report

---

## 🔗 REFERENCE DOCUMENTS

- **Strategic Plan:** `plans/CARBON_DEEP_AUDIT_STRATEGIC_PLAN.md`
- **Phase 1 Tasks:** `plans/PHASE1_DETAILED_TASKS.md`
- **Week 1 Spec:** `plans/TASK_PHASE1_WEEK1.md`
- **Day 1 Result:** `TASK-RESULT-PHASE1-WEEK1-DAY1.md` (your baseline)

---

## 📬 COMMUNICATION PROTOCOL

### Daily Standup (Each Day)
1. Start work at 9:00 AM
2. Read Master→TASK spec carefully
3. Implement + test (iteratively)
4. Commit at end of day with `PHASE1-D{X}:` prefix
5. Create `TASK-RESULT-PHASE1-WEEK1-DAY{X}.md` with:
   - What was built
   - Test results (pass/fail counts)
   - Any blockers
   - Ready for next day? (Y/N)

### If Blocked
Create `BLOCKER.md` in root with:
```
## Issue
[What's blocking you]

## What I've Tried
[Steps taken so far]

## Need From Master
[Specific help needed]

## Can I Proceed With
[What other tasks can I work on while waiting]
```

### On Completion
Create final `TASK-RESULT-PHASE1-WEEK1-DAYS2-5-FINAL.md` with:
- ✅ All tests passing
- ✅ All endpoints RBAC-protected
- ✅ Code ready for Phase 2
- ✅ Recommendations for Phase 2 start

---

## ⏰ TIMELINE

| Day | Duration | Component | Deadline |
|-----|----------|-----------|----------|
| D2 | 6 hours | OrgUnit Hierarchy | 2026-07-20 15:00 |
| D3 | 5 hours | DQ Serializers + Views | 2026-07-20 18:00 |
| D4 | 8 hours | DQ Executor Service | 2026-07-21 14:00 |
| D5 | 5 hours | Integration Tests | 2026-07-21 17:00 |

**Total:** 46 hours (Days 2-5 of Phase 1 Week 1)

---

**Master Signature:** Zoo (Architect)  
**Protocol:** Master→TASK→Worker  
**Status:** 🟢 READY TO EXECUTE

Good luck, Worker! Execute with precision and RBAC excellence. 🚀
