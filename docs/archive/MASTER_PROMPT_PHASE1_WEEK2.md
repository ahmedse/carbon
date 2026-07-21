# MASTER PROMPT: PHASE 1 WEEK 2 — LINEAGE, GOVERNANCE & FINAL INTEGRATION
**To:** Code Worker (Claude Models)  
**From:** Master (Zoo Architect)  
**Date:** 2026-07-20  
**Deadline:** 2026-07-27 (end of business day)  
**Allocated Time:** 50 hours

---

## 🎯 YOUR MISSION

Complete **Phase 1 Week 2** to finalize the Data Trust Platform's core foundation:

**Week 2 Objectives:**
- ✅ **Days 1-2:** Lineage APIs (DataLineage, FieldLineage models + viewsets with RBAC)
- ✅ **Days 3-4:** Governance Policies API (access control, audit enforcement)
- ✅ **Day 5:** AssetProfile Stewardship + Final Integration Tests

**Success Definition:** 50 hours delivered, all 50+ tests passing, RBAC enforced on every endpoint, zero data leakage, >95% test coverage.

---

## 📋 CRITICAL: NON-NEGOTIABLE RULES (INHERITED FROM WEEK 1)

### Rule 1: RBAC is ABSOLUTE
✅ **Every list endpoint filters by ScopedRole org_units**
```python
def get_queryset(self):
    user = self.request.user
    if user.is_superuser or user.is_staff:
        return Model.objects.filter(is_active=True)
    
    user_org_units = ScopedRole.objects.filter(
        user=user, is_active=True
    ).values_list('org_unit_id', flat=True).distinct()
    
    if not user_org_units:
        return Model.objects.none()  # NO DATA LEAKAGE
    
    return Model.objects.filter(data_path__org_unit_id__in=user_org_units, is_active=True)
```

### Rule 2: 403 for Permission Denial (Not 401)
✅ **Use PermissionDenied for authorization failures**
```python
from rest_framework.exceptions import PermissionDenied
if not user_can_edit:
    raise PermissionDenied("Only steward can edit")  # 403, not 401
```

### Rule 3: Soft Deletes Only
✅ **No hard deletes — set is_active=False**
```python
def perform_destroy(self, instance):
    instance.is_active = False
    instance.save()
```

### Rule 4: Auto-Assign Creator/Steward
✅ **created_by or steward auto-assigned on create**
```python
def perform_create(self, serializer):
    serializer.save(created_by=self.request.user)
```

### Rule 5: ScopedRole Integration
✅ **Integrate throughout — no exceptions**

---

## 📅 WEEK 2 DETAILED BREAKDOWN

---

## DAY 1-2: LINEAGE APIs (14 hours)

### Context: Why Lineage Matters
Data lineage tracks data flow through pipelines:
- **DataLineage:** Source table → Transformation → Target table
- **FieldLineage:** Source field → Column transformation → Target field
- Critical for compliance, debugging, impact analysis

### Task 1.1: Create Lineage Models (2 hours)

**File:** `backend/lineage/models.py` (NEW)

```python
# backend/lineage/models.py
"""Data lineage models tracking data flow through pipelines."""
from django.db import models
from django.contrib.auth import get_user_model
from dataschema.models import DataTable, DataField

User = get_user_model()


class DataLineage(models.Model):
    """Track data flow from source to target tables."""
    
    # Source
    source_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='lineage_sources'
    )
    source_module = models.CharField(
        max_length=255, help_text="Name of source system/module"
    )
    
    # Target
    target_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='lineage_targets'
    )
    
    # Transformation
    transform_type = models.CharField(
        max_length=50, choices=[
            ('copy', 'Direct Copy'),
            ('map', 'Field Mapping'),
            ('aggregate', 'Aggregation'),
            ('join', 'Join'),
            ('filter', 'Filter'),
            ('custom', 'Custom Transformation'),
        ], default='map'
    )
    transform_logic = models.JSONField(
        default=dict, blank=True,
        help_text="SQL/logic describing the transformation"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_lineages'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)  # Soft delete
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['source_table', 'target_table']]
    
    def __str__(self):
        return f"{self.source_table} → {self.target_table} ({self.transform_type})"


class FieldLineage(models.Model):
    """Track data flow from source to target fields."""
    
    # Reference parent lineage
    lineage = models.ForeignKey(
        DataLineage, on_delete=models.CASCADE, related_name='field_lineages'
    )
    
    # Source field
    source_field = models.ForeignKey(
        DataField, on_delete=models.CASCADE, related_name='lineage_sources'
    )
    
    # Target field
    target_field = models.ForeignKey(
        DataField, on_delete=models.CASCADE, related_name='lineage_targets'
    )
    
    # Transformation (e.g., "UPPER(source)", "CASE WHEN ...", etc.)
    transform_expr = models.CharField(
        max_length=500, blank=True,
        help_text="SQL expression for field transformation"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['lineage', 'source_field', 'target_field']]
    
    def __str__(self):
        return f"{self.source_field} → {self.target_field}"


class LineageImpactAnalysis(models.Model):
    """Cache results of impact analysis (what breaks if source changes)."""
    
    source_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='impact_analyses'
    )
    
    # Cached impact: list of affected downstream tables
    affected_tables = models.JSONField(
        default=list, help_text="List of table IDs that depend on this source"
    )
    
    # Metadata
    analyzed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Lineage Impact Analyses"
    
    def __str__(self):
        return f"Impact of {self.source_table}"
```

