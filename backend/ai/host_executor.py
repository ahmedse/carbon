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
    """Normalize an endpoint path for the in-process route table.

    Strips the leading scheme-ish slash(es), any trailing slash, and any
    query string so ``/carbon-api/dataschema/tables/?module_id=31`` maps to
    ``carbon-api/dataschema/tables``.
    """
    path = (endpoint or "").strip()
    if "?" in path:
        path = path.split("?", 1)[0]
    while path.startswith("/"):
        path = path[1:]
    return path.rstrip("/")


#: Endpoints handled in-process instead of over HTTP.  Values are the names of
#: private ``_<name>_in_process`` coroutines on :class:`CarbonHostExecutor`.
_IN_PROCESS_ENDPOINTS: dict[str, str] = {
    "carbon-api/dq/rules": "dq_rules",
    "carbon-api/dataschema/tables": "tables",
    "carbon-api/dataschema/tables/detail": "table_detail",
    "carbon-api/dq/rule-assignments": "rule_assignments",
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
        """Execute a host API call in-process (no HTTP, no JWT).

        Both GET (read-only, no confirmation) and POST (mutation, staged via
        ``create_pending_execution``) dispatch through this method so the LLM's
        ``call_host_api`` tool sees a uniform transport.
        """
        key = _canonical_endpoint(endpoint)
        handler_name = _IN_PROCESS_ENDPOINTS.get(key)
        if handler_name:
            handler = getattr(self, f"_{handler_name}_in_process", None)
            if handler is not None:
                # Merge query-string params (e.g. the `?module_id={id}` baked
                # into a catalog path) into the explicit params dict so
                # in-process handlers see a uniform view.
                merged = dict(params or {})
                if "?" in (endpoint or ""):
                    from urllib.parse import parse_qs, urlsplit

                    for qk, qv in parse_qs(urlsplit(endpoint).query).items():
                        merged.setdefault(qk, qv[0] if len(qv) == 1 else qv)
                return await handler(
                    method=method.upper(), params=merged, body=body or {}
                )
        raise ToolExecutionError(
            f"Host API endpoint {method} {endpoint} is not available for "
            "in-process execution from the AI workspace."
        )

    async def _dq_rules_in_process(
        self, method: str = "POST", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET/POST /carbon-api/dq/rules/ executed directly in-process.

        - ``POST`` creates a rule via ``DQRuleSerializer`` and returns the same
          ``{"status_code": 201, "data": {...}}`` shape the HTTP transport would.
        - ``GET`` lists rules (used by ``list_dq_rules`` so the LLM can reuse an
          existing rule instead of duplicating it).
        """
        from asgiref.sync import sync_to_async
        from django.contrib.auth import get_user_model

        if method == "GET":
            return await self._list_dq_rules_in_process(params or {})

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

    async def _list_dq_rules_in_process(self, params: dict) -> dict:
        """GET /carbon-api/dq/rules/ — list non-archived rules visible to the user."""
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for rule listing — please refresh the page."
            )

        def _list() -> list[dict]:
            from dq.models import DQRule
            from dq.views import _get_user_org_units

            qs = DQRule.objects.filter(archived=False)
            if not (user.is_superuser or user.is_staff):
                org_units = list(_get_user_org_units(user))
                if not org_units:
                    return []
                qs = qs.filter(
                    field_assignments__data_table__module__org_unit_id__in=org_units
                ).distinct()
            search = params.get("search")
            if search:
                qs = qs.filter(name__icontains=search)
            return [
                {
                    "id": r.pk,
                    "name": r.name,
                    "rule_type": r.rule_type,
                    "rule_level": r.rule_level,
                    "severity": r.severity,
                    "dimension": r.dimension,
                    "is_active": r.is_active,
                }
                for r in qs[:200]
            ]

        try:
            data = await sync_to_async(_list, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process DQ rule listing failed")
            raise ToolExecutionError(f"Rule listing failed: {exc}") from exc
        return {"status_code": 200, "data": {"results": data}}

    async def _tables_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET/POST /carbon-api/dataschema/tables/ executed directly in-process.

        - ``GET`` lists tables (optionally filtered by ``module_id``) — backs
          ``get_data_product_details`` / ``list_data_tables``.
        - ``POST`` creates a table with optional nested ``fields`` (schema
          change) and mirrors ``DataTableViewSet.perform_create`` logging.
        """
        if method == "GET":
            return await self._list_tables_in_process(params or {})
        return await self._create_table_in_process(body or {})

    async def _list_tables_in_process(self, params: dict) -> dict:
        """GET /carbon-api/dataschema/tables/ — tables visible to the user."""
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for table listing — please refresh the page."
            )

        def _list() -> list[dict]:
            from dataschema.models import DataTable
            from accounts.rbac_utils import get_visible_module_ids

            qs = DataTable.objects.select_related("module").filter(is_archived=False)
            visible = get_visible_module_ids(user)
            if visible is not None:
                qs = qs.filter(module_id__in=visible)
            module_id = params.get("module_id")
            if module_id:
                qs = qs.filter(module_id=module_id)
            return [
                {
                    "id": t.pk,
                    "title": t.title,
                    "name": t.name,
                    "module": t.module_id,
                    "module_name": getattr(t.module, "name", None),
                    "description": t.description,
                    "is_locked": t.is_locked,
                }
                for t in qs[:200]
            ]

        try:
            data = await sync_to_async(_list, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process data table listing failed")
            raise ToolExecutionError(f"Table listing failed: {exc}") from exc
        return {"status_code": 200, "data": {"results": data}}

    async def _table_detail_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET /carbon-api/dataschema/tables/detail/?id=N — read-only detail.

        Returns one table with its active fields (id/name/label). Added for
        the Flight Director acceptance re-query (Phase 25-C, spec §3.5: the
        ``table_fields`` criterion asserts the EXACT field set vs the brief).
        Read-only — never stages or mutates; visibility-scoped exactly like
        ``_list_tables_in_process`` (CBAC via ``get_visible_module_ids``).
        """
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for table detail — please refresh the page."
            )

        table_id = (params or {}).get("id") or (params or {}).get("table_id")
        if not table_id:
            return {
                "status_code": 400,
                "data": {"detail": "table id is required"},
            }

        def _detail() -> dict | None:
            from dataschema.models import DataTable
            from accounts.rbac_utils import get_visible_module_ids

            try:
                table = DataTable.objects.select_related("module").get(
                    pk=table_id, is_archived=False
                )
            except (DataTable.DoesNotExist, ValueError, TypeError):
                return None
            visible = get_visible_module_ids(user)
            if visible is not None and table.module_id not in visible:
                return None
            fields = [
                {"id": f.pk, "name": f.name, "label": f.label}
                for f in table.fields.filter(is_active=True, is_archived=False)
            ]
            return {
                "id": table.pk,
                "title": table.title,
                "name": table.name,
                "module": table.module_id,
                "module_name": getattr(table.module, "name", None),
                "description": table.description,
                "is_locked": table.is_locked,
                "fields": fields,
            }

        try:
            data = await sync_to_async(_detail, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process table detail lookup failed")
            raise ToolExecutionError(f"Table detail lookup failed: {exc}") from exc
        if data is None:
            return {"status_code": 404, "data": {"detail": "Table not found"}}
        return {"status_code": 200, "data": data}

    async def _create_table_in_process(self, body: dict) -> dict:
        """POST /carbon-api/dataschema/tables/ — create table + optional fields."""
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for table creation — please refresh the page."
            )

        def _create() -> dict:
            from dataschema.models import DataTable
            from dataschema.serializers import DataFieldSerializer, DataTableSerializer
            from dataschema.views import _log_schema_change

            serializer = DataTableSerializer(data=body)
            if not serializer.is_valid():
                raise ToolExecutionError(
                    "Table validation failed: "
                    + json.dumps(serializer.errors, default=str)[:1200]
                )
            table = serializer.save(created_by=user)
            fields = []
            for i, raw in enumerate(body.get("fields") or []):
                field_body = dict(raw)
                field_body.setdefault("data_table", table.pk)
                field_body.setdefault("order", i)
                fser = DataFieldSerializer(data=field_body)
                if not fser.is_valid():
                    raise ToolExecutionError(
                        "Field validation failed: "
                        + json.dumps(fser.errors, default=str)[:1200]
                    )
                field = fser.save(created_by=user)
                fields.append({"id": field.pk, "name": field.name, "label": field.label})
            _log_schema_change(
                user, "add", data_table=table, after=DataTableSerializer(table).data
            )
            return {
                "id": table.pk,
                "title": table.title,
                "name": table.name,
                "module": table.module_id,
                "module_name": getattr(table.module, "name", None),
                "description": table.description,
                "is_locked": table.is_locked,
                "fields": fields,
            }

        try:
            data = await sync_to_async(_create, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process data table creation failed")
            raise ToolExecutionError(f"Table creation failed: {exc}") from exc
        return {"status_code": 201, "data": data}

    async def _rule_assignments_in_process(
        self, method: str = "POST", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """POST /carbon-api/dq/rule-assignments/ — bind rule(s) to a table.

        Accepts either ``{"rule": <id>, "data_table": <id>, "data_field": <id|null>}``
        or ``{"table_id": <id>, "dq_rule_ids": [<ids>]}``.
        """
        from asgiref.sync import sync_to_async

        if method != "POST":
            raise ToolExecutionError(
                "Rule assignments only support POST via call_host_api."
            )
        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for rule binding — please refresh the page."
            )

        def _bind() -> dict:
            from dq.models import RuleFieldAssignment

            table_id = body.get("data_table") or body.get("table_id")
            rule_ids = body.get("dq_rule_ids")
            if not rule_ids and body.get("rule"):
                rule_ids = [body.get("rule")]
            if not table_id or not rule_ids:
                raise ToolExecutionError(
                    "Rule binding requires 'data_table'/'table_id' and "
                    "'rule'/'dq_rule_ids'."
                )
            data_field = body.get("data_field")
            created = []
            for rid in rule_ids:
                # Guard against the unique_rule_table constraint when the LLM
                # retries or reuses an existing binding.
                if RuleFieldAssignment.objects.filter(
                    rule_id=rid, data_table_id=table_id, data_field_id=data_field
                ).exists():
                    continue
                assn = RuleFieldAssignment.objects.create(
                    rule_id=rid, data_table_id=table_id, data_field_id=data_field
                )
                created.append({"id": assn.pk, "rule": assn.rule_id, "data_table": assn.data_table_id})
            return {"bindings": created, "count": len(created)}

        try:
            data = await sync_to_async(_bind, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process rule binding failed")
            raise ToolExecutionError(f"Rule binding failed: {exc}") from exc
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
