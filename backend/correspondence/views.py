"""Correspondence engine API views (Phase OF-7 / OF-15).

List/inbox/detail, a generic payload-only create (OF-15), and step actions
(approve/acknowledge/reject/send-back/cancel/resubmit). Business logic lives in
``correspondence.fsm``; views stay thin (validate → call fsm → serialize).

Layering: this module never imports ``people``. It is self-contained on
``correspondence`` models, FSM and CBAC permissions.
"""

import uuid

from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.capabilities import has_capability
from mdm.models import OrgUnit, ReferenceValue

from . import fsm
from .exceptions import (
    CommentRequired,
    InvalidTransition,
    NotActorError,
    SubmissionBlocked,
)
from .models import ACTIONABLE, Correspondence, Notification, WorkflowPolicy
from .permissions import (
    CanActOnCorrespondence,
    CanSubmitCorrespondence,
    CanViewCorrespondence,
    CorrespondenceAdminOnly,
)
from .policies import PolicyNotFound
from .serializers import (
    CorrespondenceDetailSerializer,
    CorrespondenceSerializer,
    NotificationSerializer,
    WorkflowPolicySerializer,
)


class CorrespondenceViewSet(viewsets.ReadOnlyModelViewSet):
    """List/inbox/detail + create (payload-only submit) + step actions
    (approve/acknowledge/reject/send-back/cancel/resubmit)."""

    serializer_class = CorrespondenceSerializer

    def get_queryset(self):
        qs = (
            Correspondence.objects
            .select_related('requester', 'org_unit', 'corr_type')
            .prefetch_related('events')
        )
        # The list endpoint is self-scoped for non-admins. A
        # ``correspondence:admin`` may widen the filter surface to answer
        # cross-employee questions ("what is pending for this person?").
        if self.action == 'list':
            if has_capability(self.request.user, 'correspondence:admin'):
                requester_id = self.request.query_params.get('requester')
                if requester_id:
                    qs = qs.filter(requester_id=requester_id)
                employee_id = self.request.query_params.get('employee')
                if employee_id:
                    qs = qs.filter(
                        Q(requester__employee_profile=employee_id)
                        | Q(subject_type='people.Employee', subject_id=employee_id),
                    )
                org_unit_id = self.request.query_params.get('org_unit')
                if org_unit_id:
                    qs = qs.filter(org_unit_id=org_unit_id)
                corr_type_code = self.request.query_params.get('corr_type')
                if corr_type_code:
                    qs = qs.filter(corr_type__code=corr_type_code)
                status_code = self.request.query_params.get('status')
                if status_code:
                    qs = qs.filter(status=status_code)
            else:
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
                           'cancel', 'resubmit', 'acknowledge', 'archive'):
            return CorrespondenceDetailSerializer
        return CorrespondenceSerializer

    def get_permissions(self):
        base = [IsAuthenticated()]
        if self.action == 'create':
            return base + [CanSubmitCorrespondence()]
        if self.action == 'retrieve':
            return base + [CanViewCorrespondence()]
        if self.action in ('approve', 'reject', 'send_back', 'acknowledge',
                           'review'):
            return base + [CanActOnCorrespondence()]
        if self.action in ('cancel', 'resubmit', 'archive'):
            # cancel/resubmit/archive are requester-only (fsm enforces + maps
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
        except PolicyNotFound as exc:
            return Response(
                {'detail': str(exc)},
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

    def create(self, request):
        """Generic submit for payload-only types (internal_memo/circular/decision).

        Creates a subject-less draft Correspondence then drives it through the
        workflow via ``fsm.submit_correspondence`` (no DQ gate — ``subject=None``).
        """
        data = request.data or {}
        corr_type_code = (data.get('corr_type') or '').strip()
        title = (data.get('title') or '').strip()
        payload = data.get('payload') or {}
        org_unit_id = data.get('org_unit')

        if not corr_type_code:
            return Response(
                {'detail': 'corr_type is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not title:
            return Response(
                {'detail': 'title is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(payload, dict):
            return Response(
                {'detail': 'payload must be an object'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        corr_type = ReferenceValue.objects.filter(
            reference_set__name='correspondence_type', code=corr_type_code,
        ).first()
        if corr_type is None:
            return Response(
                {'detail': f'Unknown corr_type {corr_type_code!r}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not org_unit_id:
            return Response(
                {'detail': 'org_unit is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org_unit = OrgUnit.objects.filter(pk=org_unit_id).first()
        if org_unit is None:
            return Response(
                {'detail': f'Unknown org_unit {org_unit_id!r}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                corr = Correspondence.objects.create(
                    corr_type=corr_type,
                    subject_type='',
                    subject_id=None,
                    org_unit=org_unit,
                    requester=request.user,
                    title=title,
                    payload=payload,
                    status='draft',
                    reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
                )
                corr = fsm.submit_correspondence(
                    corr=corr, by=request.user, subject=None,
                )
        except SubmissionBlocked as exc:
            return Response(
                {'detail': 'Submission blocked by DQ gate', 'failures': exc.failures},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PolicyNotFound:
            return Response(
                {'detail': 'No workflow policy configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidTransition as exc:
            return Response(
                {'detail': f'Invalid transition: {exc}'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            CorrespondenceDetailSerializer(corr).data,
            status=status.HTTP_201_CREATED,
        )

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

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        corr = self.get_object()
        comment = self._comment(request) or None
        return self._transition(
            corr, request.user,
            lambda: fsm.acknowledge(corr, request.user, comment),
        )

    @action(detail=True, methods=['post'], url_path='review')
    def review(self, request, pk=None):
        corr = self.get_object()
        comment = self._comment(request) or None
        return self._transition(
            corr, request.user,
            lambda: fsm.review(corr, request.user, comment),
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

    @action(detail=True, methods=['post'], url_path='archive')
    def archive(self, request, pk=None):
        corr = self.get_object()
        return self._transition(
            corr, request.user, lambda: fsm.archive(corr, request.user),
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


class NotificationViewSet(viewsets.GenericViewSet):
    """In-app correspondence notifications, self-scoped to the calling user.

    ``notify`` writes ``Notification`` rows; this surface lets managers and
    requesters read them and mark them read. Notifications are never created
    through the API — only listed and read. The top-level ``unread_count``
    always reflects the caller's total unread notifications, independent of the
    ``is_read`` filter applied to the result set."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.select_related('correspondence').filter(
            user=self.request.user,
        )

    def _apply_is_read_filter(self, qs):
        is_read = self.request.query_params.get('is_read')
        if is_read is None:
            return qs
        if is_read.lower() in ('true', '1', 'yes'):
            return qs.filter(is_read=True)
        if is_read.lower() in ('false', '0', 'no'):
            return qs.filter(is_read=False)
        return qs

    def list(self, request):
        base_qs = self.get_queryset()
        unread_count = base_qs.filter(is_read=False).count()
        qs = self._apply_is_read_filter(base_qs)
        page = self.paginate_queryset(qs)
        if page is not None:
            response = self.get_paginated_response(
                NotificationSerializer(page, many=True).data,
            )
            response.data['unread_count'] = unread_count
            return response
        return Response({
            'unread_count': unread_count,
            'results': NotificationSerializer(qs, many=True).data,
        })

    @action(detail=True, methods=['post'], url_path='read')
    def read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({
            'updated': updated,
            'unread_count': 0,
        })
