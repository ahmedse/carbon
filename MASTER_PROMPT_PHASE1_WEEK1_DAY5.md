i mean no need to load the whole # MASTER PROMPT: PHASE 1 WEEK 1 DAY 5 — INTEGRATION TESTS & FINAL VERIFICATION
**To:** Code Worker (Claude Models)  
**From:** Master (Zoo Architect)  
**Date:** 2026-07-19  
**Deadline:** 2026-07-20 (end of business day)  
**Allocated Time:** 5 hours

---

## 🎯 YOUR MISSION

Complete **Phase 1 Week 1** (Days 1-5) by implementing comprehensive integration tests, fixing 3 identified issues, and achieving **>90% test coverage** with **zero data leakage**.

**Success Criteria:**
- ✅ All 35+ tests passing
- ✅ >90% code coverage on MDM + DQ modules
- ✅ Execute action endpoint tested
- ✅ DQRuleExecutor service fully tested (5 validators)
- ✅ Cross-org-unit access prevention verified
- ✅ Soft delete cascade working
- ✅ TASK-RESULT-PHASE1-WEEK1-DAY5-FINAL.md created

---

## ⚠️ CRITICAL ISSUES TO FIX

### Issue #1: NULL Reference in Serializer (15 min)
**File:** `backend/dq/serializers.py:36-38`

**Current Code (BROKEN):**
```python
created_by_name = serializers.CharField(
    source='created_by.get_full_name', read_only=True, allow_null=True
)
```

**Problem:** If `created_by` is NULL, accessing `.get_full_name` crashes

**Fix Required:**
```python
def get_created_by_name(self, obj):
    """Safely return creator name or default."""
    if obj.created_by:
        return obj.created_by.get_full_name()
    return "System"

created_by_name = serializers.SerializerMethodField()
```

**Test:**
```python
# Should not crash when created_by is NULL
rule = DQRule.objects.create(created_by=None, name='Test')
serializer = DQRuleSerializer(rule)
self.assertEqual(serializer.data['created_by_name'], 'System')
```

---

### Issue #2: Missing Execute Action Tests (45 min)
**File:** `backend/dq/tests/test_dq.py` → Add new test class

**Missing Tests:**
```python
class DQRuleExecuteActionTestCase(TestCase):
    """Test DQRule.execute() custom action."""
    
    def setUp(self):
        self.admin_user = User.objects.create_user('admin', password='pass', is_staff=True)
        self.org_unit = OrgUnit.objects.create(name='Test Org', code='TST')
        self.module = DataModule.objects.create(
            name='Module', slug='module', org_unit=self.org_unit
        )
        self.table = DataTable.objects.create(
            name='Table', slug='table', module=self.module
        )
        self.field = DataField.objects.create(
            name='amount', data_type='decimal', data_table=self.table
        )
        self.client = APIClient()
    
    def test_execute_rule_happy_path(self):
        """Test: authenticated user can execute rule."""
        rule = DQRule.objects.create(
            name='Amount Check', scope='field', data_field=self.field,
            rule_type='range', params={'min': 0, 'max': 1000},
            is_active=True, created_by=self.admin_user
        )
        
        self.client.force_authenticate(self.admin_user)
        response = self.client.post(f'/dq/rules/{rule.id}/execute/')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('score', response.data)
        self.assertIn('passed', response.data)
    
    def test_execute_rule_unauthenticated(self):
        """Test: unauthenticated user gets 401."""
        rule = DQRule.objects.create(
            name='Check', scope='field', data_field=self.field,
            rule_type='not_null', is_active=True
        )
        response = self.client.post(f'/dq/rules/{rule.id}/execute/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_execute_rule_unauthorized_org_unit(self):
        """Test: user without access to rule's org_unit gets 403."""
        other_org = OrgUnit.objects.create(name='Other', code='OTH')
        other_module = DataModule.objects.create(name='Other', slug='other', org_unit=other_org)
        other_table = DataTable.objects.create(name='Other', slug='other', module=other_module)
        other_field = DataField.objects.create(name='f', data_type='text', data_table=other_table)
        
        rule = DQRule.objects.create(
            name='Check', scope='field', data_field=other_field,
            rule_type='not_null', is_active=True
        )
        
        user_no_access = User.objects.create_user('user', password='pass')
        self.client.force_authenticate(user_no_access)
        response = self.client.post(f'/dq/rules/{rule.id}/execute/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
```

