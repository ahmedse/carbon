"""Phase I1-B — Platform as MCP server (HTTP endpoints).

Exposes the platform's existing AI tool catalog as an inbound MCP-over-HTTP
surface for external MCP clients:

* ``GET  {api_prefix}/mcp/``                     — discover apps (servers).
* ``GET  {api_prefix}/mcp/{app}/tools/``         — list an app's tools.
* ``POST {api_prefix}/mcp/{app}/tools/call/``    — call a tool / stage a mutation.

Everything is registry-driven (``ai.domain_protocol``), CBAC-filtered per tool
(mirroring ``CarbonHostAdapter.get_tool_catalog``), and executes through the
existing ``CarbonHostExecutor`` in-process seam — no new HTTP client, no
loopback, no re-declared tools, no new models (RULE_21 for mutations).
"""

import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import has_capability
from ai.adapter.types import ToolDef
from ai.audit_service import AuditService
from ai.domain_protocol import get_domain, has_domain, list_domains
from ai.engine.core.database import get_session_factory
from ai.engine.core.exceptions import ToolExecutionError
from ai.engine_runtime import _carbon_instance_config
from ai.host_executor import CarbonHostExecutor

logger = logging.getLogger("carbon.ai.mcp")

_api_prefix = getattr(settings, "API_PREFIX", "/api/v1/").strip("/")


def _tool_allowed(user, tool: ToolDef) -> bool:
    """Per-tool CBAC filter (mirrors ``CarbonHostAdapter.get_tool_catalog``)."""
    if tool.required_capability is None:
        return True
    return has_capability(user, tool.required_capability)


def _filter_tools(user, domain) -> list[ToolDef]:
    """Return the domain's tools the user is allowed to call."""
    return [t for t in domain.get_tools() if _tool_allowed(user, t)]


def _serialize_tool(tool: ToolDef) -> dict:
    return {
        "name": tool.id,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "output_description": tool.output_description,
    }


class McpDiscoveryView(APIView):
    """GET / — list apps (servers) that expose ≥1 CBAC-visible tool."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        servers: list[dict] = []
        for app_id in sorted(list_domains()):
            domain = get_domain(app_id)()
            tools = _filter_tools(request.user, domain)
            if not tools:
                continue
            servers.append(
                {
                    "id": app_id,
                    "app_identifier": app_id,
                    "name": domain.app_display_name,
                    "description": (
                        domain.system_prompt_extension or domain.app_display_name
                    ),
                    "tools_url": f"/{_api_prefix}/mcp/{app_id}/tools/",
                }
            )
        return Response({"servers": servers})


class McpToolsView(APIView):
    """GET /{app_identifier}/tools/ — list an app's CBAC-visible tools."""

    permission_classes = [IsAuthenticated]

    def get(self, request, app_identifier):
        if not has_domain(app_identifier):
            return Response(
                {"detail": "Unknown app_identifier"},
                status=status.HTTP_404_NOT_FOUND,
            )
        domain = get_domain(app_identifier)()
        tools = _filter_tools(request.user, domain)
        return Response({"tools": [_serialize_tool(t) for t in tools]})


class McpToolCallView(APIView):
    """POST /{app_identifier}/tools/call/ — call a tool or stage a mutation."""

    permission_classes = [IsAuthenticated]

    def post(self, request, app_identifier):
        if not has_domain(app_identifier):
            return Response(
                {"detail": "Unknown app_identifier"},
                status=status.HTTP_404_NOT_FOUND,
            )

        domain = get_domain(app_identifier)()

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"detail": "Malformed request body"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tool_id = data.get("tool")
        if not tool_id or not isinstance(tool_id, str):
            return Response(
                {"detail": "Missing 'tool'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        arguments = data.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return Response(
                {"detail": "'arguments' must be an object"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tool = next((t for t in domain.get_tools() if t.id == tool_id), None)
        if tool is None:
            return Response(
                {"detail": "Unknown tool"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not _tool_allowed(request.user, tool):
            return Response(
                {"detail": f"You do not have permission to call '{tool.id}'."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # api_name = tool.id with the "{domain}." prefix stripped.
        api_name = tool.id[len(tool.domain) + 1:]

        user_pk = str(request.user.pk)
        instance_config = _carbon_instance_config(user_pk)
        factory = get_session_factory("carbon")

        def _run():
            async def _call():
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config=instance_config,
                        user_token=f"inproc:carbon:{user_pk}",
                        host_user_id=user_pk,
                    )
                    entry = executor.get_catalog_entry(api_name)
                    if entry is None:
                        raise ToolExecutionError(
                            f"No host API catalog entry for '{tool.id}' "
                            f"(api_name={api_name!r})."
                        )
                    method = entry.get("method", "GET")
                    path = entry.get("path", "")

                    if tool.is_mutation:
                        confirmation_message = entry.get(
                            "confirmation_message"
                        ) or (
                            f"This will execute {method} {path}. "
                            "Do you want to proceed?"
                        )
                        execution = await executor.create_pending_execution(
                            conversation_id="",
                            tool_name=f"mcp:{tool.id}",
                            method=method,
                            endpoint=path,
                            params=arguments,
                            body=None,
                            confirmation_message=confirmation_message,
                        )
                        return {
                            "requires_confirmation": True,
                            "execution_id": execution.id,
                            "confirmation_message": confirmation_message,
                        }

                    result = await executor.call_api_direct(
                        method, path, arguments, None
                    )
                    return {"result": result}

            return async_to_sync(_call)()

        try:
            payload = _run()
        except ToolExecutionError as exc:
            logger.warning("MCP tool call failed for %s: %s", tool.id, exc)
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("MCP tool call failed for %s", tool.id)
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

        AuditService.log(
            action="ai.mcp_tool_call",
            actor=request.user.pk,
            host_user_id=user_pk,
            detail={
                "source": "mcp_external",
                "tool": tool.id,
                "app_identifier": app_identifier,
            },
        )

        return Response(payload, status=status.HTTP_200_OK)
