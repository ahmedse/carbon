# TASK: PHASE 1 WEEK 1 — Data Trust Platform Core Foundation

**Phase:** 1  
**Week:** 1 of 2  
**Owner:** Code Copilot (Worker)  
**Duration:** 5 days (50 hours)  
**Submission Deadline:** End of Week 1  
**Escalation Point:** Ahmed (Master/Architect)

---

## Week 1 Overview

**Objective:** Complete MDM APIs (reference data management) + DQ Rule infrastructure.

**Daily Breakdown:**
- **Day 1:** MDM ReferenceSet Serializers + Views (4 hours)
- **Day 2:** MDM OrgUnit Serializers + Views + Tests (6 hours)
- **Day 3:** DQ Rule Serializers + Views + Initial Tests (5 hours)
- **Day 4:** DQ Rule Executor Service (8 hours) — CRITICAL PATH
- **Day 5:** Integration Tests + Documentation (5 hours)

**Deliverables by End of Week 1:**
- ✅ All MDM endpoints CRUD-complete + tested
- ✅ All DQ rule endpoints CRUD-complete + tested
- ✅ DQ rule executor service working (not_null, unique, range, allowed_values, regex)
- ✅ All tests passing (>90% coverage)
- ✅ No performance regressions
- ✅ RBAC enforced (non-steward/non-owner gets 403)

---

## CRITICAL: RBAC Enforcement (NON-NEGOTIABLE)

**Every endpoint must enforce RBAC. No exceptions.**

```python
# Template for every view:
class ReferenceSetViewSet(viewsets.GenericViewSet, ...):
    permission_classes = [IsAuthenticated]  # 401 if not logged in
    
    def get_queryset(self):
        user_org_units = self.request.user.scoped_roles.values_list('org_unit_id', flat=True)
        # Filter: user only sees reference sets in their org units
        return ReferenceSet.objects.filter(domain__id__in=user_org_units) if user_org_units else ReferenceSet.objects.none()
    
    def create(self, request, *args, **kwargs):
        self.check_object_permissions(request, obj)  # 403 if not authorized
        # ... rest of create logic
    
    def update(self, request, *args, **kwargs):
        # Only steward of ReferenceSet can edit
        if request.user != obj.steward and not request.user.is_admin:
            raise PermissionDenied("Only steward can edit this reference set")
        # ... rest of update logic
```

**GOLDEN RULE:** If user is not allowed, return **403 Forbidden**, not 401 Unauthorized.

---

# DAY 1: MDM ReferenceSet Serializers & Views

**Duration:** 4 hours  
**Owner:** Code Copilot  
**Success Criteria:**
- ✅ ReferenceSetSerializer created + validates
- ✅ ReferenceSetViewSet CRUD endpoints working
- ✅ Unauthenticated users get 401
- ✅ Non-steward edit attempts get 403
- ✅ All 3 tests passing (create, list, update permission)

---

## Task 1.1: Create ReferenceSetSerializer

**File:** `backend/mdm/serializers.py`

**Requirements:**
```python
# Create or enhance existing file with:

from rest_framework import serializers
from .models import ReferenceSet, ReferenceValue
from accounts.models import User
from catalog.models import DataDomain

class ReferenceValueSerializer(serializers.ModelSerializer):
    """Nested serializer for reference values within a ReferenceSet"""
    class Meta:
        model = ReferenceValue
        fields = ['id', 'code', 'label', 'description', 'is_active', 'sort_order', 'valid_from', 'valid_to', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_code(self, value):
        # Validate code is alphanumeric_underscore
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError("Code must be alphanumeric with underscores only")
        return value


class ReferenceSetSerializer(serializers.ModelSerializer):
    """Serializer for ReferenceSet with nested values"""
    values = ReferenceValueSerializer(many=True, source='get_active_values', read_only=True)
    steward_name = serializers.CharField(source='steward.get_full_name', read_only=True)
    domain_name = serializers.CharField(source='domain.name', read_only=True)
    
    class Meta:
        model = ReferenceSet
        fields = [
            'id', 'name', 'slug', 'description', 'domain', 'domain_name',
            'steward', 'steward_name', 'is_active', 'version',
            'created_at', 'updated_at', 'values'
        ]
        read_only_fields = ['id', 'slug', 'version', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        # Ensure name is unique
        qs = ReferenceSet.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Reference set with this name already exists")
        return value
    
    def create(self, validated_data):
        # Auto-set steward to current user
        validated_data['steward'] = self.context['request'].user
        return super().create(validated_data)
```

