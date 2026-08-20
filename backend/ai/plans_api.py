"""
Agentic Task Orchestration — plan REST API (Sprint 23 W3-A).

Endpoints (all owner-scoped, CBAC via ``host_user_id``):

    POST   /carbon-api/ai/plans/                      create (brief → pending_approval)
    GET    /carbon-api/ai/plans/                      list my plans
    GET    /carbon-api/ai/plans/{id}/                 plan detail + steps
    POST   /carbon-api/ai/plans/{id}/approve/         plan-level consent (RULE_21)
    POST   /carbon-api/ai/plans/{id}/decline/         decline a pending plan
    POST   /carbon-api/ai/plans/{id}/run/             SSE streamed run
    PATCH  /carbon-api/ai/plans/{id}/                 edit plan (replan + diff)
    PATCH  /carbon-api/ai/plans/{id}/steps/{step}/    edit a single plan step
    POST   /carbon-api/ai/plans/{id}/pause/           pause a running plan
    POST   /carbon-api/ai/plans/{id}/resume/          resume a paused plan (SSE)
    POST   /carbon-api/ai/plans/{id}/fork/            fork into a new reviewable plan
    POST   /carbon-api/ai/plans/{id}/steps/confirm/   confirm a paused consent step
    POST   /carbon-api/ai/plans/{id}/steps/decline/   decline a paused consent step
    POST   /carbon-api/ai/plans/{id}/stop/            cancel a run
    GET    /carbon-api/ai/plans/{id}/ledger/          audit ledger

No engine internals are touched — everything delegates to
:mod:`ai.plans_service`.
"""

from __future__ import annotations

import json

from django.http import StreamingHttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai.plans_service import (
    PlanNotAccessibleError,
    PlanNotRunnableError,
    PlanStepError,
    PlansService,
)

import logging

logger = logging.getLogger("carbon.ai.plans_api")


class PlanCreateSerializer(serializers.Serializer):
    brief = serializers.CharField(required=True, allow_blank=False, max_length=4000)
    conversation_id = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


class PlanConfirmSerializer(serializers.Serializer):
    step_id = serializers.IntegerField(required=True)


class PlanEditSerializer(serializers.Serializer):
    """PATCH /plans/{id}/ — new brief (+ optional step deltas).

    ``brief`` may be omitted to re-plan the existing brief while applying
    ``step_deltas``; the service keeps at least one of them meaningful.
    """

    brief = serializers.CharField(
        required=False, allow_blank=True, max_length=4000
    )
    step_deltas = serializers.ListField(
        child=serializers.DictField(), required=False
    )


class PlanStepEditSerializer(serializers.Serializer):
    """PATCH /plans/{id}/steps/{step}/ — ``title`` → intent, instructions,
    depends_on. All fields optional (PATCH semantics)."""

    title = serializers.CharField(required=False, allow_blank=True)
    instructions = serializers.CharField(required=False, allow_blank=True)
    depends_on = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )


