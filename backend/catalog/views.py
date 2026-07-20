# catalog/views.py
from django.db.models import Q
from django.utils.text import slugify
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent, GovernancePolicy
from .serializers import (
    DataDomainSerializer, GlossaryTermSerializer, TagSerializer,
    AssetProfileSerializer, GovernanceEventSerializer, GovernancePolicySerializer,
)
from accounts.permissions import ReadAnyWriteGlobalAdmin
from core.feedback import AppFeedback
from .services import ensure_asset_profiles


class DataDomainViewSet(viewsets.ModelViewSet):
    queryset = DataDomain.objects.all().order_by('name')
    serializer_class = DataDomainSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))


class GlossaryTermViewSet(viewsets.ModelViewSet):
    queryset = GlossaryTerm.objects.all().order_by('term')
    serializer_class = GlossaryTermSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['term']))


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by('name')
    serializer_class = TagSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))


class AssetProfileViewSet(viewsets.ModelViewSet):
    serializer_class = AssetProfileSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]
    http_method_names = ['get', 'patch', 'put', 'head', 'options']  # profiles are auto-managed; no create/delete

    def get_queryset(self):
        ensure_asset_profiles()
        qs = AssetProfile.objects.select_related(
            'data_table', 'data_field', 'data_field__data_table',
            'domain', 'owner', 'steward', 'glossary_term',
        ).prefetch_related('tags')
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
        before = AssetProfileSerializer(serializer.instance).data
        obj = serializer.save(updated_by=self.request.user)
        after = AssetProfileSerializer(obj).data
        GovernanceEvent.objects.create(
            asset=obj, entity_type='asset', entity_id=obj.id, action='update',
            before=before, after=after, user=self.request.user,
        )


class GovernanceEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GovernanceEvent.objects.all()
    serializer_class = GovernanceEventSerializer
    permission_classes = [IsAuthenticated]


class GovernancePolicyViewSet(viewsets.ModelViewSet):
    """
    Admin-managed governance policies. Read for authenticated users,
    write for global admins only. A policy that is enabled and has been
    enforced (usage_count > 0) cannot be deleted — only disabled.
    """
    queryset = GovernancePolicy.objects.all()
    serializer_class = GovernancePolicySerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteGlobalAdmin]

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