**Create migration:**
```bash
python manage.py makemigrations lineage
python manage.py migrate lineage
```

### Task 1.2: Create Lineage Serializers (2 hours)

**File:** `backend/lineage/serializers.py` (NEW)

```python
# backend/lineage/serializers.py
from rest_framework import serializers
from .models import DataLineage, FieldLineage, LineageImpactAnalysis
from dataschema.models import DataTable, DataField


class FieldLineageSerializer(serializers.ModelSerializer):
    """Serializer for field-level lineage."""
    source_field_name = serializers.CharField(source='source_field.name', read_only=True)
    target_field_name = serializers.CharField(source='target_field.name', read_only=True)
    
    class Meta:
        model = FieldLineage
        fields = [
            'id', 'lineage', 'source_field', 'source_field_name',
            'target_field', 'target_field_name', 'transform_expr',
            'created_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_at']


class DataLineageSerializer(serializers.ModelSerializer):
    """Serializer for table-level lineage."""
    source_table_name = serializers.CharField(source='source_table.name', read_only=True)
    target_table_name = serializers.CharField(source='target_table.name', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )
    field_lineages = FieldLineageSerializer(many=True, read_only=True)
    
    class Meta:
        model = DataLineage
        fields = [
            'id', 'source_table', 'source_table_name', 'source_module',
            'target_table', 'target_table_name', 'transform_type',
            'transform_logic', 'created_by', 'created_by_name',
            'field_lineages', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def validate_transform_type(self, value):
        """Validate transform type."""
        ALLOWED = ['copy', 'map', 'aggregate', 'join', 'filter', 'custom']
        if value not in ALLOWED:
            raise serializers.ValidationError(f"transform_type must be in {ALLOWED}")
        return value
    
    def validate(self, data):
        """Ensure source and target are different."""
        if data.get('source_table') == data.get('target_table'):
            raise serializers.ValidationError("Source and target tables must be different")
        return data


class LineageImpactAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for impact analysis results."""
    source_table_name = serializers.CharField(source='source_table.name', read_only=True)
    affected_table_names = serializers.SerializerMethodField()
    
    class Meta:
        model = LineageImpactAnalysis
        fields = ['id', 'source_table', 'source_table_name', 'affected_tables', 'affected_table_names', 'analyzed_at']
        read_only_fields = ['id', 'analyzed_at']
    
    def get_affected_table_names(self, obj):
        """Return names of affected tables."""
        tables = DataTable.objects.filter(id__in=obj.affected_tables)
        return [t.name for t in tables]
```

### Task 1.3: Create Lineage ViewSets (4 hours)

**File:** `backend/lineage/views.py` (NEW)

