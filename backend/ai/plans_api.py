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
    GET    /carbon-api/ai/plans/{id}/qos/             acceptance QoS report (W4-D/25-C)
    GET    /carbon-api/ai/plans/{id}/flight/          supervision state (W4-D/25-C)

No engine internals are touched — everything delegates to
:mod:`ai.plans_service`.
"""

from __future__ import annotations

import json

from django.http import FileResponse, StreamingHttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai.plans_service import (
    PlanForbiddenError,
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
    # W5-B: when true, start in guided-discovery mode (Pulse asks first)
    # instead of immediately decomposing into a plan.
    discovery_mode = serializers.BooleanField(required=False, default=False)


class PlanDiscoverSerializer(serializers.Serializer):
    """POST /plans/{id}/discover/ — the user's reply to Pulse's question."""

    reply = serializers.CharField(required=True, allow_blank=False, max_length=4000)


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


class PlanTemplateSerializer(serializers.Serializer):
    """POST /plans/{id}/promote-template/ — name + optional description."""

    name = serializers.CharField(required=True, allow_blank=False, max_length=200)
    description = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


class ScheduleCreateSerializer(serializers.Serializer):
    """POST /plans/schedules/ — recurring ``cron_expr`` or one-off ``run_at``.

    ``template_id`` (an owned template) or a ``plan_json`` snapshot supplies
    the plan shape; exactly one of ``cron_expr`` / ``run_at`` is required.
    """

    name = serializers.CharField(required=True, allow_blank=False, max_length=200)
    description = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    template_id = serializers.CharField(required=False, allow_blank=True)
    plan_json = serializers.DictField(required=False)
    cron_expr = serializers.CharField(required=False, allow_blank=True)
    run_at = serializers.DateTimeField(required=False)


class ScheduleEditSerializer(serializers.Serializer):
    """PATCH /plans/schedules/{id}/ — all fields optional (PATCH semantics)."""

    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    cron_expr = serializers.CharField(required=False, allow_blank=True)
    run_at = serializers.DateTimeField(required=False)


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
        """Create a reviewable plan from a brief — planning only, no execution.

        W5-B: with ``discovery_mode=True`` the brief opens a guided discovery
        conversation instead (Pulse asks clarifying questions before planning).
        """
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            if serializer.validated_data.get("discovery_mode"):
                plan = self.service.start_discovery(
                    request.user,
                    brief=serializer.validated_data["brief"],
                    conversation_id=serializer.validated_data.get(
                        "conversation_id", ""
                    ),
                )
            else:
                plan = self.service.create_plan(
                    request.user,
                    brief=serializer.validated_data["brief"],
                    conversation_id=serializer.validated_data.get(
                        "conversation_id", ""
                    ),
                )
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(plan, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path="discover",
        url_name="advance-discovery",
    )
    def advance_discovery(self, request, pk=None):
        """Advance a guided discovery conversation by one user reply (W5-B)."""
        serializer = PlanDiscoverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.advance_discovery(
                request.user,
                pk,
                user_reply=serializer.validated_data["reply"],
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except (PlanNotRunnableError, ValueError) as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result)

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

    def destroy(self, request, pk=None):
        """DELETE /plans/{id}/ — hard-delete a cancelled/failed/completed plan."""
        try:
            result = self.service.delete_plan(request.user, pk)
        except PlanNotAccessibleError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except PlanNotRunnableError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)

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

    # ── W3-D: plan templates (Gap #3) ─────────────────────────────────────

    def list_templates(self, request):
        """GET /plans/templates/ — list the requesting user's templates."""
        return Response(self.service.list_templates(request.user))

    def promote_template(self, request, pk=None):
        """POST /plans/{id}/promote-template/ — save a plan shape as a template."""
        serializer = PlanTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.promote_template(
                request.user,
                pk,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result, status=status.HTTP_201_CREATED)

    def instantiate_template(self, request, template_id=None):
        """POST /plans/templates/{id}/instantiate/ — new reviewable plan."""
        try:
            result = self.service.create_from_template(
                request.user, template_id
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(result, status=status.HTTP_201_CREATED)

    # ── W6-E F-29: scheduling ─────────────────────────────────────────────

    def list_schedules(self, request):
        """GET /plans/schedules/ — the requesting user's schedules, soonest first."""
        return Response(self.service.list_schedules(request.user))

    def create_schedule(self, request):
        """POST /plans/schedules/ — create a recurring/one-off schedule."""
        serializer = ScheduleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.create_schedule(
                request.user,
                serializer.validated_data["name"],
                template_id=serializer.validated_data.get("template_id"),
                plan_json=serializer.validated_data.get("plan_json"),
                cron_expr=serializer.validated_data.get("cron_expr"),
                run_at=serializer.validated_data.get("run_at"),
                description=serializer.validated_data.get("description"),
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result, status=status.HTTP_201_CREATED)

    def edit_schedule(self, request, schedule_id=None):
        """PATCH /plans/schedules/{id}/ — edit name/description/trigger."""
        serializer = ScheduleEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.service.edit_schedule(
                request.user,
                schedule_id,
                name=serializer.validated_data.get("name"),
                description=serializer.validated_data.get("description"),
                cron_expr=serializer.validated_data.get("cron_expr"),
                run_at=serializer.validated_data.get("run_at"),
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result)

    def delete_schedule(self, request, schedule_id=None):
        """DELETE /plans/schedules/{id}/ — delete an owned schedule."""
        try:
            return Response(self.service.delete_schedule(request.user, schedule_id))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

    def pause_schedule(self, request, schedule_id=None):
        """POST /plans/schedules/{id}/pause/ — toggle ``enabled`` (no deletion)."""
        try:
            return Response(self.service.pause_schedule(request.user, schedule_id))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

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

    # ── W4-D/25-C: QoS + supervision ─────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="qos", url_name="plan-qos")
    def qos(self, request, pk=None):
        """Acceptance QoS report for a plan (owner-scoped).

        Returns ``{"report": {status, requirements[], metrics,
        final_response, supervision}}`` — outcome copy only (RULE_23).
        """
        try:
            return Response(self.service.get_qos_report(request.user, pk))
        except PlanForbiddenError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_403_FORBIDDEN
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["get"], url_path="flight", url_name="plan-flight")
    def flight(self, request, pk=None):
        """Supervision state for a plan (owner-scoped).

        Returns ``{"supervision": {ledger, repairs, escalations, fidelity,
        contract}}`` from ``working_notes.flight``.
        """
        try:
            return Response(self.service.get_flight_state(request.user, pk))
        except PlanForbiddenError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_403_FORBIDDEN
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

    # ── W5-C: artifact delivery ───────────────────────────────────────────

    @action(
        detail=True,
        methods=["get"],
        url_path="artifacts",
        url_name="list-plan-artifacts",
    )
    def list_artifacts(self, request, pk=None):
        """List the artifacts a plan produced (owner-scoped)."""
        try:
            return Response(self.service.list_artifacts(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )

    @action(
        detail=True,
        methods=["get"],
        url_path=r"artifacts/(?P<artifact_id>[^/.]+)/download",
        url_name="download-plan-artifact",
    )
    def download_artifact(self, request, pk=None, artifact_id=None):
        """Stream an artifact file as an attachment (owner-scoped)."""
        try:
            artifact = self.service.get_artifact(
                request.user, pk, artifact_id
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        response = FileResponse(
            artifact.file.open("rb"),
            as_attachment=True,
            filename=artifact.name,
            content_type=artifact.mime_type
            or "application/octet-stream",
        )
        return response
