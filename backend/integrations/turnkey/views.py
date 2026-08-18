"""
integrations/turnkey/views.py — THIN views for the TurnKey Bridge.

Pattern (per base-rules): validate → call service → serialize. No business
logic in views. CBAC gating per DESIGN-PLATFORM.md §6.6:

  * configs list/create      → turnkey:manage (AdminOrSuperuserOnly)
  * links list               → turnkey:view / create → turnkey:manage
  * link promote             → turnkey:manage
  * predictions / feedback   → turnkey:view
  * drift alerts list        → turnkey:view
  * callbacks (inbound)      → HMAC-SHA256 signed (no JWT), 401 on bad signature

Reads are org-scoped at the boundary: links are filtered by the visible module
ids of the requesting user (module-level ScopedRole is the CBAC anchor).
"""
import hashlib
import hmac
import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import AdminOrSuperuserOnly
from accounts.rbac_utils import get_visible_module_ids
from django.conf import settings

from . import services
from .models import (
    DriftAlert, PredictionRecord, TurnKeyConfig, TurnKeyModelLink,
)
from .permissions import TurnKeyReadViewWriteManage
from .serializers import (
    DriftAlertSerializer, PredictionRecordSerializer, TurnKeyConfigCreateSerializer,
    TurnKeyConfigSerializer, TurnKeyModelLinkSerializer,
    PredictionFeedbackSerializer,
)

logger = logging.getLogger(__name__)

TURNKEY_MANAGE = 'turnkey:manage'
TURNKEY_VIEW = 'turnkey:view'


def _verify_signature(request) -> bool:
    """Verify the HMAC-SHA256 signature over the raw request body.

    Header: ``X-TurnKey-Signature`` = hex(hmac_sha256(TURNKEY_CALLBACK_SECRET,
    request.body)). Uses compare_digest to avoid timing side channels.
    """
    provided = request.headers.get('X-TurnKey-Signature', '')
    if not provided:
        return False
    expected = hmac.new(
        settings.TURNKEY_CALLBACK_SECRET.encode(),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(provided, expected)


def _scoped_links_qs(user):
    """Org-scope model links by the user's visible modules.

    Returns None-filter-free queryset for unrestricted (superuser / global
    admin) users, otherwise links whose dataset version's module is visible.
    """
    visible = get_visible_module_ids(user)
    qs = TurnKeyModelLink.objects.select_related(
        'dataset_version', 'dataset_version__dataset', 'turnkey_config',
    )
    if visible is None:
        return qs
    return qs.filter(dataset_version__dataset__module_id__in=visible)


# ── Configs (turnkey:manage for all access) ────────────────────────────────

class TurnKeyConfigListCreateView(APIView):
    """GET list of TurnKey configs; POST add a config (API key via set_api_key())."""
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = TURNKEY_MANAGE

    def get(self, request):
        qs = TurnKeyConfig.objects.all()
        return Response(TurnKeyConfigSerializer(qs, many=True).data)

    def post(self, request):
        serializer = TurnKeyConfigCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save(created_by=request.user)
        return Response(
            TurnKeyConfigSerializer(config).data,
            status=status.HTTP_201_CREATED,
        )


# ── Links ──────────────────────────────────────────────────────────────────

class TurnKeyLinkListCreateView(APIView):
    """GET list of model links (turnkey:view); POST create link + register model
    (turnkey:manage)."""
    permission_classes = [TurnKeyReadViewWriteManage]
    required_capability = TURNKEY_VIEW
    required_write_capability = TURNKEY_MANAGE

    def get(self, request):
        qs = _scoped_links_qs(request.user)
        return Response(TurnKeyModelLinkSerializer(qs, many=True).data)

    def post(self, request):
        serializer = TurnKeyModelLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            link = serializer.save(linked_by=request.user)
        except Exception as exc:
            logger.exception('Failed to persist TurnKeyModelLink')
            raise ValidationError({'detail': str(exc)}) from exc

        # Register the model in TurnKey (idempotent by name).
        model_name = request.data.get('model_name') or \
            (link.dataset_version.dataset.name if link.dataset_version_id else '')
        try:
            services.register_link(
                link, model_name, model_type=request.data.get('model_type', 'custom'),
            )
        except Exception as exc:
            link.status = 'failed'
            link.error_detail = str(exc)[:2000]
            link.save(update_fields=['status', 'error_detail'])
            logger.warning('TurnKey register failed for link %s: %s', link.pk, exc)

        return Response(
            TurnKeyModelLinkSerializer(link).data,
            status=status.HTTP_201_CREATED,
        )


class TurnKeyLinkPromoteView(APIView):
    """POST push version (optional artifact_path) + promote to production."""
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = TURNKEY_MANAGE

    def post(self, request, link_id):
        link = get_object_or_404(_scoped_links_qs(request.user), pk=link_id)
        artifact_path = request.data.get('artifact_path', '')
        try:
            services.promote_link(
                link,
                artifact_path=artifact_path,
                metrics=request.data.get('metrics'),
                feature_names=request.data.get('feature_names'),
            )
        except Exception as exc:
            # Security RULE 7: never leak upstream internals to the client.
            logger.exception('Promote failed for link %s', link_id)
            return Response(
                {'detail': 'TurnKey promotion failed — check the integration log.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(TurnKeyModelLinkSerializer(link).data)


class TurnKeyLinkPredictionsView(APIView):
    """GET predictions for a link (turnkey:view)."""
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = TURNKEY_VIEW

    def get(self, request, link_id):
        link = get_object_or_404(_scoped_links_qs(request.user), pk=link_id)
        qs = link.predictions.select_related('input_data_row').all()[:100]
        return Response(PredictionRecordSerializer(qs, many=True).data)


class PredictionFeedbackView(APIView):
    """POST submit the actual outcome for a prediction (turnkey:view)."""
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = TURNKEY_VIEW

    def post(self, request, link_id, prediction_id):
        link = get_object_or_404(_scoped_links_qs(request.user), pk=link_id)
        prediction = get_object_or_404(link.predictions, pk=prediction_id)
        serializer = PredictionFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prediction = services.submit_feedback(
            prediction, serializer.validated_data['actual'], request.user,
        )
        return Response(PredictionRecordSerializer(prediction).data)


class TurnKeyLinkDriftAlertsView(APIView):
    """GET drift alerts for a link (turnkey:view)."""
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = TURNKEY_VIEW

    def get(self, request, link_id):
        link = get_object_or_404(_scoped_links_qs(request.user), pk=link_id)
        qs = link.drift_alerts.all()[:100]
        return Response(DriftAlertSerializer(qs, many=True).data)


# ── Inbound callbacks (HMAC-signed, no JWT) ────────────────────────────────

class PredictionCallbackView(APIView):
    """POST receive a prediction result from TurnKey (HMAC-signed)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _verify_signature(request):
            return Response(
                {'detail': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            record = services.handle_prediction_callback(request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PredictionRecordSerializer(record).data,
                        status=status.HTTP_201_CREATED)


class DriftAlertCallbackView(APIView):
    """POST receive a drift alert from TurnKey (HMAC-signed)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _verify_signature(request):
            return Response(
                {'detail': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            alert = services.handle_drift_callback(request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DriftAlertSerializer(alert).data,
                        status=status.HTTP_201_CREATED)
