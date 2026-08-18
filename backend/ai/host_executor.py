"""In-process Carbon host executor — Django-side transport for Pulse tools.

The vendored engine's :class:`HostAPIExecutor` talks to the host system over
HTTP + per-user JWT.  For the Carbon platform the host API *is* this Django
process, so the transport is in-process:

  * ``create_pending_execution`` stages a ``ToolExecution`` row exactly as the
    engine designs it (status ``pending_confirmation``, RULE_21).
  * ``confirm_execution`` / ``decline_execution`` operate on the staged row
    with the Django Store session (the base class uses raw SQLAlchemy
    ``execute()``, which the Django Store session does not expose).
  * ``_call_api`` dispatches known mutation endpoints directly against the
    platform's serializers — no loopback HTTP, no JWT minting.

The plugin layer (``ai.plugins.create_dq_rule``) stays untouched: it only
needs ``ctx.host_api`` with a truthy ``user_token`` and a ``db`` session, both
of which this class provides.

RULE_20 applies to plugins, not to this host-side adapter: this module is the
Carbon implementation of the executor interface and is allowed to import the
platform's own serializers/models (it plays the same role as the HTTP view
stack would).
"""

from __future__ import annotations

import json
import logging

from ai.engine.agent.executor import HostAPIExecutor
from ai.engine.core.exceptions import ToolExecutionError

logger = logging.getLogger("carbon.ai.host_executor")


def _canonical_endpoint(endpoint: str) -> str:
    """Normalize an endpoint path for the in-process route table."""
    path = (endpoint or "").strip()
    while path.startswith("/"):
        path = path[1:]
    return path.rstrip("/")


#: Endpoints handled in-process instead of over HTTP.  Values are the names of
#: private ``_<name>_in_process`` coroutines on :class:`CarbonHostExecutor`.
_IN_PROCESS_ENDPOINTS: dict[str, str] = {
    "carbon-api/dq/rules": "dq_rules",
}


