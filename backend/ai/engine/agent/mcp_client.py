"""
MCP (Model Context Protocol) client — connects Pulse to external tool servers.

Discovers tools from user-configured MCP servers at startup and registers
them alongside Pulse's built-in tools.  All server names, commands, and keys
come from MCP_SERVERS config — nothing is hardcoded.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.agent.mcp_client")


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class MCPTool:
    """A single tool discovered from an MCP server."""
    name: str            # "mcp_brave_web_search"
    server_name: str     # "brave"
    description: str
    input_schema: dict   # JSON Schema for the tool's arguments


@dataclass
class MCPServer:
    """A connected MCP server with its discovered tools."""
    name: str
    params: Any  # StdioServerParameters (lazy import, type is mcp.StdioServerParameters)
    tools: list[MCPTool] = field(default_factory=list)


# ── Registry ───────────────────────────────────────────────────────────────────

class MCPToolRegistry:
    """Connects to MCP servers, discovers tools, and provides execution.

    All server config comes from settings.MCP_SERVERS (JSON string).  If it is
    empty or malformed, connect_all() returns an empty list — Pulse starts
    normally with only its built-in tools.
    """

    def __init__(self):
        self._servers: list[MCPServer] = []
        self._sessions: dict[str, Any] = {}  # server_name → ClientSession
        self._read_streams: list[Any] = []    # for cleanup
        self._write_streams: list[Any] = []   # for cleanup
        self._contexts: list[Any] = []        # for cleanup

    # ── connect_all ────────────────────────────────────────────────────────

    async def connect_all(self) -> list[MCPServer]:
        """Parse MCP_SERVERS config, connect to each, discover their tools.

        Returns the list of successfully connected servers (may be empty).
        Failures are logged but never raised — graceful degradation.
        """
        settings = get_settings()
        raw = (settings.MCP_SERVERS or "").strip()
        if not raw:
            logger.debug("MCP_SERVERS is empty — skipping MCP connections")
            return []

        try:
            server_configs = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("MCP_SERVERS is not valid JSON: %s", exc)
            return []

        if not isinstance(server_configs, list):
            logger.warning("MCP_SERVERS must be a JSON array, got %s", type(server_configs).__name__)
            return []

        connect_timeout = settings.MCP_CONNECT_TIMEOUT

        for cfg in server_configs:
            if not isinstance(cfg, dict):
                logger.warning("MCP server entry is not a dict, skipping: %r", cfg)
                continue

            name = cfg.get("name", "")
            if not name:
                logger.warning("MCP server entry missing 'name', skipping: %r", cfg)
                continue

            command = cfg.get("command", "")
            args = cfg.get("args", [])
            env = cfg.get("env", {})

            try:
                server = await asyncio.wait_for(
                    self.connect_server(name, command, args, env),
                    timeout=connect_timeout,
                )
                self._servers.append(server)
                logger.info(
                    "MCP server '%s' connected — %d tools discovered",
                    name, len(server.tools),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "MCP server '%s' connection timed out after %ds — skipping",
                    name, connect_timeout,
                )
            except Exception as exc:
                logger.warning(
                    "MCP server '%s' connection failed: %s — skipping",
                    name, exc,
                )

        logger.info(
            "MCP connection complete: %d/%d servers connected, %d total tools",
            len(self._servers), len(server_configs),
            sum(len(s.tools) for s in self._servers),
        )
        return self._servers

    # ── connect_server ────────────────────────────────────────────────────

    async def connect_server(
        self, name: str, command: str, args: list, env: dict,
    ) -> MCPServer:
        """Connect to a single MCP server via stdio and list its tools.

        Tool names are prefixed:  mcp_{server_name}_{tool_name}
        Capped at MCP_MAX_TOOLS_PER_SERVER.
        """
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        settings = get_settings()
        max_tools = settings.MCP_MAX_TOOLS_PER_SERVER
        prefix = settings.MCP_TOOL_PREFIX

        params = StdioServerParameters(
            command=command,
            args=list(args) if args else [],
            env=dict(env) if env else {},
        )

        # stdio_client returns an async context manager with (read, write) streams.
        # We enter both and hold them for the lifetime of the server connection.
        ctx = stdio_client(params)
        read, write = await ctx.__aenter__()
        self._contexts.append(ctx)
        self._read_streams.append(read)
        self._write_streams.append(write)

        session = await ClientSession(read, write).__aenter__()
        self._sessions[name] = session

        # Initialize the session
        await session.initialize()

        # Discover tools
        result = await session.list_tools()
        tools: list[MCPTool] = []
        for tool in result.tools[:max_tools]:
            prefixed_name = f"{prefix}{name}_{tool.name}"
            mcp_tool = MCPTool(
                name=prefixed_name,
                server_name=name,
                description=getattr(tool, "description", "") or "",
                input_schema=getattr(tool, "inputSchema", {}) or {},
            )
            tools.append(mcp_tool)

        if len(result.tools) > max_tools:
            logger.warning(
                "MCP server '%s' has %d tools, capped at %d",
                name, len(result.tools), max_tools,
            )

        server = MCPServer(name=name, params=params, tools=tools)
        return server

    # ── get_tool_definitions ───────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[dict]:
        """Return OpenAI function-call format definitions for all MCP tools."""
        definitions: list[dict] = []
        for server in self._servers:
            for tool in server.tools:
                definitions.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema or {
                            "type": "object",
                            "properties": {},
                        },
                    },
                })
        return definitions

    # ── execute_tool ───────────────────────────────────────────────────────

    async def execute_tool(self, tool_name: str, args: dict) -> dict:
        """Execute an MCP tool by its prefixed name (e.g. 'mcp_brave_web_search').

        Args:
            tool_name: The prefixed tool name (mcp_{server}_{tool}).
            args: Arguments to pass to the tool.

        Returns:
            dict with either {"result": ...} or {"error": ...}
        """
        prefix = get_settings().MCP_TOOL_PREFIX

        # Parse server name from tool name: mcp_brave_web_search → brave
        if not tool_name.startswith(prefix):
            return {"error": f"Tool '{tool_name}' is not an MCP tool (missing '{prefix}' prefix)"}

        rest = tool_name[len(prefix):]
        # Find the server whose name is a prefix of rest
        # Strategy: try each connected server; the longest matching prefix wins
        matched_server = None
        matched_tool_local_name = None
        for server in self._servers:
            server_prefix = server.name + "_"
            if rest.startswith(server_prefix):
                if matched_server is None or len(server.name) > len(matched_server.name):
                    matched_server = server
                    matched_tool_local_name = rest[len(server_prefix):]

        if matched_server is None:
            return {"error": f"No MCP server found for tool '{tool_name}'"}

        session = self._sessions.get(matched_server.name)
        if session is None:
            return {"error": f"MCP server '{matched_server.name}' is not connected"}

        try:
            result = await session.call_tool(matched_tool_local_name, arguments=args or {})
            # Extract content from the result
            if hasattr(result, "content") and result.content:
                # Content is typically a list of TextContent/ImageContent objects
                parts = []
                for item in result.content:
                    if hasattr(item, "text"):
                        parts.append(item.text)
                    elif hasattr(item, "data"):
                        parts.append(f"[binary data: {item.type}]")
                    else:
                        parts.append(str(item))
                return {"result": "\n".join(parts) if len(parts) > 1 else parts[0] if parts else ""}
            elif hasattr(result, "structured_content") and result.structured_content:
                return {"result": result.structured_content}
            else:
                return {"result": str(result)}
        except Exception as exc:
            logger.exception("MCP tool execution failed: %s", tool_name)
            return {"error": f"MCP tool '{tool_name}' failed: {exc}"}

    # ── disconnect_all ─────────────────────────────────────────────────────

    async def disconnect_all(self):
        """Close all MCP sessions and streams on shutdown."""
        for name, session in list(self._sessions.items()):
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                logger.debug("Error closing session for '%s'", name, exc_info=True)
        self._sessions.clear()

        for ctx in reversed(self._contexts):
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                logger.debug("Error closing MCP stream context", exc_info=True)
        self._contexts.clear()
        self._read_streams.clear()
        self._write_streams.clear()
        self._servers.clear()

        logger.info("All MCP connections closed")