**Tests:** `backend/mdm/tests/test_serializers.py`
```python
# Create file with:

from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from mdm.models import ReferenceSet
from mdm.serializers import ReferenceSetSerializer

User = get_user_model()

class ReferenceSetSerializerTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='pass123')
    
    def test_serialize_reference_set(self):
        """Test serializing ReferenceSet with nested values"""
        ref_set = ReferenceSet.objects.create(name='Status', slug='status', steward=self.user)
        serializer = ReferenceSetSerializer(ref_set)
        self.assertEqual(serializer.data['name'], 'Status')
        self.assertIn('values', serializer.data)
    
    def test_validate_unique_name(self):
        """Test unique constraint on name"""
        ReferenceSet.objects.create(name='Status', steward=self.user)
        serializer = ReferenceSetSerializer(
            data={'name': 'Status', 'steward': self.user.id},
            context={'request': self.request}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
    
    def test_auto_set_steward(self):
        """Test that steward defaults to current user on create"""
        request = self.factory.post('/mdm/reference-sets/')
        request.user = self.user
        serializer = ReferenceSetSerializer(
            data={'name': 'Department'},
            context={'request': request}
        )
        self.assertTrue(serializer.is_valid())
        obj = serializer.save()
        self.assertEqual(obj.steward, self.user)
```

---

## Task 1.2: Create ReferenceSetViewSet

**File:** `backend/mdm/views.py`

**Requirements:**
```python
# Create or enhance with:

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import ReferenceSet, ReferenceValue
from .serializers import ReferenceSetSerializer, ReferenceValueSerializer
from .permissions import IsReferenceSetSteward, IsAuthenticated as IsAuth

class ReferenceSetViewSet(viewsets.ModelViewSet):
    """
    CRUD for ReferenceSet (master data lookup lists)
    
    Endpoints:
    - GET    /mdm/reference-sets/           List all reference sets (filtered by user scope)
    - POST   /mdm/reference-sets/           Create new reference set (steward = current user)
    - GET    /mdm/reference-sets/{id}/      Detail
    - PUT    /mdm/reference-sets/{id}/      Update (only steward)
    - PATCH  /mdm/reference-sets/{id}/      Partial update (only steward)
    - DELETE /mdm/reference-sets/{id}/      Soft delete (is_active=False)
    """
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ReferenceSetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Filter by user's organization unit scopes"""
        user = self.request.user
        
        # If user is superuser/admin, see all
        if user.is_superuser or user.is_staff:
            return ReferenceSet.objects.all()
        
        # Otherwise, filter by org_unit through ScopedRole
        from accounts.models import ScopedRole
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        # If no org units assigned, return empty (user has no access)
        if not user_org_units:
            return ReferenceSet.objects.none()
        
        # Filter reference sets by domain's org_unit
        from catalog.models import DataDomain
        domains = DataDomain.objects.filter(id__in=user_org_units)
        return ReferenceSet.objects.filter(domain__in=domains, is_active=True)
    
    def perform_create(self, serializer):
        """Auto-assign steward to current user"""
        serializer.save(steward=self.request.user)
    
    def perform_update(self, serializer):
        """Check permission before update"""
        obj = self.get_object()
        if obj.steward != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Only steward can edit this reference set")
        serializer.save()
    
    def perform_destroy(self, instance):
        """Soft delete: set is_active=False"""
        instance.is_active = False
        instance.save()
    
    @action(detail=True, methods=['get'])
    def values(self, request, pk=None):
        """GET /mdm/reference-sets/{id}/values/ — list active values"""
        ref_set = self.get_object()
        values = ref_set.get_active_values()
        serializer = ReferenceValueSerializer(values, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_value(self, request, pk=None):
        """POST /mdm/reference-sets/{id}/add_value/ — add value to set"""
        ref_set = self.get_object()
        
        # Check permission
        if ref_set.steward != request.user and not request.user.is_staff:
            self.permission_denied(request, "Only steward can add values")
        
        serializer = ReferenceValueSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(reference_set=ref_set)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

---

## Task 1.3: Create Permissions Module

**File:** `backend/mdm/permissions.py` (NEW)

**Requirements:**
```python
from rest_framework import permissions