class CarbonHostExecutor(HostAPIExecutor):
    """HostAPIExecutor whose transport is this Django process.

    ``user_token`` is a synthetic marker (``inproc:<app>:<user_id>``) — the
    plugin layer gates on truthiness, and no real JWT is ever needed because
    requests never leave the process.  ``host_user_id`` is the Django user PK
    the staged actions execute as.
    """

    def __init__(
        self,
        db,
        instance_config: dict | None = None,
        user_token: str | None = None,
        host_user_id: str | None = None,
    ):
        super().__init__(db, instance_config=instance_config, user_token=user_token)
        self.host_user_id = host_user_id

    # ── In-process transport ────────────────────────────────────────────

    async def _call_api(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """Execute a host API call in-process (no HTTP, no JWT)."""
        key = _canonical_endpoint(endpoint)
        handler_name = _IN_PROCESS_ENDPOINTS.get(key) if method.upper() == "POST" else None
        if handler_name:
            handler = getattr(self, f"_{handler_name}_in_process", None)
            if handler is not None:
                return await handler(body or {})
        raise ToolExecutionError(
            f"Host API endpoint {method} {endpoint} is not available for "
            "in-process execution from the AI workspace."
        )

    async def _dq_rules_in_process(self, body: dict) -> dict:
        """POST /carbon-api/dq/rules/ executed directly against DQRuleSerializer.

        Returns the same ``{"status_code": 201, "data": {...}}`` shape the HTTP
        transport would, so ``confirm_execution`` stays uniform.
        """
        from asgiref.sync import sync_to_async
        from django.contrib.auth import get_user_model

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for rule creation — please refresh the page."
            )

        def _create() -> dict:
            from dq.serializers import DQRuleSerializer

            serializer = DQRuleSerializer(data=body)
            if not serializer.is_valid():
                raise ToolExecutionError(
                    "Rule validation failed: "
                    + json.dumps(serializer.errors, default=str)[:1200]
                )
            rule = serializer.save(created_by=user)
            return {
                "id": rule.pk,
                "name": rule.name,
                "rule_type": rule.rule_type,
                "rule_level": rule.rule_level,
                "severity": rule.severity,
                "dimension": rule.dimension,
                "is_active": rule.is_active,
            }

        try:
            data = await sync_to_async(_create, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process DQ rule creation failed")
            raise ToolExecutionError(f"Rule creation failed: {exc}") from exc
        return {"status_code": 201, "data": data}

    async def _resolve_user(self):
        """Resolve the Django user for ``host_user_id`` (or ``None``)."""
        from asgiref.sync import sync_to_async
        from django.contrib.auth import get_user_model

        if not self.host_user_id:
            return None
        User = get_user_model()
        try:
            return await sync_to_async(User.objects.get)(pk=self.host_user_id)
        except User.DoesNotExist:
            return None

    # ── Confirmation lifecycle (Django Store-session compatible) ────────

    async def create_pending_execution(
        self,
        conversation_id: str,
        tool_name: str,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
        confirmation_message: str | None = None,
    ) -> "ToolExecution":
        """Stage a pending confirmation, stamped with the acting user.

        Same contract as :meth:`HostAPIExecutor.create_pending_execution`,
        plus ``host_user_id`` so ownership checks (P0-2) and tenant filtering
        hold in the in-process transport.
        """
        from ai.engine.core.models import ToolExecution, generate_uuid

        execution = ToolExecution(
            id=generate_uuid(),
            conversation_id=conversation_id,
            tool_name=tool_name,
            input_params=json.dumps({
                "method": method,
                "endpoint": endpoint,
                "params": params,
                "body": body,
                "confirmation_message": confirmation_message,
            }),
            status="pending_confirmation",
            confirmed_by_user=False,
            host_user_id=self.host_user_id,
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        logger.info("Created pending execution: %s for %s %s", execution.id, method, endpoint)
        return execution

    async def confirm_execution(
        self,
        execution_id: str,
        expected_host_user_id: str | None = None,
    ) -> dict:
        """Confirm a staged execution and run it in-process.

        Re-implements :meth:`HostAPIExecutor.confirm_execution` using the
        Django Store session surface (``select``/``commit`` — the base class
        uses SQLAlchemy ``execute()`` which the Store session does not expose).
        """
        from ai.engine.core.models import ToolExecution

        rows = await self.db.select(ToolExecution, {"id": execution_id})
        execution = rows[0] if rows else None

        if execution is None:
            raise ToolExecutionError(f"Execution '{execution_id}' not found")
        if execution.status != "pending_confirmation":
            raise ToolExecutionError(
                f"Execution '{execution_id}' is not pending confirmation "
                f"(status: {execution.status})"
            )

        # Defense-in-depth ownership check (P0-2)
        if (
            expected_host_user_id is not None
            and execution.host_user_id is not None
            and execution.host_user_id != expected_host_user_id
        ):
            raise ToolExecutionError(
                f"Execution '{execution_id}' belongs to {execution.host_user_id}, "
                f"not {expected_host_user_id}"
            )

        params = json.loads(execution.input_params) if execution.input_params else {}
        method = params.get("method", "GET")
        endpoint = params.get("endpoint", "")
        query_params = params.get("params")
        body = params.get("body")

        try:
            api_result = await self._call_api(method, endpoint, query_params, body)
        except Exception as exc:  # noqa: BLE001 - fail-visible
            execution.status = "failed"
            execution.output = json.dumps({"error": str(exc)})
            execution.executed_at = _utcnow()
            await self.db.commit()
            raise

        execution.status = "confirmed"
        execution.confirmed_by_user = True
        execution.output = json.dumps(api_result, default=str)
        execution.executed_at = _utcnow()
        await self.db.commit()

        logger.info("Executed confirmed action: %s → %s %s", execution_id, method, endpoint)
        return api_result

    async def decline_execution(
        self,
        execution_id: str,
        expected_host_user_id: str | None = None,
    ) -> None:
        """Decline a staged execution (Django Store-session compatible)."""
        from ai.engine.core.models import ToolExecution

        rows = await self.db.select(ToolExecution, {"id": execution_id})
        execution = rows[0] if rows else None

        if expected_host_user_id is not None and execution is not None:
            if (
                execution.host_user_id is not None
                and execution.host_user_id != expected_host_user_id
            ):
                raise ToolExecutionError(
                    f"Execution '{execution_id}' belongs to {execution.host_user_id}, "
                    f"not {expected_host_user_id}"
                )

        if execution is not None and execution.status == "pending_confirmation":
            execution.status = "declined"
            execution.executed_at = _utcnow()
            await self.db.commit()


def _utcnow():
    """Timezone-aware now for ``executed_at`` (matches engine clock)."""
    from django.utils.timezone import now

    return now()
