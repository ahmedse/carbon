"""Phase I1-B — MCP server routes (mounted at ``{api_prefix}/mcp/``)."""

from django.urls import path

from ai.mcp.server_views import (
    McpDiscoveryView,
    McpToolCallView,
    McpToolsView,
)

urlpatterns = [
    path("", McpDiscoveryView.as_view(), name="mcp-discovery"),
    path(
        "<str:app_identifier>/tools/",
        McpToolsView.as_view(),
        name="mcp-tools",
    ),
    path(
        "<str:app_identifier>/tools/call/",
        McpToolCallView.as_view(),
        name="mcp-tool-call",
    ),
]
