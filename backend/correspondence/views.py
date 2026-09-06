"""Correspondence engine API views (Phase OF-7).

Read + action only — no generic create/update/delete. Business logic lives in
``correspondence.fsm``; views stay thin (validate → call fsm → serialize).

Layering: this module never imports ``people``. It is self-contained on
``correspondence`` models, FSM and CBAC permissions.
"""

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import fsm
from .exceptions import (
    CommentRequired,
    InvalidTransition,
    NotActorError,
    SubmissionBlocked,
)
from .models import ACTIONABLE, Correspondence, WorkflowPolicy
from .permissions import (
    CanActOnCorrespondence,
    CanViewCorrespondence,
    CorrespondenceAdminOnly,
)
from .serializers import (
    CorrespondenceDetailSerializer,
    CorrespondenceSerializer,
    WorkflowPolicySerializer,
)


class CorrespondenceViewSet(viewsets.ReadOnlyModelViewSet):
    """List/inbox/detail + approve/reject/send-back/cancel/resubmit actions."""

    serializer_class = CorrespondenceSerializer

    def get_queryset(self):
        qs = (
            Correspondence.objects
            .select_related('requester', 'org_unit', 'corr_type')
            .prefetch_related('events')
        )
        # The list endpoint is self-scoped; inbox/detail/actions operate over
        # the full queryset and are gated by object-level permissions instead.
        if self.action == 'list':
            qs = qs.filter(requester=self.request.user)
            status_code = self.request.query_params.get('status')
            if status_code:
                qs = qs.filter(status=status_code)
            corr_type_code = self.request.query_params.get('corr_type')
            if corr_type_code:
                qs = qs.filter(corr_type__code=corr_type_code)
        return qs

    def get_serializer_class(self):
        if self.action in ('retrieve', 'approve', 'reject', 'send_back',
                           'cancel', 'resubmit'):
            return CorrespondenceDetailSerializer
        return CorrespondenceSerializer

    def get_permissions(self):
        base = [IsAuthenticated()]
        if self.action == 'retrieve':
            return base + [CanViewCorrespondence()]
        if self.action in ('approve', 'reject', 'send_back'):
            return base + [CanActOnCorrespondence()]
        if self.action in ('cancel', 'resubmit'):
            # cancel/resubmit are requester-only (fsm enforces + maps
            # NotActorError -> 403); requester-or-admin gate is CanViewCorrespondence.
            return base + [CanViewCorrespondence()]
        return base

    def _transition(self, corr, user, fn):
        """Run an fsm transition, map engine exceptions to HTTP, and return the
        refreshed, fully-serialized correspondence on success."""
        try:
            with transaction.atomic():
                corr = fn()
        except CommentRequired:
            return Response(
                {'detail': 'Comment is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except NotActorError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidTransition as exc:
            return Response(
                {'detail': f'Invalid transition: {exc}'},
                status=status.HTTP_409_CONFLICT,
            )
        except SubmissionBlocked as exc:
            return Response(
                {'detail': 'Submission blocked by DQ gate', 'failures': exc.failures},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refreshed = self.get_queryset().get(pk=corr.pk)
        return Response(CorrespondenceDetailSerializer(refreshed).data)

    @staticmethod
    def _comment(request):
        raw = request.data.get('comment') if hasattr(request.data, 'get') else None
        return (raw or '').strip()

    @staticmethod
    def _require_comment(request):
        comment = CorrespondenceViewSet._comment(request)
        if not comment:
            return None
        return comment

    @action(detail=False, methods=['get'], url_path='inbox')
    def inbox(self, request):
        qs = self.get_queryset().filter(
            status__in=ACTIONABLE,
            current_approver_ids__contains=request.user.id,
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        corr = self.get_object()
        comment = self._comment(request) or None
        return self._transition(
            corr, request.user, lambda: fsm.approve(corr, request.user, comment),
        )

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        corr = self.get_object()
        comment = self._require_comment(request)
        if comment is None:
            return Response(
                {'detail': 'Comment is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._transition(
            corr, request.user, lambda: fsm.reject(corr, request.user, comment),
        )

    @action(detail=True, methods=['post'], url_path='send-back')
    def send_back(self, request, pk=None):
        corr = self.get_object()
        comment = self._require_comment(request)
        if comment is None:
            return Response(
                {'detail': 'Comment is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._transition(
            corr, request.user,
            lambda: fsm.send_back(corr, request.user, comment),
        )

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        corr = self.get_object()
        return self._transition(
            corr, request.user, lambda: fsm.cancel(corr, request.user),
        )

    @action(detail=True, methods=['post'], url_path='resubmit')
    def resubmit(self, request, pk=None):
        corr = self.get_object()
        return self._transition(
            corr, request.user, lambda: fsm.resubmit(corr, request.user),
        )


class WorkflowPolicyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only policy endpoints (create/update/delete deferred to P7)."""

    serializer_class = WorkflowPolicySerializer
    permission_classes = [IsAuthenticated, CorrespondenceAdminOnly]
    queryset = (
        WorkflowPolicy.objects
        .select_related('corr_type', 'org_unit')
        .prefetch_related('steps')
    )
