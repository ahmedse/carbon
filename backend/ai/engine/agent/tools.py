"""
Tool definitions and execution functions for the Pulse agent.
"""
import json
import logging
import re

from ai.engine.core.config import get_settings
from ai.engine.core.exceptions import ToolExecutionError
from ai.engine.llm.router import route_chat

logger = logging.getLogger("pulse.agent.tools")

STATIC_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search Pulse's knowledge base for information about the system's entities, schema, and business meaning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query about the system.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_details",
            "description": "Get detailed schema and business description for a specific database table or API endpoint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Name of the table or entity.",
                    },
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_host_api",
            "description": "Call the host system's REST API. Use for reading data via GET endpoints (no confirmation needed) or for mutations (POST/PUT/DELETE) which require user confirmation. Consult the instance's API catalog (available through search_knowledge) for the exact endpoint names. Endpoints typically follow patterns like: list entities, get entity details, get entity records, get latest results, get daily summaries, trigger actions. IMPORTANT: for any question about a specific calendar date, you MUST pass the date through query_params (date / date_from / date_to) — never rely on 'latest' endpoints for a historical or arbitrary date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_name": {
                        "type": "string",
                        "description": "Name of the API endpoint from the catalog (e.g., 'list_datasets', 'trigger_training').",
                    },
                    "path_params": {
                        "type": "object",
                        "description": "Path parameters to substitute in the URL template (e.g., {\"id\": \"123\"}).",
                    },
                    "query_params": {
                        "type": "object",
                        "description": "Query string parameters for filtering/pagination.",
                    },
                    "body": {
                        "type": "object",
                        "description": "Request body for POST/PUT requests.",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why you're making this API call.",
                    },
                },
                "required": ["api_name", "explanation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_to",
            "description": "Navigate the user's browser to a specific page in the host system. Sends a navigation command to the widget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "description": "The frontend route to navigate to (e.g., '/dashboard', '/items/123').",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why you're suggesting this navigation.",
                    },
                },
                "required": ["route", "explanation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_entity",
            "description": (
                "Navigate to the detail page of an entity in the host system. "
                "Available entity types and their subpages depend on the connected system — "
                "they are listed in the instance configuration. "
                "Use the entity type and subpage names exactly as they appear in the config."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity to open. Must match an entity type name from the instance config.",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "The ID of the entity to navigate to.",
                    },
                    "subpage": {
                        "type": "string",
                        "description": "Optional sub-page name. Must match a subpage key from the entity config.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date for date-driven sub-pages (YYYY-MM-DD). Use the date field from the entity's resolver data if available.",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why you're opening this entity.",
                    },
                },
                "required": ["entity_type", "entity_id", "explanation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_clarification",
            "description": "Ask the user a clarifying question when the request is ambiguous and you need them to choose between specific options before you can proceed. Fetch the available options from the host system (e.g. list endpoints from the API catalog), then call this tool with those options as choices. Always use this instead of giving up or saying you can't answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The clarifying question to ask the user.",
                    },
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The available options the user can pick from (e.g. engine names, dataset names).",
                    },
                },
                "required": ["question", "choices"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learn_fact",
            "description": "PROPOSE to memorize something the user taught you — a correction, a business rule, a preference, or domain knowledge. This does NOT save anything immediately: it surfaces a preview card and the user decides whether to remember, edit, or ignore it. Use it whenever the user tells you something new about the system, corrects a mistake, or clarifies how something works. Never claim you have memorized something until the user approves the proposal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The fact to memorize, written as a clear standalone statement (e.g. 'The billing service must not be called for archived accounts').",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: 'correction' (user fixed a mistake), 'business_rule' (domain logic), 'preference' (how user wants responses), 'observation' (something you noticed).",
                        "enum": ["correction", "business_rule", "preference", "observation"],
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "A short, honest explanation of WHY you want to remember this, shown to the user so they can decide.",
                    },
                },
                "required": ["fact", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "PROPOSE to forget (archive) something previously memorized — because it is outdated, wrong, or the user asked you to unlearn it. This does NOT delete anything immediately: it surfaces a preview card and the user decides whether to forget it or keep it. Identify the fact by its memory id (if known) or by a content description; never forget silently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The id of the remembered fact to forget, if you know it.",
                    },
                    "content": {
                        "type": "string",
                        "description": "A description of the fact to forget, used to locate it when you don't have its id (e.g. 'the rule that managed datasets are DataHub-serviced').",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this should be forgotten, shown to the user so they can decide.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_ops_workflow",
            "description": (
                "Run an end-to-end operations workflow autonomously, as the user: ingest a "
                "provided CSV into the host dataset (idempotent upsert on timestamp), validate "
                "it against the live field schema, then run inference and read back the "
                "forecast/ops output. Weather and other external features are sourced by the "
                "host, never from the CSV. ALWAYS run with dry_run=true first to preview the "
                "parse/validation; only set dry_run=false once the user confirms the preview "
                "looks right. The workflow STOPS and asks if validation fails or a real write "
                "needs confirmation. Pass the staged upload_id (preferred — given to you when a "
                "CSV is uploaded) so the full file is ingested losslessly, or paste the raw CSV "
                "text into csv_content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "upload_id": {
                        "type": "string",
                        "description": "ID of a previously uploaded/staged CSV (preferred). Provided in the upload pointer message.",
                    },
                    "csv_content": {
                        "type": "string",
                        "description": "The raw CSV text to ingest (header row + data rows). Use only if no upload_id is available.",
                    },
                    "workflow": {
                        "type": "string",
                        "description": "Name of the ops workflow to run (from the instance config). Omit to use the default workflow.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true (default), parse + validate + host dry-run only; nothing is written. Set false to actually write and run inference.",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Original CSV filename, for provenance.",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why you're running this workflow.",
                    },
                },
                "required": ["explanation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_skill",
            "description": (
                "Draft a reusable skill — a packaged snippet of know-how you can invoke "
                "later by name. Kinds: 'sql_macro' (a reusable SQL fragment), 'api_call' "
                "(a host API recipe: api_name + method + path), 'prompt_template' (a "
                "reusable system/user prompt with {placeholders}), 'multi_step_plan' "
                "(a fixed sequence of steps), or 'code_snippet' (a small Python expression "
                "or function that runs in a secure sandbox — no I/O, no imports, no "
                "subprocess). Drafting is safe — it only saves the skill "
                "for this user; nothing is executed on the host."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short, unique name for the skill (e.g. 'weekly_load_report').",
                    },
                    "description": {
                        "type": "string",
                        "description": "What the skill does and when to use it.",
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["sql_macro", "api_call", "prompt_template", "multi_step_plan", "code_snippet"],
                        "description": "Skill kind — determines how invoke_skill returns the body.",
                    },
                    "signature": {
                        "type": "string",
                        "description": "JSON string describing the inputs/outputs (default '{}').",
                    },
                    "body": {
                        "type": "string",
                        "description": (
                            "JSON string with the skill payload. For sql_macro: {\"sql\": \"...\"}. "
                            "For api_call: {\"api_name\": \"...\", \"method\": \"GET\", \"path\": \"/api/...\"}. "
                            "For prompt_template: {\"system_prompt\": \"...\", \"user_prompt_template\": \"...{arg}...\"}. "
                            "For multi_step_plan: {\"steps\": [{\"tool\": \"...\", \"args\": {...}}]}. "
                            "For code_snippet: {\"code\": \"def main(x): return x * 2\", \"args_schema\": {\"x\": \"int\"}}."
                        ),
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why you're drafting this skill.",
                    },
                },
                "required": ["name", "description", "kind", "explanation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "invoke_skill",
            "description": (
                "Invoke a previously drafted or promoted skill by name. Returns the skill's "
                "body as DATA only — it does NOT execute SQL or call host APIs itself; you "
                "decide what to do with the recipe (e.g. run the SQL via the appropriate "
                "tool). Use this to reuse a known-good workflow instead of re-deriving it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to invoke.",
                    },
                    "args": {
                        "type": "object",
                        "description": "Arguments to pass into the skill body (e.g. for prompt template rendering). Default {}.",
                        "additionalProperties": True,
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why you're invoking this skill.",
                    },
                },
                "required": ["skill_name", "explanation"],
            },
        },
    },
]