---

### Issue #3: Missing Executor Unit Tests (1.5 hours)
**File:** `backend/dq/tests/test_executor.py` (NEW)

**Create comprehensive executor tests:**
```python
# backend/dq/tests/test_executor.py
"""Unit tests for DQRuleExecutor service."""
from django.test import TestCase
from dq.models import DQRule, DQResult
from dq.executor import DQRuleExecutor
from dataschema.models import DataTable, DataField, DataModule
from mdm.models import OrgUnit

class DQRuleExecutorTestCase(TestCase):
    """Test DQRuleExecutor validators."""
    
    def setUp(self):
        self.org_unit = OrgUnit.objects.create(name='Test', code='TST')
        self.module = DataModule.objects.create(name='Mod', slug='mod', org_unit=self.org_unit)
        self.table = DataTable.objects.create(name='T', slug='t', module=self.module)
        self.field = DataField.objects.create(name='f', data_type='text', data_table=self.table)
    
    def test_validate_not_null_all_pass(self):
        """Test: not_null validator passes when all values present."""
        rule = DQRule.objects.create(
            name='Not Null', scope='field', data_field=self.field,
            rule_type='not_null', params={'field': 'f'}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'f': 'value1'}, {'f': 'value2'}, {'f': 'value3'}
        ]
        result = executor.execute(data_sample)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_count, 0)
        self.assertEqual(result.score, 100)
    
    def test_validate_not_null_has_failures(self):
        """Test: not_null validator detects null values."""
        rule = DQRule.objects.create(
            name='Not Null', scope='field', data_field=self.field,
            rule_type='not_null', params={'field': 'f'}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'f': 'value1'}, {'f': None}, {'f': ''}
        ]
        result = executor.execute(data_sample)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.failed_count, 2)
        self.assertLess(result.score, 100)
    
    def test_validate_unique_all_pass(self):
        """Test: unique validator passes when all distinct."""
        rule = DQRule.objects.create(
            name='Unique', scope='field', data_field=self.field,
            rule_type='unique', params={'field': 'f'}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'f': 'a'}, {'f': 'b'}, {'f': 'c'}
        ]
        result = executor.execute(data_sample)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_count, 0)
    
    def test_validate_unique_has_duplicates(self):
        """Test: unique validator detects duplicates."""
        rule = DQRule.objects.create(
            name='Unique', scope='field', data_field=self.field,
            rule_type='unique', params={'field': 'f'}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'f': 'a'}, {'f': 'a'}, {'f': 'b'}
        ]
        result = executor.execute(data_sample)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.failed_count, 1)
    
    def test_validate_allowed_values_pass(self):
        """Test: allowed_values validator passes for valid values."""
        rule = DQRule.objects.create(
            name='Allowed', scope='field', data_field=self.field,
            rule_type='allowed_values',
            params={'field': 'status', 'allowed_values': ['active', 'inactive']}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'status': 'active'}, {'status': 'inactive'}
        ]
        result = executor.execute(data_sample)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_count, 0)
    
    def test_validate_allowed_values_fail(self):
        """Test: allowed_values validator rejects invalid values."""
        rule = DQRule.objects.create(
            name='Allowed', scope='field', data_field=self.field,
            rule_type='allowed_values',
            params={'field': 'status', 'allowed_values': ['active', 'inactive']}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'status': 'active'}, {'status': 'unknown'}
        ]
        result = executor.execute(data_sample)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.failed_count, 1)
    
    def test_validate_range_pass(self):
        """Test: range validator passes for values within bounds."""
        rule = DQRule.objects.create(
            name='Range', scope='field', data_field=self.field,
            rule_type='range',
            params={'field': 'amount', 'min': 0, 'max': 1000}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'amount': 100}, {'amount': 500}, {'amount': 0}, {'amount': 1000}
        ]
        result = executor.execute(data_sample)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_count, 0)
    
    def test_validate_range_fail(self):
        """Test: range validator rejects out-of-range values."""
        rule = DQRule.objects.create(
            name='Range', scope='field', data_field=self.field,
            rule_type='range',
            params={'field': 'amount', 'min': 0, 'max': 1000}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'amount': 100}, {'amount': 1500}, {'amount': -10}
        ]
        result = executor.execute(data_sample)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.failed_count, 2)
    
    def test_validate_regex_pass(self):
        """Test: regex validator passes for matching patterns."""
        rule = DQRule.objects.create(
            name='Email', scope='field', data_field=self.field,
            rule_type='regex',
            params={'field': 'email', 'pattern': r'^[a-z]+@[a-z]+\.[a-z]+$'}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'email': 'user@example.com'}, {'email': 'test@domain.org'}
        ]
        result = executor.execute(data_sample)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_count, 0)
    
    def test_validate_regex_fail(self):
        """Test: regex validator rejects non-matching values."""
        rule = DQRule.objects.create(
            name='Email', scope='field', data_field=self.field,
            rule_type='regex',
            params={'field': 'email', 'pattern': r'^[a-z]+@[a-z]+\.[a-z]+$'}
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [
            {'email': 'user@example.com'}, {'email': 'invalid-email'}
        ]
        result = executor.execute(data_sample)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.failed_count, 1)
    
    def test_executor_error_handling(self):
        """Test: executor handles errors gracefully."""
        rule = DQRule.objects.create(
            name='Bad', scope='field', data_field=self.field,
            rule_type='regex',
            params={'field': 'f', 'pattern': '[invalid(regex'}  # Invalid regex
        )
        
        executor = DQRuleExecutor(rule)
        data_sample = [{'f': 'value'}]
        result = executor.execute(data_sample)
        
        self.assertFalse(result.passed)
        self.assertIn('error', result.sample_failures[0])
```

