"""Pulse Control Plane API (ADR-0036 Phases 2–6).

Mounted under ``/carbon-api/ai/pulse/control/``:

    GET  command/          — Command Center aggregates (health + queues + containment)
    GET  evidence/         — unified evidence spine by run_id / conversation_id
    POST containment/      — graduated containment (operator)
    GET  candidates/       — Learning Studio unified candidates
    POST pdp/dry-run/      — PDP dry-run (policy_owner / process_owner)
    GET|PATCH budget/      — Platform budget override (manage_console)

Containment + budget state live in :class:`PulseControlState` (one row per
instance). Every mutation writes :class:`AuditLog`.
"""

from __future__ import annotations

import logging
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import (
    AI_MANAGE_CONSOLE,
    AI_OPERATOR,
    AI_POLICY_OWNER,
    AI_PROCESS_OWNER,
    AI_VIEW_CONSOLE,
    has_any_capability,
)
from ai.audit_service import AuditService
from ai.instance_registry import resolve_instance_id
from ai.models.control_state import (
    CONTAINMENT_LEVELS,
    PulseControlState,
    get_or_create_control_state,
)
logger = logging.getLogger("carbon.ai.control_plane")


class _HasAnyCap(BasePermission):
    capability_keys: frozenset[str] = frozenset()
    message = "Missing required capability."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return has_any_capability(user, set(self.capability_keys))


class ControlReadPermission(_HasAnyCap):
    capability_keys = frozenset({AI_VIEW_CONSOLE.key, AI_PROCESS_OWNER.key})


class OperatorPermission(_HasAnyCap):
    capability_keys = frozenset({AI_OPERATOR.key, AI_PROCESS_OWNER.key, AI_MANAGE_CONSOLE.key})


class ManageConsolePermission(_HasAnyCap):
    capability_keys = frozenset({AI_MANAGE_CONSOLE.key})


class PolicyDryRunPermission(_HasAnyCap):
    capability_keys = frozenset(
        {AI_POLICY_OWNER.key, AI_PROCESS_OWNER.key, AI_MANAGE_CONSOLE.key}
    )


# ── Command Center ─────────────────────────────────────────────────────────