```python
# backend/lineage/views.py
"""ViewSets for data lineage with RBAC enforcement."""
from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q

from .models import DataLineage, FieldLineage, LineageImpactAnalysis
from .serializers import DataLineageSerializer, FieldLineageSerializer, LineageImpactAnalysisSerializer
from accounts.models import ScopedRole
from dataschema.models import DataTable


class DataLineageViewSet(viewsets.ModelViewSet):
    """CRUD for data lineage with RBAC enforcement (Rule 1: ABSOLUTE)."""
    serializer_class = DataLineageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['source_table__name', 'target_table__name', 'source_module']
    ordering_fields = ['created_at', 'transform_type']
    
    def get_queryset(self):
        """Rule 1: Filter by user's org_unit via ScopedRole."""
        user = self.request.user
        
        # Superusers see all
        if user.is_superuser or user.is_staff:
            return DataLineage.objects.filter(is_active=True)
        
        # Get user's org_units
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        # NO DATA LEAKAGE
        if not user_org_units:
            return DataLineage.objects.none()
        
        # Filter by both source and target tables' org_units
        qs = DataLineage.objects.filter(is_active=True)
        qs = qs.filter(
            Q(source_table__module__org_unit_id__in=user_org_units) |
            Q(target_table__module__org_unit_id__in=user_org_units)
        )
        
        return qs.distinct()
    
    def perform_create(self, serializer):
        """Auto-assign created_by to current user."""
        serializer.save(created_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete."""
        instance.is_active = False
        instance.save()
    
    @action(detail=True, methods=['get'])
    def impact(self, request, pk=None):
        """GET /lineages/{id}/impact/ - What breaks if this source changes?"""
        lineage = self.get_object()
        
        # Recursively find all downstream tables
        def find_downstream(table_id, visited=None):
            if visited is None:
                visited = set()
            if table_id in visited:
                return visited
            visited.add(table_id)
            
            downstream = DataLineage.objects.filter(
                source_table_id=table_id, is_active=True
            ).values_list('target_table_id', flat=True)
            
            for target_id in downstream:
                find_downstream(target_id, visited)
            
            return visited
        
        affected_ids = find_downstream(lineage.source_table_id)
        affected_ids.discard(lineage.source_table_id)
        
        return Response({
            'source_table': lineage.source_table_id,
            'affected_tables': list(affected_ids),
            'count': len(affected_ids)
        })
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """POST /lineages/bulk_create/ - Create multiple lineages."""
        lineages_data = request.data.get('lineages', [])
        
        if not lineages_data:
            return Response(
                {'error': 'lineages list required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created = []
        for data in lineages_data:
            serializer = DataLineageSerializer(data=data)
            if serializer.is_valid():
                serializer.save(created_by=request.user)
                created.append(serializer.data)
        
        return Response({
            'created': len(created),
            'lineages': created
        }, status=status.HTTP_201_CREATED)


class FieldLineageViewSet(viewsets.ModelViewSet):
    """Read-only access to field-level lineage."""
    serializer_class = FieldLineageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        """Filter by lineage's tables' org_units."""
        user = self.request.user
        
        if user.is_superuser or user.is_staff:
            return FieldLineage.objects.filter(is_active=True)
        
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        if not user_org_units:
            return FieldLineage.objects.none()
        
        # Filter by parent lineage's tables
        qs = FieldLineage.objects.filter(is_active=True)
        qs = qs.filter(
            Q(lineage__source_table__module__org_unit_id__in=user_org_units) |
            Q(lineage__target_table__module__org_unit_id__in=user_org_units)
        )
        
        return qs.distinct()
    
    def list(self, request, *args, **kwargs):
        """Optional filtering by lineage_id."""
        lineage_id = request.query_params.get('lineage_id')
        if lineage_id:
            self.queryset = self.get_queryset().filter(lineage_id=lineage_id)
        return super().list(request, *args, **kwargs)
```

### Task 1.4: Create Lineage Tests (4 hours)

**File:** `backend/lineage/tests/test_lineage.py` (NEW)