---

## 📋 REQUIRED INTEGRATION TESTS

### Task 5.1: Cross-Org-Unit Access Prevention (1.5 hours)
**File:** `backend/mdm/tests/test_integration.py` (NEW)

```python
# backend/mdm/tests/test_integration.py
"""Integration tests for RBAC enforcement across modules."""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from mdm.models import OrgUnit, ReferenceSet
from accounts.models import ScopedRole
from catalog.models import DataDomain
from django.contrib.auth.models import Group

User = get_user_model()

class CrossOrgUnitAccessPreventionTestCase(APITestCase):
    """Verify users cannot access other org units' data."""
    
    def setUp(self):
        """Set up two org units with different users."""
        self.client_api = self.client
        
        # Users
        self.user_org1 = User.objects.create_user('user1', password='pass')
        self.user_org2 = User.objects.create_user('user2', password='pass')
        
        # Org Units
        self.org_unit_1 = OrgUnit.objects.create(
            name='Engineering', code='ENG', org_type='college'
        )
        self.org_unit_2 = OrgUnit.objects.create(
            name='Medicine', code='MED', org_type='college'
        )
        
        # Domains
        self.domain_1 = DataDomain.objects.create(
            name='Engineering Domain', id=self.org_unit_1.id
        )
        self.domain_2 = DataDomain.objects.create(
            name='Medicine Domain', id=self.org_unit_2.id
        )
        
        # Admin group
        self.admins_group = Group.objects.create(name='admins_group')
        
        # Assign org units to users
        ScopedRole.objects.create(
            user=self.user_org1, group=self.admins_group,
            org_unit=self.org_unit_1, is_active=True
        )
        ScopedRole.objects.create(
            user=self.user_org2, group=self.admins_group,
            org_unit=self.org_unit_2, is_active=True
        )
    
    def test_user_org1_cannot_see_org2_reference_sets(self):
        """Test: user from org1 cannot list org2's reference sets."""
        # Create reference set in org2
        ref_set_org2 = ReferenceSet.objects.create(
            name='Org2 Data', slug='org2-data',
            steward=self.user_org2, domain=self.domain_2, is_active=True
        )
        
        # User1 tries to access it
        self.client_api.force_authenticate(self.user_org1)
        response = self.client_api.get('/api/v1/mdm/reference-sets/')
        
        # Should NOT see org2's data
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ref_set_ids = [r['id'] for r in response.data['results']]
        self.assertNotIn(ref_set_org2.id, ref_set_ids)
    
    def test_user_org1_cannot_access_org2_reference_set_detail(self):
        """Test: user from org1 cannot detail-view org2's reference set."""
        ref_set_org2 = ReferenceSet.objects.create(
            name='Org2 Data', slug='org2-data',
            steward=self.user_org2, domain=self.domain_2, is_active=True
        )
        
        self.client_api.force_authenticate(self.user_org1)
        response = self.client_api.get(f'/api/v1/mdm/reference-sets/{ref_set_org2.id}/')
        
        # Should get 404 (not found in filtered queryset)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_user_with_no_org_units_sees_no_data(self):
        """Test: user with no org unit assignments gets empty results."""
        user_no_org = User.objects.create_user('noorg', password='pass')
        
        ref_set_org1 = ReferenceSet.objects.create(
            name='Org1 Data', slug='org1-data',
            steward=self.user_org1, domain=self.domain_1, is_active=True
        )
        
        self.client_api.force_authenticate(user_no_org)
        response = self.client_api.get('/api/v1/mdm/reference-sets/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
```