class IsReferenceSetSteward(permissions.BasePermission):
    """Only steward of ReferenceSet can edit it"""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to steward or admin
        return obj.steward == request.user or request.user.is_staff
```

---

## Task 1.4: Register Routes

**File:** `backend/mdm/urls.py`

**Requirements:**
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReferenceSetViewSet

router = DefaultRouter()
router.register(r'reference-sets', ReferenceSetViewSet, basename='reference-set')

urlpatterns = [
    path('', include(router.urls)),
]
```

**Verify in:** `backend/config/urls.py` (should already have `path(f'{api_prefix}/mdm/', include('mdm.urls'))`)

---

## Task 1.5: Day 1 Testing

**File:** `backend/mdm/tests/test_reference_sets.py`

**Create with 3 tests:**

```python
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from mdm.models import ReferenceSet

User = get_user_model()

class ReferenceSetViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user('user1', password='pass123')
        self.user2 = User.objects.create_user('user2', password='pass123')
    
    def test_unauthenticated_get_401(self):
        """Test: unauthenticated user gets 401"""
        response = self.client.get('/api/v1/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_list_reference_sets(self):
        """Test: authenticated user can list reference sets"""
        ReferenceSet.objects.create(name='Status', steward=self.user1)
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_sets_steward_to_current_user(self):
        """Test: creating reference set auto-assigns steward"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.post('/api/v1/mdm/reference-sets/', {
            'name': 'Department'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ref_set = ReferenceSet.objects.get(name='Department')
        self.assertEqual(ref_set.steward, self.user1)
    
    def test_non_steward_cannot_edit_403(self):
        """Test: non-steward gets 403 on update"""
        ref_set = ReferenceSet.objects.create(name='Status', steward=self.user1)
        
        self.client.force_authenticate(user=self.user2)
        response = self.client.put(f'/api/v1/mdm/reference-sets/{ref_set.id}/', {
            'name': 'Modified'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_steward_can_edit(self):
        """Test: steward can edit reference set"""
        ref_set = ReferenceSet.objects.create(name='Status', steward=self.user1)
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.put(f'/api/v1/mdm/reference-sets/{ref_set.id}/', {
            'name': 'Status Updated'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ref_set.refresh_from_db()
        self.assertEqual(ref_set.name, 'Status Updated')
```

---

## Execution Checklist for Day 1

- [ ] Read requirements above carefully
- [ ] Create `backend/mdm/serializers.py` with ReferenceSetSerializer + ReferenceValueSerializer
- [ ] Create `backend/mdm/views.py` with ReferenceSetViewSet
- [ ] Create `backend/mdm/permissions.py` with IsReferenceSetSteward
- [ ] Update `backend/mdm/urls.py` to register routes
- [ ] Create `backend/mdm/tests/test_serializers.py` (3 tests)
- [ ] Create `backend/mdm/tests/test_reference_sets.py` (5 tests)
- [ ] Run: `pytest backend/mdm/tests/ -v --cov=backend/mdm --cov-report=term-missing`
- [ ] Verify: All 8 tests passing, coverage >90%
- [ ] Run: `python manage.py migrate` (should show no issues)
- [ ] Test manually: curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/v1/mdm/reference-sets/
- [ ] Commit: `git commit -m "PHASE1-D1: MDM ReferenceSet Serializers, Views, RBAC Permissions"`
- [ ] Report to Master: Create TASK-RESULT_PHASE1_WEEK1_DAY1.md with results

---

# DAY 2: MDM OrgUnit Serializers, Views & Tests