```python
# backend/lineage/tests/test_lineage.py
"""Tests for data lineage API."""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from dataschema.models import DataTable, DataField, DataModule
from mdm.models import OrgUnit
from lineage.models import DataLineage, FieldLineage
from accounts.models import ScopedRole
from django.contrib.auth.models import Group

User = get_user_model()


class DataLineageCRUDTestCase(APITestCase):
    """Test CRUD operations on lineages."""
    
    def setUp(self):
        self.client_api = self.client
        self.admin = User.objects.create_user('admin', password='pass', is_staff=True)
        self.user_org1 = User.objects.create_user('user1', password='pass')
        
        # Org units
        self.org1 = OrgUnit.objects.create(name='Org1', code='O1')
        self.org2 = OrgUnit.objects.create(name='Org2', code='O2')
        
        # Modules
        self.mod1 = DataModule.objects.create(name='Mod1', slug='mod1', org_unit=self.org1)
        self.mod2 = DataModule.objects.create(name='Mod2', slug='mod2', org_unit=self.org1)
        
        # Tables
        self.table1 = DataTable.objects.create(name='T1', slug='t1', module=self.mod1)
        self.table2 = DataTable.objects.create(name='T2', slug='t2', module=self.mod2)
        
        # Fields
        self.field1 = DataField.objects.create(name='F1', data_type='text', data_table=self.table1)
        self.field2 = DataField.objects.create(name='F2', data_type='text', data_table=self.table2)
        
        # Assign org unit to user
        group = Group.objects.create(name='admins_group')
        ScopedRole.objects.create(
            user=self.user_org1, group=group, org_unit=self.org1, is_active=True
        )
    
    def test_create_lineage(self):
        """Test: authenticated user can create lineage."""
        self.client_api.force_authenticate(self.admin)
        payload = {
            'source_table': self.table1.id,
            'target_table': self.table2.id,
            'source_module': 'ETL Pipeline',
            'transform_type': 'map'
        }
        response = self.client_api.post('/lineage/lineages/', payload)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['transform_type'], 'map')
        self.assertTrue(DataLineage.objects.filter(id=response.data['id']).exists())
    
    def test_create_lineage_self_reference_fails(self):
        """Test: cannot create lineage where source = target."""
        self.client_api.force_authenticate(self.admin)
        payload = {
            'source_table': self.table1.id,
            'target_table': self.table1.id,
            'source_module': 'Test',
            'transform_type': 'map'
        }
        response = self.client_api.post('/lineage/lineages/', payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_lineages_rbac(self):
        """Test: user only sees lineages in their org units."""
        lineage = DataLineage.objects.create(
            source_table=self.table1, target_table=self.table2,
            transform_type='map', created_by=self.admin
        )
        
        self.client_api.force_authenticate(self.user_org1)
        response = self.client_api.get('/lineage/lineages/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lineage_ids = [l['id'] for l in response.data]
        self.assertIn(lineage.id, lineage_ids)
    
    def test_lineage_impact_analysis(self):
        """Test: /lineages/{id}/impact/ shows downstream tables."""
        # Create chain: T1 -> T2 -> T3
        org3 = OrgUnit.objects.create(name='Org3', code='O3')
        mod3 = DataModule.objects.create(name='Mod3', slug='mod3', org_unit=org3)
        table3 = DataTable.objects.create(name='T3', slug='t3', module=mod3)
        
        lineage1 = DataLineage.objects.create(
            source_table=self.table1, target_table=self.table2,
            transform_type='map', created_by=self.admin
        )
        lineage2 = DataLineage.objects.create(
            source_table=self.table2, target_table=table3,
            transform_type='map', created_by=self.admin
        )
        
        self.client_api.force_authenticate(self.admin)
        response = self.client_api.get(f'/lineage/lineages/{lineage1.id}/impact/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(table3.id, response.data['affected_tables'])
```

### Task 1.5: Register Lineage URLs (1 hour)

**File:** `backend/lineage/urls.py` (NEW)

```python
from rest_framework.routers import DefaultRouter
from .views import DataLineageViewSet, FieldLineageViewSet

router = DefaultRouter()
router.register(r'lineages', DataLineageViewSet, basename='lineage')
router.register(r'field-lineages', FieldLineageViewSet, basename='field-lineage')

urlpatterns = router.urls
```

**Add to main config:**
```python
# backend/config/urls.py
urlpatterns += [
    path('api/v1/lineage/', include('lineage.urls')),
]
```

---

## DAY 3-4: GOVERNANCE POLICIES API (14 hours)

### Context: Why Governance Policies Matter
Policies define access control rules:
- **Who** can access **what** under **which conditions**
- Examples: "Only managers can view sensitive emissions data", "Finance team can only edit approved periods"

### Task 2.1: Create Governance Models (2 hours)

**File:** `backend/governance/models.py` (NEW)