### Task 5.2: Soft Delete Cascade Tests (1 hour)
**File:** `backend/mdm/tests/test_integration.py` (add to existing)

```python
class SoftDeleteCascadeTestCase(APITestCase):
    """Verify soft deletes preserve audit trail."""
    
    def setUp(self):
        self.admin_user = User.objects.create_user('admin', password='pass', is_staff=True)
        self.client_api = self.client
    
    def test_soft_delete_sets_is_active_false(self):
        """Test: DELETE sets is_active=False instead of hard delete."""
        from mdm.models import ReferenceSet
        from catalog.models import DataDomain
        
        org_unit = OrgUnit.objects.create(name='Test', code='TST')
        domain = DataDomain.objects.create(name='Domain', id=org_unit.id)
        
        ref_set = ReferenceSet.objects.create(
            name='Test Set', slug='test', steward=self.admin_user,
            domain=domain, is_active=True
        )
        
        self.client_api.force_authenticate(self.admin_user)
        response = self.client_api.delete(f'/api/v1/mdm/reference-sets/{ref_set.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify record still exists but is_active=False
        ref_set.refresh_from_db()
        self.assertFalse(ref_set.is_active)
        self.assertTrue(ReferenceSet.objects.filter(id=ref_set.id).exists())
    
    def test_soft_deleted_data_not_returned_in_list(self):
        """Test: soft-deleted records excluded from list endpoints."""
        from mdm.models import ReferenceSet
        from catalog.models import DataDomain
        
        org_unit = OrgUnit.objects.create(name='Test', code='TST')
        domain = DataDomain.objects.create(name='Domain', id=org_unit.id)
        
        # Create and soft-delete
        ref_set = ReferenceSet.objects.create(
            name='Deleted', slug='deleted', steward=self.admin_user,
            domain=domain, is_active=False
        )
        
        # Create active one
        ref_set_active = ReferenceSet.objects.create(
            name='Active', slug='active', steward=self.admin_user,
            domain=domain, is_active=True
        )
        
        self.client_api.force_authenticate(self.admin_user)
        response = self.client_api.get('/api/v1/mdm/reference-sets/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ref_set_ids = [r['id'] for r in response.data['results']]
        
        self.assertNotIn(ref_set.id, ref_set_ids)  # Deleted not shown
        self.assertIn(ref_set_active.id, ref_set_ids)  # Active shown
```

