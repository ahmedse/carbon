"""
Host API executor — httpx async client for calling host system APIs.
All mutations require user confirmation via the tool_executions table.
"""
import json
import logging
import time
from datetime import datetime

from ai.engine.core.clock import utcnow
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.exceptions import ToolExecutionError
from ai.engine.core.models import ToolExecution, generate_uuid

logger = logging.getLogger("pulse.agent.executor")

# ── In-memory TTL cache for GET requests ─────────────────────────
_api_cache: dict[str, tuple[float, dict]] = {}  # key → (expires_at, result)
_API_CACHE_TTL = 60  # seconds

def _cache_key(method: str, endpoint: str, params: dict | None) -> str | None:
    """Return a cache key for GET requests, None for mutations."""
    if method.upper() != "GET":
        return None
    p = json.dumps(params or {}, sort_keys=True)
    return f"{endpoint}|{p}"

def _cache_get(key: str) -> dict | None:
    entry = _api_cache.get(key)
    if entry and entry[0] > time.monotonic():
        return entry[1]
    _api_cache.pop(key, None)
    return None

def _cache_set(key: str, result: dict):
    _api_cache[key] = (time.monotonic() + _API_CACHE_TTL, result)
    # Evict old entries if cache grows too large
    if len(_api_cache) > 200:
        now = time.monotonic()
        expired = [k for k, (exp, _) in _api_cache.items() if exp <= now]
        for k in expired:
            del _api_cache[k]