async def execute_search_knowledge(
    query: str, knowledge_store=None, instance_id: str = "", **kwargs
) -> dict:
    """Semantic search of knowledge store. Returns top entities with descriptions."""
    if knowledge_store is None:
        return {"entities": [], "message": "Knowledge store not available"}

    entities = await knowledge_store.search(instance_id, query, top_k=10)
    return {"entities": entities, "count": len(entities)}


async def execute_get_entity_details(
    entity_name: str, knowledge_store=None, instance_id: str = "", **kwargs
) -> dict:
    """Lookup entity by name from knowledge store. Returns schema + description."""
    if knowledge_store is None:
        return {"entity": None, "message": "Knowledge store not available"}

    entity = await knowledge_store.get_entity(instance_id, entity_name)
    if entity:
        return {"entity": entity}
    return {"entity": None, "message": f"Entity '{entity_name}' not found"}


def _get_slug_resolution(executor, api_name: str) -> tuple[str, list[str]] | None:
    """Read slug resolution config from the executor's instance config.

    Returns (list_api_name, match_fields) or None if no resolution is configured.
    """
    if executor is None:
        return None
    cfg = getattr(executor, "instance_config", None) or {}
    slug_entries = cfg.get("tools", {}).get("slug_resolution", [])
    if not isinstance(slug_entries, list):
        return None
    for entry in slug_entries:
        if entry.get("detail_endpoint") == api_name:
            list_endpoint = entry.get("list_endpoint")
            match_fields = entry.get("match_fields", ["name"])
            if list_endpoint:
                return (list_endpoint, match_fields)
    return None


def _get_param_resolution(executor, param_name: str) -> tuple[str, str, str] | None:
    """Read param auto-resolution config from the executor's instance config.

    Returns (list_api, id_field, display_field) or None if not configured.
    """
    if executor is None:
        return None
    cfg = getattr(executor, "instance_config", None) or {}
    param_res = cfg.get("tools", {}).get("param_resolution", {})
    if not isinstance(param_res, dict):
        return None
    entry = param_res.get(param_name)
    if not entry:
        return None
    return (
        entry.get("list_endpoint", ""),
        entry.get("id_field", "id"),
        entry.get("display_field", "name"),
    )
    """Extract a list of items from an API response.

    Handles the executor wrapper ({"status_code": ..., "data": ...}),
    DRF pagination ({"results": [...]}), and plain lists.
    """
    if isinstance(api_result, list):
        return api_result
    if not isinstance(api_result, dict):
        return []
    # Unwrap executor wrapper: {"status_code": ..., "data": <inner>}
    inner = api_result.get("data", api_result)
    if isinstance(inner, list):
        return inner
    if isinstance(inner, dict):
        # DRF pagination: {"results": [...], "count": N}
        results = inner.get("results", inner.get("data", []))
        if isinstance(results, list):
            return results
    return []