class PlanViewSet(viewsets.GenericViewSet):
    """Agentic task orchestration — reviewable plan lifecycle."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service: PlansService | None = None

    @property
    def service(self) -> PlansService:
        if self._service is None:
            self._service = PlansService()
        return self._service

    # ── CRUD ──────────────────────────────────────────────────────────────

    def list(self, request):
        """List the requesting user's plans (newest first)."""
        limit = request.query_params.get("limit", 50)
        try:
            return Response(self.service.list_plans(request.user, limit=limit))
        except (ValueError, TypeError):
            return Response(
                {"error": "limit must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def create(self, request):
        """Create a reviewable plan from a brief — planning only, no execution."""
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plan = self.service.create_plan(
                request.user,
                brief=serializer.validated_data["brief"],
                conversation_id=serializer.validated_data.get("conversation_id", ""),
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(plan, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        """Fetch a plan + its steps."""
        try:
            return Response(self.service.get_plan(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

    def partial_update(self, request, pk=None):
        """Edit the plan brief → re-plan and return the diff for review.

        Editing never auto-approves (RULE_21): a non-pending plan drops to
        ``pending_approval`` and the response carries ``replan_gate``.
        """
        serializer = PlanEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.edit_plan(
                request.user,
                pk,
                brief=serializer.validated_data.get("brief"),
                step_deltas=serializer.validated_data.get("step_deltas"),
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except (PlanNotRunnableError, PlanStepError, ValueError) as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"steps/(?P<step_id>[^/.]+)",
        url_name="edit-plan-step",
    )
    def edit_step(self, request, pk=None, step_id=None):
        """Edit a single plan step (title/instructions/depends_on).

        Same diff-review rule as ``partial_update``: non-pending plans drop
        to ``pending_approval`` (RULE_21).
        """
        serializer = PlanStepEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.edit_step(
                request.user,
                pk,
                step_id,
                title=serializer.validated_data.get("title"),
                instructions=serializer.validated_data.get("instructions"),
                depends_on=serializer.validated_data.get("depends_on"),
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except (PlanNotRunnableError, PlanStepError, ValueError) as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result)

    # ── Plan-level consent ────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="approve", url_name="approve-plan")
    def approve(self, request, pk=None):
        """Approve a pending plan for execution (RULE_21 gate)."""
        try:
            return Response(self.service.approve_plan(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except PlanNotRunnableError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="decline", url_name="decline-plan")
    def decline(self, request, pk=None):
        """Decline a pending plan — nothing is executed."""
        try:
            return Response(self.service.decline_plan(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except PlanNotRunnableError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

    # ── W3-C: pause / resume / fork ───────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="pause", url_name="pause-plan")
    def pause(self, request, pk=None):
        """Pause a running plan (ledger-level; consent steps untouched)."""
        try:
            return Response(self.service.pause_plan(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except PlanNotRunnableError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="resume", url_name="resume-plan")
    def resume(self, request, pk=None):
        """Resume a paused/approved plan — re-enters ``run_plan_stream`` (SSE).

        Same frame protocol as ``run``; a non-runnable plan is a plain 400
        instead of an ``error`` frame.
        """
        try:
            self.service.resume_plan(request.user, pk)  # pre-flight gate
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except PlanNotRunnableError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

        def event_stream():
            try:
                for frame in self.service.run_plan_stream(request.user, pk):
                    yield f"data: {json.dumps(frame)}\n\n"
            except Exception as exc:  # noqa: BLE001 - never hang the stream
                logger.warning("plan resume stream failed plan=%s: %s", pk, exc)
                yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )

    @action(detail=True, methods=["post"], url_path="fork", url_name="fork-plan")
    def fork(self, request, pk=None):
        """Fork a plan into a new reviewable copy (``forked_from`` provenance)."""
        try:
            result = self.service.fork_plan(request.user, pk)
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(result, status=status.HTTP_201_CREATED)
    # ── Execution ─────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="run", url_name="run-plan")
    def run(self, request, pk=None):
        """Run an approved/paused plan as a Server-Sent Events stream.

        Frames::

            {"type": "plan_start"|"step_start"|"step_result"|
                    "step_confirm"|"step_end"|"done"|"error", ...}

        Terminal ``done`` carries ``status``: ``completed`` | ``paused`` |
        ``stopped`` | ``failed``.  Access errors surface as an ``error``
        frame (404-style) so the streaming client always terminates.
        """
        try:
            self.service.get_plan(request.user, pk)  # ownership check
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

        def event_stream():
            try:
                for frame in self.service.run_plan_stream(request.user, pk):
                    yield f"data: {json.dumps(frame)}\n\n"
            except Exception as exc:  # noqa: BLE001 - never hang the stream
                logger.warning("plan run stream failed plan=%s: %s", pk, exc)
                yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )

    # ── Step-level consent ────────────────────────────────────────────────

    @action(
        detail=True,
        methods=["post"],
        url_path="steps/confirm",
        url_name="confirm-plan-step",
    )
    def confirm_step(self, request, pk=None):
        """Confirm a paused consent step — executes the staged mutation."""
        serializer = PlanConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.confirm_step(
                request.user, pk, serializer.validated_data["step_id"]
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except (PlanNotRunnableError, PlanStepError) as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result)

    @action(
        detail=True,
        methods=["post"],
        url_path="steps/decline",
        url_name="decline-plan-step",
    )
    def decline_step(self, request, pk=None):
        """Decline a paused consent step — nothing is written."""
        serializer = PlanConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.decline_step(
                request.user, pk, serializer.validated_data["step_id"]
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except (PlanNotRunnableError, PlanStepError) as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result)

    # ── Stop / audit ──────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-plan")
    def stop(self, request, pk=None):
        """Request cancellation of a plan run (idempotent)."""
        try:
            return Response(self.service.stop_plan(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["get"], url_path="ledger", url_name="plan-ledger")
    def ledger(self, request, pk=None):
        """Audit ledger: steps, confirmations, replans, latency, tokens,
        provenance, actor."""
        try:
            return Response(self.service.get_ledger(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