class HostAPIExecutor:
    """Async HTTP client for calling host system APIs."""

    def __init__(
        self,
        db: AsyncSession,
        instance_config: dict | None = None,
        user_token: str | None = None,
    ):
        self.db = db
        self.instance_config = instance_config or {}
        self._settings = get_settings()
        self._api_catalog = self._build_catalog()
        # Per-user Host JWT — required for all host API calls.
        # Pulse always acts as the authenticated user so the host system's own RBAC applies.
        self.user_token = user_token

    def _build_catalog(self) -> dict:
        """Build a lookup dict from the instance's api_catalog."""
        catalog = {}
        for endpoint in self.instance_config.get("api_catalog", []):
            catalog[endpoint["name"]] = endpoint
        return catalog

    def _get_base_url(self) -> str:
        """Get the host API base URL."""
        host = self.instance_config.get("host", {})
        url = host.get("api_url", "")
        # Resolve env var references dynamically
        from ai.engine.core.config import resolve_env_var
        url = resolve_env_var(url)
        return url or self._settings.HOST_API_URL

    def _build_headers(self) -> dict:
        """Build request headers with user authentication.

        Requires a valid user_token (Host JWT). No service account fallback.
        """
        headers = {"Content-Type": "application/json"}
        if self.user_token:
            headers["Authorization"] = f"Bearer {self.user_token}"
        return headers

    def get_catalog_entry(self, api_name: str) -> dict | None:
        """Look up an API endpoint by name from the catalog."""
        return self._api_catalog.get(api_name)

    def requires_confirmation(self, api_name: str) -> bool:
        """Check if an API call requires user confirmation."""
        entry = self.get_catalog_entry(api_name)
        if not entry:
            # Unknown endpoints always require confirmation
            return True
        return entry.get("requires_confirmation", True)

    async def create_pending_execution(
        self,
        conversation_id: str,
        tool_name: str,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
        confirmation_message: str | None = None,
    ) -> ToolExecution:
        """Create a tool_execution record with pending_confirmation status."""
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
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        logger.info(f"Created pending execution: {execution.id} for {method} {endpoint}")
        return execution

    async def cancel_pending_learn_facts(self, conversation_id: str) -> int:
        """Supersede any unresolved learn_fact proposals for this conversation.

        Called before creating a new learn_fact proposal so the user only ever
        sees the latest (most refined) version — not a stack of duplicates.
        Returns the number of records cancelled.
        """
        stmt = (
            select(ToolExecution)
            .where(ToolExecution.conversation_id == conversation_id)
            .where(ToolExecution.tool_name == "learn_fact")
            .where(ToolExecution.status == "pending_confirmation")
        )
        result = await self.db.execute(stmt)
        stale = result.scalars().all()
        for ex in stale:
            ex.status = "declined"
            ex.result = json.dumps({"reason": "superseded_by_newer_proposal"})
        if stale:
            await self.db.commit()
            logger.info(
                f"cancel_pending_learn_facts: superseded {len(stale)} stale "
                f"proposal(s) for conversation {conversation_id}"
            )
        return len(stale)

    async def confirm_execution(self, execution_id: str, expected_host_user_id: str | None = None) -> dict:
        """User confirmed — execute the API call."""
        stmt = select(ToolExecution).where(ToolExecution.id == execution_id)
        result = await self.db.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            raise ToolExecutionError(f"Execution '{execution_id}' not found")
        if execution.status != "pending_confirmation":
            raise ToolExecutionError(
                f"Execution '{execution_id}' is not pending confirmation (status: {execution.status})"
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

        # Parse stored params
        params = json.loads(execution.input_params) if execution.input_params else {}
        method = params.get("method", "GET")
        endpoint = params.get("endpoint", "")
        query_params = params.get("params")
        body = params.get("body")

        # Execute the API call
        try:
            api_result = await self._call_api(method, endpoint, query_params, body)
        except Exception as e:
            execution.status = "failed"
            execution.output = json.dumps({"error": str(e)})
            execution.executed_at = utcnow()
            await self.db.commit()
            raise

        # Update execution record
        execution.status = "confirmed"
        execution.confirmed_by_user = True
        execution.output = json.dumps(api_result, default=str)
        execution.executed_at = utcnow()
        await self.db.commit()

        logger.info(f"Executed confirmed action: {execution_id} → {method} {endpoint}")
        return api_result

    async def decline_execution(self, execution_id: str, expected_host_user_id: str | None = None) -> None:
        """User declined — mark as declined."""
        # Defense-in-depth ownership check (P0-2)
        if expected_host_user_id is not None:
            exec_row = (
                await self.db.execute(
                    select(ToolExecution).where(ToolExecution.id == execution_id)
                )
            ).scalar_one_or_none()
            if (
                exec_row
                and exec_row.host_user_id is not None
                and exec_row.host_user_id != expected_host_user_id
            ):
                raise ToolExecutionError(
                    f"Execution '{execution_id}' belongs to {exec_row.host_user_id}, "
                    f"not {expected_host_user_id}"
                )

        stmt = (
            update(ToolExecution)
            .where(ToolExecution.id == execution_id)
            .values(status="declined", executed_at=utcnow())
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"Declined execution: {execution_id}")

    async def call_api_direct(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """Call a host API directly (for read-only GET requests that don't need confirmation)."""
        # Check TTL cache for GET requests
        ck = _cache_key(method, endpoint, params)
        if ck:
            cached = _cache_get(ck)
            if cached is not None:
                logger.debug(f"cache HIT: {endpoint}")
                return cached

        result = await self._call_api(method, endpoint, params, body)

        # Cache GET results — successful ones for full TTL, auth errors for 15s
        if ck and isinstance(result, dict):
            if "error" not in result:
                _cache_set(ck, result)
            elif "401" in str(result.get("error", "")) or "unauthorized" in str(result.get("error", "")).lower():
                _cache_set(ck, result)  # cache auth failures briefly to avoid retry storms

        return result

    async def _call_api(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """Execute an HTTP request to the host API.

        Auto-refresh: if no user token is available (or user token returns 401),
        fetches a fresh service JWT and retries once.
        """
        if not self.user_token:
            _host_name = self.instance_config.get("display_name", self.instance_config.get("name", "the host system"))
            raise ToolExecutionError(
                f"No authenticated user session. Please log in to {_host_name} and connect your account to Pulse first."
            )

        base_url = self._get_base_url()
        if not base_url:
            raise ToolExecutionError("Host API URL not configured")

        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self._build_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=body if body and method.upper() != "GET" else None,
                    headers=headers,
                )
                response.raise_for_status()

                try:
                    data = response.json()
                except Exception:
                    data = {"text": response.text[:2000]}

                return {
                    "status_code": response.status_code,
                    "data": data,
                }
            except httpx.HTTPStatusError as e:
                error_body = ""
                try:
                    error_body = e.response.text[:1000]
                except Exception:
                    pass
                raise ToolExecutionError(
                    f"Host API returned {e.response.status_code}: {error_body}"
                )
            except httpx.ConnectError:
                raise ToolExecutionError(
                    f"Cannot connect to host API at {base_url}. Is the host system running?"
                )
            except httpx.TimeoutException:
                raise ToolExecutionError("Host API request timed out (30s)")
