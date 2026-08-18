"""
appregistry/views.py — THIN views for the App Registry.

Pattern (per base-rules): validate → call service → serialize. No business
logic in views. CBAC gating per DESIGN §7.3:
  * list / detail        → appregistry:view   (AdminOrSuperuserOnly)
  * activate / deactivate → appregistry:manage (AdminOrSuperuserOnly)
Superusers and global admins (admins_group, org_unit=None) always pass via
the accounts capability rail — this app only adds a source, never weakens it.
"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import AdminOrSuperuserOnly

from .models import AppManifest
from .serializers import AppManifestSerializer
from .services import AppRegistryService


class AppManifestViewSet(ModelViewSet):
    """List apps (with activation state) or fetch one app's detail."""
    permission_classes = [IsAuthenticated, AdminOrSuperuserOnly]
    required_capability = 'appregistry:view'
    queryset = AppManifest.objects.select_related('activation').all()
    serializer_class = AppManifestSerializer
    lookup_field = 'slug'
    http_method_names = ['get', 'head', 'options']  # control-plane reads only

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AppManifest.objects.none()
        return AppManifest.objects.select_related('activation').all()


class ActivateAppView(APIView):
    """POST /apps/{slug}/activate/ — turn an app on."""
    permission_classes = [IsAuthenticated, AdminOrSuperuserOnly]
    required_capability = 'appregistry:manage'

    def post(self, request, slug):
        app = get_object_or_404(AppManifest, slug=slug)
        AppRegistryService.activate(app, user=request.user)
        return Response(AppManifestSerializer(app).data)


class DeactivateAppView(APIView):
    """POST /apps/{slug}/deactivate/ — turn a non-system app off."""
    permission_classes = [IsAuthenticated, AdminOrSuperuserOnly]
    required_capability = 'appregistry:manage'

    def post(self, request, slug):
        app = get_object_or_404(AppManifest, slug=slug)
        try:
            AppRegistryService.deactivate(app, user=request.user)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(AppManifestSerializer(app).data)
