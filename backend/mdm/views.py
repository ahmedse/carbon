# mdm/views.py
from django.db import models
from django.utils.text import slugify
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

from dataschema.models import DataField, DataRow
from catalog.audit_utils import emit_governance_event
from .models import ReferenceSet, ReferenceValue, OrgUnit
from .serializers import ReferenceSetSerializer, ReferenceValueSerializer, OrgUnitSerializer
from .services import ReferenceSetService, OrgUnitService
from accounts.permissions import ReadAnyWriteGlobalAdmin
from catalog.permissions import AdminOrSuperuserOnly
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
        - If user has no org_unit assignments, show all (for now - permissive)
        """
        if getattr(self, 'swagger_fake_view', False):
            return ReferenceSet.objects.none()
        user = self.request.user
        
        # Optimize queryset with select_related for foreign keys
        qs = ReferenceSet.objects.select_related(
            'domain', 'steward'
        )
        
        # Annotate to avoid N+1 on value counts
        from django.db.models import Count, Q
        qs = qs.annotate(
            values_count=Count('values', filter=Q(values__is_active=True))
        )
        
        # Superusers and staff see everything
        if user.is_superuser or user.is_staff:
            return qs.filter(is_active=True)
        
        # Get user's accessible org_unit IDs from ScopedRole
        user_org_units = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        
        # If no org units assigned, show all reference sets (permissive mode)
        # TODO: Make this restrictive once RBAC is fully implemented
        if not user_org_units:
            return qs.filter(is_active=True)
        
        # Filter reference sets by domain's org_unit or show all if domain is null
        from catalog.models import DataDomain
        domains_in_scope = DataDomain.objects.filter(id__in=user_org_units)
        return qs.filter(
            models.Q(domain__in=domains_in_scope) | models.Q(domain__isnull=True),
            is_active=True
        )

    def perform_create(self, serializer):
        """Auto-assign steward to current user on create."""
        instance = serializer.save(
            slug=slugify(serializer.validated_data.get('name', '')),
            steward=self.request.user
        )
        emit_governance_event(
            entity_type='ReferenceSet',
            entity_id=instance.id,
            action='create',
            before={},
            after={
                'name': instance.name,
                'description': instance.description,
                'domain': instance.domain_id,
                'steward': instance.steward_id,
                'is_active': instance.is_active,
                'version': instance.version,
            },
            user=self.request.user,
        )

    def perform_update(self, serializer):
        """Check permission before update: only steward or staff can edit."""
        obj = self.get_object()
        if obj.steward != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("Only steward can edit this reference set")
        before = {
            'name': obj.name,
            'description': obj.description,
            'domain': obj.domain_id,
            'steward': obj.steward_id,
            'is_active': obj.is_active,
            'version': obj.version,
        }
        instance = serializer.save()
        after = {
            'name': instance.name,
            'description': instance.description,
            'domain': instance.domain_id,
            'steward': instance.steward_id,
            'is_active': instance.is_active,
            'version': instance.version,
        }
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='ReferenceSet',
                entity_id=instance.id,
                action='update',
                before={k: before[k] for k in changed},
                after=changed,
                user=self.request.user,
            )

    def perform_destroy(self, instance):
        """Soft delete: set is_active=False instead of hard delete."""
        before = {'is_active': instance.is_active}
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        emit_governance_event(
            entity_type='ReferenceSet',
            entity_id=instance.id,
            action='delete',
            before=before,
            after={'is_active': False},
            user=self.request.user,
        )

    @swagger_auto_schema(
        methods=['get'],
        operation_description='Return reference values valid on a given date, optionally filtered to active values only.',
        manual_parameters=[
            openapi.Parameter('date', openapi.IN_QUERY, description='ISO date to query historical values', type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE, required=False),
            openapi.Parameter('active', openapi.IN_QUERY, description='Filter to active values only', type=openapi.TYPE_BOOLEAN, required=False),
        ],
        responses={200: 'List of reference values', 400: 'Invalid date format', 404: 'Reference set not found'},
    )
    @action(detail=True, methods=['get'])
    def values(self, request, pk=None):
        """GET /mdm/reference-sets/{id}/values/?date=YYYY-MM-DD&active=true -> values of this set."""
        from datetime import date

        ref_set = self.get_object()
        qs = ReferenceValue.objects.filter(reference_set=ref_set)
        if request.query_params.get('active') in ('1', 'true', 'True'):
            qs = qs.filter(is_active=True)

        date_str = request.query_params.get('date')
        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                return Response(
                    {'error': 'date must be a valid ISO date YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(
                models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=target_date),
                models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=target_date),
            )

        return Response(ReferenceValueSerializer(qs, many=True).data)

    @swagger_auto_schema(
        methods=['post'],
        operation_description='Advance a reference set through its lifecycle states.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'state': openapi.Schema(type=openapi.TYPE_STRING, description='Target lifecycle state')},
            required=['state'],
        ),
        responses={200: 'Transition accepted', 400: 'Invalid lifecycle transition', 404: 'Reference set not found'},
    )
    @action(detail=True, methods=['post'])
    def transition(self, request, pk=None):
        """POST /mdm/reference-sets/{id}/transition/ to move lifecycle state."""
        ref_set = self.get_object()
        try:
            result = ReferenceSetService.transition_set(
                ref_set, request.data.get('state'), user=request.user
            )
        except ValueError as exc:
            # Service raises ValueError({'state': [...]}) with the exact
            # messages the view used to raise as DRFValidationError.
            raise DRFValidationError(exc.args[0] if exc.args else {'state': ['Invalid transition.']})
        return Response(result)

    @swagger_auto_schema(
        methods=['post'],
        operation_description='Add a new reference value to this reference set.',
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT),
        responses={201: 'Value created', 400: 'Validation error'},
    )
    @action(detail=True, methods=['post'])
    def add_value(self, request, pk=None):
        """POST /mdm/reference-sets/{id}/add_value/ -> add value to set."""
        ref_set = self.get_object()

        # Check permission: only steward can add values (authz stays in view)
        if ref_set.steward != request.user and not request.user.is_staff:
            raise PermissionDenied("Only steward can add values to this set")

        data, created = ReferenceSetService.add_value(ref_set, request.data)
        if created:
            return Response(data, status=status.HTTP_201_CREATED)
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        methods=['post'],
        operation_description=(
            'Archive multiple reference sets in one request. '
            'Sets is_active=False and lifecycle_state=archived for each ID. '
            'Returns per-item success/failure so partial failures do not abort the batch.'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of ReferenceSet IDs to archive',
                ),
            },
            required=['ids'],
        ),
        responses={
            200: openapi.Response(
                description='Per-item success/failure summary',
                examples={'application/json': {'success': [1, 2], 'failed': [{'id': 99, 'error': 'ReferenceSet not found'}]}},
            ),
            400: 'ids must be a non-empty list',
        },
    )
    @action(detail=False, methods=['post'], url_path='archive-bulk')
    def archive_bulk(self, request):
        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)

        results = ReferenceSetService.archive_bulk(ids, user=request.user)
        return Response(results, status=status.HTTP_200_OK)


class ReferenceValueViewSet(viewsets.ModelViewSet):
    serializer_class = ReferenceValueSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    @swagger_auto_schema(
        methods=['post'],
        operation_description='Create multiple reference values atomically for bulk import workflows.',
        request_body=openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
        responses={201: 'Bulk-create succeeded', 400: 'One or more values failed validation'},
    )
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        payload = request.data
        if not isinstance(payload, list) or not payload:
            return Response({'error': 'A non-empty list of values is required'}, status=status.HTTP_400_BAD_REQUEST)

        reference_set_id = request.query_params.get('reference_set')
        if isinstance(request.data, dict):
            reference_set_id = reference_set_id or request.data.get('reference_set')
        if not reference_set_id:
            return Response({'error': 'reference_set is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ref_set = ReferenceSet.objects.get(pk=reference_set_id)
        except ReferenceSet.DoesNotExist:
            return Response({'error': 'reference_set not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            data = ReferenceSetService.bulk_create(payload, ref_set, user=request.user)
        except ValueError as exc:
            return Response(exc.args[0], status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        # Optimize: select_related reference_set (serializer exposes it)
        qs = ReferenceValue.objects.select_related('reference_set').all()
        p = self.request.query_params
        if p.get('reference_set'):
            qs = qs.filter(reference_set_id=p['reference_set'])
        if p.get('active') in ('1', 'true', 'True'):
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        emit_governance_event(
            entity_type='ReferenceValue',
            entity_id=instance.id,
            action='create',
            before={},
            after={
                'code': instance.code,
                'label': instance.label,
                'is_active': instance.is_active,
                'sort_order': instance.sort_order,
                'valid_from': str(instance.valid_from) if instance.valid_from else None,
                'valid_to': str(instance.valid_to) if instance.valid_to else None,
            },
            user=self.request.user,
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        before = {
            'code': instance.code,
            'label': instance.label,
            'is_active': instance.is_active,
            'sort_order': instance.sort_order,
            'valid_from': str(instance.valid_from) if instance.valid_from else None,
            'valid_to': str(instance.valid_to) if instance.valid_to else None,
        }
        obj = serializer.save()
        after = {
            'code': obj.code,
            'label': obj.label,
            'is_active': obj.is_active,
            'sort_order': obj.sort_order,
            'valid_from': str(obj.valid_from) if obj.valid_from else None,
            'valid_to': str(obj.valid_to) if obj.valid_to else None,
        }
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='ReferenceValue',
                entity_id=obj.id,
                action='update',
                before={k: before[k] for k in changed},
                after=changed,
                user=self.request.user,
            )

    def perform_destroy(self, instance):
        before = {'is_active': instance.is_active}
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        emit_governance_event(
            entity_type='ReferenceValue',
            entity_id=instance.id,
            action='delete',
            before=before,
            after={'is_active': False},
            user=self.request.user,
        )


class BindFieldView(APIView):
    """POST /mdm/bind-field/ to bind or unbind one or many DataFields.

    Body examples:
      {"data_field": 1, "reference_set": 5}
      {"data_fields": [1,2,3], "reference_set": 5}
      {"data_fields": [1,2], "reference_set": null, "force": true}
    """
    permission_classes = [ReadAnyWriteGlobalAdmin]

    @swagger_auto_schema(
        operation_description='Bind or unbind one or many data fields to a reference set.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'data_field': openapi.Schema(type=openapi.TYPE_INTEGER),
                'data_fields': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)),
                'reference_set': openapi.Schema(type=openapi.TYPE_INTEGER),
                'force': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            },
        ),
        responses={200: 'Binding updated', 400: 'Invalid request', 404: 'Field or reference set not found'},
    )
    def post(self, request):
        field_ids = request.data.get('data_fields') or [request.data.get('data_field')]
        set_id = request.data.get('reference_set')
        force = request.data.get('force') in (True, 'true', 'True', '1')

        if not field_ids or field_ids == [None]:
            return Response({'error': 'data_field or data_fields is required'}, status=status.HTTP_400_BAD_REQUEST)

        field_ids = [fid for fid in field_ids if fid is not None]
        fields = list(DataField.objects.filter(pk__in=field_ids))
        if len(fields) != len(set(field_ids)):
            return Response({'error': 'one or more data_fields not found'}, status=status.HTTP_404_NOT_FOUND)

        reference_set = None
        if set_id not in (None, '', 'null'):
            try:
                reference_set = ReferenceSet.objects.get(pk=set_id)
            except ReferenceSet.DoesNotExist:
                return Response({'error': 'reference_set not found'}, status=status.HTTP_404_NOT_FOUND)

        updated = []
        for field in fields:
            if reference_set is None:
                if field.reference_set_id and not force:
                    if DataRow.objects.filter(
                        data_table=field.data_table,
                        is_archived=False,
                        values__has_key=field.name,
                    ).exists():
                        return Response(
                            {
                                'error': 'Field unbind rejected because existing rows reference this field. Use force=true to override.'
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                field.reference_set = None
            else:
                field.reference_set = reference_set
            field.save(update_fields=['reference_set'])
            updated.append({'data_field': field.id, 'reference_set': field.reference_set_id})

        return Response({'updated': updated})


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
        # Optimize: select_related parent (OrgUnitSerializer exposes parent_name)
        qs = OrgUnit.objects.select_related('parent').filter(is_active=True)
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
        instance = serializer.save(slug=base)
        emit_governance_event(
            entity_type='OrgUnit',
            entity_id=instance.id,
            action='create',
            before={},
            after={
                'name': instance.name,
                'org_type': instance.org_type,
                'parent': instance.parent_id,
                'is_active': instance.is_active,
            },
            user=self.request.user,
        )

    def perform_update(self, serializer):
        """Validate hierarchy before update."""
        obj = self.get_object()
        new_parent = serializer.validated_data.get('parent', obj.parent)
        
        # Prevent circular references
        if new_parent and new_parent.id in obj.get_descendant_ids(include_self=True):
            raise PermissionDenied("Cannot set parent to be a descendant of this unit")
        before = {
            'name': obj.name,
            'org_type': obj.org_type,
            'parent': obj.parent_id,
            'is_active': obj.is_active,
        }
        instance = serializer.save()
        after = {
            'name': instance.name,
            'org_type': instance.org_type,
            'parent': instance.parent_id,
            'is_active': instance.is_active,
        }
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='OrgUnit',
                entity_id=instance.id,
                action='update',
                before={k: before[k] for k in changed},
                after=changed,
                user=self.request.user,
            )

    def perform_destroy(self, instance):
        """Soft delete: set is_active=False. Prevent if has active children."""
        if instance.children.filter(is_active=True).exists():
            raise PermissionDenied("Cannot delete org unit with active children")
        before = {'is_active': instance.is_active}
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        emit_governance_event(
            entity_type='OrgUnit',
            entity_id=instance.id,
            action='delete',
            before=before,
            after={'is_active': False},
            user=self.request.user,
        )

    @swagger_auto_schema(
        methods=['get'],
        operation_description=(
            'Return the full subtree of org units rooted at this unit, '
            'including self and all active descendants (breadth-first order).'
        ),
        responses={
            200: openapi.Response(description='Flat list of OrgUnit objects in the subtree'),
            404: 'Org unit not found',
        },
    )
    @action(detail=True, methods=['get'])
    def tree(self, request, pk=None):
        """GET /mdm/org-units/{id}/tree/ -> subtree rooted at this unit."""
        org_unit = self.get_object()
        qs = OrgUnitService.get_tree(org_unit)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        methods=['get'],
        operation_description=(
            'Return the ancestor chain from the root org unit down to this unit\'s parent '
            '(ordered root-first). Self is not included.'
        ),
        responses={
            200: openapi.Response(description='Ordered list of ancestor OrgUnit objects from root to parent'),
            404: 'Org unit not found',
        },
    )
    @action(detail=True, methods=['get'])
    def ancestors(self, request, pk=None):
        """GET /mdm/org-units/{id}/ancestors/ -> path to root."""
        org_unit = self.get_object()
        ancestors = OrgUnitService.get_ancestors(org_unit)
        serializer = self.get_serializer(ancestors, many=True)
        return Response(serializer.data)