### Task 5.3: DQ Rule Soft Delete Tests (30 min)
**File:** `backend/dq/tests/test_integration.py` (NEW)

```python
# backend/dq/tests/test_integration.py
"""Integration tests for DQ Rule soft deletes."""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from dq.models import DQRule
from dataschema.models import DataTable, DataField, DataModule
from mdm.models import OrgUnit

User = get_user_model()

class DQRuleSoftDeleteTestCase(APITestCase):
    """Verify DQ rules soft delete correctly."""
    
    def setUp(self):
        self.admin_user = User.objects.create_user('admin', password='pass', is_staff=True)
        self.org_unit = OrgUnit.objects.create(name='Test', code='TST')
        self.module = DataModule.objects.create(name='Mod', slug='mod', org_unit=self.org_unit)
        self.table = DataTable.objects.create(name='T', slug='t', module=self.module)
        self.field = DataField.objects.create(name='f', data_type='text', data_table=self.table)
        self.client_api = self.client
    
    def test_delete_rule_soft_deletes(self):
        """Test: DELETE /dq-rules/{id}/ soft deletes rule."""
        rule = DQRule.objects.create(
            name='Test Rule', scope='field', data_field=self.field,
            rule_type='not_null', is_active=True, created_by=self.admin_user
        )
        
        self.client_api.force_authenticate(self.admin_user)
        response = self.client_api.delete(f'/dq-rules/{rule.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
        self.assertTrue(DQRule.objects.filter(id=rule.id).exists())
    
    def test_soft_deleted_rules_excluded_from_list(self):
        """Test: soft-deleted rules not in list endpoint."""
        rule_deleted = DQRule.objects.create(
            name='Deleted', scope='field', data_field=self.field,
            rule_type='not_null', is_active=False, created_by=self.admin_user
        )
        rule_active = DQRule.objects.create(
            name='Active', scope='field', data_field=self.field,
            rule_type='unique', is_active=True, created_by=self.admin_user
        )
        
        self.client_api.force_authenticate(self.admin_user)
        response = self.client_api.get('/dq-rules/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rule_ids = [r['id'] for r in response.data]
        
        self.assertNotIn(rule_deleted.id, rule_ids)
        self.assertIn(rule_active.id, rule_ids)
```

---

## 📊 CODE COVERAGE REQUIREMENTS

### Task 5.4: Verify Coverage >90% (30 min)

**Run coverage:**
```bash
cd backend
pytest mdm/tests/ dq/tests/ --cov=mdm --cov=dq --cov-report=html
```

**Expected Output:**
```
Name              Stmts   Miss  Cover
backend/mdm       XXX     YY    >90%
backend/dq        XXX     YY    >90%
```

**If Coverage < 90%:**
1. Identify missing lines: `coverage report -m`
2. Add tests for uncovered branches
3. Prioritize critical paths (RBAC, validation, error handling)

---

## 🧪 COMPLETE TEST RUN

**Task 5.5: Full Test Suite (30 min)**

```bash
# Run all backend tests
cd backend
pytest -v --tb=short

# Expected: ALL PASSING
# Sample output:
# ✓ test_reference_sets.py::ReferenceSetViewSetTest::test_unauthenticated_get_401 PASSED
# ✓ test_org_units.py::OrgUnitHierarchyTestCase::test_tree_endpoint PASSED
# ✓ test_dq.py::DQRuleCRUDTestCase::test_create_rule_admin PASSED
# ✓ test_executor.py::DQRuleExecutorTestCase::test_validate_not_null_all_pass PASSED
# ✓ test_integration.py::CrossOrgUnitAccessPreventionTestCase::test_user_org1_cannot_see_org2_reference_sets PASSED

# ===== 35+ passed in X.XXs =====
```

---

## 📝 COMPLETION DELIVERABLE

