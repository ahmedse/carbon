# mdm/views.py
from django.utils.text import slugify
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from dataschema.models import DataField
from .models import ReferenceSet, ReferenceValue, OrgUnit
from .serializers import ReferenceSetSerializer, ReferenceValueSerializer, OrgUnitSerializer
from accounts.permissions import ReadAnyWriteGlobalAdmin
from accounts.models import ScopedRole


class ReferenceSetViewSet(viewsets.ModelViewSet):
    """
    CRUD for ReferenceSet (master data lookup lists).
    RBAC: Filters by user's organization unit scopes via ScopedRole.
    Only steward can edit.
    
    Endpoints:
    - GET    /mdm/reference-sets/           List all reference sets (filtered by user scope)
    - POST   /mdm/reference-sets/           Create new reference set (steward = current user)
    - GET    /mdm/reference-sets/{id}/      Detail
    - PUT    /mdm/reference-sets/{id}/      Update (only steward)
    - PATCH  /mdm/reference-sets/{id}/      Partial update (only steward)
    - DELETE /mdm/reference-sets/{id}/      Soft delete (is_active=False)
    """
    serializer_class = ReferenceSetSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter by user's organization unit scopes via ScopedRole.
        
        RBAC Logic:
        - Superusers/staff see all reference sets
        - Regular users see only reference sets in their assigned org_units
        - If user has no org_unit assignments, return empty (no access)
        """
        user = self.request.user
        
        # Superusers and staff see everything
        if user.is_superuser or user.is_staff:
            return ReferenceSet.objects.filter(is_active=True)
        
        # Get user's accessible org_unit IDs from ScopedRole
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        # If no org units assigned, user has no access
        if not user_org_units:
            return ReferenceSet.objects.none()
        
        # Filter reference sets by domain's org_unit
        from catalog.models import DataDomain
        domains = DataDomain.objects.filter(id__in=user_org_units)
        return ReferenceSet.objects.filter(domain__in=domains, is_active=True)

    def perform_create(self, serializer):
        """Auto-assign steward to current user on create."""
        serializer.save(
            slug=slugify(serializer.validated_data.get('name', '')),
            steward=self.request.user
        )

    def perform_update(self, serializer):
        """Check permission before update: only steward or staff can edit."""
        obj = self.get_object()
        if obj.steward != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("Only steward can edit this reference set")
        serializer.save()

    def perform_destroy(self, instance):
        """Soft delete: set is_active=False instead of hard delete."""
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=['get'])
    def values(self, request, pk=None):
        """GET /mdm/reference-sets/{id}/values/?active=1 -> values of this set."""
        ref_set = self.get_object()
        qs = ReferenceValue.objects.filter(reference_set=ref_set)
        if request.query_params.get('active') in ('1', 'true', 'True'):
            qs = qs.filter(is_active=True)
        return Response(ReferenceValueSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def add_value(self, request, pk=None):
        """POST /mdm/reference-sets/{id}/add_value/ -> add value to set."""
        ref_set = self.get_object()
        
        # Check permission: only steward can add values
        if ref_set.steward != request.user and not request.user.is_staff:
            raise PermissionDenied("Only steward can add values to this set")
        
        serializer = ReferenceValueSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(reference_set=ref_set)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReferenceValueViewSet(viewsets.ModelViewSet):
    serializer_class = ReferenceValueSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def get_queryset(self):
        qs = ReferenceValue.objects.all()
        p = self.request.query_params
        if p.get('reference_set'):
            qs = qs.filter(reference_set_id=p['reference_set'])
        if p.get('active') in ('1', 'true', 'True'):
            qs = qs.filter(is_active=True)
        return qs


class BindFieldView(APIView):
    """POST /mdm/bind-field/ {"data_field": <id>, "reference_set": <id|null>}
    Binds (or unbinds) a dataschema DataField to a ReferenceSet. Admin only."""
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def post(self, request):
        field_id = request.data.get('data_field')
        set_id = request.data.get('reference_set')
        if not field_id:
            return Response({'error': 'data_field is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            field = DataField.objects.get(pk=field_id)
        except DataField.DoesNotExist:
            return Response({'error': 'data_field not found'}, status=status.HTTP_404_NOT_FOUND)
        if set_id in (None, '', 'null'):
            field.reference_set = None
        else:
            try:
                field.reference_set = ReferenceSet.objects.get(pk=set_id)
            except ReferenceSet.DoesNotExist:
                return Response({'error': 'reference_set not found'}, status=status.HTTP_404_NOT_FOUND)
        field.save(update_fields=['reference_set'])
        return Response({'data_field': field.id, 'reference_set': field.reference_set_id})


class FieldOptionsView(APIView):
    """GET /mdm/field-options/?data_field=<id> -> ACTIVE values of the set bound
    to this field (empty list if the field is not bound). Read: any authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        field_id = request.query_params.get('data_field')
        if not field_id:
            return Response({'error': 'data_field is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            field = DataField.objects.get(pk=field_id)
        except DataField.DoesNotExist:
            return Response({'error': 'data_field not found'}, status=status.HTTP_404_NOT_FOUND)
        if not field.reference_set_id:
            return Response({'data_field': field.id, 'reference_set': None, 'values': []})
        qs = ReferenceValue.objects.filter(reference_set_id=field.reference_set_id, is_active=True)
        return Response({
            'data_field': field.id,
            'reference_set': field.reference_set_id,
            'values': ReferenceValueSerializer(qs, many=True).data,
        })


class OrgUnitViewSet(viewsets.ModelViewSet):
    """CRUD for organisational units. Supports tree hierarchy via parent FK.
    
    RBAC: All authenticated users can read org units. Only admin can write.
    Endpoints:
    - GET    /mdm/org-units/                List all org units (with optional filters)
    - POST   /mdm/org-units/                Create new org unit (admin only)
    - GET    /mdm/org-units/{id}/           Detail
    - PUT    /mdm/org-units/{id}/           Update (admin only)
    - PATCH  /mdm/org-units/{id}/           Partial update (admin only)
    - DELETE /mdm/org-units/{id}/           Delete (admin only)
    - GET    /mdm/org-units/{id}/tree/      Get tree with children
    - GET    /mdm/org-units/{id}/ancestors/ Get ancestors (path to root)
    """
    serializer_class = OrgUnitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter org units based on query parameters."""
        qs = OrgUnit.objects.filter(is_active=True)
        p = self.request.query_params
        
        # Filter by parent
        if p.get('parent'):
            qs = qs.filter(parent_id=p['parent'])
        
        # Get root org units (no parent)
        if p.get('root') in ('1', 'true', 'True'):
            qs = qs.filter(parent=None)
        
        # Filter by org_type
        if p.get('org_type'):
            qs = qs.filter(org_type=p['org_type'])
        
        return qs

    def perform_create(self, serializer):
        """Auto-generate slug based on parent and name."""
        name = serializer.validated_data.get('name', '')
        parent = serializer.validated_data.get('parent')
        base = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
        serializer.save(slug=base)

    def perform_update(self, serializer):
        """Validate hierarchy before update."""
        obj = self.get_object()
        new_parent = serializer.validated_data.get('parent', obj.parent)
        
        # Prevent circular references
        if new_parent and new_parent.id in obj.get_descendant_ids(include_self=True):
            raise PermissionDenied("Cannot set parent to be a descendant of this unit")
        
        serializer.save()

    def perform_destroy(self, instance):
        """Soft delete: set is_active=False. Prevent if has active children."""
        if instance.children.filter(is_active=True).exists():
            raise PermissionDenied("Cannot delete org unit with active children")
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=['get'])
    def tree(self, request, pk=None):
        """GET /mdm/org-units/{id}/tree/ -> subtree rooted at this unit."""
        org_unit = self.get_object()
        children_ids = org_unit.get_descendant_ids(include_self=True)
        qs = OrgUnit.objects.filter(id__in=children_ids, is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def ancestors(self, request, pk=None):
        """GET /mdm/org-units/{id}/ancestors/ -> path to root."""
        org_unit = self.get_object()
        ancestors = org_unit.get_ancestors()
        serializer = self.get_serializer(ancestors, many=True)
        return Response(serializer.data)