**Duration:** 6 hours  
**Owner:** Code Copilot  
**Success Criteria:**
- ✅ OrgUnitSerializer created (tree structure, full_path, ancestors, descendants)
- ✅ OrgUnitViewSet CRUD + tree endpoints working
- ✅ Hierarchy validation (no circular refs, can't delete parent with active children)
- ✅ All 8 tests passing (list, create, update, delete, tree, permission)
- ✅ Performance: list 1000 org units in <1 second

---

## Task 2.1: Create OrgUnitSerializer

**File:** `backend/mdm/serializers.py`

**Enhance with:**

```python
class OrgUnitSerializer(serializers.ModelSerializer):
    """Serializer for organizational hierarchy"""
    
    children = serializers.SerializerMethodField(read_only=True)
    full_path = serializers.CharField(read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = OrgUnit
        fields = [
            'id', 'name', 'slug', 'code', 'org_type', 'description',
            'parent', 'parent_name', 'is_active',
            'children', 'full_path',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'full_path', 'created_at', 'updated_at']
    
    def get_children(self, obj):
        """Return immediate children of this org unit"""
        children = obj.children.filter(is_active=True)
        return OrgUnitSerializer(children, many=True).data
    
    def validate_parent(self, value):
        """Prevent circular references"""
        if value and value.id == self.instance.id if self.instance else False:
            raise serializers.ValidationError("An org unit cannot be its own parent")
        return value
    
    def validate_name(self, value):
        """Validate name is unique under parent"""
        parent = self.initial_data.get('parent')
        qs = OrgUnit.objects.filter(name=value, parent_id=parent)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Org unit with this name already exists under parent")
        return value
```

---

## Task 2.2: Create OrgUnitViewSet

**File:** `backend/mdm/views.py`

**Enhance with:**

```python
from .models import OrgUnit

class OrgUnitViewSet(viewsets.ModelViewSet):
    """
    CRUD for OrgUnit (organizational hierarchy)
    
    Endpoints:
    - GET    /mdm/orgunits/                 List all org units (tree structure)
    - POST   /mdm/orgunits/                 Create org unit
    - GET    /mdm/orgunits/{id}/            Detail
    - PUT    /mdm/orgunits/{id}/            Update
    - DELETE /mdm/orgunits/{id}/            Soft delete (validate no active children)
    - GET    /mdm/orgunits/{id}/descendants/  List all descendants + self
    - GET    /mdm/orgunits/{id}/ancestors/    List all ancestors
    - GET    /mdm/orgunits/by-path/{path}/   Resolve full path to org unit
    """
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = OrgUnitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Get all active org units (admin only, but users filter by scope)"""
        user = self.request.user
        
        # If admin, see all
        if user.is_superuser or user.is_staff:
            return OrgUnit.objects.filter(is_active=True)
        
        # Otherwise, filter to user's accessible org units via ScopedRole
        from accounts.models import ScopedRole
        accessible_org_units = ScopedRole.objects.filter(
            user=user, is_active=True, org_unit__isnull=False
        ).values_list('org_unit_id', flat=True).distinct()
        
        if not accessible_org_units:
            return OrgUnit.objects.none()
        
        return OrgUnit.objects.filter(id__in=accessible_org_units, is_active=True)
    
    def perform_destroy(self, instance):
        """Soft delete with validation"""
        # Check if has active children
        if instance.children.filter(is_active=True).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Cannot delete org unit with active children")
        instance.is_active = False
        instance.save()
    
    @action(detail=True, methods=['get'])
    def descendants(self, request, pk=None):
        """GET /mdm/orgunits/{id}/descendants/ — all descendants + self"""
        org_unit = self.get_object()
        descendant_ids = org_unit.get_descendant_ids(include_self=True)
        descendants = OrgUnit.objects.filter(id__in=descendant_ids)
        serializer = self.get_serializer(descendants, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def ancestors(self, request, pk=None):
        """GET /mdm/orgunits/{id}/ancestors/ — all ancestors (root to parent)"""
        org_unit = self.get_object()
        ancestors = org_unit.get_ancestors()
        serializer = self.get_serializer(ancestors, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_path(self, request):
        """GET /mdm/orgunits/by-path/?path=Root%2FDepartment%2FTeam"""
        path = request.query_params.get('path', '')
        if not path:
            return Response({'error': 'path parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        parts = path.split('/')
        current = None
        for part in parts:
            try:
                current = OrgUnit.objects.get(name=part, parent=current, is_active=True)
            except OrgUnit.DoesNotExist:
                return Response({'error': f'Org unit not found: {part}'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(current)
        return Response(serializer.data)
```

---

## Task 2.3: Day 2 Testing

**File:** `backend/mdm/tests/test_orgunits.py`

**Create with 8 tests:**

```python
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from mdm.models import OrgUnit

User = get_user_model()

class OrgUnitViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user('admin', password='pass123', is_staff=True)
        self.user = User.objects.create_user('user1', password='pass123')
        
        # Create hierarchy: University > College > Department
        self.university = OrgUnit.objects.create(
            name='AASTMT', org_type='university', code='AAST'
        )
        self.college = OrgUnit.objects.create(
            name='Engineering', org_type='college', code='ENG', parent=self.university
        )
        self.department = OrgUnit.objects.create(
            name='Civil', org_type='department', code='CIVIL', parent=self.college
        )
    
    def test_list_orgunits_tree_structure(self):
        """Test: list returns tree structure with children nested"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/mdm/orgunits/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        # Verify university has college as child
        self.assertTrue(any(u['id'] == self.university.id for u in data))
    
    def test_create_child_orgunit(self):
        """Test: create org unit with parent"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/mdm/orgunits/', {
            'name': 'Structures',
            'org_type': 'team',
            'code': 'STRUCT',
            'parent': self.department.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        team = OrgUnit.objects.get(name='Structures')
        self.assertEqual(team.parent, self.department)
    
    def test_descendants_includes_all_levels(self):
        """Test: descendants endpoint returns all descendants + self"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/mdm/orgunits/{self.university.id}/descendants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [d['id'] for d in response.data]
        self.assertIn(self.university.id, ids)
        self.assertIn(self.college.id, ids)
        self.assertIn(self.department.id, ids)
    
    def test_ancestors_returns_path_to_root(self):
        """Test: ancestors endpoint returns all ancestors"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/mdm/orgunits/{self.department.id}/ancestors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [a['id'] for a in response.data]
        self.assertIn(self.university.id, ids)
        self.assertIn(self.college.id, ids)
        self.assertNotIn(self.department.id, ids)  # Department is not its own ancestor
    
    def test_by_path_resolves_hierarchy(self):
        """Test: by_path endpoint resolves full path"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/mdm/orgunits/by-path/?path=AASTMT%2FEngineering%2FCivil')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.department.id)
    
    def test_delete_parent_with_children_fails(self):
        """Test: cannot delete org unit with active children"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f'/api/v1/mdm/orgunits/{self.college.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_delete_leaf_succeeds(self):
        """Test: can delete org unit with no children"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f'/api/v1/mdm/orgunits/{self.department.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.department.refresh_from_db()
        self.assertFalse(self.department.is_active)
    
    def test_circular_reference_validation(self):
        """Test: cannot create circular parent-child relationship"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.put(f'/api/v1/mdm/orgunits/{self.university.id}/', {
            'name': 'AASTMT',
            'parent': self.university.id  # Self-reference
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
```

---

## Execution Checklist for Day 2

- [ ] Enhance `backend/mdm/serializers.py` with OrgUnitSerializer
- [ ] Enhance `backend/mdm/views.py` with OrgUnitViewSet
- [ ] Update `backend/mdm/urls.py` to register OrgUnit routes
- [ ] Create `backend/mdm/tests/test_orgunits.py` with 8 tests
- [ ] Run: `pytest backend/mdm/tests/test_orgunits.py -v`
- [ ] Verify: All 8 tests passing
- [ ] Performance test: `python manage.py shell`
  ```python
  # Create 1000 org units
  import time
  from mdm.models import OrgUnit
  start = time.time()
  for i in range(1000):
      OrgUnit.objects.create(name=f'Unit{i}')
  # Time should be <5 seconds
  print(f"Created 1000 in {time.time()-start:.2f}s")
  ```
- [ ] Verify: List endpoint returns in <1 second
- [ ] Commit: `git commit -m "PHASE1-D2: MDM OrgUnit CRUD, Hierarchy, Tests"`
- [ ] Report to Master: Update TASK-RESULT_PHASE1_WEEK1_DAY1.md, create DAY2

---

# SUMMARY FOR WORKER

**What to do:**
1. Read Day 1 requirements above
2. Create/modify files in exact order specified
3. Run tests after each task
4. If test fails: debug immediately, don't move forward
5. After Day 1 complete: commit + report results

**What to report in TASK-RESULT file:**
- ✅ Completed tasks (with file paths)
- ❌ Failed tasks (with error message + stack trace)
- 📊 Test coverage % (pytest --cov output)
- ⏱️ Time spent (was it 4 hours or more?)
- 🎯 Blockers (anything preventing next day)
- 💭 Questions for Master (any ambiguity?)

**Next:** Master reviews results → Approves Day 2 or asks for rework

---

**END OF TASK_PHASE1_WEEK1**

**Master:** Submit TASK-RESULT-PHASE1-WEEK1-DAY1.md when Day 1 complete.