### Task 5.6: Create TASK-RESULT-PHASE1-WEEK1-DAY5-FINAL.md

**Template:**
```markdown
# TASK-RESULT: PHASE 1 WEEK 1 DAY 5 — INTEGRATION TESTS & FINAL VERIFICATION
**Date:** 2026-07-20  
**Owner:** Code Worker  
**Status:** ✅ 100% COMPLETE

## Summary
- ✅ Fixed 3 critical issues (NULL serializer, execute tests, executor tests)
- ✅ Added 20+ integration tests
- ✅ Achieved >90% code coverage
- ✅ All 35+ tests passing
- ✅ RBAC verified across all endpoints
- ✅ No data leakage between org units
- ✅ Soft delete cascade working

## Files Modified
- backend/dq/serializers.py (1 fix)
- backend/dq/tests/test_dq.py (1 new test class)
- backend/dq/tests/test_executor.py (NEW - comprehensive)
- backend/mdm/tests/test_integration.py (NEW - cross-org-unit tests)
- backend/dq/tests/test_integration.py (NEW - soft delete tests)

## Test Coverage
- MDM: >90%
- DQ: >90%
- Overall: >90%

## Non-Negotiable Rules Status
- Rule 1 (RBAC): ✅ 100% — All viewsets filter by org_unit
- Rule 2 (403 vs 401): ✅ 100% — PermissionDenied used correctly
- Rule 3 (Soft Deletes): ✅ 100% — No hard deletes
- Rule 4 (Auto-Assign): ✅ 100% — created_by/steward assigned
- Rule 5 (ScopedRole): ✅ 100% — Integrated throughout

## Issues Fixed
1. ✅ NULL Serializer Reference → Safe method field
2. ✅ Missing Execute Action Tests → Full test class added
3. ✅ Missing Executor Unit Tests → 10 comprehensive tests added

## Git Commits
- PHASE1-D5: Integration Tests + Issue Fixes
- PHASE1-W1: Week 1 Final Verification

## Ready for Phase 1 Week 2
- Lineage APIs
- Governance Policies
- AssetProfile Stewardship
```

---

## ⏰ TIME ALLOCATION

| Task | Time | Priority |
|---|---|---|
| 5.1: Fix NULL Serializer | 15 min | CRITICAL |
| 5.2: Execute Action Tests | 45 min | CRITICAL |
| 5.3: Executor Unit Tests | 1.5 hrs | CRITICAL |
| 5.4: Cross-Org-Unit Tests | 1.5 hrs | HIGH |
| 5.5: Soft Delete Tests | 1 hr | HIGH |
| 5.6: Coverage Verification | 30 min | HIGH |
| 5.7: Full Test Run | 30 min | MEDIUM |
| 5.8: Final Report | 30 min | MEDIUM |
| **TOTAL** | **5 hours** | |

---

## ✅ SUCCESS CRITERIA (GATE TO PHASE 2)

- [ ] All 3 issues fixed
- [ ] All new test files created with >15 tests each
- [ ] Coverage >90% for MDM + DQ
- [ ] All 35+ tests passing
- [ ] No RBAC violations detected
- [ ] TASK-RESULT-PHASE1-WEEK1-DAY5-FINAL.md created
- [ ] Git history clean (5 commits: D1-D5)

**SIGN-OFF:** When all criteria met, create completion report and notify Master.

---

## 🚨 BLOCKER PROTOCOL

If you encounter blocking issues:
1. Create `BLOCKER-DAY5.md` with:
   - Problem description
   - What you've tried
   - Impact on timeline
   - Suggested workaround or needs from Master
2. Continue with other tasks
3. Notify Master immediately

---

## 🎓 LEARNING OBJECTIVES

After Day 5, you will have:
- ✅ Mastered RBAC enforcement patterns
- ✅ Implemented comprehensive integration tests
- ✅ Understood soft delete audit trails
- ✅ Created extensible executor service
- ✅ Verified zero data leakage in multi-org system

**Ready for Phase 2: Lineage + Governance APIs**

