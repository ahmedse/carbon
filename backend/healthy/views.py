"""Healthy app views (thin — orchestration lives in services).

Capability gating (DESIGN-PLATFORM.md §8.5):
  * reads  → ``healthy:view``
  * writes → ``healthy:manage``
Superusers and global admins bypass capability checks.
"""
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.capabilities import has_capability
from .models import ERPSnapshot, LoadoutSheet, RepHealthCard
from .serializers import (
    ERPSnapshotSerializer, LoadoutSheetSerializer, RepHealthCardSerializer,
)
from .services import (
    PIPELINES, DashboardService, ERPSnapshotService, HealthyPipelineService,
    LoadoutService,
)


def _can(user, capability: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from accounts.models import ScopedRole
    if ScopedRole.objects.filter(
        user=user, is_active=True,
        group__name__in=['admin', 'admins_group'],
        org_unit__isnull=True, module__isnull=True,
    ).exists():
        return True
    return has_capability(user, capability)


class HealthyAccess(BasePermission):
    """healthy:view for reads, healthy:manage for writes."""

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return _can(request.user, 'healthy:view')
        return _can(request.user, 'healthy:manage')


class SnapshotListCreateView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request):
        qs = ERPSnapshot.objects.select_related('data_source', 'triggered_by').all()
        return Response({
            'count': qs.count(),
            'results': ERPSnapshotSerializer(qs[:100], many=True).data,
        })

    def post(self, request):
        data = request.data or {}
        pipeline_key = data.get('pipeline')
        if pipeline_key:
            if pipeline_key not in PIPELINES:
                return Response(
                    {'detail': f"Unknown healthy pipeline: {pipeline_key!r}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            auto_approve = data.get('auto_approve') in (True, 'true', 'True', 1, '1')
            result = HealthyPipelineService().run_pipeline(
                pipeline_key, user=request.user, auto_approve=auto_approve,
            )
            return Response({
                'snapshot': ERPSnapshotSerializer(result['snapshot']).data,
                'dataset_version_id': str(result['version'].id),
                'turnkey_model_link_id': str(result['link'].id),
                'prediction_id': str(result['prediction'].id),
            }, status=status.HTTP_201_CREATED)

        source_view = data.get('source_view')
        if not source_view:
            return Response(
                {'detail': "Provide either 'pipeline' or 'source_view'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        snapshot, _version = ERPSnapshotService().run_snapshot(
            source_view, user=request.user,
        )
        return Response(ERPSnapshotSerializer(snapshot).data,
                        status=status.HTTP_201_CREATED)


class LoadoutListView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request):
        qs = LoadoutSheet.objects.all()
        week = request.query_params.get('week')
        if week:
            qs = qs.filter(week_start=week)
        return Response({
            'count': qs.count(),
            'results': LoadoutSheetSerializer(qs[:100], many=True).data,
        })


class LoadoutWeekView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request, week):
        qs = LoadoutSheet.objects.filter(week_start=week)
        return Response({
            'count': qs.count(),
            'results': LoadoutSheetSerializer(qs, many=True).data,
        })


class LoadoutRepView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request, week, rep):
        sheet = get_object_or_404(LoadoutSheet, week_start=week, rep_code=rep)
        return Response(LoadoutSheetSerializer(sheet).data)


class LoadoutActualsView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def post(self, request, week, rep):
        sheet = get_object_or_404(LoadoutSheet, week_start=week, rep_code=rep)
        LoadoutService().submit_actuals(sheet, request.data or {})
        return Response(LoadoutSheetSerializer(sheet).data)


class RepHealthListView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request):
        qs = RepHealthCard.objects.all()
        week = request.query_params.get('week')
        if week:
            qs = qs.filter(week_start=week)
        return Response({
            'count': qs.count(),
            'results': RepHealthCardSerializer(qs[:100], many=True).data,
        })


class RepHealthDetailView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request, week, rep):
        card = get_object_or_404(RepHealthCard, week_start=week, rep_code=rep)
        return Response(RepHealthCardSerializer(card).data)


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request):
        return Response(DashboardService().summary())


class DashboardARQueueView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request):
        results = DashboardService().ar_queue()
        return Response({'count': len(results), 'results': results})


class DashboardSlowMoversView(APIView):
    permission_classes = [IsAuthenticated, HealthyAccess]

    def get(self, request):
        results = DashboardService().slow_movers()
        return Response({'count': len(results), 'results': results})
