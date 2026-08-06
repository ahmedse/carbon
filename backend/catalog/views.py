# catalog/views.py
from django.db.models import Count, Q
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import ReadAnyWriteGlobalAdmin
from accounts.models import ScopedRole
from core.feedback import AppFeedback
from .audit_utils import emit_governance_event
from .filters import GovernanceEventFilter
from .models import DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent, GovernancePolicy
from .serializers import (
    DataDomainSerializer, GlossaryTermSerializer, TagSerializer,
    AssetProfileSerializer, GovernanceEventSerializer, GovernancePolicySerializer,
)
from .services import ensure_asset_profiles


class GovernanceEventPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


class DataDomainViewSet(viewsets.ModelViewSet):
    queryset = DataDomain.objects.all().order_by('name')
    serializer_class = DataDomainSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(
            {
                'detail': 'Hard delete not supported; use PATCH {"is_active": false} to archive this resource.',
                'resource': 'DataDomain',
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class GlossaryTermViewSet(viewsets.ModelViewSet):
    queryset = GlossaryTerm.objects.all().order_by('term')
    serializer_class = GlossaryTermSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(
            {
                'detail': 'Hard delete not supported; use PATCH {"is_active": false} to archive this resource.',
                'resource': 'GlossaryTerm',
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_create(self, serializer):
        instance = serializer.save(slug=slugify(serializer.validated_data['term']))
        emit_governance_event(
            entity_type='GlossaryTerm',
            entity_id=instance.id,
            action='create',
            before={},
            after={
                'term': instance.term,
                'definition': instance.definition,
                'status': instance.status,
                'steward': instance.steward_id,
                'domain': instance.domain_id,
            },
            user=self.request.user,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        before = {
            'term': old.term,
            'definition': old.definition,
            'status': old.status,
            'steward': old.steward_id,
            'domain': old.domain_id,
        }
        instance = serializer.save()
        after = {
            'term': instance.term,
            'definition': instance.definition,
            'status': instance.status,
            'steward': instance.steward_id,
            'domain': instance.domain_id,
        }
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='GlossaryTerm',
                entity_id=instance.id,
                action='update',
                before={k: before[k] for k in changed},
                after=changed,
                user=self.request.user,
            )

    def perform_destroy(self, instance):
        before = {'term': instance.term, 'definition': instance.definition, 'status': instance.status}
        entity_id = instance.id
        instance.delete()
        emit_governance_event(
            entity_type='GlossaryTerm',
            entity_id=entity_id,
            action='delete',
            before=before,
            after={'deleted': True},
            user=self.request.user,
        )


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by('name')
    serializer_class = TagSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(
            {
                'detail': 'Hard delete not supported; use PATCH {"is_active": false} to archive this resource.',
                'resource': 'Tag',
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))


class AssetProfileViewSet(viewsets.ModelViewSet):
    serializer_class = AssetProfileSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]
    http_method_names = ['get', 'post', 'patch', 'put', 'head', 'options']  # profiles are auto-managed; no create/delete

    @swagger_auto_schema(
        operation_description='Archive multiple asset profiles in one request.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)),
            },
            required=['ids'],
        ),
        responses={200: 'Per-item success/failure summary', 400: 'Invalid request'},
    )
    @action(detail=False, methods=['post'], url_path='archive-bulk')
    def archive_bulk(self, request):
        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)

        results = {'success': [], 'failed': []}
        for asset_id in ids:
            try:
                asset = AssetProfile.objects.get(pk=asset_id)
            except AssetProfile.DoesNotExist:
                results['failed'].append({'id': asset_id, 'error': 'AssetProfile not found'})
                continue

            asset.is_active = False
            asset.save(update_fields=['is_active'])
            emit_governance_event(
                entity_type='AssetProfile',
                entity_id=asset.id,
                action='delete',
                before={'is_active': True},
                after={'is_active': False},
                user=request.user,
            )
            results['success'].append(asset.id)

        return Response(results, status=status.HTTP_200_OK)

    def get_queryset(self):
        ensure_asset_profiles()
        qs = AssetProfile.objects.select_related(
            'data_table', 'data_field', 'data_field__data_table',
            'domain', 'owner', 'steward', 'glossary_term',
        ).prefetch_related('tags')
        
        # RBAC: Scope to user's org units (superusers/staff see all)
        user = self.request.user
        if not (user.is_superuser or user.is_staff):
            org_units = list(
                ScopedRole.objects.filter(
                    user=user, is_active=True
                ).values_list('org_unit_id', flat=True).distinct()
            )
            if not org_units:
                return AssetProfile.objects.none()
            qs = qs.filter(
                Q(data_table__module__org_unit_id__in=org_units) |
                Q(data_field__data_table__module__org_unit_id__in=org_units)
            )
        
        p = self.request.query_params
        if p.get('classification'):
            qs = qs.filter(classification=p['classification'])
        if p.get('quality_status'):
            qs = qs.filter(quality_status=p['quality_status'])
        if p.get('domain'):
            qs = qs.filter(domain_id=p['domain'])
        if p.get('owner'):
            qs = qs.filter(owner_id=p['owner'])
        if p.get('tag'):
            qs = qs.filter(tags__id=p['tag'])
        if p.get('module_id'):
            mid = p['module_id']
            qs = qs.filter(Q(data_table__module_id=mid) | Q(data_field__data_table__module_id=mid))
        return qs.distinct().order_by('id')

    def perform_update(self, serializer):
        instance = self.get_object()
        before = {
            'owner': instance.owner_id,
            'steward': instance.steward_id,
            'classification': instance.classification,
            'domain': instance.domain_id,
            'glossary_term': instance.glossary_term_id,
            'quality_status': instance.quality_status,
            'quality_score': instance.quality_score,
        }
        obj = serializer.save(updated_by=self.request.user)
        after = {
            'owner': obj.owner_id,
            'steward': obj.steward_id,
            'classification': obj.classification,
            'domain': obj.domain_id,
            'glossary_term': obj.glossary_term_id,
            'quality_status': obj.quality_status,
            'quality_score': obj.quality_score,
        }
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='AssetProfile',
                entity_id=obj.id,
                action='update',
                before={k: before[k] for k in changed},
                after=changed,
                user=self.request.user,
                asset_profile=obj,
            )


class GovernanceEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GovernanceEvent.objects.all().order_by('-timestamp')
    serializer_class = GovernanceEventSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GovernanceEventFilter
    ordering = ['-timestamp']
    ordering_fields = ['timestamp', 'entity_type', 'action']
    pagination_class = GovernanceEventPagination


class GovernanceComplianceView(APIView):
    permission_classes = [ReadAnyWriteGlobalAdmin]

    @swagger_auto_schema(
        operation_description='Summarize governance events for a recent time window.',
        manual_parameters=[
            openapi.Parameter('days', openapi.IN_QUERY, description='Number of days to include', type=openapi.TYPE_INTEGER, required=False),
        ],
        responses={200: 'Compliance summary of recent governance activity'},
    )
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = GovernanceEvent.objects.filter(timestamp__gte=cutoff)
        return Response({
            'window_days': days,
            'total_events': qs.count(),
            'by_action': list(qs.values('action').annotate(count=Count('action')).order_by().values('action', 'count')),
            'by_entity_type': list(qs.values('entity_type').annotate(count=Count('entity_type')).order_by().values('entity_type', 'count')),
            'recent_events': GovernanceEventSerializer(qs.order_by('-timestamp')[:10], many=True).data,
        })


class GovernancePolicyViewSet(viewsets.ModelViewSet):
    """
    Admin-managed governance policies. Read for authenticated users,
    write for global admins only. A policy that is enabled and has been
    enforced (usage_count > 0) cannot be deleted — only disabled.
    """
    queryset = GovernancePolicy.objects.all()
    serializer_class = GovernancePolicySerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Cannot delete an active policy that is actively enforcing rules.
        if instance.enabled and instance.usage_count > 0:
            raise AppFeedback(
                code="policy_in_use",
                title="Cannot delete an active policy",
                detail=f"'{instance.name}' is enabled and has been enforced {instance.usage_count} time(s).",
                reasons=[
                    "This policy is currently active.",
                    f"It has already blocked {instance.usage_count} action(s), so it is in use.",
                ],
                remediation=[
                    "Disable the policy first if you no longer want it enforced.",
                    "Once disabled, it can be safely deleted.",
                ],
                context={"policy_id": instance.id, "usage_count": instance.usage_count},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)


class CatalogSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ensure_asset_profiles()
        q = (request.query_params.get('q') or '').strip()
        assets, terms = [], []
        if q:
            asset_qs = AssetProfile.objects.filter(
                Q(description__icontains=q) |
                Q(data_table__title__icontains=q) | Q(data_table__name__icontains=q) |
                Q(data_field__label__icontains=q) | Q(data_field__name__icontains=q)
            ).distinct()[:50]
            assets = AssetProfileSerializer(asset_qs, many=True).data
            term_qs = GlossaryTerm.objects.filter(
                Q(term__icontains=q) | Q(definition__icontains=q)
            )[:50]
            terms = GlossaryTermSerializer(term_qs, many=True).data
        return Response({'query': q, 'assets': assets, 'glossary': terms})