```python
# backend/governance/models.py
"""Governance policy models for access control."""
from django.db import models
from django.contrib.auth import get_user_model
from catalog.models import AssetProfile
from accounts.models import ScopedRole

User = get_user_model()


class GovernancePolicy(models.Model):
    """Define access control policies for assets."""
    
    # Policy basics
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    
    # Asset covered
    asset = models.ForeignKey(
        AssetProfile, on_delete=models.CASCADE, related_name='governance_policies'
    )
    
    # Access control
    EFFECT_CHOICES = [
        ('allow', 'Allow'),
        ('deny', 'Deny'),
    ]
    effect = models.CharField(
        max_length=10, choices=EFFECT_CHOICES, default='allow',
        help_text="Allow or deny the action"
    )
    
    # Who (principals)
    ACTION_CHOICES = [
        ('read', 'Read'),
        ('write', 'Write'),
        ('delete', 'Delete'),
        ('admin', 'Admin'),
    ]
    actions = models.JSONField(
        default=list, help_text="List of allowed actions: read, write, delete, admin"
    )
    
    # Conditions (optional)
    CONDITION_TYPE_CHOICES = [
        ('org_unit', 'Org Unit'),
        ('time', 'Time-Based'),
        ('role', 'Role-Based'),
        ('custom', 'Custom Expression'),
    ]
    condition_type = models.CharField(
        max_length=20, choices=CONDITION_TYPE_CHOICES, blank=True
    )
    condition_value = models.JSONField(
        default=dict, blank=True, help_text="Condition parameters"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_policies'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.effect})"


class PolicyAuditLog(models.Model):
    """Track policy enforcement decisions for compliance."""
    
    # Reference policy
    policy = models.ForeignKey(
        GovernancePolicy, on_delete=models.CASCADE, related_name='audit_logs'
    )
    
    # Who accessed
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # What happened
    ACTION_CHOICES = [
        ('allow', 'Access Allowed'),
        ('deny', 'Access Denied'),
        ('audit', 'Access Logged'),
    ]
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    # Metadata
    asset_id = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"
```

**Create migration:**
```bash
python manage.py makemigrations governance
python manage.py migrate governance
```

### Task 2.2: Create Governance Serializers (2 hours)

**File:** `backend/governance/serializers.py` (NEW)

```python
# backend/governance/serializers.py
from rest_framework import serializers
from .models import GovernancePolicy, PolicyAuditLog
from catalog.models import AssetProfile


class GovernancePolicySerializer(serializers.ModelSerializer):
    """Serializer for governance policies."""
    asset_name = serializers.CharField(source='asset.asset_name', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )
    
    class Meta:
        model = GovernancePolicy
        fields = [
            'id', 'name', 'slug', 'description', 'asset', 'asset_name',
            'effect', 'actions', 'condition_type', 'condition_value',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'slug', 'created_by', 'created_at', 'updated_at']
    
    def validate_effect(self, value):
        """Validate effect."""
        if value not in ['allow', 'deny']:
            raise serializers.ValidationError("effect must be 'allow' or 'deny'")
        return value
    
    def validate_actions(self, value):
        """Validate actions."""
        ALLOWED = ['read', 'write', 'delete', 'admin']
        for action in value:
            if action not in ALLOWED:
                raise serializers.ValidationError(f"Invalid action: {action}")
        return value


class PolicyAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    policy_name = serializers.CharField(source='policy.name', read_only=True)
    
    class Meta:
        model = PolicyAuditLog
        fields = [
            'id', 'policy', 'policy_name', 'user', 'user_name',
            'action', 'asset_id', 'timestamp', 'details'
        ]
        read_only_fields = ['id', 'timestamp']
```

### Task 2.3: Create Governance ViewSets (4 hours)

**File:** `backend/governance/views.py` (NEW)

