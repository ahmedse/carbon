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
from typing import Any

from django.utils import timezone

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
from ai.domain_protocol import DomainContext, get_domain, has_domain
from ai.domain import emissions  # noqa: F401  (registers the emissions domain)
from ai.domain import water  # noqa: F401  (registers the water domain)
from ai.context_assembler import assemble_context
from ai.generation_registry import GENERATIONS

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

        # Auto-title from the first user message while the title is still default.
        self._maybe_autotitle(conversation, content)

        # Save user message
        user_msg = AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=content,
        )

        # Build fresh scope (NOT frozen — user's permissions may have changed)
        scope = build_scope(user)
        if conversation.app_identifier:
            scope.app_identifier = conversation.app_identifier

        # Assemble tiered, budgeted context from history (Sprint 15).
        history = list(
            conversation.messages.order_by("created_at").values(
                "role", "content", "created_at",
            )
        )
        assembled = assemble_context(conversation, history, scope)
        conv_ctx = ConversationContext(
            conversation_id=str(conversation.id),
            messages=assembled["messages"],
        )

        # Persist the context budget telemetry snapshot.
        conversation.context_snapshot_json = assembled["budget"]
        conversation.save(update_fields=["context_snapshot_json"])

        # Mark working
        conversation.status = "working"
        conversation.save(update_fields=["status"])

        # Route to provider based on conversation type.
        try:
            response = self._route_typed_message(
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

    def send_message_stream(
        self,
        user,
        conversation_id: str,
        content: str,
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

        conv_id = str(conversation.id)
        GENERATIONS.start(conv_id)
        generation = AIGeneration.objects.create(
            conversation=conversation,
            token=uuid.uuid4().hex,
            status="running",
        )

        def _finalize_generation(final_status: str) -> None:
            generation.status = final_status
            update_fields = ["status"]
            if final_status == "cancelled":
                generation.cancelled_at = timezone.now()
                update_fields.append("cancelled_at")
            generation.save(update_fields=update_fields)

        conv_type = conversation.conversation_type

        try:
            # Save user message (identical to send_message).
            self._maybe_autotitle(conversation, content)
            AIMessage.objects.create(
                conversation=conversation,
                role="user",
                content=content,
            )

            # Build fresh scope (NOT frozen — user's permissions may have changed).
            scope = build_scope(user)
            if conversation.app_identifier:
                scope.app_identifier = conversation.app_identifier

            # Assemble tiered, budgeted context from history (Sprint 15).
            history = list(
                conversation.messages.order_by("created_at").values(
                    "role", "content", "created_at",
                )
            )
            assembled = assemble_context(conversation, history, scope)
            conv_ctx = ConversationContext(
                conversation_id=conv_id,
                messages=assembled["messages"],
            )

            # Persist the context budget telemetry snapshot.
            conversation.context_snapshot_json = assembled["budget"]
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
                )

                partial_parts: list[str] = []
                for kind, value in self.provider.chat_stream(chat_request):
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
                        self._save_assistant_message(
                            conversation,
                            value,
                            metadata={},
                            status="failed",
                            message_status="failed",
                        )
                        _finalize_generation("failed")
                        yield {"type": "error", "error": value}
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
                        )
                        _finalize_generation("completed")
                        done_frame = {
                            "type": "done",
                            "conversation": self.get_conversation(user, conv_id),
                        }
                        if usage:
                            done_frame["usage"] = usage
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

                self._route_typed_message(conversation, content, conv_ctx, scope)

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
            msg = f"{conv_type} failed: {exc}"
            self._save_assistant_message(
                conversation,
                msg,
                metadata={},
                status="failed",
                message_status="failed",
            )
            _finalize_generation("failed")
            yield {"type": "error", "error": msg}
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
        from django.db.models import Q

        from ai.models import AIConversation

        qs = AIConversation.objects.filter(user=user)
        if is_archived is True:
            qs = qs.filter(is_archived=True)
        else:
            qs = qs.filter(is_archived=False)
        if is_pinned is not None:
            qs = qs.filter(is_pinned=is_pinned)
        if conversation_type:
            qs = qs.filter(conversation_type=conversation_type)
        if query:
            qs = qs.filter(Q(title__icontains=query))
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
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
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
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

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
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

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

        Returns the serialized conversation.
        """
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found.")

        if not force and conversation.summary:
            return _serialize_conversation(conversation)

        # TODO(Sprint 16+): LLM summarizer seam — dispatch a compaction prompt to
        # the provider and store the returned summary.  The deterministic fallback
        # below is the shipped behavior: cheap, deterministic, and offline-safe
        # (no hidden LLM cost in tests).
        user_messages = list(
            conversation.messages.filter(role="user").order_by("created_at")[:3]
        )
        snippets = []
        for message in user_messages:
            text = (message.content or "").strip()
            if text:
                snippets.append(text[:120])

        conversation.summary = " ".join(snippets) if snippets else "No user messages yet."
        conversation.save(update_fields=["summary"])
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
        from ai.models import AIConversation

        try:
            conversation = AIConversation.objects.get(
                id=conversation_id, user=user,
            )
        except AIConversation.DoesNotExist:
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
    ) -> dict[str, Any]:
        """Edit a user message's content, then regenerate the reply.

        Only user messages are editable.  Raises ``NotUserMessageError`` (a
        ``ValueError`` subclass) for non-user messages so the API can map it
        to a 400.
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

        self.send_message(user, conversation_id, content)
        return self.get_conversation(user, conversation_id)

    def _maybe_autotitle(self, conversation, content: str) -> None:
        """Set the conversation title from the first user message.

        Only fires while the title is still a default title (from
        ``_default_title``) and no prior user message exists, so an explicit
        user rename is never overwritten.
        """
        if not content:
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
        return self._send_chat_message(conversation, content, conv_ctx, scope)

    def _progress_stage_label(self, conversation_type: str) -> str:
        """Human label for the progress frame of a non-chat generation."""
        labels = {
            "dq_validate": "Validating rows…",
            "dq_suggest": "Analyzing table profile…",
            "nl_query": "Translating question to SQL…",
            "anomaly": "Detecting anomalies…",
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
        message = self._prepend_domain_context(scope, message)
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

    def _prepend_domain_context(self, scope: Scope, content: str) -> str:
        """Inject domain context (GHG vocabulary, etc.) when scope.app_identifier
        maps to a registered domain. AI CONTRACT §8: platform-level injection.

        NEVER crashes on missing/unregistered/malformed domain — returns
        content unchanged in every failure path.
        """
        if not scope or not getattr(scope, "app_identifier", None):
            return content
        if not has_domain(scope.app_identifier):
            return content
        try:
            ctx = get_domain(scope.app_identifier)().get_domain_context()
        except Exception:
            return content
        prefix = _domain_context_prompt_prefix(ctx)
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
        usage: dict[str, Any] | None = None,
        message_status: str = "completed",
    ) -> dict[str, Any]:
        from ai.models import AIMessage

        ai_msg = AIMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=content,
            metadata_json=metadata,
            token_usage_json=usage or {},
            status=message_status,
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
            message_status="failed",
        )

    def _build_ai_message(
        self,
        conversation,
        status: str,
        content: str | None,
        follow_up_questions: list[str],
        usage: dict[str, Any] | None = None,
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
            usage=usage,
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
        "is_archived": conversation.is_archived,
        "is_pinned": conversation.is_pinned,
        "summary": conversation.summary,
        "last_message_at": (
            conversation.last_message_at.isoformat()
            if conversation.last_message_at
            else None
        ),
        "visibility": conversation.visibility,
        "context_snapshot_json": conversation.context_snapshot_json,
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
        "token_usage_json": message.token_usage_json,
        "parent_message_id": (
            str(message.parent_message_id)
            if message.parent_message_id
            else None
        ),
        "status": message.status,
        "provider_model": message.provider_model,
        "outcome": message.outcome,
        "correction_text": message.correction_text,
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