async def _resolve_slug_to_id(
    executor,
    api_name: str,
    path_params: dict,
) -> dict:
    """
    If any path param value is non-numeric (a slug or name), auto-resolve it to
    the real numeric PK by fetching the corresponding list endpoint first.
    Returns a (possibly updated) copy of path_params.
    """
    resolution = _get_slug_resolution(executor, api_name)
    if not resolution:
        return path_params

    _UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

    def _is_resolved(v: str) -> bool:
        """True if the value looks like a valid PK (numeric or UUID)."""
        s = str(v)
        return s.lstrip("-").isdigit() or bool(_UUID_RE.match(s))

    needs_resolution = any(not _is_resolved(v) for v in path_params.values())
    if not needs_resolution:
        return path_params

    list_api_name, match_fields = resolution
    list_entry = executor.get_catalog_entry(list_api_name)
    if not list_entry:
        return path_params

    try:
        list_result = await executor.call_api_direct("GET", list_entry["path"])
        items = _extract_items(list_result)
        if not isinstance(items, list):
            return path_params

        resolved = dict(path_params)
        for param_key, param_val in path_params.items():
            if _is_resolved(param_val):
                continue  # already numeric or UUID
            needle = str(param_val).lower()
            match = next(
                (
                    item for item in items
                    if any(
                        str(item.get(f, "")).lower() == needle
                        for f in match_fields
                    )
                ),
                None,
            )
            if match and "id" in match:
                logger.info(
                    f"Resolved slug '{param_val}' → id={match['id']} "
                    f"for {api_name} via {list_api_name}"
                )
                resolved[param_key] = match["id"]
            else:
                logger.warning(
                    f"Could not resolve '{param_val}' to a numeric id via {list_api_name}"
                )
        return resolved
    except Exception as e:
        logger.warning(f"Slug resolution failed for {api_name}: {e}")
        return path_params


async def _auto_resolve_missing_params(
    executor,
    api_name: str,
    missing_params: list[str],
) -> dict:
    """
    When the LLM omits path_params entirely, try to auto-resolve them.
    If exactly one option exists, use it. Otherwise return an error with
    available options so the LLM can call ask_clarification.
    """
    # Determine the right list endpoint based on the api_name's slug resolution config
    resolution = _get_slug_resolution(executor, api_name)

    resolved = {}
    for param in missing_params:
        auto = _get_param_resolution(executor, param)
        if not auto:
            # If we have a resolution map entry, derive the list endpoint from it
            if resolution:
                list_api_name = resolution[0]
            else:
                return {"error": f"Missing required path parameter '{param}'. Provide it in path_params."}
        else:
            list_api_name = auto[0]

        id_field = auto[1] if auto else "id"
        display_field = auto[2] if auto else "name"

        list_entry = executor.get_catalog_entry(list_api_name)
        if not list_entry:
            return {"error": f"Missing required path parameter '{param}' and cannot auto-resolve (no list endpoint)."}

        try:
            list_result = await executor.call_api_direct("GET", list_entry["path"])
            items = _extract_items(list_result)
            if not items:
                return {"error": f"Missing required path parameter '{param}'. No items found via {list_api_name}."}

            if len(items) == 1:
                item = items[0]
                resolved[param] = item[id_field]
                logger.info(
                    f"Auto-resolved missing '{param}' → {item[id_field]} "
                    f"({item.get(display_field, '?')}) for {api_name}"
                )
            else:
                names = [item.get(display_field) or item.get("name") or str(item.get(id_field)) for item in items]
                return {
                    "error": (
                        f"Missing required path parameter '{param}'. "
                        f"Multiple options available: {names}. "
                        f"Use ask_clarification to let the user choose, then retry with the correct {param}."
                    )
                }
        except Exception as e:
            logger.warning(f"Auto-resolve for '{param}' failed: {e}")
            return {"error": f"Missing required path parameter '{param}'. Could not auto-resolve: {e}"}

    return resolved


_REPAIR_PROMPT = """\
A read-only GET call to the host API endpoint '{api_name}' failed.

Endpoint method+path: {method} {path}
Query parameters sent: {query_params}
Error returned: {error}

The query parameters are likely malformed (e.g. wrong date format — dates must be
YYYY-MM-DD, an unsupported filter key, or an out-of-range value). Propose corrected
query parameters that keep the user's original intent.

Respond with ONLY a JSON object, no prose:
  {{"query_params": {{...}}}}   to retry with corrected parameters
  {{"give_up": true}}            if the parameters cannot be sensibly corrected
"""