```python
# backend/governance/views.py
"""ViewSets for governance policies with RBAC."""
from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q

from .models import GovernancePolicy, PolicyAuditLog
from .serializers import GovernancePolicySerializer, PolicyAuditLogSerializer
from accounts.models import ScopedRole
from catalog.models import AssetProfile


class GovernancePolicyViewSet(viewsets.ModelViewSet):
    """CRUD for governance policies with RBAC (Rule 1: ABSOLUTE)."""
    serializer_class = GovernancePolicySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name']
    
    def get_queryset(self):
        """Rule 1: Filter by user's org_unit via asset's org_unit."""
        user = self.request.user
        
        if user.is_superuser or user.is_staff:
            return GovernancePolicy.objects.filter(is_active=True)
        
        # Get user's org_units
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        # NO DATA LEAKAGE
        if not user_org_units:
            return GovernancePolicy.objects.none()
        
        # Filter by asset's org_unit (assets belong to org units)
        qs = GovernancePolicy.objects.filter(is_active=True)
        # Assume AssetProfile has org_unit FK; adjust path if different
        qs = qs.filter(asset__data_table__module__org_unit_id__in=user_org_units)
        
        return qs.distinct()
    
    def perform_create(self, serializer):
        """Auto-assign created_by."""
        from django.utils.text import slugify
        name = serializer.validated_data.get('name', '')
        serializer.save(created_by=self.request.user, slug=slugify(name))
    
    def perform_destroy(self, instance):
        """Soft delete."""
        instance.is_active = False
        instance.save()
    
    @action(detail=True, methods=['post'])
    def enforce(self, request, pk=None):
        """POST /policies/{id}/enforce/ - Check if user has access."""
        policy = self.get_object()
        user = request.query_params.get('user_id') or request.user.id
        asset_id = request.data.get('asset_id')
        action = request.data.get('action')
        
        # Check conditions
        can_access = self._check_policy(policy, user, action)
        
        # Log access attempt
        PolicyAuditLog.objects.create(
            policy=policy, user_id=user,
            action='allow' if can_access else 'deny',
            asset_id=asset_id,
            details={'action': action}
        )
        
        return Response({
            'can_access': can_access,
            'policy_id': policy.id,
            'reason': 'Policy evaluation complete'
        })
    
    def _check_policy(self, policy, user_id, action):
        """Check if user satisfies policy conditions."""
        # Simple logic; extend with complex condition evaluation
        if policy.effect == 'deny':
            return False
        
        if action not in policy.actions:
            return False
        
        # Check time-based conditions
        if policy.condition_type == 'time':
            # TODO: Implement time-based access
            pass
        
        # Check role-based conditions
        if policy.condition_type == 'role':
            # TODO: Check user's roles
            pass
        
        return True


class PolicyAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to policy audit logs."""
    serializer_class = PolicyAuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'action']
    
    def get_queryset(self):
        """Filter by policies user can see."""
        user = self.request.user
        
        if user.is_superuser or user.is_staff:
            return PolicyAuditLog.objects.all()
        
        # Get user's org_units
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        if not user_org_units:
            return PolicyAuditLog.objects.none()
        
        # Filter by policy's asset's org_unit
        qs = PolicyAuditLog.objects.filter(
            policy__asset__data_table__module__org_unit_id__in=user_org_units
        )
        
        return qs.distinct()
    
    def list(self, request, *args, **kwargs):
        """Optional filtering by policy_id."""
        policy_id = request.query_params.get('policy_id')
        if policy_id:
            self.queryset = self.get_queryset().filter(policy_id=policy_id)
        return super().list(request, *args, **kwargs)
```

### Task 2.4: Governance Tests & Registration (6 hours)

**File:** `backend/governance/tests/test_governance.py` (NEW)

```python
# Similar structure to lineage tests
# Focus on: CRUD, RBAC, policy enforcement, audit logging
```

**File:** `backend/governance/urls.py` (NEW)

```python
from rest_framework.routers import DefaultRouter
from .views import GovernancePolicyViewSet, PolicyAuditLogViewSet

router = DefaultRouter()
router.register(r'policies', GovernancePolicyViewSet, basename='policy')
router.register(r'audit-logs', PolicyAuditLogViewSet, basename='audit-log')

urlpatterns = router.urls
```

---

## DAY 5: ASSETPROFILE STEWARDSHIP & FINAL INTEGRATION (12 hours)

### Task 3.1: Enhance AssetProfile Model (2 hours)

**File:** `backend/catalog/models.py` (modify existing)

```python
# Add to AssetProfile model
steward = models.ForeignKey(
    User, null=True, blank=True, on_delete=models.SET_NULL,
    related_name='stewarded_assets',
    help_text="User responsible for this asset"
)

owners = models.ManyToManyField(
    User, blank=True, related_name='owned_assets',
    help_text="Team members with edit access"
)
```

**Create migration:**
```bash
python manage.py makemigrations catalog
python manage.py migrate catalog
```

### Task 3.2: Integration Tests (8 hours)

**File:** `backend/tests/test_integration_week2.py` (NEW)

```python
# Comprehensive integration tests covering:
# - Lineage → Governance → AssetProfile flow
# - Cross-org-unit isolation throughout
# - Soft delete cascade across all models
# - RBAC enforcement on all APIs
# - Audit logging
```

### Task 3.3: Final Verification & Reporting (2 hours)

**Create:** `TASK-RESULT-PHASE1-WEEK2-FINAL.md`

---

## 📊 SUCCESS CRITERIA FOR WEEK 2

- [ ] All Lineage APIs tested + RBAC verified
- [ ] All Governance APIs tested + RBAC verified
- [ ] AssetProfile Stewardship enhanced
- [ ] >95% test coverage (MDM + DQ + Lineage + Governance)
- [ ] All 50+ tests passing
- [ ] Zero data leakage detected
- [ ] TASK-RESULT-PHASE1-WEEK2-FINAL.md created
- [ ] Git history clean (5 commits minimum)

---

## 🚀 READY FOR PHASE 2: FRONTEND CATALOG STUDIO

Once Week 2 is complete, Phase 2 begins:
- Catalog Studio UI (React)
- Lineage Visualizer
- Governance Audit Dashboard

