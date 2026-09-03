"""
CarbonIntelligence — Single entry point for all AI calls in Carbon.

Wave C. Bridges Carbon ORM objects and the protocol's typed dataclasses.
All Carbon code calls CarbonIntelligence — never a specific provider
directly. The engine is wired in-process (Phase 2); there is no runtime
provider swap and no HTTP transport.

Two modes:
  Sync  — calls AIProvider ABC methods, returns typed responses.
  Async — dispatches tasks in-process via ai.engine_runtime, returns task_id
          dicts for the DQ job system (nl_check, suggest, anomaly jobs).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import timedelta
from typing import Any

from django.db import models
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from ai.engine_runtime import dispatch_task, get_task
from ai.audit_service import AuditService
from ai.protocol import (
    AIProvider,
    AnomalyDetectRequest,
    ChatRequest,
    ConversationContext,
    DqRuleInput,
    DqSuggestRequest,
    DqValidateRequest,
    DqValidateResponse,
    NlQueryRequest,
    ProviderStatus,
    ReportDraftRequest,
    Scope,
    TableProfile,
    WorkspaceContext,
)
from ai.providers.pulse import PulseProvider
from ai.domain_protocol import DomainContext, get_domain, has_domain
from ai.domain import emissions  # noqa: F401  (registers the emissions domain)
from ai.domain import water  # noqa: F401  (registers the water domain)
from ai.context_assembler import assemble_context
from ai.adapter.contract import HostAdapterContract
from ai.engine.llm.provider import classify_llm_error
from ai.generation_registry import GENERATIONS
from ai.usage_service import QuotaExceededError
from accounts.capabilities import has_capability
from accounts.constants import VISIBILITY_ROLES
from accounts.rbac_utils import get_allowed_org_unit_ids, user_is_global_admin

logger = logging.getLogger("carbon.ai.intelligence")


class NotAssistantMessageError(ValueError):
    """Feedback can only target assistant messages (client error, not a 404)."""


class NotUserMessageError(ValueError):
    """Only user messages can be edited (client error, not a 404)."""


# ── Scope builder ─────────────────────────────────────────────────────────


def build_scope(user) -> Scope:
    """Extract a Scope from a Django User (RBAC-aware).

    Called by every CarbonIntelligence method that takes a user.  The
    Scope is injected into every AIProvider request so the provider
    can enforce data-access boundaries.
    """
    from accounts.constants import READ_ONLY_ROLES
    from accounts.models import ScopedRole

    org_unit_ids: list[str] = []
    module_ids: list[str] = []
    is_read_only = True

    if user is None or not user.is_authenticated:
        return Scope()

    if user.is_superuser:
        return Scope(
            is_superuser=True,
            org_unit_ids=["*"],
            user_identifier=str(user.pk),
            active_apps=_active_apps_for_user(user),
        )

    if user.is_staff:
        is_read_only = False

    roles = ScopedRole.objects.filter(user=user, is_active=True).select_related(
        "org_unit", "module", "group"
    )

    for role in roles:
        if role.org_unit_id and str(role.org_unit_id) not in org_unit_ids:
            org_unit_ids.append(str(role.org_unit_id))
        if role.module_id and str(role.module_id) not in module_ids:
            module_ids.append(str(role.module_id))
        # Read-only is derived from the group name (ScopedRole has no is_read_only
        # column). A single write-capable role flips the user out of read-only.
        if role.group.name not in READ_ONLY_ROLES:
            is_read_only = False

    return Scope(
        org_unit_ids=org_unit_ids,
        module_ids=module_ids,
        is_read_only=is_read_only,
        user_identifier=str(user.pk),
        active_apps=_active_apps_for_user(user),
    )


def _active_apps_for_user(user) -> list[str]:
    """App Registry §7.5 — active apps the user can reach.

    Returns slugs of AppManifests that are BOTH runtime-activated AND
    capability-gated for this user. Superusers pass every capability via
    the "*" wildcard, so they see every activated app.
    """
    from appregistry.models import AppActivation, AppManifest

    activated = (
        AppActivation.objects.filter(is_active=True)
        .select_related("app")
        .values_list("app__slug", "app__required_capabilities")
    )
    if user.is_superuser:
        return [slug for slug, _ in activated]

    result: list[str] = []
    for slug, required_capabilities in activated:
        # No capability gate → any authenticated user can reach the app.
        if not required_capabilities or has_capability(
            user, required_capabilities[0]
        ):
            result.append(slug)
    return result


# ── CarbonIntelligence ───────────────────────────────────────────────────


class CarbonIntelligence:
    """Single entry point for all AI calls in Carbon.

    Usage::

        intelligence = CarbonIntelligence()
        result = intelligence.validate_dq_rule(rule, rows, user=request.user)

    The provider is the in-process PulseProvider (the vendored engine).
    """

    def __init__(self, adapter: HostAdapterContract | None = None) -> None:
        self._provider: AIProvider | None = None
        if adapter is None:
            from ai.adapter.carbon import CarbonHostAdapter

            adapter = CarbonHostAdapter()
        self.adapter = adapter

    # ── Provider access ────────────────────────────────────────────────

    @property
    def provider(self) -> AIProvider:
        """Lazy-instantiate the in-process PulseProvider."""
        if self._provider is None:
            self._provider = PulseProvider()
        return self._provider

    # ── Health ─────────────────────────────────────────────────────────

    def health_check(self) -> ProviderStatus:
        return self.provider.health_check()

    # ── Sync: DQ Validate ──────────────────────────────────────────────

    def validate_dq_rule(
        self,
        rule,
        rows: list[dict[str, Any]],
        user=None,
        context: dict[str, Any] | None = None,
    ) -> DqValidateResponse:
        """Validate a DQRule against rows.

        Args:
            rule: DQRule model instance
            rows: list of {field_name: value} dicts
            user: Django User for scope
            context: optional dict with table_name, row_count_hint, etc.
        """
        prompt = _extract_prompt(rule)
        scope = build_scope(user)

        request = DqValidateRequest(
            rules=[
                DqRuleInput(
                    id=str(rule.pk),
                    prompt=prompt,
                    fields=_rule_fields(rule),
                    severity=rule.severity or "error",
                )
            ],
            rows=rows,
            context=context or {},
            scope=scope,
        )
        return self.provider.validate_dq(request)

    # ── Async: Submit DQ Validate (for DQ job system) ──────────────────

    def submit_dq_validate(
        self,
        rules: list[dict[str, Any]],
        rows: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit a dq.validate task and return immediately.

        Returns the raw Pulse response dict (may be ``status: completed``
        or ``status: pending``).  Callers poll ``get_task_status()``.
        """
        mapped_rules = [
            {
                "id": str(r.get("id", "")),
                "prompt": r.get("prompt", ""),
                "fields": r.get("fields", []),
                "severity": r.get("severity", "error"),
            }
            for r in rules
        ]
        payload = {
            "rules": mapped_rules,
            "rows": rows,
            "context": context or {},
        }
        return dispatch_task(
            task_type="dq.validate",
            payload=payload,
            timeout=30,
        )

    # ── Async: Submit DQ Suggest ────────────────────────────────────────

    def submit_dq_suggest(self, table_payload: dict[str, Any]) -> dict[str, Any]:
        """Submit a dq.suggest task and return immediately."""
        return dispatch_task(
            task_type="dq.suggest",
            payload={"table": table_payload},
            timeout=60,
        )

    # ── Async: Submit Anomaly Detect ─────────────────────────────────────

    def submit_anomaly_detect(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit an anomaly.detect task and return immediately."""
        return dispatch_task(
            task_type="anomaly.detect",
            payload={"profile": payload},
            timeout=120,
        )

    # ── Task status polling ──────────────────────────────────────────────

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Retrieve an in-process task's current status.

        Returns a raw dict or ``{status: pulse_unavailable, error: {...}}``.
        """
        return get_task(task_id, timeout=10)

    # ── Workspace: Conversation management ────────────────────────────

    def create_conversation(
        self,
        user,
        conversation_type: str,
        title: str = "",
        app_identifier: str | None = None,
        task_payload: dict[str, Any] | None = None,
        workspace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation.

        ``workspace_context`` (optional, additive) is merged into
        ``task_payload_json`` under the ``workspace_context`` key
        (AI CONTRACT §11.2).

        Returns a serialized dict of the AIConversation.
        """
        from ai.models import AIConversation

        scope = build_scope(user)
        scope_json = scope.to_dict() if scope else {}

        stored_payload = dict(task_payload or {})
        if workspace_context:
            stored_payload["workspace_context"] = workspace_context

        conversation = AIConversation.objects.create(
            user=user,
            conversation_type=conversation_type,
            title=title or _default_title(conversation_type),
            app_identifier=app_identifier,
            status="pending",
            scope_json=scope_json,
            task_payload_json=stored_payload,
        )

        self._seed_intent_aware_opener(conversation, workspace_context)

        return _serialize_conversation(conversation)

    def _enforce_quota(self, user) -> dict[str, Any]:
        """Request-time quota gate (Phase 21-A).

        Returns the quota snapshot when the user is within budget; raises
        :class:`QuotaExceededError` (``.code == "quota"``) when the monthly
        token budget is exhausted.  Never mutates state.
        """
        from ai.usage_service import AIUsage

        return AIUsage(user).check_quota()

    def send_message(
        self,
        user,
        conversation_id: str,
        content: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Send a user message and get AI response.

        1. Load conversation + messages from DB
        2. Build ConversationContext from message history
        3. Build fresh Scope from user
        4. Route to provider based on conversation_type
        5. Save both user message and AI response
        6. Detect needs_input state
        """
        from ai.models import AIConversation, AIMessage

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        # Normalize a blank/whitespace message to a greeting so the assistant
        # still responds helpfully (the serializer allows blank; a raw API caller
        # might send one even though the UI never does).
        content = (content or "").strip() or "Hello"

        # Phase 21-A — request-time quota gate (before any user message is saved).
        self._enforce_quota(user)

        # Phase 22-A — resolve durable preferences (profile → domain manifest)
        # for this turn.  The per-message ``model`` param still wins: it is the
        # highest tier of the resolution order.
        profile = self._user_preferences(user)
        resolved_model = self._resolve_preferred_model(
            user, model, conversation.app_identifier,
        )
        resolved_temperature = self._resolve_preferred_temperature(user)

        # Auto-title from the first user message while the title is still default.
        self._maybe_autotitle(
            conversation, content,
            enabled=profile.auto_title if profile is not None else True,
        )

        # Save user message
        user_msg = AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=content,
        )
        # Phase 19-A — thread linkage + context signature for this turn.
        conversation._turn_parent_id = user_msg.id

        # Build fresh scope (NOT frozen — user's permissions may have changed)
        scope = build_scope(user)
        if conversation.app_identifier:
            scope.app_identifier = conversation.app_identifier

        # Assemble tiered, budgeted context from history (Sprint 15).
        history = list(
            conversation.messages.order_by("created_at").values(
                "id", "role", "content", "created_at", "is_deleted",
            )
        )
        assembled = assemble_context(
            conversation, history, scope, model=resolved_model, adapter=self.adapter,
        )
        conversation._turn_context_signature = assembled["context_signature"]
        conv_ctx = ConversationContext(
            conversation_id=str(conversation.id),
            messages=assembled["messages"],
        )

        # Persist the context budget telemetry snapshot + retrieved KG entities.
        conversation.context_snapshot_json = {
            **assembled["budget"],
            "kg_entities": assembled["kg_entities"],
        }
        conversation.save(update_fields=["context_snapshot_json"])

        # Mark working
        conversation.status = "working"
        conversation.save(update_fields=["status"])

        # Route to provider based on conversation type.
        try:
            response = self._route_typed_message(
                conversation, content, conv_ctx, scope,
                resolved_model, resolved_temperature,
            )
        except (PermissionError, ValueError) as exc:
            response = self._save_assistant_message(
                conversation,
                str(exc),
                metadata={},
                status="failed",
            )
            raise

        return {
            "conversation": _serialize_conversation(conversation),
            "user_message": _serialize_message(user_msg),
            "assistant_message": response,
        }

    def send_message_stream(
        self,
        user,
        conversation_id: str,
        content: str,
        model: str | None = None,
    ):
        """Stream an answer as a generator of SSE-ready dict frames.

        Mirrors :meth:`send_message` for persistence and finalization.  For
        ``conversation_type == "chat"`` it streams provider deltas; for every
        other type it emits ``progress`` frames around the blocking sync
        dispatch (replacing the old 2s frontend poll).  Yields:

          {"type": "chunk", "content": delta}          (chat only)
          {"type": "progress", "stage": ..., "message": ...}  (non-chat only)
          {"type": "done", "conversation": {...}}
          {"type": "stopped", "conversation": {...}}
          {"type": "error", "error": message}

        A user message is always persisted and the conversation is never left
        stuck in ``working``.
        """
        from ai.models import AIConversation, AIMessage, AIGeneration

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        # Phase 21-A — request-time quota gate.  Emit a "quota" error frame
        # before any user message is persisted or a generation is created.
        try:
            self._enforce_quota(user)
        except QuotaExceededError as exc:
            yield {
                "type": "error",
                "error": str(exc),
                "error_code": "quota",
                "quota": exc.quota,
            }
            return

        conv_id = str(conversation.id)
        GENERATIONS.start(conv_id)
        generation = AIGeneration.objects.create(
            conversation=conversation,
            token=uuid.uuid4().hex,
            status="running",
        )

        def _finalize_generation(
            final_status: str, usage: dict[str, Any] | None = None
        ) -> None:
            generation.status = final_status
            update_fields = ["status"]
            if final_status == "cancelled":
                generation.cancelled_at = timezone.now()
                update_fields.append("cancelled_at")
            if final_status == "completed":
                generation.completed_at = timezone.now()
                update_fields.append("completed_at")
                update_fields += self._populate_generation_usage(generation, usage)
            generation.save(update_fields=update_fields)

        conv_type = conversation.conversation_type

        try:
            # Phase 22-A — resolve durable preferences (profile → domain
            # manifest) for this turn; the per-message ``model`` param wins.
            profile = self._user_preferences(user)
            resolved_model = self._resolve_preferred_model(
                user, model, conversation.app_identifier,
            )
            resolved_temperature = self._resolve_preferred_temperature(user)

            # Save user message (identical to send_message).
            self._maybe_autotitle(
                conversation, content,
                enabled=profile.auto_title if profile is not None else True,
            )
            user_msg = AIMessage.objects.create(
                conversation=conversation,
                role="user",
                content=content,
            )
            # Phase 19-A — thread linkage + context signature for this turn.
            conversation._turn_parent_id = user_msg.id

            # Build fresh scope (NOT frozen — user's permissions may have changed).
            scope = build_scope(user)
            if conversation.app_identifier:
                scope.app_identifier = conversation.app_identifier

            # Assemble tiered, budgeted context from history (Sprint 15).
            history = list(
                conversation.messages.order_by("created_at").values(
                    "id", "role", "content", "created_at", "is_deleted",
                )
            )
            assembled = assemble_context(
                conversation, history, scope, model=resolved_model, adapter=self.adapter,
            )
            conversation._turn_context_signature = assembled["context_signature"]
            conv_ctx = ConversationContext(
                conversation_id=conv_id,
                messages=assembled["messages"],
            )

            # Persist the context budget telemetry snapshot + retrieved KG entities.
            conversation.context_snapshot_json = {
                **assembled["budget"],
                "kg_entities": assembled["kg_entities"],
            }
            conversation.save(update_fields=["context_snapshot_json"])

            # Mark working.
            conversation.status = "working"
            conversation.save(update_fields=["status"])

            if conv_type == "chat":
                started_at = time.perf_counter()
                guard_chain, operation = self._guard_workspace_operation(
                    scope,
                    "workspace_chat",
                    conversation.task_payload_json or {},
                )
                message = self._prepend_workspace_context(conversation, content)
                message = self._prepend_domain_context(scope, message)
                chat_request = ChatRequest(
                    message=message,
                    conversation=conv_ctx,
                    scope=scope,
                    model=resolved_model,
                    temperature=resolved_temperature,
                )

                partial_parts: list[str] = []
                for frame in self.provider.chat_stream(chat_request):
                    kind = frame[0]
                    value = frame[1] if len(frame) > 1 else None
                    meta = frame[2] if len(frame) > 2 else {}
                    if GENERATIONS.is_cancelled(conv_id):
                        self._save_assistant_message(
                            conversation,
                            "".join(partial_parts),
                            metadata={},
                            status="completed",
                            message_status="stopped",
                        )
                        _finalize_generation("cancelled")
                        yield {
                            "type": "stopped",
                            "conversation": self.get_conversation(user, conv_id),
                        }
                        return
                    if kind == "chunk":
                        partial_parts.append(value)
                        yield {"type": "chunk", "content": value}
                        continue
                    if kind == "error":
                        latency_ms = int((time.perf_counter() - started_at) * 1000)
                        guard_chain.audit_trail.log(
                            scope,
                            operation,
                            self.provider.provider_name,
                            latency_ms,
                            "failed",
                            error_message=value,
                        )
                        user_message = "I couldn't reach the AI service — try again in a moment."
                        self._save_assistant_message(
                            conversation,
                            user_message,
                            metadata={},
                            status="failed",
                            message_status="failed",
                        )
                        _finalize_generation("failed")
                        yield {
                            "type": "error",
                            "error": user_message,
                            "error_kind": meta.get("error_kind", "permanent"),
                        }
                        return
                    if kind == "done":
                        latency_ms = int((time.perf_counter() - started_at) * 1000)
                        result = value or {}
                        res = result.get("result") or {}
                        guard_chain.audit_trail.log(
                            scope,
                            operation,
                            self.provider.provider_name,
                            latency_ms,
                            result.get("status", "completed"),
                        )
                        usage = self._extract_chat_usage(res, latency_ms)
                        self._build_ai_message(
                            conversation,
                            "completed",
                            res.get("content"),
                            res.get("follow_up_questions", []),
                            usage=usage,
                            actions=res.get("actions"),
                            pending_actions=res.get("pending_actions"),
                            tool_trace=res.get("tool_trace"),
                            external_sources=res.get("external_sources"),
                            code_result=res.get("code_result"),
                        )
                        _finalize_generation("completed", usage)
                        done_frame = {
                            "type": "done",
                            "conversation": self.get_conversation(user, conv_id),
                        }
                        if usage:
                            done_frame["usage"] = usage
                        # Phase H1-B — append-only audit trail: record each
                        # completed tool call (RULE_21 — recording only).
                        for _tool in (res.get("tool_trace") or []):
                            _tool_id = _tool.get("tool_id") or _tool.get("tool_name")
                            if not _tool_id:
                                continue
                            AuditService.log(
                                action="ai.tool_call",
                                actor=user.pk,
                                host_user_id=str(user.pk),
                                target=str(_tool_id),
                                detail={
                                    "tool_id": _tool_id,
                                    "duration_ms": _tool.get("duration_ms"),
                                },
                            )
                        yield done_frame
                        return
            else:
                # Non-chat: server-driven progress streaming around the
                # blocking sync dispatch (the old 2s poll replacement).
                yield {
                    "type": "progress",
                    "stage": "start",
                    "message": self._progress_stage_label(conv_type),
                }

                if GENERATIONS.is_cancelled(conv_id):
                    self._save_assistant_message(
                        conversation,
                        "Interrupted by user.",
                        metadata={},
                        status="completed",
                        message_status="stopped",
                    )
                    _finalize_generation("cancelled")
                    yield {
                        "type": "stopped",
                        "conversation": self.get_conversation(user, conv_id),
                    }
                    return

                self._route_typed_message(
                    conversation, content, conv_ctx, scope,
                    resolved_model, resolved_temperature,
                )

                if GENERATIONS.is_cancelled(conv_id):
                    self._save_assistant_message(
                        conversation,
                        "Interrupted by user.",
                        metadata={},
                        status="completed",
                        message_status="stopped",
                    )
                    _finalize_generation("cancelled")
                    yield {
                        "type": "stopped",
                        "conversation": self.get_conversation(user, conv_id),
                    }
                    return

                yield {"type": "progress", "stage": "done", "message": "Done"}
                _finalize_generation("completed")
                yield {
                    "type": "done",
                    "conversation": self.get_conversation(user, conv_id),
                }
                return
        except (PermissionError, ValueError) as exc:
            self._save_assistant_message(
                conversation,
                str(exc),
                metadata={},
                status="failed",
                message_status="failed",
            )
            _finalize_generation("failed")
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible, never stuck in working
            logger.exception("%s failed for conversation=%s", conv_type, conv_id)
            user_message = "I couldn't reach the AI service — try again in a moment."
            self._save_assistant_message(
                conversation,
                user_message,
                metadata={},
                status="failed",
                message_status="failed",
            )
            _finalize_generation("failed")
            yield {
                "type": "error",
                "error": user_message,
                "error_kind": classify_llm_error(exc),
            }
            return
        finally:
            GENERATIONS.finish(conv_id)

    def run_agent_action_stream(
        self,
        user,
        conversation_id: str,
        *,
        action_type: str,
        tool: str | None = None,
        agent: str | None = None,
        args: dict | None = None,
        verbosity: str = "concise",
    ):
        """Stream a user-initiated agent/tool action run (Sprint W1-A).

        Mirrors :meth:`send_message_stream` for persistence and finalization —
        quota gate, AIGeneration lifecycle, user message, ``working`` marker,
        guard chain, provider action frames, terminal frame.  The
        conversation is never left stuck in ``working``.

        Yields:
          {"type": "turn_start"|"tool_start"|"tool_arg"|"tool_result"|"tool_end"|"turn_end", ...}
          {"type": "done", "conversation": {...}}
          {"type": "stopped", "conversation": {...}}
          {"type": "error", "error": message, ...}

        Cancellation (``GENERATIONS.cancel`` via the existing ``stop``
        endpoint) surfaces as a ``stopped`` ``turn_end`` frame and a
        ``{"type": "stopped", ...}`` terminal — never an ``error`` frame.
        """
        from ai.models import AIConversation, AIMessage, AIGeneration

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        try:
            self._enforce_quota(user)
        except QuotaExceededError as exc:
            yield {
                "type": "error",
                "error": str(exc),
                "error_code": "quota",
                "quota": exc.quota,
            }
            return

        conv_id = str(conversation.id)
        GENERATIONS.start(conv_id)
        generation = AIGeneration.objects.create(
            conversation=conversation,
            token=uuid.uuid4().hex,
            status="running",
        )

        def _finalize_generation(
            final_status: str, usage: dict[str, Any] | None = None
        ) -> None:
            generation.status = final_status
            update_fields = ["status"]
            if final_status == "cancelled":
                generation.cancelled_at = timezone.now()
                update_fields.append("cancelled_at")
            if final_status == "completed":
                generation.completed_at = timezone.now()
                update_fields.append("completed_at")
                update_fields += self._populate_generation_usage(generation, usage)
            generation.save(update_fields=update_fields)

        started_at = time.perf_counter()
        try:
            # Human-readable, outcome-oriented label (RULE_23 — never engine
            # class names or transport details in user-facing copy).
            if action_type == "agent":
                action_label = f"Run agent {agent}" if agent else "Run agent"
            else:
                action_label = f"Run tool {tool}" if tool else "Run tool"

            # Persist the user message + mark working (identical to send path).
            profile = self._user_preferences(user)
            self._maybe_autotitle(
                conversation,
                action_label,
                enabled=profile.auto_title if profile is not None else True,
            )
            user_msg = AIMessage.objects.create(
                conversation=conversation,
                role="user",
                content=action_label,
            )
            conversation._turn_parent_id = user_msg.id

            # Fresh scope (not frozen — permissions may have changed).
            scope = build_scope(user)
            if conversation.app_identifier:
                scope.app_identifier = conversation.app_identifier

            conversation.status = "working"
            conversation.save(update_fields=["status"])

            # CBAC guard chain — scope validity + data isolation; host
            # mutations stay staged via RULE_21, never auto-run here.
            guard_chain, operation = self._guard_workspace_operation(
                scope,
                "workspace_action_run",
                args or {},
            )

            run_status = "completed"
            for kind, value, *rest in self.provider.run_tool_stream(
                conversation_id=conv_id,
                action_type=action_type,
                tool=tool,
                agent=agent,
                args=args or {},
                verbosity=verbosity,
                host_user_id=str(user.pk),
            ):
                if kind == "frame":
                    if isinstance(value, dict) and value.get("type") == "turn_end":
                        run_status = value.get("status", run_status)
                    yield value
                    continue

                if kind == "error":
                    latency_ms = int((time.perf_counter() - started_at) * 1000)
                    guard_chain.audit_trail.log(
                        scope,
                        operation,
                        self.provider.provider_name,
                        latency_ms,
                        "failed",
                        error_message=value,
                    )
                    user_message = "I couldn't run that action — try again in a moment."
                    self._save_assistant_message(
                        conversation,
                        user_message,
                        metadata={},
                        status="failed",
                        message_status="failed",
                    )
                    _finalize_generation("failed")
                    yield {
                        "type": "error",
                        "error": user_message,
                        "error_kind": (
                            rest[0].get("error_kind", "permanent")
                            if rest
                            else "permanent"
                        ),
                    }
                    return

                if kind == "done":
                    latency_ms = int((time.perf_counter() - started_at) * 1000)
                    if run_status == "stopped":
                        guard_chain.audit_trail.log(
                            scope,
                            operation,
                            self.provider.provider_name,
                            latency_ms,
                            "stopped",
                        )
                        self._save_assistant_message(
                            conversation,
                            "Stopped by user.",
                            metadata={},
                            status="completed",
                            message_status="stopped",
                        )
                        _finalize_generation("cancelled")
                        yield {
                            "type": "stopped",
                            "conversation": self.get_conversation(user, conv_id),
                        }
                        return

                    if run_status == "failed":
                        guard_chain.audit_trail.log(
                            scope,
                            operation,
                            self.provider.provider_name,
                            latency_ms,
                            "failed",
                        )
                        user_message = "The action didn't complete — some steps failed."
                        self._save_assistant_message(
                            conversation,
                            user_message,
                            metadata={},
                            status="failed",
                            message_status="failed",
                        )
                        _finalize_generation("failed")
                        yield {
                            "type": "error",
                            "error": user_message,
                            "error_kind": "permanent",
                        }
                        return

                    guard_chain.audit_trail.log(
                        scope,
                        operation,
                        self.provider.provider_name,
                        latency_ms,
                        "completed",
                    )
                    usage = {"latency_ms": latency_ms, "execution_ms": latency_ms}
                    self._save_assistant_message(
                        conversation,
                        "Action completed.",
                        metadata={},
                        status="completed",
                        message_status="completed",
                    )
                    _finalize_generation("completed", usage)
                    yield {
                        "type": "done",
                        "conversation": self.get_conversation(user, conv_id),
                    }
                    return
        except (PermissionError, ValueError) as exc:
            self._save_assistant_message(
                conversation,
                str(exc),
                metadata={},
                status="failed",
                message_status="failed",
            )
            _finalize_generation("failed")
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible, never stuck in working
            logger.exception("action run failed for conversation=%s", conv_id)
            user_message = "I couldn't run that action — try again in a moment."
            self._save_assistant_message(
                conversation,
                user_message,
                metadata={},
                status="failed",
                message_status="failed",
            )
            _finalize_generation("failed")
            yield {
                "type": "error",
                "error": user_message,
                "error_kind": classify_llm_error(exc),
            }
            return
        finally:
            GENERATIONS.finish(conv_id)

    def _extract_chat_usage(
        self,
        res: dict[str, Any],
        latency_ms: int,
    ) -> dict[str, Any]:
        """Build a usage dict for the done frame / ``token_usage_json``.

        Provider results may carry an explicit ``usage`` block; otherwise we
        at least capture the per-turn ``execution_ms`` latency.
        """
        usage: dict[str, Any] = {}
        raw_usage = res.get("usage")
        if isinstance(raw_usage, dict):
            usage.update(raw_usage)
        execution_ms = res.get("execution_ms")
        if execution_ms is not None:
            usage.setdefault("execution_ms", execution_ms)
        if latency_ms is not None:
            usage.setdefault("latency_ms", latency_ms)
        model = res.get("model")
        if model:
            usage.setdefault("model", model)
        return usage

    def get_conversation(
        self,
        user,
        conversation_id: str,
    ) -> dict[str, Any]:
        """Get a conversation with all its messages."""
        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")

        data = _serialize_conversation(conversation)
        data["messages"] = [
            _serialize_message(m)
            for m in conversation.messages.order_by("created_at")
        ]
        return data

    def record_feedback(
        self,
        user,
        conversation_id,
        message_id,
        outcome,
        correction_text="",
    ):
        """Record user judgement (accept/reject/correct/ignore) on an AI message.

        The message lookup is scoped through the user's own conversation so
        feedback can never leak across users. Idempotent: re-posting the same
        outcome simply overwrites.
        """
        from ai.models import AIConversation, AIMessage

        try:
            conversation = AIConversation.objects.get(id=conversation_id, user=user)
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        try:
            message = AIMessage.objects.get(id=message_id, conversation=conversation)
        except AIMessage.DoesNotExist:
            raise ValueError(f"Message {message_id} not found.")

        if message.role != "assistant":
            raise NotAssistantMessageError("Only assistant messages can receive feedback.")

        if outcome == "corrected":
            message.correction_text = correction_text
        else:
            message.correction_text = ""

        message.outcome = outcome
        message.save(update_fields=["outcome", "correction_text"])

        # Phase 24-D — DQ-context feedback capture (best-effort). When the
        # judged message carries metadata_json["dq"], the signal is mirrored
        # into the DqFeedbackEvent ledger for the Phase 24 pipeline.
        try:
            from ai.feedback import capture_workspace_feedback

            capture_workspace_feedback(message)
        except Exception:  # noqa: BLE001 — capture must never break feedback
            logger.warning(
                "DQ feedback capture failed for message %s",
                message.id,
                exc_info=True,
            )

        # Sprint 11 — real-time learning: consume the judgement immediately so the
        # feedback flywheel turns without waiting for the scheduler sweep. Best-effort
        # only: a failure here leaves learned_at NULL and the sweep retries it; it must
        # never turn a successful feedback write into a 500.
        try:
            from ai.learning import learn_from_message

            learn_from_message(message)
        except Exception:  # noqa: BLE001 — feedback must still succeed
            logger.warning(
                "real-time learning failed for message %s",
                message.id,
                exc_info=True,
            )

        return _serialize_message(message)

    def list_conversations(
        self,
        user,
        status: str | None = None,
        limit: int = 50,
        query: str | None = None,
        is_archived: bool | None = None,
        is_pinned: bool | None = None,
        conversation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List user's conversations, newest first.

        Archived conversations are excluded by default and only included when
        ``is_archived=True`` is explicitly passed.
        """
        from ai.models import AIConversation

        if getattr(user, "is_authenticated", False):
            shared_ids = self._shared_conversation_ids(user)
            qs = AIConversation.objects.filter(
                models.Q(user=user) | models.Q(id__in=shared_ids)
            )
        else:
            qs = AIConversation.objects.none()
        if is_archived is True:
            qs = qs.filter(is_archived=True)
        else:
            qs = qs.filter(is_archived=False)
        if is_pinned is not None:
            qs = qs.filter(is_pinned=is_pinned)
        if conversation_type:
            qs = qs.filter(conversation_type=conversation_type)
        if query:
            qs = qs.filter(models.Q(title__icontains=query))
        if status:
            qs = qs.filter(status=status)
        qs = qs.order_by("-updated_at")[:limit]

        return [_serialize_conversation(c) for c in qs]

    def update_conversation(
        self,
        user,
        conversation_id: str,
        **fields: Any,
    ) -> dict[str, Any]:
        """Apply a partial update to the user's own conversation.

        Only ``title``/``is_pinned``/``is_archived``/``visibility`` are accepted;
        any other keys are ignored.  Raises ``ValueError`` when the conversation
        is not found or not owned by the user.
        """
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(id=conversation_id, user=user)
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        allowed = {"title", "is_pinned", "is_archived", "visibility"}
        update_fields = []
        for field_name in allowed:
            if field_name in fields:
                setattr(conversation, field_name, fields[field_name])
                update_fields.append(field_name)

        if update_fields:
            conversation.save(update_fields=update_fields)

        return _serialize_conversation(conversation)

    def delete_conversation(
        self,
        user,
        conversation_id: str,
    ) -> dict[str, Any]:
        """Hard-delete the user's own conversation.

        Raises ``ValueError`` when the conversation is not found or not owned.
        """
        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")

        if conversation.visibility == "shared" and not has_capability(user, "ai:manage_console"):
            raise PermissionDenied("Deleting a shared conversation requires ai:manage_console.")
        if conversation.visibility != "shared" and conversation.user_id != user.id:
            raise PermissionDenied("You do not have access to delete this conversation.")

        deleted_id = conversation.id
        conversation.delete()
        return {"deleted": str(deleted_id)}

    def list_messages(
        self,
        user,
        conversation_id: str,
        limit: int = 50,
        before: str | None = None,
        after: str | None = None,
    ) -> dict[str, Any]:
        """Paginate a conversation's messages by cursor.

        ``before`` pages backwards (newest-first) and ``after`` pages forward
        (oldest-first).  ``has_more`` reports whether additional messages remain
        in the pagination direction.  Raises ``ValueError`` when the conversation
        or a cursor message is not found.
        """
        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")

        if conversation.visibility != "shared" and conversation.user_id != user.id:
            raise PermissionDenied("You do not have access to this conversation.")

        qs = conversation.messages.order_by("created_at")

        if before:
            before_msg = self._resolve_message(conversation, before)
            qs = qs.filter(created_at__lt=before_msg.created_at)
        if after:
            after_msg = self._resolve_message(conversation, after)
            qs = qs.filter(created_at__gt=after_msg.created_at)

        if before:
            window = list(qs.order_by("-created_at")[:limit])
        else:
            window = list(qs[:limit])

        has_more = False
        if window:
            if before:
                has_more = conversation.messages.filter(
                    created_at__lt=window[-1].created_at
                ).exists()
            elif after:
                has_more = conversation.messages.filter(
                    created_at__gt=window[-1].created_at
                ).exists()
            else:
                # No cursor: the default page is the OLDEST `limit` messages in
                # ascending order, so more remain when a newer message exists.
                has_more = conversation.messages.filter(
                    created_at__gt=window[-1].created_at
                ).exists()

        return {
            "messages": [_serialize_message(m) for m in window],
            "has_more": has_more,
        }

    def summarize_conversation(
        self,
        user,
        conversation_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Produce (or refresh) a conversation's rolling summary.

        Deterministic fallback: concatenate the first three user messages
        (each truncated to 120 chars) into a single summary line.  No LLM call
        is made — the LLM summarizer is a future seam (see TODO below).
        if conversation.visibility == "shared" and not has_capability(user, "ai:manage_console"):
        Returns the serialized conversation.
        if conversation.visibility != "shared" and conversation.user_id != user.id:
            raise PermissionDenied("You do not have access to delete this conversation.")
        """
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        latest_message_id = conversation.messages.order_by("-created_at", "-id").values_list(
            "id",
            flat=True,
        ).first()

        if (
            not force
            and conversation.summary
            and conversation.last_summarized_message_id == latest_message_id
        ):
            return _serialize_conversation(conversation)

        # TODO(Sprint 16+): LLM summarizer seam — dispatch a compaction prompt to
        # the provider and store the returned summary.  The deterministic fallback
        # below is the shipped behavior: cheap, deterministic, and offline-safe
        # (no hidden LLM cost in tests).
        conversation.summary = _build_deterministic_summary(conversation)
        conversation.last_summarized_message_id = latest_message_id
        conversation.save(update_fields=["summary", "last_summarized_message_id"])
        return _serialize_conversation(conversation)

    def export_conversation(
        self,
        user,
        conversation_id: str,
        fmt: str = "json",
    ) -> dict[str, Any]:
        """Export a conversation as JSON or Markdown.

        ``fmt="json"`` → ``{"conversation": {...}, "messages": [...]}``;
        ``fmt="markdown"`` → a Markdown transcript (``metadata_json`` rendered as
        a fenced ```json block when non-empty).  Both are wrapped as
        ``{"format": fmt, "content": <...>}``.
        """
        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")

        messages = [
            _serialize_message(m)
            for m in conversation.messages.order_by("created_at")
        ]

        if fmt == "markdown":
            lines = [f"# {conversation.title or 'Untitled'}", ""]
            for message in messages:
                role = message["role"].capitalize()
                lines.append(f"**{role}** ({message['created_at']})")
                lines.append("")
                lines.append(message["content"])
                if message["metadata_json"]:
                    lines.append("")
                    lines.append("```json")
                    lines.append(
                        json.dumps(
                            message["metadata_json"],
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    lines.append("```")
                lines.append("")
            return {"format": fmt, "content": "\n".join(lines)}

        if fmt == "json":
            return {
                "format": fmt,
                "content": {
                    "conversation": _serialize_conversation(conversation),
                    "messages": messages,
                },
            }

        raise ValueError(f"Unsupported export format: {fmt}")

    def list_artifacts(self, user) -> list[dict[str, Any]]:
        from ai.models import AIArtifact

        shared_conversation_ids = list(
            self._shared_conversation_queryset(user).values_list("id", flat=True)
        )
        artifacts = AIArtifact.objects.filter(
            models.Q(conversation__user=user) | models.Q(conversation_id__in=shared_conversation_ids, visibility="shared")
        ).order_by("-created_at")
        return [self._serialize_artifact(artifact) for artifact in artifacts]

    def get_artifact(self, user, artifact_id: str) -> dict[str, Any]:
        from ai.models import AIArtifact

        try:
            artifact = AIArtifact.objects.select_related("conversation").get(id=artifact_id)
        except AIArtifact.DoesNotExist:
            raise ValueError(f"Artifact {artifact_id} not found.")

        self._ensure_artifact_access(user, artifact)
        return self._serialize_artifact(artifact)

    def create_artifact(
        self,
        user,
        conversation_id: str,
        title: str,
        artifact_type: str,
        content_json: dict[str, Any],
        message_id: str | None = None,
        visibility: str = "private",
    ) -> dict[str, Any]:
        from ai.models import AIArtifact, AIMessage

        conversation = self._get_own_conversation(user, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")

        message = None
        if message_id is not None:
            try:
                message = AIMessage.objects.get(id=message_id, conversation=conversation)
            except AIMessage.DoesNotExist:
                raise ValueError(f"Message {message_id} not found.")

        artifact = AIArtifact.objects.create(
            conversation=conversation,
            message=message,
            created_by=user,
            title=title,
            artifact_type=artifact_type,
            content_json=content_json,
            visibility=visibility,
        )
        return self._serialize_artifact(artifact)

    def update_artifact(
        self,
        user,
        artifact_id: str,
        **updates: Any,
    ) -> dict[str, Any]:
        from ai.models import AIArtifact

        try:
            artifact = AIArtifact.objects.select_related("conversation").get(id=artifact_id)
        except AIArtifact.DoesNotExist:
            raise ValueError(f"Artifact {artifact_id} not found.")

        self._ensure_artifact_access(user, artifact, write=True)

        if "message_id" in updates:
            message_id = updates.pop("message_id")
            if message_id is None:
                artifact.message = None
            else:
                artifact.message = artifact.conversation.messages.get(id=message_id)

        for field in ("title", "artifact_type", "content_json", "visibility"):
            if field in updates:
                setattr(artifact, field, updates[field])

        artifact.save()
        return self._serialize_artifact(artifact)

    def delete_artifact(self, user, artifact_id: str) -> dict[str, Any]:
        from ai.models import AIArtifact

        try:
            artifact = AIArtifact.objects.select_related("conversation").get(id=artifact_id)
        except AIArtifact.DoesNotExist:
            raise ValueError(f"Artifact {artifact_id} not found.")

        self._ensure_artifact_access(user, artifact, write=True)
        deleted = str(artifact.id)
        artifact.delete()
        return {"deleted": deleted}

    # ------------------------------------------------------------------ #
    # Proactive suggestions (Phase 5 item 3)
    # ------------------------------------------------------------------ #
    def list_proactive_suggestions(
        self,
        user,
        conversation_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return pending, unexpired proactive suggestions scoped to the user.

        CBAC-scoped via ``scope_ai_queryset`` (app + visibility + org subtree).
        When ``conversation_id`` is given it is only used to verify access —
        the result set is the user's workspace-level suggestion rail.
        """
        from django.db.models import Q

        from accounts.ai_scoping import scope_ai_queryset
        from ai.models import KgProactiveInsight

        qs = scope_ai_queryset(KgProactiveInsight.objects.all(), user)
        qs = qs.filter(disposition="pending")
        now = timezone.now()
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

        if conversation_id is not None:
            if self._get_accessible_conversation(user, conversation_id) is None:
                raise ValueError(f"Conversation {conversation_id} not found.")

        qs = qs.order_by("-created_at")[:limit]
        return [self._serialize_proactive_suggestion(insight) for insight in qs]

    def _serialize_proactive_suggestion(self, insight) -> dict[str, Any]:
        def _coerce(value, default):
            if value is None:
                return default
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return default
            return value

        return {
            "id": str(insight.id),
            "severity": insight.severity,
            "title": insight.title,
            "narrative": insight.narrative,
            "insight_type": insight.insight_type,
            "recommended_actions": _coerce(insight.recommended_actions_json, []),
            "context": _coerce(insight.context_json, {}),
            "created_at": insight.created_at.isoformat(),
        }

    def acknowledge_proactive_suggestion(
        self,
        user,
        conversation_id: str,
        suggestion_id: str,
        disposition: str = "acknowledged",
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Mark a proactive suggestion acknowledged or dismissed.

        Scoped identically to ``list_proactive_suggestions``: the user must be
        able to access both the conversation and the insight.
        """
        from accounts.ai_scoping import scope_ai_queryset
        from ai.models import KgProactiveInsight

        if self._get_accessible_conversation(user, conversation_id) is None:
            raise ValueError(f"Conversation {conversation_id} not found.")
        if disposition not in {"acknowledged", "dismissed"}:
            raise ValueError(f"Invalid disposition: {disposition}")

        qs = scope_ai_queryset(KgProactiveInsight.objects.all(), user)
        try:
            insight = qs.get(id=suggestion_id)
        except KgProactiveInsight.DoesNotExist:
            raise ValueError(f"Suggestion {suggestion_id} not found.")

        update_fields = ["disposition"]
        insight.disposition = disposition
        if reason and disposition == "dismissed":
            insight.dismissed_reason = reason
            update_fields.append("dismissed_reason")
        insight.save(update_fields=update_fields)
        return self._serialize_proactive_suggestion(insight)

    # ------------------------------------------------------------------ #
    # Resume catch-up (Phase 5 item 4)
    # ------------------------------------------------------------------ #
    RESUME_CATCH_UP_GAP_HOURS = 24

    def resume_conversation(self, user, conversation_id: str) -> dict[str, Any]:
        """Mark a conversation as resumed; return a catch-up summary when stale.

        When more than ``RESUME_CATCH_UP_GAP_HOURS`` have elapsed since the last
        view, a backend-generated catch-up is built (new DQ violations,
        anomalies, durable memory facts, and proactive suggestions).  The
        ``last_viewed_at`` marker is bumped on every resume so the summary is
        not re-emitted on every open.
        """
        from ai.models import AIConversation

        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")

        now = timezone.now()
        previous_viewed_at = conversation.last_viewed_at
        catch_up = None
        if previous_viewed_at is not None:
            if now - previous_viewed_at > timedelta(hours=self.RESUME_CATCH_UP_GAP_HOURS):
                catch_up = self._build_catch_up_summary(
                    user, conversation, previous_viewed_at
                )

        conversation.last_viewed_at = now
        conversation.save(update_fields=["last_viewed_at"])

        return {
            "conversation": _serialize_conversation(conversation),
            "catch_up": catch_up,
        }

    def _build_catch_up_summary(self, user, conversation, since) -> dict[str, Any]:
        from accounts.ai_scoping import scope_ai_queryset
        from ai.models import KgProactiveInsight, MemoryLongTerm

        org_int_ids, is_global = self._conversation_org_scope(conversation)

        new_memory_facts = scope_ai_queryset(
            MemoryLongTerm.objects.all(), user
        ).filter(archived=False, created_at__gt=since).count()

        new_suggestions = scope_ai_queryset(
            KgProactiveInsight.objects.all(), user
        ).filter(disposition="pending", created_at__gt=since).count()

        new_dq_violations = self._count_new_dq_violations(org_int_ids, is_global, since)
        new_anomalies = self._count_new_anomalies(org_int_ids, is_global, since)

        lines = []
        if new_dq_violations:
            lines.append(f"{new_dq_violations} new DQ violation(s)")
        if new_anomalies:
            lines.append(f"{new_anomalies} new anomaly/anomalies")
        if new_memory_facts:
            lines.append(f"{new_memory_facts} new memory fact(s)")
        if new_suggestions:
            lines.append(f"{new_suggestions} new suggestion(s)")

        return {
            "since": since.isoformat(),
            "hours_since_last_view": int(
                (timezone.now() - since).total_seconds() // 3600
            ),
            "new_dq_violations": new_dq_violations,
            "new_anomalies": new_anomalies,
            "new_memory_facts": new_memory_facts,
            "new_suggestions": new_suggestions,
            "summary_lines": lines or ["No new activity since your last visit."],
        }

    @staticmethod
    def _conversation_org_scope(conversation) -> tuple[list[int], bool]:
        """Extract the frozen org scope from a conversation's ``scope_json``.

        Returns ``(org_int_ids, is_global)``.  ``is_global`` means the thread was
        created with scope ``["*"]`` (superuser/global) and DQ counts should not
        be org-filtered.
        """
        scope_org_ids = (conversation.scope_json or {}).get("org_unit_ids") or []
        if "*" in scope_org_ids:
            return [], True
        int_ids = [int(o) for o in scope_org_ids if str(o).isdigit()]
        return int_ids, False

    @staticmethod
    def _count_new_dq_violations(org_int_ids, is_global, since) -> int:
        from dq.models import DQResult

        qs = DQResult.objects.filter(status="failed", run_at__gt=since)
        if is_global:
            return qs.count()
        if not org_int_ids:
            return 0
        return qs.filter(
            rule__field_assignments__data_table__module__org_unit_id__in=org_int_ids
        ).distinct().count()

    @staticmethod
    def _count_new_anomalies(org_int_ids, is_global, since) -> int:
        from dq.models import DQAnomaly

        qs = DQAnomaly.objects.filter(detected_at__gt=since)
        if is_global:
            return qs.count()
        if not org_int_ids:
            return 0
        return qs.filter(
            data_table__module__org_unit_id__in=org_int_ids
        ).count()

    def _get_own_conversation(self, user, conversation_id: str):
        from ai.models import AIConversation

        try:
            return AIConversation.objects.get(id=conversation_id, user=user)
        except AIConversation.DoesNotExist:
            return None

    def _shared_conversation_queryset(self, user):
        from ai.models import AIConversation

        if not getattr(user, "is_authenticated", False):
            return AIConversation.objects.none()

        scope = build_scope(user)
        org_ids = set(scope.org_unit_ids)
        qs = AIConversation.objects.filter(visibility="shared")
        if "*" in org_ids:
            return qs

        shared_ids = [
            str(conversation.id)
            for conversation in qs
            if self._conversation_scope_matches_user(conversation, org_ids)
        ]
        return AIConversation.objects.filter(id__in=shared_ids)

    def _get_accessible_conversation(self, user, conversation_id: str):
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(id=conversation_id, user=user)
        except AIConversation.DoesNotExist:
            conversation = None

        if conversation is not None:
            return conversation

        if not getattr(user, "is_authenticated", False):
            return None

        try:
            return self._shared_conversation_queryset(user).get(id=conversation_id)
        except AIConversation.DoesNotExist:
            return None

    def _shared_conversation_ids(self, user) -> list[str]:
        return [str(conversation.id) for conversation in self._shared_conversation_queryset(user)]

    def _conversation_scope_matches_user(self, conversation, user_org_ids: set[str]) -> bool:
        scope_org_ids = set((conversation.scope_json or {}).get("org_unit_ids") or [])
        if "*" in scope_org_ids:
            return True
        if not user_org_ids and not scope_org_ids:
            return True
        return bool(user_org_ids & scope_org_ids)

    def _ensure_artifact_access(self, user, artifact, write: bool = False) -> None:
        conversation = artifact.conversation
        if conversation.user_id == user.id:
            return
        if artifact.visibility != "shared" or conversation.visibility != "shared":
            raise PermissionDenied("Artifact is not shared.")
        if write and not has_capability(user, "ai:manage_console"):
            raise PermissionDenied("Modifying a shared artifact requires ai:manage_console.")
        if not self._get_accessible_conversation(user, conversation.id):
            raise PermissionDenied("You do not have access to this shared artifact.")

    def _serialize_artifact(self, artifact) -> dict[str, Any]:
        return {
            "id": str(artifact.id),
            "conversation_id": str(artifact.conversation_id),
            "message_id": str(artifact.message_id) if artifact.message_id else None,
            "title": artifact.title,
            "artifact_type": artifact.artifact_type,
            "content_json": artifact.content_json,
            "visibility": artifact.visibility,
            "created_by_id": str(artifact.created_by_id) if artifact.created_by_id else None,
            "created_at": artifact.created_at.isoformat(),
            "updated_at": getattr(artifact, "updated_at", artifact.created_at).isoformat(),
        }

    def _resolve_message(self, conversation, message_id: str):
        """Resolve a message cursor id to its message (scoped to the conversation)."""
        from ai.models import AIMessage

        try:
            return AIMessage.objects.get(id=message_id, conversation=conversation)
        except AIMessage.DoesNotExist:
            raise ValueError(f"Message {message_id} not found.")

    def stop_generation(
        self,
        user,
        conversation_id: str,
    ) -> dict[str, Any]:
        """Request cancellation of a running generation.

        Idempotent: cancelling when nothing is running returns
        ``{"stopped": false}`` instead of an error.
        """
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        cancelled = GENERATIONS.cancel(str(conversation.id))

        latest = conversation.generations.order_by("-started_at").first()
        if latest is not None and latest.status == "running":
            latest.status = "cancelled"
            latest.cancelled_at = timezone.now()
            latest.save(update_fields=["status", "cancelled_at"])

        return {"stopped": cancelled}

    # ── Sprint 20 W1-B — context lifecycle (checkpoint/restore/fork/clear) ─
    def _get_lifecycle_conversation(self, user, conversation_id: str):
        """Load a conversation the user can ACCESS (ValueError when absent).

        Uses the canonical access helper — own OR shared — so console
        operators (gated by ``ai:manage_console`` at the API layer) can
        checkpoint/restore/fork/clear conversations they can already see,
        mirroring ``get_conversation`` / ``export_conversation``.
        """
        conversation = self._get_accessible_conversation(
            user, conversation_id,
        )
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found.")
        return conversation

    def _get_checkpoint(self, conversation, checkpoint_id: str):
        """Load a checkpoint scoped to ``conversation`` (ValueError when absent)."""
        from ai.models import ConversationCheckpoint

        try:
            return ConversationCheckpoint.objects.get(
                id=checkpoint_id, conversation=conversation,
            )
        except ConversationCheckpoint.DoesNotExist:
            raise ValueError(f"Checkpoint {checkpoint_id} not found.")

    def _assemble_context_bundle(self, conversation, user) -> dict[str, Any]:
        """Assemble the conversation's current context bundle (W1-B).

        Mirrors the ``send_message_stream`` assembly: fresh scope, full
        history, tiered budget.  Returns the raw ``assemble_context`` output
        (messages + budget + kg_entities + context_signature) plus the
        conversation summary and the last message id as the checkpoint
        boundary.
        """
        history = list(
            conversation.messages.order_by("created_at").values(
                "id", "role", "content", "created_at", "is_deleted",
            )
        )
        scope = build_scope(user)
        if conversation.app_identifier:
            scope.app_identifier = conversation.app_identifier
        assembled = assemble_context(conversation, history, scope, adapter=self.adapter)
        last_msg = conversation.messages.order_by("-created_at").first()
        return {
            **assembled,
            "summary": conversation.summary,
            # JSON-safe: snapshot_json is persisted via psycopg2's plain JSON
            # encoder, so UUIDs/datetimes must be stringified here.
            "message_boundary_id": (
                str(last_msg.id) if last_msg else None
            ),
        }

    def checkpoint_conversation(
        self,
        user,
        conversation_id: str,
        name: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Snapshot the conversation's working context under ``name`` (W1-B).

        Builds the current bundle via ``assemble_context`` (messages + budget
        + kg_entities + memory) and persists it as ``snapshot_json``.
        Idempotent: re-saving the same ``name`` overwrites the existing
        checkpoint (updates snapshot + note).  Never deletes messages or
        learned facts.  Returns the serialized checkpoint.
        """
        from ai.models import ConversationCheckpoint

        conversation = self._get_lifecycle_conversation(user, conversation_id)
        bundle = self._assemble_context_bundle(conversation, user)

        checkpoint, _created = ConversationCheckpoint.objects.update_or_create(
            conversation=conversation,
            name=name,
            defaults={
                "owner": user,
                "note": note or "",
                "snapshot_json": bundle,
                "message_boundary_id": bundle.get("message_boundary_id"),
            },
        )
        return _serialize_checkpoint(checkpoint)

    def list_checkpoints(
        self, user, conversation_id: str,
    ) -> list[dict[str, Any]]:
        """List the conversation's named checkpoints, newest first (picker)."""
        conversation = self._get_lifecycle_conversation(user, conversation_id)
        return [
            _serialize_checkpoint(c) for c in conversation.checkpoints.all()
        ]

    def restore_conversation(
        self,
        user,
        conversation_id: str,
        checkpoint_id: str,
    ) -> dict[str, Any]:
        """Re-seed the conversation's *working* context from a checkpoint.

        Restores the summary + context snapshot (budget / KG entities /
        context signature) captured at checkpoint time.  The durable
        ``AIMessage`` log is NOT overwritten and no learning/forget path is
        touched — the next turn reassembles history from the log while
        carrying the restored summary.
        """
        conversation = self._get_lifecycle_conversation(user, conversation_id)
        checkpoint = self._get_checkpoint(conversation, checkpoint_id)

        snapshot = checkpoint.snapshot_json or {}
        conversation.summary = snapshot.get("summary") or ""
        conversation.context_snapshot_json = {
            "budget": snapshot.get("budget") or {},
            "kg_entities": snapshot.get("kg_entities") or [],
            "context_signature": snapshot.get("context_signature") or "",
            "restored_from_checkpoint": str(checkpoint.id),
            "restored_at": timezone.now().isoformat(),
        }
        conversation.save(
            update_fields=["summary", "context_snapshot_json", "updated_at"],
        )
        return _serialize_conversation(conversation)

    def fork_conversation(
        self,
        user,
        conversation_id: str,
        checkpoint_id: str,
    ) -> dict[str, Any]:
        """Clone the conversation into a NEW row seeded from a checkpoint.

        The fork gets its own conversation id (never aliases the source row),
        title ``"{old} — fork"``, and a durable message log cloned up to the
        checkpoint's ``message_boundary_id`` (inclusive).  Its working context
        (summary + context snapshot) is seeded from the checkpoint bundle.
        """
        from ai.models import AIConversation, AIMessage

        conversation = self._get_lifecycle_conversation(user, conversation_id)
        checkpoint = self._get_checkpoint(conversation, checkpoint_id)
        snapshot = checkpoint.snapshot_json or {}

        fork = AIConversation.objects.create(
            user=user,
            conversation_type=conversation.conversation_type,
            title=f"{conversation.title or 'Conversation'} — fork",
            app_identifier=conversation.app_identifier,
            status="pending",
            scope_json=conversation.scope_json,
            task_payload_json=conversation.task_payload_json,
        )

        # Clone the durable log up to the checkpoint boundary (inclusive) —
        # new rows in the fork, same content/order; never alias the source.
        source_messages = conversation.messages.order_by("created_at")
        boundary_id = checkpoint.message_boundary_id
        if boundary_id is not None:
            boundary = AIMessage.objects.filter(
                id=boundary_id, conversation=conversation,
            ).first()
            if boundary is not None:
                source_messages = source_messages.filter(
                    created_at__lte=boundary.created_at,
                )
        for msg in source_messages:
            AIMessage.objects.create(
                conversation=fork,
                role=msg.role,
                content=msg.content,
                metadata_json=msg.metadata_json,
                token_usage_json=msg.token_usage_json,
                parent_message_id=msg.parent_message_id,
                is_deleted=msg.is_deleted,
                context_signature=msg.context_signature,
                status=msg.status,
                provider_model=msg.provider_model,
                outcome=msg.outcome,
                correction_text=msg.correction_text,
                learned_at=msg.learned_at,
                created_at=msg.created_at,
            )

        fork.summary = snapshot.get("summary") or ""
        fork.context_snapshot_json = {
            "budget": snapshot.get("budget") or {},
            "kg_entities": snapshot.get("kg_entities") or [],
            "context_signature": snapshot.get("context_signature") or "",
            "forked_from": str(conversation.id),
            "forked_from_checkpoint": str(checkpoint.id),
            "forked_at": timezone.now().isoformat(),
        }
        fork.save(update_fields=["summary", "context_snapshot_json"])
        return _serialize_conversation(fork)

    def clear_context(self, user, conversation_id: str) -> dict[str, Any]:
        """Reset the conversation's *working* context (W1-B).

        Clears the summary + context snapshot levers only.  The conversation
        row, the durable message log, per-message provenance, and learned
        facts are all untouched — no learning forget path is called.  A
        conversation stuck in ``working`` is released back to ``pending``.
        """
        conversation = self._get_lifecycle_conversation(user, conversation_id)
        conversation.summary = ""
        conversation.context_snapshot_json = {}
        update_fields = ["summary", "context_snapshot_json", "updated_at"]
        if conversation.status == "working":
            conversation.status = "pending"
            update_fields.append("status")
        conversation.save(update_fields=update_fields)
        return _serialize_conversation(conversation)

    def regenerate_message(
        self,
        user,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        """Regenerate an assistant reply.

        Re-runs the send path with the user message that immediately preceded
        the target assistant message, then links the new assistant reply to the
        original via ``parent_message_id``.
        """
        from ai.models import AIConversation, AIMessage

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        target = self._resolve_message(conversation, message_id)
        if target.role != "assistant":
            raise ValueError(f"Message {message_id} is not an assistant message.")

        preceding_user = (
            conversation.messages.filter(
                role="user", created_at__lt=target.created_at,
            )
            .order_by("-created_at")
            .first()
        )
        if preceding_user is None:
            raise ValueError(f"No preceding user message found for {message_id}.")

        result = self.send_message(user, conversation_id, preceding_user.content)

        new_assistant_id = result["assistant_message"]["id"]
        new_assistant = AIMessage.objects.get(
            id=new_assistant_id, conversation=conversation,
        )
        new_assistant.parent_message_id = target.id
        new_assistant.save(update_fields=["parent_message_id"])

        return self.get_conversation(user, conversation_id)

    def edit_message(
        self,
        user,
        conversation_id: str,
        message_id: str,
        content: str,
        regenerate: bool = True,
    ) -> dict[str, Any]:
        """Edit a user message's content and, by default, regenerate the reply.

        Phase 19-A: ``regenerate=False`` only edits the stored text (no new
        assistant message).  Only user messages are editable.  Raises
        ``NotUserMessageError`` (a ``ValueError`` subclass) for non-user
        messages so the API can map it to a 400.
        """
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        message = self._resolve_message(conversation, message_id)
        if message.role != "user":
            raise NotUserMessageError("Only user messages can be edited.")

        message.content = content
        message.save(update_fields=["content"])

        if regenerate:
            self.send_message(user, conversation_id, content)
        return self.get_conversation(user, conversation_id)

    def _abort_inflight_generations(self, conversation) -> int:
        """Cancel every in-flight generation for a conversation.

        Cancels both the in-process registry (``GENERATIONS``) and any
        still-``running`` ``AIGeneration`` rows.  Returns the number of DB rows
        transitioned to ``cancelled`` (idempotent)."""
        from ai.models import AIGeneration

        GENERATIONS.cancel(str(conversation.id))
        updated = 0
        for gen in conversation.generations.filter(status="running"):
            gen.status = "cancelled"
            gen.cancelled_at = timezone.now()
            gen.save(update_fields=["status", "cancelled_at"])
            updated += 1
        return updated

    def _latest_reply_to_turn(self, conversation, user_message):
        """Return the latest assistant reply to a user turn (or ``None``).

        Prefers ``parent_id`` lineage (Phase 19-A); falls back to the
        immediately-following assistant message by creation order when lineage
        is absent (pre-migration rows)."""
        from ai.models import AIMessage

        reply = (
            conversation.messages.filter(
                role="assistant", parent_id=user_message.id,
            )
            .order_by("-created_at")
            .first()
        )
        if reply is not None:
            return reply
        return (
            conversation.messages.filter(
                role="assistant", created_at__gt=user_message.created_at,
            )
            .order_by("created_at")
            .first()
        )

    def retry_message(
        self,
        user,
        conversation_id: str,
        user_message_id: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Retry a user turn == regenerate: re-run the pipeline for that turn.

        Phase 19-A: aborts any in-flight generation first, reuses the context
        *snapshot* (not the live tail), and produces a fresh assistant reply
        linked to the original turn (``parent_id``) and the replaced reply
        (``parent_message_id``)."""
        from ai.models import AIConversation, AIMessage

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        turn = self._resolve_message(conversation, user_message_id)
        if turn.role != "user":
            raise NotUserMessageError("Only user messages can be retried.")

        self._abort_inflight_generations(conversation)
        replaced = self._latest_reply_to_turn(conversation, turn)

        conversation._turn_parent_id = turn.id
        if replaced is not None:
            conversation._turn_replaced_message_id = replaced.id
        else:
            conversation._turn_replaced_message_id = None

        scope = build_scope(user)
        if conversation.app_identifier:
            scope.app_identifier = conversation.app_identifier

        # Phase 22-A — resolve durable preferences (profile → domain manifest)
        # for this regeneration; the per-message ``model`` param still wins.
        resolved_model = self._resolve_preferred_model(
            user, model, conversation.app_identifier,
        )
        resolved_temperature = self._resolve_preferred_temperature(user)

        # Rebuild the *snapshot* of that turn: everything up to and including
        # the user message, excluding soft-deleted and later messages.
        history = list(
            conversation.messages.filter(
                created_at__lte=turn.created_at,
            )
            .order_by("created_at")
            .values("id", "role", "content", "created_at", "is_deleted")
        )
        assembled = assemble_context(
            conversation, history, scope, model=resolved_model, adapter=self.adapter,
        )
        conversation._turn_context_signature = assembled["context_signature"]
        conv_ctx = ConversationContext(
            conversation_id=str(conversation.id),
            messages=assembled["messages"],
        )

        # Persist the context budget telemetry snapshot + retrieved KG entities.
        conversation.context_snapshot_json = {
            **assembled["budget"],
            "kg_entities": assembled["kg_entities"],
        }
        conversation.save(update_fields=["context_snapshot_json"])

        conversation.status = "working"
        conversation.save(update_fields=["status"])

        try:
            response = self._route_typed_message(
                conversation, turn.content, conv_ctx, scope,
                resolved_model, resolved_temperature,
            )
        except (PermissionError, ValueError) as exc:
            response = self._save_assistant_message(
                conversation,
                str(exc),
                metadata={},
                status="failed",
            )
            raise

        return {
            "conversation": _serialize_conversation(conversation),
            "assistant_message": response,
        }

    def retry_message_stream(
        self,
        user,
        conversation_id: str,
        user_message_id: str,
        model: str | None = None,
    ):
        """Streaming variant of :meth:`retry_message` (SSE path).

        Aborts any in-flight generation first, re-runs the pipeline for the
        user turn using its context snapshot, and streams a fresh assistant
        reply.  Yields the same frame shapes as :meth:`send_message_stream`.
        """
        from ai.models import AIConversation, AIMessage, AIGeneration

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        # Phase 21-A — request-time quota gate.
        try:
            self._enforce_quota(user)
        except QuotaExceededError as exc:
            yield {
                "type": "error",
                "error": str(exc),
                "error_code": "quota",
                "quota": exc.quota,
            }
            return

        turn = self._resolve_message(conversation, user_message_id)
        if turn.role != "user":
            raise NotUserMessageError("Only user messages can be retried.")

        self._abort_inflight_generations(conversation)
        replaced = self._latest_reply_to_turn(conversation, turn)

        conversation._turn_parent_id = turn.id
        conversation._turn_replaced_message_id = (
            replaced.id if replaced is not None else None
        )

        scope = build_scope(user)
        if conversation.app_identifier:
            scope.app_identifier = conversation.app_identifier

        # Phase 22-A — resolve durable preferences (profile → domain manifest)
        # for this regeneration; the per-message ``model`` param still wins.
        resolved_model = self._resolve_preferred_model(
            user, model, conversation.app_identifier,
        )
        resolved_temperature = self._resolve_preferred_temperature(user)

        # Rebuild the *snapshot* of that turn (up to and including the user
        # message, excluding soft-deleted and later messages).
        history = list(
            conversation.messages.filter(created_at__lte=turn.created_at)
            .order_by("created_at")
            .values("id", "role", "content", "created_at", "is_deleted")
        )
        assembled = assemble_context(
            conversation, history, scope, model=resolved_model, adapter=self.adapter,
        )
        conversation._turn_context_signature = assembled["context_signature"]
        conv_ctx = ConversationContext(
            conversation_id=str(conversation.id),
            messages=assembled["messages"],
        )

        conversation.context_snapshot_json = {
            **assembled["budget"],
            "kg_entities": assembled["kg_entities"],
        }
        conversation.save(update_fields=["context_snapshot_json"])

        conv_id = str(conversation.id)
        conv_type = conversation.conversation_type
        GENERATIONS.start(conv_id)
        generation = AIGeneration.objects.create(
            conversation=conversation,
            token=uuid.uuid4().hex,
            status="running",
        )

        def _finalize_generation(
            final_status: str, usage: dict[str, Any] | None = None
        ) -> None:
            generation.status = final_status
            update_fields = ["status"]
            if final_status == "cancelled":
                generation.cancelled_at = timezone.now()
                update_fields.append("cancelled_at")
            if final_status == "completed":
                generation.completed_at = timezone.now()
                update_fields.append("completed_at")
                update_fields += self._populate_generation_usage(generation, usage)
            generation.save(update_fields=update_fields)

        try:
            conversation.status = "working"
            conversation.save(update_fields=["status"])

            if conv_type == "chat":
                started_at = time.perf_counter()
                guard_chain, operation = self._guard_workspace_operation(
                    scope,
                    "workspace_chat",
                    conversation.task_payload_json or {},
                )
                message = self._prepend_workspace_context(
                    conversation, turn.content,
                )
                message = self._prepend_domain_context(scope, message)
                chat_request = ChatRequest(
                    message=message,
                    conversation=conv_ctx,
                    scope=scope,
                    model=resolved_model,
                    temperature=resolved_temperature,
                )

                partial_parts: list[str] = []
                for frame in self.provider.chat_stream(chat_request):
                    kind = frame[0]
                    value = frame[1] if len(frame) > 1 else None
                    meta = frame[2] if len(frame) > 2 else {}
                    if GENERATIONS.is_cancelled(conv_id):
                        self._save_assistant_message(
                            conversation,
                            "".join(partial_parts),
                            metadata={},
                            status="completed",
                            message_status="stopped",
                        )
                        _finalize_generation("cancelled")
                        yield {
                            "type": "stopped",
                            "conversation": self.get_conversation(user, conv_id),
                        }
                        return
                    if kind == "chunk":
                        partial_parts.append(value)
                        yield {"type": "chunk", "content": value}
                        continue
                    if kind == "error":
                        latency_ms = int((time.perf_counter() - started_at) * 1000)
                        guard_chain.audit_trail.log(
                            scope,
                            operation,
                            self.provider.provider_name,
                            latency_ms,
                            "failed",
                            error_message=value,
                        )
                        user_message = "I couldn't reach the AI service — try again in a moment."
                        self._save_assistant_message(
                            conversation,
                            user_message,
                            metadata={},
                            status="failed",
                            message_status="failed",
                        )
                        _finalize_generation("failed")
                        yield {
                            "type": "error",
                            "error": user_message,
                            "error_kind": meta.get("error_kind", "permanent"),
                        }
                        return
                    if kind == "done":
                        latency_ms = int((time.perf_counter() - started_at) * 1000)
                        result = value or {}
                        res = result.get("result") or {}
                        guard_chain.audit_trail.log(
                            scope,
                            operation,
                            self.provider.provider_name,
                            latency_ms,
                            result.get("status", "completed"),
                        )
                        usage = self._extract_chat_usage(res, latency_ms)
                        self._build_ai_message(
                            conversation,
                            "completed",
                            res.get("content"),
                            res.get("follow_up_questions", []),
                            usage=usage,
                            actions=res.get("actions"),
                            pending_actions=res.get("pending_actions"),
                            tool_trace=res.get("tool_trace"),
                            external_sources=res.get("external_sources"),
                            code_result=res.get("code_result"),
                        )
                        _finalize_generation("completed", usage)
                        done_frame = {
                            "type": "done",
                            "conversation": self.get_conversation(user, conv_id),
                        }
                        if usage:
                            done_frame["usage"] = usage
                        # Phase H1-B — append-only audit trail: record each
                        # completed tool call (RULE_21 — recording only).
                        for _tool in (res.get("tool_trace") or []):
                            _tool_id = _tool.get("tool_id") or _tool.get("tool_name")
                            if not _tool_id:
                                continue
                            AuditService.log(
                                action="ai.tool_call",
                                actor=user.pk,
                                host_user_id=str(user.pk),
                                target=str(_tool_id),
                                detail={
                                    "tool_id": _tool_id,
                                    "duration_ms": _tool.get("duration_ms"),
                                },
                            )
                        yield done_frame
                        return
            else:
                yield {
                    "type": "progress",
                    "stage": "start",
                    "message": self._progress_stage_label(conv_type),
                }

                if GENERATIONS.is_cancelled(conv_id):
                    self._save_assistant_message(
                        conversation,
                        "Interrupted by user.",
                        metadata={},
                        status="completed",
                        message_status="stopped",
                    )
                    _finalize_generation("cancelled")
                    yield {
                        "type": "stopped",
                        "conversation": self.get_conversation(user, conv_id),
                    }
                    return

                self._route_typed_message(
                    conversation, turn.content, conv_ctx, scope,
                    resolved_model, resolved_temperature,
                )

                if GENERATIONS.is_cancelled(conv_id):
                    self._save_assistant_message(
                        conversation,
                        "Interrupted by user.",
                        metadata={},
                        status="completed",
                        message_status="stopped",
                    )
                    _finalize_generation("cancelled")
                    yield {
                        "type": "stopped",
                        "conversation": self.get_conversation(user, conv_id),
                    }
                    return

                yield {"type": "progress", "stage": "done", "message": "Done"}
                _finalize_generation("completed")
                yield {
                    "type": "done",
                    "conversation": self.get_conversation(user, conv_id),
                }
                return
        except (PermissionError, ValueError) as exc:
            self._save_assistant_message(
                conversation,
                str(exc),
                metadata={},
                status="failed",
                message_status="failed",
            )
            _finalize_generation("failed")
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("retry failed for conversation=%s", conv_id)
            user_message = "I couldn't reach the AI service — try again in a moment."
            self._save_assistant_message(
                conversation,
                user_message,
                metadata={},
                status="failed",
                message_status="failed",
            )
            _finalize_generation("failed")
            yield {
                "type": "error",
                "error": user_message,
                "error_kind": classify_llm_error(exc),
            }
            return
        finally:
            GENERATIONS.finish(conv_id)

    def delete_message(
        self,
        user,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        """Soft-delete a message (Phase 19-A).

        Deleting a *user* turn soft-deletes the turn plus all its descendant
        replies (thread-cut).  Deleting an *assistant* reply soft-deletes only
        that reply (orphans are tolerated and rendered dimmed).  In-flight
        generations are aborted first so no orphaned stream writes a reply.
        """
        from ai.models import AIConversation, AIMessage

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        message = self._resolve_message(conversation, message_id)
        self._abort_inflight_generations(conversation)

        ids = [message.id]
        if message.role == "user":
            # Direct lineage replies first; fall back to the created_at "turn"
            # span for pre-migration rows that have no parent_id.
            direct = list(
                conversation.messages.filter(
                    role="assistant", parent_id=message.id,
                )
            )
            if direct:
                ids.extend(m.id for m in direct)
            else:
                next_user = (
                    conversation.messages.filter(
                        role="user", created_at__gt=message.created_at,
                    )
                    .order_by("created_at")
                    .first()
                )
                qs = conversation.messages.filter(
                    role="assistant", created_at__gt=message.created_at,
                )
                if next_user is not None:
                    qs = qs.filter(created_at__lt=next_user.created_at)
                ids.extend(qs.values_list("id", flat=True))

        AIMessage.objects.filter(
            id__in=ids, conversation=conversation,
        ).update(is_deleted=True)

        if conversation.status == "working":
            conversation.status = "completed"
            conversation.save(update_fields=["status"])

        return self.get_conversation(user, conversation_id)

    # ── Phase 22-A: preference resolution ─────────────────────────────────
    # RESOLUTION ORDER (low → high), applied at turn time:
    #
    #     system default → domain manifest → user profile → per-message override
    #
    # * system default  — settings-driven (``get_model_for_task`` in the
    #                     engine router).  Lowest tier.
    # * domain manifest — optional ``default_model_id`` class attribute on a
    #                     registered ``DomainAIOperations`` subclass.
    # * user profile    — ``AIUserProfile`` (Phase 22-A durable prefs).
    # * per-message     — the ``model`` parameter the caller (frontend model
    #                     picker / retry) passes for THIS turn.  Highest tier.
    #
    # The user profile NEVER overrides a per-message override, and the domain
    # manifest NEVER overrides the profile.  Future workers: keep this order —
    # swapping profile and per-message is a correctness bug.
    def _user_preferences(self, user) -> "AIUserProfile | None":
        """Return the user's AIUserProfile row (or None when never saved)."""
        from ai.models import AIUserProfile

        try:
            return AIUserProfile.objects.select_related(
                "default_model_id"
            ).get(user=user)
        except AIUserProfile.DoesNotExist:
            return None

    def _resolve_preferred_model(
        self,
        user,
        per_message_model: str | None,
        app_identifier: str | None = None,
    ) -> str | None:
        """Resolve the model for a turn following the Phase 22-A order.

        Returns the highest-priority model slug available; ``None`` means "no
        preference" and the engine falls back to its system default
        (``get_model_for_task``).  The per-message override always wins.
        """
        if per_message_model:
            return per_message_model
        profile = self._user_preferences(user)
        if profile is not None and profile.default_model_id_id is not None:
            return profile.default_model_id.model_id
        if app_identifier:
            from ai.domain_protocol import get_domain, has_domain

            if has_domain(app_identifier):
                domain_default = get_domain(app_identifier).default_model_id
                if domain_default:
                    return domain_default
        return None

    def _resolve_preferred_temperature(self, user) -> float | None:
        """User's default chat temperature (0.0-2.0) or None → engine default."""
        profile = self._user_preferences(user)
        if profile is not None:
            return profile.temperature
        return None

    def _maybe_autotitle(
        self, conversation, content: str, *, enabled: bool = True
    ) -> None:
        """Set the conversation title from the first user message.

        Only fires while the title is still a default title (from
        ``_default_title``) and no prior user message exists, so an explicit
        user rename is never overwritten.  ``enabled`` (Phase 22-A) is the
        user's ``auto_title`` preference — False skips auto-titling entirely.
        """
        if not content or not enabled:
            return

        default_titles = {
            _default_title(t)
            for t in ("chat", "dq_validate", "dq_suggest", "nl_query", "anomaly")
        }
        if conversation.title not in default_titles:
            return
        if conversation.messages.filter(role="user").exists():
            return

        new_title = content.strip()[:40]
        if not new_title:
            return

        conversation.title = new_title
        conversation.save(update_fields=["title"])

    def _route_typed_message(
        self,
        conversation,
        content: str,
        conv_ctx: ConversationContext,
        scope: Scope,
        model: str | None = None,
        # Phase 22-A — user's default chat temperature; chat-only.
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Dispatch a turn to the per-type ``_send_*`` handler.

        Shared by :meth:`send_message` and the non-chat branch of
        :meth:`send_message_stream` so both paths route identically.
        """
        conv_type = conversation.conversation_type
        if conv_type == "dq_validate":
            return self._send_dq_validate_message(conversation, conv_ctx, scope)
        if conv_type == "dq_suggest":
            return self._send_dq_suggest_message(conversation, conv_ctx, scope)
        if conv_type == "nl_query":
            return self._send_nl_query_message(conversation, content, conv_ctx, scope)
        if conv_type == "anomaly":
            return self._send_anomaly_message(conversation, content, conv_ctx, scope)
        if conv_type == "nl_rule_test":
            return self._send_nl_rule_test_message(conversation, content, conv_ctx, scope)
        if conv_type == "investigate":
            return self._send_investigate_message(conversation, content, conv_ctx, scope)
        if conv_type == "report_draft":
            return self._send_report_draft_message(conversation, content, conv_ctx, scope)
        return self._send_chat_message(
            conversation, content, conv_ctx, scope, model, temperature,
        )

    def _send_report_draft_message(
        self,
        conversation,
        content: str,
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> dict[str, Any]:
        """Handle report_draft conversation messages (Phase 10-A).

        The engine (``_run_report_draft``), protocol dataclasses, and provider
        (``draft_report``) are already built and tested; this is the typed
        intelligence-layer handler that bridges the frontend entry-point
        payload (``{module_id, module_name, period_id}``) to the engine's
        ``{report_type, period_start, period_end}`` shape.
        """
        payload = conversation.task_payload_json or {}
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_report_draft",
            payload,
        )

        # Translate payload → report params. Wrap in try/except so a malformed
        # scope (missing period, bad period_id) never crashes the turn.
        try:
            from emissions.models import ReportingPeriod

            period_id = payload.get("period_id")
            if period_id:
                period = ReportingPeriod.objects.get(id=period_id)
                period_type_map = {
                    "annual": "annual_summary",
                    "quarterly": "quarterly_summary",
                    "monthly": "monthly_summary",
                }
                report_type = period_type_map.get(period.period_type, "ghg_summary")
                period_start = period.start_date.isoformat()
                period_end = period.end_date.isoformat()
            else:
                report_type = payload.get("report_type") or "ghg_summary"
                period_start = payload.get("period_start") or ""
                period_end = payload.get("period_end") or ""
        except Exception as exc:  # noqa: BLE001 - fail-visible, never crash the turn
            guard_chain.audit_trail.log(
                scope,
                operation,
                self.provider.provider_name,
                0,
                "failed",
                error_message=f"Invalid report parameters: {exc}",
            )
            return self._save_assistant_message(
                conversation,
                f"Could not build the report request: {exc}",
                metadata={"type": "report", "sections": []},
                status="failed",
            )

        request = ReportDraftRequest(
            report_type,
            period_start,
            period_end,
            scope,
        )
        started_at = time.perf_counter()
        response = self.provider.draft_report(request)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            response.status,
            error_message=_error_message(response.error),
        )

        if response.status == "provider_unavailable":
            return self._save_provider_unavailable_message(conversation)
        if response.status != "completed":
            return self._save_assistant_message(
                conversation,
                f"Report drafting failed: {_error_message(response.error)}",
                metadata={"type": "report", "sections": []},
                status="failed",
            )

        sections = [
            {
                "title": s.title,
                "content": s.content or s.narrative or "",
                "sql": s.sql,
                "data": s.data,
                "caveat": s.caveat,
            }
            for s in response.sections
        ]
        metadata = guard_chain.sanitize_response(
            scope,
            {
                "type": "report",
                "title": response.title,
                "summary": response.summary,
                "report_type": response.report_type,
                "period_start": response.period_start,
                "period_end": response.period_end,
                "generated_at": response.generated_at,
                "sections": sections,
            },
        )
        return self._save_assistant_message(
            conversation,
            f"Drafted {response.title or 'report'} "
            f"({response.period_start} → {response.period_end}).",
            metadata=metadata,
            status="needs_input",
        )

    def _progress_stage_label(self, conversation_type: str) -> str:
        """Human label for the progress frame of a non-chat generation."""
        labels = {
            "dq_validate": "Validating rows…",
            "dq_suggest": "Reading your table…",
            "nl_query": "Working on your query…",
            "anomaly": "Detecting anomalies…",
            "investigate": "Investigating…",
            "nl_rule_test": "Testing rule…",
            "report_draft": "Drafting report…",
        }
        return labels.get(conversation_type, "Working…")

    # ── Internal helpers ──────────────────────────────────────────────

    def _send_dq_validate_message(
        self,
        conversation,
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> dict[str, Any]:
        """Handle dq_validate conversation messages."""
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_dq_validate",
            conversation.task_payload_json or {},
        )

        payload = conversation.task_payload_json or {}
        rows = payload.get("rows", [])
        rules_data = payload.get("rules", [])

        if not rules_data:
            # No stored rules — treat as chat
            chat_request = ChatRequest(
                message="",
                conversation=conv_ctx,
                scope=scope,
            )
            chat_response = self.provider.chat(chat_request)
            return self._build_ai_message(
                conversation, chat_response.status,
                chat_response.content,
                chat_response.follow_up_questions,
            )

        rules = [
            DqRuleInput(
                id=r.get("id", ""),
                prompt=r.get("prompt", ""),
                fields=r.get("fields", []),
                severity=r.get("severity", "error"),
            )
            for r in rules_data
        ]
        request = DqValidateRequest(
            rules=rules,
            rows=rows,
            context=payload.get("context", {}),
            scope=scope,
            conversation=conv_ctx,
        )
        started_at = time.perf_counter()
        response = self.provider.validate_dq(request)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            response.status,
            error_message=_error_message(response.error),
        )

        if response.status == "completed":
            summary = _format_dq_results(response)
            metadata = guard_chain.sanitize_response(
                scope,
                {
                    "type": "dq_validate_result",
                    "results": [
                        {
                            "rule_id": r.rule_id,
                            "status": r.status,
                            "failing_rows": r.failing_rows,
                            "explanation": r.explanation,
                            "confidence": r.confidence,
                        }
                        for r in response.results
                    ],
                },
            )
            return self._save_assistant_message(
                conversation,
                summary,
                metadata=metadata,
                status="completed",
            )
        if response.status == "provider_unavailable":
            return self._save_provider_unavailable_message(conversation)
        return self._save_assistant_message(
            conversation,
            f"DQ validation failed: {_error_message(response.error)}",
            metadata={},
            status="failed",
        )

    def _send_dq_suggest_message(
        self,
        conversation,
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> dict[str, Any]:
        """Handle dq_suggest conversation messages."""
        payload = conversation.task_payload_json or {}
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_dq_suggest",
            payload,
        )

        table_profile, error_message = self._build_suggest_table_profile(payload)
        if error_message:
            guard_chain.audit_trail.log(
                scope,
                operation,
                self.provider.provider_name,
                0,
                "failed",
                error_message=error_message,
            )
            return self._save_assistant_message(
                conversation,
                error_message,
                metadata={"type": "dq_suggestions", "suggestions": []},
                status="failed",
            )

        request = DqSuggestRequest(
            table=table_profile,
            scope=scope,
            conversation=conv_ctx,
        )
        started_at = time.perf_counter()
        response = self.provider.suggest_dq(request)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            response.status,
            error_message=_error_message(response.error),
        )

        if response.status == "provider_unavailable":
            return self._save_provider_unavailable_message(conversation)
        if response.status != "completed":
            return self._save_assistant_message(
                conversation,
                f"DQ suggestion failed: {_error_message(response.error)}",
                metadata={"type": "dq_suggestions", "suggestions": []},
                status="failed",
            )

        suggestions = [
            {
                "definition": suggestion.definition,
                "rationale": suggestion.rationale,
                "severity": suggestion.severity,
                "confidence": suggestion.confidence,
                "dimension": suggestion.dimension,
                "actions": ["accept", "reject", "refine"],
            }
            for suggestion in response.suggestions
        ]
        metadata = guard_chain.sanitize_response(
            scope,
            {
                "type": "dq_suggestions",
                "table": {
                    "name": table_profile.name,
                    "row_count": table_profile.row_count,
                    "columns": table_profile.columns,
                },
                "suggestions": suggestions,
            },
        )
        if not suggestions:
            return self._save_assistant_message(
                conversation,
                f"No DQ suggestions were generated for {table_profile.name}.",
                metadata=metadata,
                status="completed",
            )

        return self._save_assistant_message(
            conversation,
            f"AI generated {len(suggestions)} DQ suggestion(s) for {table_profile.name}.",
            metadata=metadata,
            status="needs_input",
        )

    def _send_nl_rule_test_message(
        self,
        conversation,
        content: str,
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> dict[str, Any]:
        """Handle nl_rule_test conversation messages (Phase 8-A).

        Parses the user's NL rule into a v1 definition and dry-runs it
        read-only against the table's rows.  Nothing is persisted to DQ —
        the frontend (8-B) owns the "Save Rule" (Execute Mode) gate.
        """
        payload = conversation.task_payload_json or {}
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_nl_rule_test",
            payload,
        )

        table_id = payload.get("table_id")
        if not table_id:
            guard_chain.audit_trail.log(
                scope,
                operation,
                self.provider.provider_name,
                0,
                "failed",
                error_message="NL rule test requires a table_id.",
            )
            return self._save_assistant_message(
                conversation,
                "NL rule testing requires a target table. Start this thread from a table or suggestion.",
                metadata={"type": "nl_rule_test", "rule_preview": None, "test_summary": None, "violations": []},
                status="failed",
            )

        from dataschema.models import DataRow, DataTable

        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            guard_chain.audit_trail.log(
                scope,
                operation,
                self.provider.provider_name,
                0,
                "failed",
                error_message=f"Table {table_id} not found.",
            )
            return self._save_assistant_message(
                conversation,
                f"Could not find the target table (id={table_id}).",
                metadata={"type": "nl_rule_test", "rule_preview": None, "test_summary": None, "violations": []},
                status="failed",
            )

        fields = list(table.fields.filter(is_archived=False))
        schema = [
            {"name": f.name, "label": f.label, "type": f.type}
            for f in fields
        ]
        rows = list(DataRow.objects.filter(data_table=table, is_archived=False))

        # Resolve the target field: prefer an explicit payload field, else the
        # first active field (the engine may still refine it from the parse).
        field_name = payload.get("field_name")
        if not field_name and fields:
            field_name = fields[0].name

        # The NL rule text may arrive as the message content (design-doc flow:
        # task_payload carries the table, the rule is the typed message) or,
        # for "Test live"-style entry points, pre-seeded in task_payload.nl.
        # Accept either so the 8-B frontend can't wire it wrong.
        nl_text = (content or "").strip() or str(payload.get("nl") or "").strip()

        task_payload = {
            "table_id": table.id,
            "table_name": table.name,
            "schema": schema,
            "nl": nl_text,
            "rows": rows,
            "field_name": field_name,
        }

        started_at = time.perf_counter()
        result = dispatch_task("dq.rule_test", task_payload, timeout=60)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            result.get("status"),
            error_message=_error_message(result.get("error")),
        )

        if result.get("status") == "pulse_unavailable":
            return self._save_provider_unavailable_message(conversation)
        if result.get("status") != "completed":
            return self._save_assistant_message(
                conversation,
                f"Rule test failed: {_error_message(result.get('error'))}",
                metadata={"type": "nl_rule_test", "rule_preview": None, "test_summary": None, "violations": []},
                status="failed",
            )

        r = result.get("result") or {}
        rule_preview = r.get("rule_preview")
        test_summary = r.get("test_summary") or {}
        violations = r.get("violations") or []
        detail_rows = r.get("rows") or []
        recommendation = r.get("recommendation") or ""

        metadata = guard_chain.sanitize_response(
            scope,
            {
                "type": "nl_rule_test",
                "rule_preview": rule_preview,
                "test_summary": test_summary,
                "violations": violations,
                "rows": detail_rows,
                "recommendation": recommendation,
            },
        )

        failed = test_summary.get("failed")
        if failed:
            summary = (
                f"Rule tested against {test_summary.get('total_rows', 0)} row(s): "
                f"{failed} violation(s) found."
            )
        else:
            summary = (
                f"Rule tested against {test_summary.get('total_rows', 0)} row(s): "
                "no violations."
            )
        if recommendation:
            summary = f"{summary} {recommendation}"

        return self._save_assistant_message(
            conversation,
            summary,
            metadata=metadata,
            status="needs_input",
        )

    def _send_investigate_message(
        self,
        conversation,
        content: str,
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> dict[str, Any]:
        """Handle investigate conversation messages (Phase 9-A).

        Runs the READ-ONLY investigation pipeline (RULE_21): profile (latest
        ``TableProfile`` only), DQ rules via the pure ``dq.engine.evaluate``
        loop, anomaly detection reusing ``_run_anomaly_detect``, and KG
        retrieval (here, because it needs ``scope``).  Nothing in this path
        calls ``run_dq`` or ``profile_table`` — neither mutates DQ state.
        """
        payload = conversation.task_payload_json or {}
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_investigate",
            payload,
        )

        table_id = payload.get("table_id")
        if not table_id:
            guard_chain.audit_trail.log(
                scope,
                operation,
                self.provider.provider_name,
                0,
                "failed",
                error_message="Investigate requires a table_id.",
            )
            return self._save_assistant_message(
                conversation,
                "Investigation requires a target table. Start this thread from a table or asset.",
                metadata={"type": "investigation", "findings": []},
                status="failed",
            )

        from django.db.models import Q

        from dataschema.models import DataRow, DataTable
        from dq.models import DQRule, TableProfile
        from dq.services import build_anomaly_payload

        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            guard_chain.audit_trail.log(
                scope,
                operation,
                self.provider.provider_name,
                0,
                "failed",
                error_message=f"Table {table_id} not found.",
            )
            return self._save_assistant_message(
                conversation,
                f"Could not find the target table (id={table_id}).",
                metadata={"type": "investigation", "findings": []},
                status="failed",
            )

        # ── READ-ONLY pre-load ─────────────────────────────────────────
        fields = list(table.fields.filter(is_archived=False))
        schema = [
            {"name": f.name, "label": f.label, "type": f.type}
            for f in fields
        ]
        rows = list(DataRow.objects.filter(data_table=table, is_archived=False))

        # Latest TableProfile only — do NOT re-profile.
        profile_summary: dict[str, Any] = {}
        latest_profile = (
            TableProfile.objects.filter(data_table=table)
            .order_by("-profiled_at")
            .first()
        )
        if latest_profile is not None:
            profile_summary = {
                "row_count": latest_profile.row_count,
                "completeness_pct": latest_profile.completeness_pct,
                "field_count": len(fields),
                "profiled_at": (
                    latest_profile.profiled_at.isoformat()
                    if latest_profile.profiled_at
                    else None
                ),
            }

        # Active deterministic rules, mirroring run_dq's selection (but with no
        # persistence). nl_check/anomaly_detect are excluded — the former is
        # LLM-only, the latter is fed to the anomaly step.
        field_by_id = {f.id: f for f in fields}
        field_ids = list(field_by_id)
        rules = list(
            DQRule.objects.filter(is_active=True)
            .filter(
                Q(field_assignments__data_table_id=table.id)
                | Q(field_assignments__data_field_id__in=field_ids)
            )
            .prefetch_related("field_assignments__data_field")
            .distinct()
        )
        rule_defs: list[dict[str, Any]] = []
        for rule in rules:
            if rule.rule_type in ("nl_check", "anomaly_detect"):
                continue
            field_name = None
            reference_set_id = None
            for assn in rule.field_assignments.all():
                if assn.data_field_id and assn.data_field_id in field_by_id:
                    f = field_by_id[assn.data_field_id]
                    field_name = f.name
                    reference_set_id = f.reference_set_id
                    break
            if field_name is None:
                for assn in rule.field_assignments.all():
                    if assn.data_field_id:
                        field_name = assn.data_field.name
                        reference_set_id = assn.data_field.reference_set_id
                        break
            if field_name is None:
                # Field-level deterministic rules need a resolvable field.
                continue
            rule_defs.append(
                {
                    "id": rule.id,
                    "name": rule.name,
                    "type": rule.rule_type,
                    "severity": rule.severity,
                    "params": rule.params or {},
                    "field_name": field_name,
                    "reference_set_id": reference_set_id,
                }
            )

        # Anomaly payload, translated into the shape _run_anomaly_detect
        # consumes (mirrors _build_anomaly_request). None = insufficient history
        # → a "done" step with 0 anomalies, NOT an error.
        raw_anomaly_payload, anomaly_err = build_anomaly_payload(table.id)
        anomaly_payload: dict[str, Any] | None = None
        if raw_anomaly_payload is not None:
            anomaly_payload = {
                "table_name": raw_anomaly_payload["table"].get("name", table.name),
                "profile_history": raw_anomaly_payload.get("history", []),
                "sensitivity": float(raw_anomaly_payload.get("sensitivity", 2.0)),
                "volume_threshold_pct": float(
                    raw_anomaly_payload.get("volume_anomaly_pct", 30.0)
                ),
            }

        # KG retrieval needs scope, so it happens here (not in the engine).
        kg_entries, kg_tokens = self.adapter.retrieve_knowledge_graph(scope, 800)

        task_payload = {
            "table_id": table.id,
            "table_name": table.name,
            "schema": schema,
            "rows": rows,
            "profile_summary": profile_summary,
            "rule_defs": rule_defs,
            "anomaly_payload": anomaly_payload,
            "kg_entries": kg_entries,
            "kg_tokens": kg_tokens,
        }

        started_at = time.perf_counter()
        result = dispatch_task("investigate", task_payload, timeout=90)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            result.get("status"),
            error_message=_error_message(result.get("error")),
        )

        if result.get("status") == "pulse_unavailable":
            return self._save_provider_unavailable_message(conversation)
        if result.get("status") != "completed":
            return self._save_assistant_message(
                conversation,
                f"Investigation failed: {_error_message(result.get('error'))}",
                metadata={"type": "investigation", "findings": []},
                status="failed",
            )

        r = result.get("result") or {}
        metadata = guard_chain.sanitize_response(
            scope,
            {
                "type": "investigation",
                "table_id": r.get("table_id"),
                "table_name": r.get("table_name"),
                "summary": r.get("summary"),
                "plan_steps": r.get("plan_steps") or [],
                "findings": r.get("findings") or [],
                "counts": r.get("counts") or {},
            },
        )

        findings = r.get("findings") or []
        status = "needs_input" if findings else "completed"
        message = (
            f"Investigation of {r.get('table_name', 'table')} found "
            f"{len(findings)} finding(s)."
        )
        return self._save_assistant_message(
            conversation,
            message,
            metadata=metadata,
            status=status,
        )

    def _send_nl_query_message(
        self,
        conversation,
        content: str,
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> dict[str, Any]:
        """Handle nl_query conversation messages."""
        payload = conversation.task_payload_json or {}
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_nl_query",
            payload,
        )

        question = content.strip()
        if not question:
            raise ValueError("Natural language query requires a non-empty message.")

        tables = _table_names_from_payload(payload)
        request = NlQueryRequest(
            question=question,
            tables=tables or None,
            scope=scope,
            conversation=conv_ctx,
            domain_vocabulary=_domain_vocabulary_from_payload(payload),
        )
        started_at = time.perf_counter()
        response = self.provider.query_nl(request)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            response.status,
            error_message=_error_message(response.error),
        )

        if response.status == "provider_unavailable":
            return self._save_provider_unavailable_message(conversation)
        if response.status != "completed":
            return self._save_assistant_message(
                conversation,
                f"NL query failed: {_error_message(response.error)}",
                metadata={"type": "nl_query_result", "rows": []},
                status="failed",
            )

        rows = response.rows or []
        metadata = guard_chain.sanitize_response(
            scope,
            {
                "type": "nl_query_result",
                "sql": response.sql,
                "rows": rows,
                "row_count": response.row_count,
                "execution_ms": response.execution_ms,
                "recovery_applied": response.recovery_applied,
            },
        )
        return self._save_assistant_message(
            conversation,
            f"Query returned {response.row_count} row(s).",
            metadata=metadata,
            status="completed",
        )

    def _send_anomaly_message(
        self,
        conversation,
        content: str,
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> dict[str, Any]:
        """Handle anomaly conversation messages."""
        payload = conversation.task_payload_json or {}
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_anomaly",
            payload,
        )

        anomaly_request, error_message = self._build_anomaly_request(payload, conv_ctx, scope)
        if error_message:
            guard_chain.audit_trail.log(
                scope,
                operation,
                self.provider.provider_name,
                0,
                "failed",
                error_message=error_message,
            )
            return self._save_assistant_message(
                conversation,
                error_message,
                metadata={"type": "anomalies", "anomalies": []},
                status="failed",
            )

        try:
            started_at = time.perf_counter()
            response = self.provider.detect_anomalies(anomaly_request)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
        except NotImplementedError:
            return self._send_chat_message(
                conversation,
                content or f"Analyze anomalies for {anomaly_request.table_name}",
                conv_ctx,
                scope,
            )

        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            response.status,
            error_message=_error_message(response.error),
        )

        if response.status == "provider_unavailable":
            return self._save_provider_unavailable_message(conversation)
        if response.status != "completed":
            return self._save_assistant_message(
                conversation,
                f"Anomaly detection failed: {_error_message(response.error)}",
                metadata={"type": "anomalies", "anomalies": []},
                status="failed",
            )

        anomalies = [
            {
                "metric": anomaly.metric,
                "expected_range": anomaly.expected_range,
                "observed": anomaly.observed,
                "z_score": anomaly.z_score,
                "severity": anomaly.severity,
                "explanation": anomaly.explanation,
            }
            for anomaly in response.anomalies
        ]
        metadata = guard_chain.sanitize_response(
            scope,
            {
                "type": "anomalies",
                "history_snapshots": response.history_snapshots,
                "anomalies": anomalies,
            },
        )
        status = "needs_input" if anomalies else "completed"
        message = (
            f"Detected {len(anomalies)} anomaly(s) in {anomaly_request.table_name}."
            if anomalies
            else f"No anomalies detected in {anomaly_request.table_name}."
        )
        return self._save_assistant_message(
            conversation,
            message,
            metadata=metadata,
            status=status,
        )

    def _send_chat_message(
        self,
        conversation,
        content: str,
        conv_ctx: ConversationContext,
        scope: Scope,
        model: str | None = None,
        # Phase 22-A — user's default chat temperature; None → engine default.
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Handle generic chat conversation messages."""
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_chat",
            conversation.task_payload_json or {},
        )
        message = self._prepend_workspace_context(conversation, content)
        message = self._prepend_domain_context(scope, message)
        chat_request = ChatRequest(
            message=message,
            conversation=conv_ctx,
            scope=scope,
            model=model,
            temperature=temperature,
        )
        started_at = time.perf_counter()
        chat_response = self.provider.chat(chat_request)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        guard_chain.audit_trail.log(
            scope,
            operation,
            self.provider.provider_name,
            latency_ms,
            chat_response.status,
            error_message=_error_message(chat_response.error),
        )
        return self._build_ai_message(
            conversation,
            chat_response.status,
            chat_response.content,
            chat_response.follow_up_questions,
            actions=chat_response.actions,
            pending_actions=chat_response.pending_actions,
            confidence_label=chat_response.confidence_label,
            honest_uncertainty=chat_response.honest_uncertainty,
            tool_trace=chat_response.tool_trace,
            external_sources=chat_response.external_sources,
            code_result=chat_response.code_result,
        )

    def _prepend_workspace_context(
        self,
        conversation,
        content: str,
    ) -> str:
        """Prepend the WorkspaceContext prompt prefix to a chat message.

        AI CONTRACT §11.3: the engine receives WorkspaceContext as part of
        the prompt, injected by CarbonIntelligence (NOT the frontend).
        §11.4: never used for security — that is Scope's job.

        Malformed or absent context is silently ignored — never crash.
        """
        try:
            payload = conversation.task_payload_json or {}
            ctx = WorkspaceContext.from_dict(payload.get("workspace_context"))
        except Exception:
            return content
        if ctx is None:
            return content
        prefix = ctx.to_prompt_prefix()
        if not prefix:
            return content
        return f"{prefix}\n\n{content}"

    def _prepend_domain_context(self, scope: Scope, content: str) -> str:
        """Inject domain context (GHG vocabulary, etc.) when scope.app_identifier
        maps to a registered domain. AI CONTRACT §8: platform-level injection.

        Combines two static tiers into one domain prefix:
          * ``get_domain_context()`` → structured ``[Domain: ...]`` prefix; and
          * ``system_prompt_extension`` (ADR-0010) → verbatim domain vocabulary,
            folded in as the trailing paragraph of the domain context. A domain
            without an extension (e.g. ``water``) skips it via the ``""`` default.

        NEVER crashes on missing/unregistered/malformed domain — returns
        content unchanged in every failure path.
        """
        if not scope or not getattr(scope, "app_identifier", None):
            return content
        if not has_domain(scope.app_identifier):
            return content
        try:
            domain = get_domain(scope.app_identifier)()
            ctx = domain.get_domain_context()
        except Exception:
            return content
        prefix = _domain_context_prompt_prefix(ctx)
        extension = (getattr(domain, "system_prompt_extension", "") or "").strip()
        if extension:
            prefix = f"{prefix}\n\n{extension}" if prefix else extension
        if not prefix:
            return content
        return f"{prefix}\n\n{content}"

    def _seed_intent_aware_opener(
        self,
        conversation,
        workspace_context: dict[str, Any] | None,
    ) -> None:
        """Seed an initial assistant opener when WorkspaceContext carries intent.

        Sprint 6 Phase 6-C: if the workspace context has an intent_signal,
        write a context-aware first assistant message so the AI opens already
        knowing the user's intent.

        Optional + additive — no context or no intent → no opener, no status
        change. Malformed context is ignored; conversation creation never fails.
        """
        try:
            ctx = WorkspaceContext.from_dict(workspace_context)
            if ctx is None:
                return
            opener = _intent_aware_opener(ctx)
        except Exception:
            return
        if not opener:
            return
        self._save_assistant_message(
            conversation,
            opener,
            metadata={
                "type": "workspace_context_opener",
                "intent_signal": ctx.intent_signal,
            },
            status="needs_input",
        )

    def _guard_workspace_operation(
        self,
        scope: Scope,
        operation: str,
        payload: dict[str, Any],
    ):
        from ai.guards import GuardChain

        guard_chain = GuardChain()
        guard_chain.run(
            scope,
            operation,
            requested_modules=_requested_modules_from_payload(payload),
            table_names=_guard_table_names(scope, payload),
        )
        return guard_chain, operation

    def _build_suggest_table_profile(
        self,
        payload: dict[str, Any],
    ) -> tuple[TableProfile | None, str | None]:
        table_id = payload.get("table_id")
        if table_id:
            from dq.services import build_suggest_payload

            table_payload, err = build_suggest_payload(table_id)
            if err:
                return None, err.get("message", "Could not build a table profile for AI suggestions.")
            columns = table_payload.get("columns") or table_payload.get("fields") or []
            return TableProfile(
                name=table_payload.get("name", payload.get("table_name", "table")),
                description=table_payload.get("description", payload.get("table_name", "")),
                row_count=table_payload.get("row_count", 0),
                columns=columns,
            ), None

        columns = payload.get("columns") or payload.get("fields") or []
        row_count = int(payload.get("row_count") or 0)
        table_name = payload.get("table_name") or payload.get("name")
        if not table_name or not columns:
            return None, "AI suggestions require a profiled table with columns and row count."
        return TableProfile(
            name=table_name,
            description=payload.get("description", table_name),
            row_count=row_count,
            columns=columns,
        ), None

    def _build_anomaly_request(
        self,
        payload: dict[str, Any],
        conv_ctx: ConversationContext,
        scope: Scope,
    ) -> tuple[AnomalyDetectRequest | None, str | None]:
        table_id = payload.get("table_id")
        if not table_id:
            return None, "Anomaly analysis requires a table_id with profile history."

        from dq.services import build_anomaly_payload

        anomaly_payload, err = build_anomaly_payload(table_id)
        if err:
            return None, err.get("message", "Could not build anomaly payload.")

        return AnomalyDetectRequest(
            table_name=anomaly_payload["table"].get("name", payload.get("table_name", "table")),
            profile_history=anomaly_payload.get("history", []),
            sensitivity=float(anomaly_payload.get("sensitivity", 2.0)),
            volume_threshold_pct=float(anomaly_payload.get("volume_anomaly_pct", 30.0)),
            scope=scope,
            conversation=conv_ctx,
        ), None

    @staticmethod
    def _populate_generation_usage(generation, usage: dict[str, Any] | None) -> list[str]:
        """Populate Phase 21-A usage fields on a generation, return field names.

        Mutates ``generation`` in place (no save).  Cost is computed from the
        Phase 20-A ``ModelCatalog`` rates — never ad hoc.  Returns the list of
        field names that were changed so the caller can pass ``update_fields``.
        """
        from ai.models import ModelCatalog

        if not usage:
            return []
        model_id = ModelCatalog.resolve_model_id(usage.get("model"))
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0)
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens
        generation.model_id = model_id
        generation.prompt_tokens = prompt_tokens
        generation.completion_tokens = completion_tokens
        generation.total_tokens = total_tokens
        generation.cost = ModelCatalog.compute_cost(
            model_id, prompt_tokens, completion_tokens
        )
        return [
            "model_id",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
        ]

    def _save_assistant_message(
        self,
        conversation,
        content: str,
        *,
        metadata: dict[str, Any],
        status: str,
        usage: dict[str, Any] | None = None,
        message_status: str = "completed",
    ) -> dict[str, Any]:
        from ai.models import AIMessage

        # Freeze the current turn's assembled context snapshot onto the message
        # so per-turn provenance (incl. retrieved KG entities) survives later
        # turns, which overwrite ``conversation.context_snapshot_json``.
        # ``_build_message_provenance`` reads ``metadata["context_snapshot"]``
        # first, so this makes "Why this answer" per-turn rather than latest-turn.
        snapshot = dict(metadata or {})
        snapshot.setdefault(
            "context_snapshot",
            getattr(conversation, "context_snapshot_json", None) or {},
        )

        # Phase 19-A — persist thread linkage + the opaque context signature
        # (set as transient attrs by send_message / retry_* before routing).
        parent_id = getattr(conversation, "_turn_parent_id", None)
        context_signature = getattr(conversation, "_turn_context_signature", "")
        replaced_message_id = getattr(
            conversation, "_turn_replaced_message_id", None
        )

        ai_msg = AIMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=content,
            metadata_json=snapshot,
            token_usage_json=usage or {},
            status=message_status,
            parent_id=parent_id,
            context_signature=context_signature,
            parent_message_id=replaced_message_id,
        )
        conversation.status = status
        conversation.save(update_fields=["status"])
        return _serialize_message(ai_msg)

    def _save_provider_unavailable_message(self, conversation) -> dict[str, Any]:
        return self._save_assistant_message(
            conversation,
            "I couldn't reach the AI service — try again in a moment.",
            metadata={},
            status="failed",
            message_status="failed",
        )

    def _build_ai_message(
        self,
        conversation,
        status: str,
        content: str | None,
        follow_up_questions: list[str],
        usage: dict[str, Any] | None = None,
        actions: list[dict] | None = None,
        pending_actions: list[dict] | None = None,
        confidence_label: str = "",
        honest_uncertainty: bool = False,
        tool_trace: list[dict] | None = None,
        external_sources: list[dict] | None = None,
        code_result: dict | None = None,
    ) -> dict[str, Any]:
        """Save AI response message and update conversation status."""
        if status == "provider_unavailable":
            return self._save_provider_unavailable_message(conversation)

        has_follow_ups = bool(follow_up_questions)
        metadata: dict[str, Any] = {}
        if has_follow_ups:
            metadata["follow_up_questions"] = follow_up_questions
        # Sprint "fly to rule detail": machine-readable tool outcomes drive
        # the UI buttons (navigate → "View rule", staged → confirm). Only real
        # tool results ever populate these — never LLM prose.
        if actions:
            metadata["action"] = actions[-1]
            # Capability listings may surface several links at once — persist
            # the full list so the UI can render one small button per item.
            metadata["actions"] = actions
        if pending_actions:
            metadata["pending_actions"] = pending_actions
        # F3-B — read-only tool trace for the frontend "Considered…" pill.
        if tool_trace:
            metadata["tool_trace"] = tool_trace
        if external_sources:
            metadata["external_sources"] = external_sources
        if code_result:
            metadata["code_result"] = code_result
        # C2 — calibrated confidence (Faculty 7): outcome label + honest-
        # uncertainty flag (RULE_23 — outcome copy only, never raw internals).
        if confidence_label:
            metadata["confidence_label"] = confidence_label
        if honest_uncertainty:
            metadata["honest_uncertainty"] = True

        return self._save_assistant_message(
            conversation,
            content or "",
            metadata=metadata,
            status="needs_input" if has_follow_ups else "completed",
            usage=usage,
        )


# ── Helpers ───────────────────────────────────────────────────────────────


def _build_deterministic_summary(conversation) -> str:
    """Fallback summary builder used until the cheap LLM seam is wired."""
    user_messages = list(
        conversation.messages.filter(role="user").order_by("created_at")[:3]
    )
    snippets = []
    for message in user_messages:
        text = (message.content or "").strip()
        if text:
            snippets.append(text[:120])

    return " ".join(snippets) if snippets else "No user messages yet."


def _extract_prompt(rule) -> str:
    """Extract NL prompt from a DQRule (definition JSON, then legacy params)."""
    try:
        definition = rule.definition
        if isinstance(definition, dict):
            params = definition.get("params", {})
            if isinstance(params, dict) and params.get("prompt"):
                return str(params["prompt"])
    except Exception:
        pass
    try:
        if isinstance(rule.params, dict) and rule.params.get("prompt"):
            return str(rule.params["prompt"])
    except Exception:
        pass
    return ""


def _rule_fields(rule) -> list[str]:
    """Return field names assigned to a DQRule."""
    names: list[str] = []
    try:
        for assn in rule.field_assignments.select_related("data_field"):
            if assn.data_field:
                names.append(assn.data_field.name)
    except Exception:
        pass
    return names


# ── Workspace serialization helpers ───────────────────────────────────────


def _serialize_conversation(conversation) -> dict[str, Any]:
    """Serialize an AIConversation to dict (no messages)."""
    return {
        "id": str(conversation.id),
        "user_id": conversation.user_id,
        "title": conversation.title,
        "app_identifier": conversation.app_identifier,
        "conversation_type": conversation.conversation_type,
        "status": conversation.status,
        "scope_json": conversation.scope_json,
        "task_payload_json": conversation.task_payload_json,
        "is_archived": conversation.is_archived,
        "is_pinned": conversation.is_pinned,
        "summary": conversation.summary,
        "last_message_at": (
            conversation.last_message_at.isoformat()
            if conversation.last_message_at
            else None
        ),
        "last_viewed_at": (
            conversation.last_viewed_at.isoformat()
            if conversation.last_viewed_at
            else None
        ),
        "visibility": conversation.visibility,
        "context_snapshot_json": conversation.context_snapshot_json,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def _serialize_checkpoint(checkpoint) -> dict[str, Any]:
    """Serialize a ConversationCheckpoint to dict (picker-safe, no bodies).

    The full assembled bundle (incl. tiered messages) stays in
    ``snapshot_json`` on the row; the API payload carries only the metadata
    the picker needs (budget, KG count, summary, boundary).
    """
    snapshot = checkpoint.snapshot_json or {}
    return {
        "id": str(checkpoint.id),
        "conversation_id": str(checkpoint.conversation_id),
        "owner_id": str(checkpoint.owner_id) if checkpoint.owner_id else None,
        "name": checkpoint.name,
        "note": checkpoint.note,
        "message_boundary_id": (
            str(checkpoint.message_boundary_id)
            if checkpoint.message_boundary_id
            else None
        ),
        "snapshot": {
            "budget": snapshot.get("budget") or {},
            "kg_entities": snapshot.get("kg_entities") or [],
            "context_signature": snapshot.get("context_signature") or "",
            "summary": snapshot.get("summary") or "",
            # Conversation turns only — the bundle also carries system-tier
            # injection blocks (profile/summary/KG), which aren't history.
            "message_count": sum(
                1
                for m in (snapshot.get("messages") or [])
                if m.get("role") in ("user", "assistant")
            ),
            "boundary_id": snapshot.get("message_boundary_id"),
        },
        "created_at": checkpoint.created_at.isoformat(),
        "updated_at": checkpoint.updated_at.isoformat(),
    }


def _serialize_message(message) -> dict[str, Any]:
    """Serialize an AIMessage to dict."""
    metadata = message.metadata_json or {}
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "content": message.content,
        "metadata_json": message.metadata_json,
        "token_usage_json": message.token_usage_json,
        "parent_message_id": (
            str(message.parent_message_id)
            if message.parent_message_id
            else None
        ),
        "parent_id": (
            str(message.parent_id) if message.parent_id else None
        ),
        "is_deleted": bool(message.is_deleted),
        "context_signature": message.context_signature,
        "status": message.status,
        "provider_model": message.provider_model,
        "outcome": message.outcome,
        "correction_text": message.correction_text,
        # C2 — calibrated confidence (Faculty 7): outcome-shaped signal from
        # the turn (RULE_23 — outcome copy only, never raw critic internals).
        "confidence_label": metadata.get("confidence_label") or "",
        "honest_uncertainty": bool(metadata.get("honest_uncertainty")),
        # F3-B — read-only tool trace for the frontend "Considered…" pill.
        "tool_trace": metadata.get("tool_trace") or [],
        "external_sources": metadata.get("external_sources") or [],
        "code_result": metadata.get("code_result"),
        "provenance": _build_message_provenance(message),
        "created_at": message.created_at.isoformat(),
    }


def _build_message_provenance(message) -> dict[str, Any]:
    metadata = message.metadata_json or {}
    if isinstance(metadata.get("provenance"), dict):
        return metadata["provenance"]

    usage = message.token_usage_json or {}
    conversation = getattr(message, "conversation", None)
    return {
        "model": message.provider_model or usage.get("model") or None,
        "scope_snapshot": metadata.get("scope_snapshot") or getattr(conversation, "scope_json", {}) or {},
        "context_snapshot": metadata.get("context_snapshot") or getattr(conversation, "context_snapshot_json", {}) or {},
        "guard_results": metadata.get("guard_results") or [],
        "external_sources": metadata.get("external_sources") or [],
        "engine_turn_id": metadata.get("engine_turn_id") or str(message.id),
    }


def _default_title(conversation_type: str) -> str:
    """Generate a default title for a conversation."""
    titles = {
        "chat": "Chat",
        "dq_validate": "DQ Check",
        "dq_suggest": "DQ Suggestions",
        "nl_query": "Data Query",
        "anomaly": "Anomaly Review",
    }
    return titles.get(conversation_type, "Conversation")


def _intent_aware_opener(ctx: WorkspaceContext) -> str | None:
    """Build a context-aware first assistant opener from ``intent_signal``.

    Sprint 6 Phase 6-C: seed an initial assistant message so the AI opens
    already knowing the user's intent. Returns None when no opener applies
    (no intent, or an intent without a specialized opener).
    """
    intent = (ctx.intent_signal or "").strip().lower()
    if not intent:
        return None

    entity_type = (ctx.entity_type or "").strip().lower()
    entity_name = (ctx.entity_name or "").strip()

    if intent == "create" and entity_type == "rule":
        subject = f"table {entity_name}" if entity_name else "your table"
        return (
            f"I see you want to create a new DQ rule. Based on {subject}'s "
            "profile, I'd suggest starting with a completeness or uniqueness "
            "check on the key fields — tell me which fields matter most and "
            "I'll draft the rule."
        )

    if intent == "debug":
        if entity_name:
            return (
                f"I see you're debugging {entity_name}. Share the failing rows "
                "or the error you're seeing and I'll help trace the root cause."
            )
        return (
            "I see you're debugging. Share the failure context — the rule, "
            "the failing rows, or the error message — and I'll help trace it."
        )

    if intent in ("explore", "edit"):
        if entity_name:
            return (
                f"You're working on {entity_name}. What would you like to do "
                "with it — inspect, edit, or analyze?"
            )
        if entity_type:
            return f"You're working on a {entity_type}. How can I help?"
        return "How can I help with your workspace?"

    return None


def _domain_context_prompt_prefix(ctx: DomainContext) -> str:
    """Render a DomainContext into a compact system-prompt prefix."""
    lines = [f"[Domain: {ctx.app_identifier}]"]
    knowledge = ctx.domain_knowledge or {}
    config = ctx.domain_config or {}
    if knowledge.get("protocol"):
        lines.append(f"Protocol: {knowledge['protocol']}")
    scopes = knowledge.get("scopes") or {}
    if scopes:
        lines.append("Scopes:")
        for key, desc in scopes.items():
            lines.append(f"  - {key}: {desc}")
    if knowledge.get("ar_version"):
        lines.append(f"GWP version: {knowledge['ar_version']}")
    if knowledge.get("units"):
        lines.append(f"Units: {', '.join(knowledge['units'])}")
    if knowledge.get("calculation_methods"):
        lines.append(
            f"Calculation methods: {', '.join(knowledge['calculation_methods'])}"
        )
    if config:
        for key, value in config.items():
            if isinstance(value, list):
                lines.append(f"{key}: {', '.join(value)}")
            else:
                lines.append(f"{key}: {value}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _format_dq_results(response) -> str:
    """Format DQ validate results as a human-readable summary."""
    from ai.protocol import DqValidateResponse
    if not response.results:
        return "No DQ rules were evaluated."

    lines = []
    for r in response.results:
        icon = "✅" if r.status == "pass" else "❌" if r.status == "fail" else "⚠️"
        lines.append(f"{icon} Rule {r.rule_id}: {r.status}")
        if r.explanation:
            lines.append(f"   {r.explanation}")
        if r.failing_rows:
            lines.append(f"   {len(r.failing_rows)} row(s) failed")
    return "\n".join(lines)


def _requested_modules_from_payload(payload: dict[str, Any]) -> list[str] | None:
    module_id = payload.get("module_id")
    if module_id is not None:
        return [str(module_id)]
    module_ids = payload.get("module_ids")
    if isinstance(module_ids, list):
        return [str(module_id) for module_id in module_ids]
    return None


def _table_names_from_payload(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    table_name = payload.get("table_name") or payload.get("name")
    if table_name:
        names.append(str(table_name))
    tables = payload.get("tables")
    if isinstance(tables, list):
        names.extend(str(table) for table in tables if table)
    return names


def _guard_table_names(scope: Scope, payload: dict[str, Any]) -> list[str] | None:
    table_names = _table_names_from_payload(payload)
    if not table_names:
        return None
    if not scope.app_identifier:
        return None

    from ai.guards import DataIsolationGuard

    allowed_prefixes = DataIsolationGuard.DOMAIN_TABLES.get(scope.app_identifier)
    if not allowed_prefixes:
        return None
    if any(any(table_name.startswith(prefix) for prefix in allowed_prefixes) for table_name in table_names):
        return table_names
    return None


def _domain_vocabulary_from_payload(payload: dict[str, Any]) -> dict[str, str] | None:
    domain_vocabulary = payload.get("domain_vocabulary")
    if isinstance(domain_vocabulary, dict):
        return domain_vocabulary
    table_name = payload.get("table_name")
    columns = payload.get("columns") or payload.get("fields") or []
    if not table_name or not columns:
        return None
    column_names = [column.get("name") for column in columns if isinstance(column, dict) and column.get("name")]
    return {str(table_name): ", ".join(column_names)} if column_names else None


def _error_message(error: dict[str, Any] | None) -> str:
    if not error:
        return "Unknown error."
    return str(error.get("message") or error.get("code") or "Unknown error.")
