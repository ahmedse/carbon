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

import logging
import time
from typing import Any

from backend.ai.engine_runtime import dispatch_task, get_task
from backend.ai.protocol import (
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
    Scope,
    TableProfile,
    WorkspaceContext,
)
from backend.ai.providers.pulse import PulseProvider

logger = logging.getLogger("carbon.ai.intelligence")

# ── Scope builder ─────────────────────────────────────────────────────────


def build_scope(user) -> Scope:
    """Extract a Scope from a Django User (RBAC-aware).

    Called by every CarbonIntelligence method that takes a user.  The
    Scope is injected into every AIProvider request so the provider
    can enforce data-access boundaries.
    """
    from accounts.models import ScopedRole

    org_unit_ids: list[str] = []
    module_ids: list[str] = []
    is_read_only = True

    if user is None or not user.is_authenticated:
        return Scope()

    if user.is_superuser:
        return Scope(is_superuser=True, org_unit_ids=["*"])

    if user.is_staff:
        is_read_only = False

    roles = ScopedRole.objects.filter(user=user, is_active=True).select_related(
        "org_unit", "module"
    )

    for role in roles:
        if role.org_unit_id and str(role.org_unit_id) not in org_unit_ids:
            org_unit_ids.append(str(role.org_unit_id))
        if role.module_id and str(role.module_id) not in module_ids:
            module_ids.append(str(role.module_id))
        if not role.is_read_only:
            is_read_only = False

    return Scope(
        org_unit_ids=org_unit_ids,
        module_ids=module_ids,
        is_read_only=is_read_only,
        user_identifier=str(user.pk),
    )


# ── CarbonIntelligence ───────────────────────────────────────────────────


class CarbonIntelligence:
    """Single entry point for all AI calls in Carbon.

    Usage::

        intelligence = CarbonIntelligence()
        result = intelligence.validate_dq_rule(rule, rows, user=request.user)

    The provider is the in-process PulseProvider (the vendored engine).
    """

    def __init__(self) -> None:
        self._provider: AIProvider | None = None

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

    def send_message(
        self,
        user,
        conversation_id: str,
        content: str,
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

        # Save user message
        user_msg = AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=content,
        )

        # Build conversation context from history
        history = list(
            conversation.messages.order_by("created_at").values(
                "role", "content", "created_at",
            )
        )
        conv_ctx = ConversationContext(
            conversation_id=str(conversation.id),
            messages=[
                {
                    "role": m["role"],
                    "content": m["content"],
                    "timestamp": m["created_at"].isoformat(),
                }
                for m in history
            ],
        )

        # Build fresh scope (NOT frozen — user's permissions may have changed)
        scope = build_scope(user)
        if conversation.app_identifier:
            scope.app_identifier = conversation.app_identifier

        # Mark working
        conversation.status = "working"
        conversation.save(update_fields=["status"])

        # Route to provider based on conversation type
        conv_type = conversation.conversation_type

        try:
            if conv_type == "dq_validate":
                response = self._send_dq_validate_message(
                    conversation, conv_ctx, scope,
                )
            elif conv_type == "dq_suggest":
                response = self._send_dq_suggest_message(
                    conversation, conv_ctx, scope,
                )
            elif conv_type == "nl_query":
                response = self._send_nl_query_message(
                    conversation, content, conv_ctx, scope,
                )
            elif conv_type == "anomaly":
                response = self._send_anomaly_message(
                    conversation, content, conv_ctx, scope,
                )
            else:
                response = self._send_chat_message(
                    conversation, content, conv_ctx, scope,
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

    def get_conversation(
        self,
        user,
        conversation_id: str,
    ) -> dict[str, Any]:
        """Get a conversation with all its messages."""
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        data = _serialize_conversation(conversation)
        data["messages"] = [
            _serialize_message(m)
            for m in conversation.messages.order_by("created_at")
        ]
        return data

    def list_conversations(
        self,
        user,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List user's conversations, newest first."""
        from ai.models import AIConversation

        qs = AIConversation.objects.filter(user=user)
        if status:
            qs = qs.filter(status=status)
        qs = qs.order_by("-updated_at")[:limit]

        return [_serialize_conversation(c) for c in qs]

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
    ) -> dict[str, Any]:
        """Handle generic chat conversation messages."""
        guard_chain, operation = self._guard_workspace_operation(
            scope,
            "workspace_chat",
            conversation.task_payload_json or {},
        )
        message = self._prepend_workspace_context(conversation, content)
        chat_request = ChatRequest(
            message=message,
            conversation=conv_ctx,
            scope=scope,
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

    def _save_assistant_message(
        self,
        conversation,
        content: str,
        *,
        metadata: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        from ai.models import AIMessage

        ai_msg = AIMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=content,
            metadata_json=metadata,
        )
        conversation.status = status
        conversation.save(update_fields=["status"])
        return _serialize_message(ai_msg)

    def _save_provider_unavailable_message(self, conversation) -> dict[str, Any]:
        return self._save_assistant_message(
            conversation,
            "AI provider is currently unavailable. Please try again later.",
            metadata={},
            status="failed",
        )

    def _build_ai_message(
        self,
        conversation,
        status: str,
        content: str | None,
        follow_up_questions: list[str],
    ) -> dict[str, Any]:
        """Save AI response message and update conversation status."""
        if status == "provider_unavailable":
            return self._save_provider_unavailable_message(conversation)

        has_follow_ups = bool(follow_up_questions)

        return self._save_assistant_message(
            conversation,
            content or "",
            metadata={
                "follow_up_questions": follow_up_questions,
            } if has_follow_ups else {},
            status="needs_input" if has_follow_ups else "completed",
        )


# ── Helpers ───────────────────────────────────────────────────────────────


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
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def _serialize_message(message) -> dict[str, Any]:
    """Serialize an AIMessage to dict."""
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "content": message.content,
        "metadata_json": message.metadata_json,
        "created_at": message.created_at.isoformat(),
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


def _format_dq_results(response) -> str:
    """Format DQ validate results as a human-readable summary."""
    from backend.ai.protocol import DqValidateResponse
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