class CommandCenterView(APIView):
    """GET control/command/ — health + queue badges + containment + spend pulse."""

    permission_classes = [IsAuthenticated, ControlReadPermission]

    def get(self, request):
        instance_id = resolve_instance_id()
        state = get_or_create_control_state(instance_id)

        health = self._health(request)
        queues = self._queues(request)
        spend = self._spend(request, state)

        return Response(
            {
                "instance_id": instance_id,
                "health": health,
                "queues": queues,
                "containment": state.as_dict(),
                "spend": spend,
                "links": {
                    "inbox": "/admin/ai/evidence?tab=inbox",
                    "review": "/admin/ai/learning?tab=review",
                    "runs": "/admin/ai/evidence?tab=runs",
                    "domain": "/admin/ai/domain?tab=processes",
                    "platform": "/admin/ai/platform?tab=spend",
                },
            }
        )

    @staticmethod
    def _health(request) -> dict:
        try:
            from ai.ops_api import PulseHealthView

            # Reuse health payload without re-implementing probes.
            view = PulseHealthView()
            resp = view.get(request)
            return resp.data if hasattr(resp, "data") else {}
        except Exception as exc:  # noqa: BLE001
            logger.exception("command health probe failed")
            return {"healthy": False, "error": str(exc)}

    @staticmethod
    def _queues(request) -> dict:
        from ai.models.core import LearningOutcome, Run
        from ai.models.human_task import HumanTask
        from ai.models.process import STATUS_REVIEW, ProcessDefinition

        try:
            pending_tasks = HumanTask.objects.filter(status="pending").count()
        except Exception:  # noqa: BLE001
            pending_tasks = 0
        try:
            review_defs = (
                ProcessDefinition.objects.filter(status=STATUS_REVIEW)
                .values("process_id")
                .distinct()
                .count()
            )
        except Exception:  # noqa: BLE001
            review_defs = 0
        try:
            failing_runs = Run.objects.filter(
                Q(status__in=("failed", "error", "blocked", "killed"))
                | Q(kill_switched_at__isnull=False)
                | Q(budget_exceeded=True)
            ).count()
        except Exception:  # noqa: BLE001
            failing_runs = 0
        try:
            learning_queued = LearningOutcome.objects.filter(status="queued").count()
        except Exception:  # noqa: BLE001
            learning_queued = 0

        return {
            "inbox_pending": pending_tasks,
            "review_queue": review_defs,
            "failing_runs": failing_runs,
            "learning_candidates": learning_queued,
        }

    @staticmethod
    def _spend(request, state: PulseControlState) -> dict:
        try:
            from ai.engine.core.config import get_settings
            from ai.models.core import LLMCallLog
            from accounts.ai_scoping import scope_ai_queryset
            from django.db.models import Sum, Count

            settings = get_settings()
            env_budget = float(settings.LLM_DAILY_BUDGET_USD)
            budget = (
                float(state.daily_budget_usd)
                if state.daily_budget_usd is not None
                else env_budget
            )
            today = timezone.localdate()
            base = scope_ai_queryset(LLMCallLog.objects, request.user)
            agg = base.filter(created_at__date=today).aggregate(
                spent=Sum("cost_usd"), calls=Count("id")
            )
            spent = float(agg["spent"] or 0.0)
            return {
                "budget_usd": budget,
                "spent_today_usd": spent,
                "remaining_usd": max(0.0, budget - spent),
                "budget_exceeded": spent >= budget if budget > 0 else False,
                "calls_today": int(agg["calls"] or 0),
                "override_active": state.daily_budget_usd is not None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("command spend probe failed")
            return {"error": str(exc)}


# ── Evidence spine ─────────────────────────────────────────────────────────


class EvidenceExplorerView(APIView):
    """GET control/evidence/?run_id= | conversation_id=

    Unified timeline: run events + PDP decisions + human tasks + audit rows
    that reference the run.
    """

    permission_classes = [IsAuthenticated, ControlReadPermission]

    def get(self, request):
        run_id = (request.query_params.get("run_id") or "").strip()
        conversation_id = (request.query_params.get("conversation_id") or "").strip()
        if not run_id and not conversation_id:
            return Response(
                {"error": "invalid", "detail": "Provide run_id or conversation_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        events: list[dict] = []
        meta: dict = {"run_id": run_id or None, "conversation_id": conversation_id or None}

        if run_id:
            events.extend(self._run_events(request.user, run_id, meta))
            events.extend(self._pdp_events(run_id))
            events.extend(self._task_events(run_id))
            events.extend(self._audit_events(run_id))

        if conversation_id:
            events.extend(self._conversation_events(conversation_id))

        events.sort(key=lambda e: (e.get("t") or "", e.get("source") or ""))
        return Response({"meta": meta, "count": len(events), "events": events})

    @staticmethod
    def _run_events(user, run_id: str, meta: dict) -> list[dict]:
        try:
            from ai.durable_service import DurableExecutionService
            from ai.plans_service import PlanNotAccessibleError

            payload = DurableExecutionService().timeline(user, run_id)
            meta["run_status"] = payload.get("status")
            out = []
            for ev in payload.get("events") or []:
                out.append(
                    {
                        "t": ev.get("t"),
                        "source": "run",
                        "type": ev.get("type"),
                        "step_id": ev.get("step_id"),
                        "detail": ev.get("detail") or {},
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            meta["run_error"] = str(exc)
            return []

    @staticmethod
    def _pdp_events(run_id: str) -> list[dict]:
        from ai.models.pdp import PolicyDecisionRow

        rows = PolicyDecisionRow.objects.filter(
            Q(request_id=run_id)
            | Q(process_state__run_id=run_id)
            | Q(process_state__plan_id=run_id)
        ).order_by("created_at")[:200]
        out = []
        for row in rows:
            out.append(
                {
                    "t": row.created_at.isoformat() if row.created_at else None,
                    "source": "pdp",
                    "type": f"pdp_{row.decision}",
                    "detail": {
                        "decision": row.decision,
                        "reason": row.reason,
                        "action": row.action,
                        "principal": row.principal,
                        "policy_version": row.policy_version,
                        "autonomy": row.autonomy,
                        "stage": row.stage,
                    },
                }
            )
        return out

    @staticmethod
    def _task_events(run_id: str) -> list[dict]:
        from ai.models.human_task import HumanTask

        out = []
        for task in HumanTask.objects.filter(run_id=run_id).order_by("created_at")[:100]:
            out.append(
                {
                    "t": task.created_at.isoformat() if task.created_at else None,
                    "source": "inbox",
                    "type": f"task_{task.status}",
                    "detail": {
                        "task_id": task.id,
                        "step_id": task.step_id,
                        "status": task.status,
                        "decided_by": task.decided_by,
                        "decline_reason": task.decline_reason,
                    },
                }
            )
        return out

    @staticmethod
    def _audit_events(run_id: str) -> list[dict]:
        from ai.models.core import AuditLog

        qs = AuditLog.objects.filter(
            Q(detail__run_id=run_id)
            | Q(detail__plan_id=run_id)
            | Q(target=run_id)
        ).order_by("created_at")[:200]
        out = []
        for row in qs:
            out.append(
                {
                    "t": row.created_at.isoformat() if row.created_at else None,
                    "source": "audit",
                    "type": row.action,
                    "detail": {
                        "actor": row.actor,
                        "target": row.target,
                        "detail": row.detail,
                    },
                }
            )
        return out

    @staticmethod
    def _conversation_events(conversation_id: str) -> list[dict]:
        from ai.models.workspace import AIMessage

        out = []
        msgs = AIMessage.objects.filter(conversation_id=conversation_id).order_by(
            "created_at"
        )[:200]
        for msg in msgs:
            out.append(
                {
                    "t": msg.created_at.isoformat() if msg.created_at else None,
                    "source": "conversation",
                    "type": f"message_{getattr(msg, 'role', 'unknown')}",
                    "detail": {
                        "message_id": str(msg.pk),
                        "outcome": getattr(msg, "outcome", None),
                        "preview": (msg.content or "")[:240],
                    },
                }
            )
        return out


# ── Graduated containment ──────────────────────────────────────────────────


class ContainmentView(APIView):
    """POST control/containment/ — set graduated containment level.

    Body: ``{level, autonomy_ceiling?, reason?}``
    Levels: normal → autonomy_clamp → tool_freeze → learning_freeze → full_stop
    """

    permission_classes = [IsAuthenticated, OperatorPermission]

    def get(self, request):
        state = get_or_create_control_state(resolve_instance_id())
        return Response(state.as_dict())

    def post(self, request):
        level = (request.data.get("level") or "").strip()
        if level not in CONTAINMENT_LEVELS:
            return Response(
                {
                    "error": "invalid",
                    "detail": f"level must be one of {sorted(CONTAINMENT_LEVELS)}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = (request.data.get("reason") or "").strip()
        ceiling = (request.data.get("autonomy_ceiling") or "").strip() or None

        instance_id = resolve_instance_id()
        state = get_or_create_control_state(instance_id)
        prev = state.as_dict()

        state.containment_level = level
        state.learning_admissions_frozen = level in (
            "learning_freeze",
            "full_stop",
        )
        if ceiling:
            state.autonomy_ceiling = ceiling
        elif level == "autonomy_clamp" and not state.autonomy_ceiling:
            state.autonomy_ceiling = "act_confirm"
        elif level == "normal":
            state.autonomy_ceiling = ""
            state.learning_admissions_frozen = False
        if level == "full_stop":
            # Kill all active process definitions' kill_switch.
            self._kill_all_active(request.user)
        state.updated_by = request.user.username
        state.save()

        AuditService.log(
            action="ai.containment.set",
            actor=request.user.username,
            target=instance_id,
            detail={
                "from": prev,
                "to": state.as_dict(),
                "reason": reason,
            },
            host_user_id=str(request.user.pk),
            visibility="shared",
        )
        return Response(state.as_dict())

    @staticmethod
    def _kill_all_active(user) -> int:
        from ai.models.process import STATUS_ACTIVE, ProcessDefinition

        count = 0
        for obj in ProcessDefinition.objects.filter(status=STATUS_ACTIVE):
            doc = dict(obj.definition or {})
            if doc.get("kill_switch"):
                continue
            doc["kill_switch"] = True
            obj.definition = doc
            obj.save(update_fields=["definition", "updated_at"])
            count += 1
            AuditService.log(
                action="ai.process.kill_switch",
                actor=user.username,
                target=obj.process_id,
                detail={"enabled": True, "via": "containment.full_stop"},
                host_user_id=str(user.pk),
                visibility="shared",
            )
        return count


# ── Learning candidates ────────────────────────────────────────────────────


class LearningCandidatesView(APIView):
    """GET control/candidates/ — unified Learning Studio candidate list."""

    permission_classes = [IsAuthenticated, ControlReadPermission]

    def get(self, request):
        limit = min(int(request.query_params.get("limit") or 50), 200)
        items: list[dict] = []

        # Process definitions in review
        try:
            from ai.models.process import STATUS_REVIEW, ProcessDefinition

            for obj in ProcessDefinition.objects.filter(status=STATUS_REVIEW).order_by(
                "-updated_at"
            )[:limit]:
                items.append(
                    {
                        "kind": "process_review",
                        "id": obj.process_id,
                        "title": obj.process_id,
                        "status": obj.status,
                        "version": obj.version,
                        "owner": obj.owner,
                        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
                        "href": f"/admin/ai/learning?tab=review&process={obj.process_id}",
                    }
                )
        except Exception:  # noqa: BLE001
            logger.exception("candidates: process_review failed")

        # Skills pending gate
        try:
            from ai.models.core import Skill

            qs = Skill.objects.filter(
                Q(gate_status="pending") | Q(status="draft") | Q(gate_status="")
            ).order_by("-created_at")[:limit]
            for sk in qs:
                items.append(
                    {
                        "kind": "skill",
                        "id": sk.id,
                        "title": sk.name,
                        "status": sk.gate_status or sk.status,
                        "updated_at": (
                            sk.created_at.isoformat() if sk.created_at else None
                        ),
                        "href": "/admin/ai/assets?tab=skills",
                    }
                )
        except Exception:  # noqa: BLE001
            logger.exception("candidates: skills failed")

        # LearningOutcome queued
        try:
            from ai.models.core import LearningOutcome

            for lo in LearningOutcome.objects.filter(status="queued").order_by(
                "-created_at"
            )[:limit]:
                items.append(
                    {
                        "kind": "learning_outcome",
                        "id": lo.id,
                        "title": lo.pattern or lo.target or lo.id,
                        "status": lo.status,
                        "updated_at": (
                            lo.created_at.isoformat() if lo.created_at else None
                        ),
                        "href": "/admin/ai/learning?tab=candidates",
                        "detail": {
                            "pattern": lo.pattern,
                            "target": lo.target,
                            "run": getattr(lo, "run_id", None),
                        },
                    }
                )
        except Exception:  # noqa: BLE001
            logger.exception("candidates: learning_outcome failed")

        # DQ / KG review items needing review
        try:
            from ai.models.feedback import DqFeedbackEvent

            for ev in DqFeedbackEvent.objects.filter(needs_review=True).order_by(
                "-created_at"
            )[:limit]:
                items.append(
                    {
                        "kind": "dq_feedback",
                        "id": str(ev.pk),
                        "title": getattr(ev, "event_type", None) or str(ev.pk),
                        "status": "needs_review",
                        "updated_at": (
                            ev.created_at.isoformat()
                            if getattr(ev, "created_at", None)
                            else None
                        ),
                        "href": "/admin/ai/learning?tab=feedback",
                    }
                )
        except Exception:  # noqa: BLE001
            pass

        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return Response({"count": len(items), "results": items[:limit]})


# ── PDP dry-run ────────────────────────────────────────────────────────────


class PdpDryRunView(APIView):
    """POST control/pdp/dry-run/ — simulate PDP without executing.

    Body: ``{action, autonomy?, objects?, process_state?}``
    """

    permission_classes = [IsAuthenticated, PolicyDryRunPermission]

    def post(self, request):
        action = (request.data.get("action") or "").strip()
        if not action:
            return Response(
                {"error": "invalid", "detail": "action is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        autonomy = (request.data.get("autonomy") or "human_only").strip()
        objects = request.data.get("objects") or []
        process_state = request.data.get("process_state") or {}

        try:
            from asgiref.sync import async_to_sync

            from ai.pdp import PDP

            result = async_to_sync(PDP().decide)(
                principal=request.user.username,
                action=action,
                objects=objects if isinstance(objects, list) else [],
                autonomy=autonomy,
                process_state=process_state if isinstance(process_state, dict) else {},
                request_id="dry-run",
                instance_id=resolve_instance_id(),
                host_user_id=str(request.user.pk),
            )
            if isinstance(result, dict):
                raw = result.get("decision") or result.get("outcome") or ""
                decision_str = getattr(raw, "value", None) or str(raw)
                reason = str(result.get("reason") or "")
            else:
                decision_obj = getattr(result, "decision", result)
                decision_str = getattr(decision_obj, "value", None) or str(decision_obj)
                reason = getattr(result, "reason", "") or ""

            AuditService.log(
                action="ai.pdp.dry_run",
                actor=request.user.username,
                target=action,
                detail={
                    "decision": decision_str,
                    "reason": reason,
                    "autonomy": autonomy,
                    "dry_run": True,
                },
                host_user_id=str(request.user.pk),
                visibility="shared",
            )
            return Response(
                {
                    "dry_run": True,
                    "action": action,
                    "autonomy": autonomy,
                    "decision": decision_str,
                    "reason": reason,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("pdp dry-run failed")
            return Response(
                {"error": "pdp_unavailable", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


# ── Budget override ────────────────────────────────────────────────────────


class BudgetControlView(APIView):
    """GET|PATCH control/budget/ — Platform daily USD budget override."""

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), ControlReadPermission()]
        return [IsAuthenticated(), ManageConsolePermission()]

    def get(self, request):
        state = get_or_create_control_state(resolve_instance_id())
        cmd = CommandCenterView()
        spend = cmd._spend(request, state)
        return Response({"containment": state.as_dict(), "spend": spend})

    def patch(self, request):
        raw = request.data.get("daily_budget_usd", ...)
        state = get_or_create_control_state(resolve_instance_id())
        prev = state.daily_budget_usd

        if raw is None or raw == "":
            state.daily_budget_usd = None
        else:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return Response(
                    {"error": "invalid", "detail": "daily_budget_usd must be a number"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if value < 0:
                return Response(
                    {"error": "invalid", "detail": "daily_budget_usd must be >= 0"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            state.daily_budget_usd = value

        state.updated_by = request.user.username
        state.save()
        AuditService.log(
            action="ai.budget.override",
            actor=request.user.username,
            target=resolve_instance_id(),
            detail={"from": prev, "to": state.daily_budget_usd},
            host_user_id=str(request.user.pk),
            visibility="shared",
        )
        cmd = CommandCenterView()
        return Response(
            {
                "daily_budget_usd": state.daily_budget_usd,
                "spend": cmd._spend(request, state),
            }
        )