def _first_json_object(text: str) -> str | None:
    """Extract the first complete, balanced top-level JSON object from ``text``.

    Robust to markdown code fences and trailing prose/extra objects that would
    otherwise make a greedy ``{.*}`` regex capture too much and fail to parse.
    Returns the substring of the first ``{...}`` object, or ``None`` if none.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


async def _llm_repair_query_params(
    instance_id: str,
    conversation_id: str,
    api_name: str,
    entry: dict,
    query_params: dict,
    last_error: str,
) -> dict | None:
    """Ask the LLM to repair malformed query parameters for a failed GET call.

    Returns a corrected ``query_params`` dict, or ``None`` if the model declines
    or the response can't be parsed. Best-effort: any failure yields ``None`` so
    the retry loop simply stops repairing.
    """
    if not instance_id:
        return None
    prompt = _REPAIR_PROMPT.format(
        api_name=api_name,
        method=entry.get("method", "GET"),
        path=entry.get("path", ""),
        query_params=json.dumps(query_params, default=str),
        error=last_error[:500],
    )
    try:
        router_result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=conversation_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        text = (router_result["content"] or "").strip()
        snippet = _first_json_object(text)
        if not snippet:
            return None
        parsed = json.loads(snippet)
    except Exception as e:
        logger.warning(f"LLM query-param repair failed for {api_name}: {e}")
        return None

    if parsed.get("give_up"):
        return None
    fixed = parsed.get("query_params")
    if isinstance(fixed, dict) and fixed and fixed != query_params:
        return fixed
    return None


async def execute_call_host_api(
    api_name: str,
    explanation: str = "",
    path_params: dict | None = None,
    query_params: dict | None = None,
    body: dict | None = None,
    executor=None,
    conversation_id: str = "",
    llm_client=None,
    model: str = "",
    **kwargs,
) -> dict:
    """
    Call a host system API endpoint.
    GET requests execute directly. Mutations require user confirmation.
    Non-numeric path IDs (slugs/names) are automatically resolved to numeric PKs.
    """
    instance_id: str = kwargs.get("instance_id", "")

    if executor is None:
        return {"error": "Host API executor not available"}

    # Refuse anonymous sessions before making any API attempt
    if not getattr(executor, "user_token", None):
        _host_name = executor.instance_config.get(
            "display_name", executor.instance_config.get("name", "the host system")
        )
        return {
            "error": (
                f"This action requires an authenticated session. "
                f"Please log in to {_host_name} and connect your account to Pulse first."
            )
        }

    entry = executor.get_catalog_entry(api_name)
    if not entry:
        return {"error": f"Unknown API endpoint: '{api_name}'. Check the api_catalog."}

    method = entry["method"]
    path_template = entry["path"]

    # Auto-resolve slugs/names to numeric IDs before substituting path params
    if path_params:
        path_params = await _resolve_slug_to_id(executor, api_name, path_params)

    # Substitute path parameters
    path = path_template
    if path_params:
        for key, value in path_params.items():
            path = path.replace(f"{{{key}}}", str(value))

    # Detect unsubstituted placeholders and try to auto-resolve them
    remaining = re.findall(r'\{(\w+)\}', path)
    if remaining:
        resolved = await _auto_resolve_missing_params(executor, api_name, remaining)
        if isinstance(resolved, dict) and "error" in resolved:
            return resolved
        for k, v in resolved.items():
            path = path.replace(f"{{{k}}}", str(v))

    logger.debug(f"call_host_api: {method} {path}  (api={api_name})")
    logger.debug(f"  reason: {explanation}")
    # Non-GET methods ALWAYS require confirmation regardless of catalog entry
    if method.upper() != "GET" or executor.requires_confirmation(api_name):
        confirmation_msg = entry.get(
            "confirmation_message",
            f"This will execute {method} {path}. Do you want to proceed?",
        )
        execution = await executor.create_pending_execution(
            conversation_id=conversation_id,
            tool_name=f"call_host_api:{api_name}",
            method=method,
            endpoint=path,
            params=query_params,
            body=body,
            confirmation_message=confirmation_msg,
        )
        return {
            "requires_confirmation": True,
            "execution_id": execution.id,
            "method": method,
            "endpoint": path,
            "confirmation_message": confirmation_msg,
        }

    # Direct execution for read-only endpoints
    settings = get_settings()

    async def _exec_direct() -> dict:
        try:
            return await executor.call_api_direct(method, path, query_params, body)
        except Exception as e:
            return {"error": str(e)}

    # N1: optional validate→execute→retry discipline (gated, default off).
    if settings.API_DISCIPLINE_ENABLED:
        from ai.engine.agent.api_discipline import APIErrorCategory, APIRetryLoop, validate_api_call

        invalid = validate_api_call(executor, api_name)
        if invalid is not None:
            return invalid

        # Build an LLM-backed repair function only when we have both an LLM
        # client and query params to correct. Repair is limited to query_params
        # (the common bad-date / wrong-filter case); path IDs are already handled
        # deterministically by the slug resolver above.
        _last_error = [""]
        repair_fn = None
        if instance_id and query_params:
            async def repair_fn(category: "APIErrorCategory") -> bool:
                nonlocal query_params
                fixed = await _llm_repair_query_params(
                    instance_id, conversation_id, api_name, entry, query_params,
                    last_error=_last_error[0],
                )
                if fixed is None:
                    return False
                logger.info(
                    "api_discipline: LLM repaired query_params for %s: %s → %s",
                    api_name, query_params, fixed,
                )
                query_params = fixed
                return True

        async def _exec_tracked() -> dict:
            result = await _exec_direct()
            if isinstance(result, dict) and "error" in result:
                _last_error[0] = str(result["error"])
            return result

        loop = APIRetryLoop(settings.API_MAX_RETRIES, settings.API_RETRY_BACKOFF_MS)
        outcome = await loop.run(_exec_tracked, repair_fn=repair_fn)
        if outcome.retry_count:
            logger.info(
                "api_discipline: %s succeeded=%s after %d retr%s",
                api_name, outcome.succeeded, outcome.retry_count,
                "y" if outcome.retry_count == 1 else "ies",
            )
        return outcome.final_result

    # Legacy single-shot path (flag off — unchanged behaviour).
    return await _exec_direct()


async def execute_navigate_to(
    route: str, explanation: str = "", **kwargs
) -> dict:
    """Return a navigation command for the widget to handle."""
    return {
        "action": "navigate",
        "route": route,
        "explanation": explanation,
    }


def _find_entity_config(instance_config: dict, entity_type: str) -> dict | None:
    """Find an entity config entry by type name from the instance config."""
    entities = instance_config.get("tools", {}).get("open_entity", {}).get("entities", [])
    if not isinstance(entities, list):
        return None
    for ent in entities:
        if ent.get("type") == entity_type:
            return ent
    return None


async def _resolve_entity_id_from_config(
    executor,
    entity_config: dict,
    entity_id: str,
) -> str:
    """If the entity config has a resolver, fetch the list and correct the entity_id.

    Uses the same fallback logic: if the given ID doesn't match any item, use the first.
    """
    resolver = entity_config.get("resolver")
    if not resolver:
        return entity_id

    list_api = resolver.get("api")
    id_field = resolver.get("id_field", "id")
    name_field = resolver.get("name_field", "name")
    date_field = resolver.get("date_field")  # optional: for subpage date resolution

    if not list_api:
        return entity_id

    list_entry = executor.get_catalog_entry(list_api)
    if not list_entry:
        return entity_id

    try:
        list_result = await executor.call_api_direct("GET", list_entry["path"])
        items = _extract_items(list_result)
        if not items:
            return entity_id

        # Find matching item by id_field
        match = next((e for e in items if e.get(id_field) == entity_id), None)
        if match:
            return str(match.get(id_field, entity_id))

        # Fallback: use the first item
        fallback = items[0]
        canonical_id = str(fallback.get(id_field, entity_id))
        if canonical_id != entity_id:
            logger.info(
                f"open_entity: corrected entity_id {entity_id!r} → {canonical_id!r}"
            )
        return canonical_id
    except Exception as e:
        logger.warning(f"open_entity: resolver failed: {e}")
        return entity_id


def _lookup_entity_config(
    entities: list[dict],
    entity_type: str,
    entity_id: str,
    subpage: str | None,
    date: str | None,
) -> tuple[dict | None, str, str | None, str | None]:
    """Find matching entity config and compute the route.

    Returns (entity_config, route, corrected_entity_id, corrected_date).
    entity_config is None if not found.
    """
    entity_config = None
    for ent in entities:
        if ent.get("type") == entity_type:
            entity_config = ent
            break
    return entity_config, None, entity_id, date  # route computed later since it needs async resolver


def _build_route_from_config(
    entity_config: dict,
    entity_id: str,
    subpage: str | None,
    date: str | None,
    *,
    resolver_date: str | None = None,
) -> str:
    """Build a navigation route from entity config and parameters."""
    route_template = entity_config.get("route_template", f"/{entity_config.get('type')}/{entity_id}")

    if subpage:
        subpages = entity_config.get("subpages", {})
        sub_cfg = subpages.get(subpage)
        if sub_cfg:
            route_suffix = sub_cfg.get("route_suffix", "")
            if "{date}" in route_suffix and not date:
                date = resolver_date
            # Build: base_template + route_suffix with {date} subst
            base = route_template.format(id=entity_id)
            suffix = route_suffix.replace("{date}", date or "")
            return base + suffix

    return route_template.format(id=entity_id)


async def execute_open_entity(
    entity_type: str,
    entity_id: str,
    explanation: str = "",
    subpage: str = "",
    date: str = "",
    executor=None,
    **kwargs,
) -> dict:
    """Build a navigation route for a specific entity detail page.

    Reads entity routing from the executor's instance config
    (tools.open_entity.entities[]). Resolves IDs via the entity's
    configured resolver API if present. No hardcoded paths.
    """
    cfg = getattr(executor, "instance_config", None) or {}
    entity_config = _find_entity_config(cfg, entity_type)

    if not entity_config:
        # Fallback: generic route
        route = "/" + entity_type.replace("_", "/") + "/" + entity_id
        return {
            "action": "navigate",
            "route": route,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "explanation": explanation,
        }

    # Resolve entity ID through the resolver if configured
    if executor:
        entity_id = await _resolve_entity_id_from_config(executor, entity_config, entity_id)

    # Resolve date from resolver result for date-driven subpages
    resolver_date: str | None = None
    if subpage:
        subpages = entity_config.get("subpages", {})
        sub_cfg = subpages.get(subpage)
        if sub_cfg:
            date_source = sub_cfg.get("date_source")
            if date_source and executor:
                resolver = entity_config.get("resolver")
                if resolver:
                    list_api = resolver.get("api")
                    if list_api:
                        list_entry = executor.get_catalog_entry(list_api)
                        if list_entry:
                            try:
                                list_result = await executor.call_api_direct("GET", list_entry["path"])
                                items = _extract_items(list_result)
                                if items:
                                    # Find matching item or use first
                                    id_field = resolver.get("id_field", "id")
                                    match = next((e for e in items if e.get(id_field) == entity_id), items[0])
                                    resolver_date = match.get(date_source, "")
                                    if resolver_date and not date:
                                        date = resolver_date
                                        logger.info(f"open_entity: auto-resolved date → {date!r}")
                            except Exception as e:
                                logger.warning(f"open_entity: date resolution failed: {e}")

    # Build route from template
    route = _build_route_from_config(
        entity_config, entity_id, subpage, date, resolver_date=resolver_date,
    )

    return {
        "action": "navigate",
        "route": route,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "explanation": explanation,
    }


async def execute_learn_fact(
    fact: str,
    category: str = "observation",
    reasoning: str = "",
    instance_id: str = "",
    executor=None,
    conversation_id: str = "",
    **kwargs,
) -> dict:
    """Propose storing a fact in long-term memory. Nothing is written until the
    user approves the proposal via the confirmation card."""
    if not fact or not fact.strip():
        return {"error": "No fact provided to remember"}
    if not instance_id:
        return {"error": "No instance context — cannot propose a fact"}
    if executor is None or not conversation_id:
        return {
            "error": "Cannot propose a memory without an active conversation context"
        }

    label = category.replace("_", " ")
    confirmation_message = f"Remember this {label}: {fact.strip()}"

    # Supersede any existing pending learn_fact for this conversation so the
    # user only ever sees one card — the latest, most refined proposal.
    await executor.cancel_pending_learn_facts(conversation_id)

    execution = await executor.create_pending_execution(
        conversation_id=conversation_id,
        tool_name="learn_fact",
        method="MEMORY",
        endpoint=f"long_term/{category}",
        body={
            "operation": "learn",
            "fact": fact.strip(),
            "category": category,
            "reasoning": reasoning,
            "instance_id": instance_id,
        },
        confirmation_message=confirmation_message,
    )

    logger.info(f"learn_fact: proposed [{category}] {fact[:80]} (exec={execution.id})")
    return {
        "requires_confirmation": True,
        "execution_id": execution.id,
        "operation": "learn",
        "method": "MEMORY",
        "endpoint": f"long_term/{category}",
        "fact": fact.strip(),
        "category": category,
        "reasoning": reasoning,
        "confirmation_message": confirmation_message,
        "message": "Proposed to the user — awaiting their approval before saving.",
    }


async def execute_forget_fact(
    memory_id: str = "",
    content: str = "",
    reason: str = "",
    instance_id: str = "",
    executor=None,
    conversation_id: str = "",
    **kwargs,
) -> dict:
    """Propose forgetting (archiving) a previously memorized fact. Nothing is
    archived until the user approves the proposal."""
    if not instance_id:
        return {"error": "No instance context — cannot propose forgetting a fact"}
    if executor is None or not conversation_id:
        return {
            "error": "Cannot propose forgetting a memory without an active conversation context"
        }
    if not (memory_id or "").strip() and not (content or "").strip():
        return {"error": "Specify a memory_id or a content description to forget"}

    from ai.engine.memory.long_term import LongTermMemory

    resolved_id = (memory_id or "").strip()
    preview = (content or "").strip()

    # If only a content description was given, resolve the best matching fact.
    if not resolved_id:
        db = getattr(executor, "db", None)
        if db is not None:
            ltm = LongTermMemory(db)
            candidates = await ltm.find_facts_by_content(
                instance_id=instance_id, query=preview, limit=5
            )
        else:
            from ai.engine.core.database import get_session_factory
            session_factory = get_session_factory()
            async with session_factory() as _db:
                ltm = LongTermMemory(_db)
                candidates = await ltm.find_facts_by_content(
                    instance_id=instance_id, query=preview, limit=5
                )
        if not candidates:
            return {
                "error": f"No remembered fact matches '{preview}'. Nothing to forget."
            }
        if len(candidates) > 1:
            return {
                "type": "clarification",
                "question": "Which remembered fact should I forget?",
                "choices": [c["content"][:120] for c in candidates],
            }
        resolved_id = candidates[0]["id"]
        preview = candidates[0]["content"]

    confirmation_message = f"Forget this remembered fact: {preview or resolved_id}"

    execution = await executor.create_pending_execution(
        conversation_id=conversation_id,
        tool_name="forget_fact",
        method="MEMORY",
        endpoint="long_term/forget",
        body={
            "operation": "forget",
            "memory_id": resolved_id,
            "content": preview,
            "reason": reason,
            "instance_id": instance_id,
        },
        confirmation_message=confirmation_message,
    )

    logger.info(f"forget_fact: proposed archive of {resolved_id} (exec={execution.id})")
    return {
        "requires_confirmation": True,
        "execution_id": execution.id,
        "operation": "forget",
        "method": "MEMORY",
        "endpoint": "long_term/forget",
        "memory_id": resolved_id,
        "content": preview,
        "reason": reason,
        "confirmation_message": confirmation_message,
        "message": "Proposed to the user — awaiting their approval before forgetting.",
    }


async def execute_ask_clarification(
    question: str,
    choices: list[str],
    **kwargs,
) -> dict:
    """Return a clarification request — signals the agent to stop and ask the user."""
    return {
        "type": "clarification",
        "question": question,
        "choices": choices,
    }


async def execute_run_ops_workflow(
    csv_content: str = "",
    explanation: str = "",
    upload_id: str | None = None,
    workflow: str | None = None,
    dry_run: bool = True,
    filename: str | None = None,
    executor=None,
    conversation_id: str = "",
    **kwargs,
) -> dict:
    """Run the declarative ops workflow for a CSV, acting as the authenticated user.

    Accepts either a staged ``upload_id`` (preferred — full file resolved from the
    csv_uploads table) or inline ``csv_content``. Defaults to a dry run (parse +
    validate + host-side dry-run, no writes). The workflow stops and asks if
    validation fails or a real mutation needs confirmation.
    """
    if executor is None:
        return {"error": "No host executor available — cannot run ops workflow."}
    if not getattr(executor, "user_token", None):
        return {"error": "You must be logged in to the host system to run an ops workflow."}

    source: str | None = None
    # Prefer the staged upload (lossless, untruncated).
    if upload_id:
        from sqlalchemy import select
        from ai.engine.core.models import CsvUpload

        row = (
            await executor.db.execute(select(CsvUpload).where(CsvUpload.id == upload_id))
        ).scalar_one_or_none()
        if row is None:
            return {"error": f"No staged upload found for upload_id={upload_id!r}."}
        source = row.content
        filename = filename or row.filename
    elif csv_content and csv_content.strip():
        source = csv_content

    if not source:
        return {"error": "No CSV provided — pass an upload_id or csv_content."}

    from ai.engine.ingestion.ops_workflow import OpsWorkflowError, OpsWorkflowRunner

    runner = OpsWorkflowRunner(
        db=executor.db,
        instance_id=kwargs.get("instance_id", ""),
        instance_config=executor.instance_config,
        executor=executor,
        host_user_id=None,
        conversation_id=conversation_id,
    )
    try:
        result = await runner.run(
            source,
            workflow_name=workflow,
            filename=filename,
            dry_run=dry_run,
        )
    except OpsWorkflowError as e:
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001 — surface a clean message to the agent
        logger.exception("run_ops_workflow failed")
        return {"error": f"Ops workflow failed: {e}"}
    return result


# ── PR-19: Skill tools (draft_skill / invoke_skill) ──────────────────────────

def _author_user_id_from_token(user_token: str | None) -> str:
    """Best-effort decode of the host JWT payload to extract a stable user id.

    Pulse cannot verify the host's signature (separate secret), so the payload
    is decoded unverified. Falls back to a deterministic token-derived id so
    skills stay attributable per user even if the payload is opaque.
    """
    if not user_token:
        return "anonymous"
    try:
        import jwt as _jwt

        payload = _jwt.decode(user_token, options={"verify_signature": False})
        for claim in ("username", "sub", "user_id", "preferred_username"):
            value = payload.get(claim)
            if value:
                return str(value)
    except Exception:  # noqa: BLE001 — unparseable/opaque token
        logger.debug("Could not decode host token payload; using token-derived author id")
    import hashlib

    return f"token-{hashlib.sha256(user_token.encode()).hexdigest()[:12]}"


async def execute_draft_skill(
    name: str = "",
    description: str = "",
    kind: str = "",
    signature: str = "{}",
    body: str = "{}",
    explanation: str = "",
    instance_id: str = "",
    executor=None,
    **kwargs,
) -> dict:
    """Draft a reusable skill for the current user. Safe — writes only to the
    skill table, no host mutations, no confirmation gate."""
    from ai.engine.skills.registry import SkillRegistry

    name = (name or "").strip()
    if not name:
        return {"error": "No skill name provided."}
    if not instance_id:
        return {"error": "No instance context — cannot draft a skill."}
    if executor is None:
        return {"error": "No host executor available — cannot draft a skill."}
    if not getattr(executor, "user_token", None):
        return {"error": "You must be logged in to the host system to draft a skill."}

    from ai.engine.core.models import SKILL_KINDS

    if kind not in SKILL_KINDS:
        return {
            "error": f"Invalid skill kind {kind!r} — must be one of: {', '.join(sorted(SKILL_KINDS))}."
        }

    # signature/body are JSON strings from the LLM; validate they parse.
    for field, value in (("signature", signature), ("body", body)):
        if isinstance(value, str) and value.strip():
            try:
                json.loads(value)
            except json.JSONDecodeError:
                return {"error": f"{field} must be valid JSON."}

    author_user_id = _author_user_id_from_token(executor.user_token)

    registry = SkillRegistry(executor.db)
    skill = await registry.add(
        {
            "instance_id": instance_id,
            "name": name,
            "description": (description or "").strip(),
            "signature": signature if isinstance(signature, str) else json.dumps(signature, default=str),
            "body": body if isinstance(body, str) else json.dumps(body, default=str),
            "kind": kind,
            "status": "draft",
            "author_user_id": author_user_id,
        }
    )
    logger.info(
        "draft_skill: created %s (%s, %s) for %s",
        skill.id, skill.name, skill.kind, author_user_id,
    )
    return {
        "skill_id": skill.id,
        "name": skill.name,
        "kind": skill.kind,
        "status": "draft",
        "message": "Skill drafted. Use invoke_skill to test it.",
    }


async def _invoke_code_snippet(code: str, args: dict) -> dict:
    """Execute a code_snippet in the RestrictedPython sandbox.

    Returns the sandbox execution result dict or an error dict on failure.
    """
    from ai.engine.skills.sandbox import SafeExecutor, SandboxError, SandboxTimeout

    sandbox = SafeExecutor()
    try:
        exec_result = await sandbox.execute(code, args, timeout_ms=5000)
        return exec_result
    except SandboxTimeout:
        return {"error": "Code execution timed out (5s limit)."}
    except SandboxError as exc:
        return {"error": str(exc)}


def _render_prompt_template(template: str, args: dict) -> str:
    """Render {placeholder}s in a prompt template from the passed args."""
    if not template:
        return ""
    rendered = template
    for key, value in (args or {}).items():
        rendered = rendered.replace("{" + str(key) + "}", str(value))
    return rendered


async def execute_invoke_skill(
    skill_name: str = "",
    args: dict | None = None,
    explanation: str = "",
    instance_id: str = "",
    executor=None,
    **kwargs,
) -> dict:
    """Invoke a skill by name — returns the skill body as DATA only.

    Does NOT execute SQL or host API calls; the agent decides what to do with
    the returned recipe. Increments usage_count on the skill row.
    """
    from ai.engine.skills.registry import SkillRegistry

    skill_name = (skill_name or "").strip()
    if not skill_name:
        return {"error": "No skill name provided."}
    if not instance_id:
        return {"error": "No instance context — cannot invoke a skill."}
    if executor is None:
        return {"error": "No host executor available — cannot invoke a skill."}
    if not getattr(executor, "user_token", None):
        return {"error": "You must be logged in to the host system to invoke a skill."}

    author_user_id = _author_user_id_from_token(executor.user_token)
    args = args or {}

    registry = SkillRegistry(executor.db)
    matches = await registry.search(instance_id, author_user_id, skill_name)
    skill = next((s for s in matches if s.name == skill_name), None)
    if skill is None:
        return {"error": f"No skill named '{skill_name}' found — try draft_skill first."}

    try:
        body = json.loads(skill.body) if skill.body else {}
    except json.JSONDecodeError:
        body = {}

    if skill.kind == "sql_macro":
        result = {"kind": skill.kind, "body": body, "args_passed": args}
    elif skill.kind == "api_call":
        result = {"kind": skill.kind, "body": body, "args_passed": args}
    elif skill.kind == "prompt_template":
        template = (body or {}).get("user_prompt_template", "")
        result = {
            "kind": skill.kind,
            "body": body,
            "args_passed": args,
            "rendered_prompt": _render_prompt_template(template, args),
        }
    elif skill.kind == "multi_step_plan":
        result = {"kind": skill.kind, "body": body, "args_passed": args}
    elif skill.kind == "code_snippet":
        code = (body or {}).get("code", "")
        if not code:
            return {"error": "code_snippet skill has no 'code' field in its body."}
        code_result = await _invoke_code_snippet(code, args)
        if "error" in code_result:
            return code_result
        result = {"kind": skill.kind, "body": body, "args_passed": args, "sandbox_result": code_result}
    else:
        result = {"kind": skill.kind, "body": body, "args_passed": args}

    # Usage tracking — increment on the persisted row after a successful invoke.
    skill.usage_count = (skill.usage_count or 0) + 1
    await executor.db.commit()

    logger.info("invoke_skill: %s (%s, %s) used by %s", skill.id, skill.name, skill.kind, author_user_id)
    return {
        "skill_id": skill.id,
        "skill_name": skill.name,
        "kind": skill.kind,
        "result": result,
        "message": f"Invoked skill '{skill.name}' — returned its recipe as data; nothing was executed.",
    }


# Map tool names to execution functions
STATIC_TOOL_EXECUTORS = {
    "search_knowledge": execute_search_knowledge,
    "get_entity_details": execute_get_entity_details,
    "call_host_api": execute_call_host_api,
    "navigate_to": execute_navigate_to,
    "open_entity": execute_open_entity,
    "learn_fact": execute_learn_fact,
    "forget_fact": execute_forget_fact,
    "ask_clarification": execute_ask_clarification,
    "run_ops_workflow": execute_run_ops_workflow,
    "draft_skill": execute_draft_skill,
    "invoke_skill": execute_invoke_skill,
}

# ── MCP (Model Context Protocol) dynamic tool injection ──────────────────
# Populated at startup by init_mcp_tools().  Empty by default — if no MCP
# servers are configured or all fail to connect, Pulse uses only its built-in
# tools and there is no runtime penalty.
MCP_TOOLS: list[dict] = []
MCP_EXECUTORS: dict[str, object] = {}


def get_tool_definitions() -> list[dict]:
    """Return all tool definitions: static built-in + MCP-injected."""
    return STATIC_TOOL_DEFINITIONS + MCP_TOOLS


async def get_tool_executors() -> dict:
    """Return all tool executors: static built-in + MCP-injected."""
    return {**STATIC_TOOL_EXECUTORS, **MCP_EXECUTORS}


async def init_mcp_tools(registry) -> int:
    """Connect to MCP servers and register their tools.

    Args:
        registry: An MCPToolRegistry instance from agent.mcp_client.

    Returns:
        Number of MCP tools registered (0 if no servers or all failed).
    """
    servers = await registry.connect_all()
    tools = await registry.get_tool_definitions()

    # Populate module-level collections
    MCP_TOOLS[:] = tools
    MCP_EXECUTORS.clear()

    for server in servers:
        for tool in server.tools:
            # Capture tool_name in closure so each executor calls the right tool
            async def _exec(args, _tn=tool.name):
                return await registry.execute_tool(_tn, args)

            MCP_EXECUTORS[tool.name] = _exec

    count = len(tools)
    logger.info(
        "MCP tools loaded: %d tools from %d servers",
        count, len(servers),
    )
    return count
