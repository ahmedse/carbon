"""
System prompts and templates for Pulse LLM interactions.
All prompts use placeholder injection — never hardcode instance-specific content.

Prompts are now synthesized at runtime by llm.prompt_synthesizer — no
hardcoded per-instance template. The SYSTEM_PROMPT_INTROSPECT templates
below are the only remaining static prompts (schema analysis, not chat).
"""

# ── Note: SYSTEM_PROMPT_CHAT removed 2026-08-09 ──
# build_chat_prompt() now calls llm.prompt_synthesizer.synthesize_system_prompt()
# which uses LLM-powered prompt generation tailored to each instance.

SYSTEM_PROMPT_INTROSPECT_SYSTEM = """You are a database schema analyst for a {domain} platform called {instance_name}.
{instance_description}
You respond ONLY with valid JSON — no markdown, no explanation, no code fences.
Output format: {{"table_name": "2-3 sentence business description", ...}}
For each description explain: (1) what the entity represents in the business domain, (2) what data it holds, (3) how it connects to the system's purpose."""

SYSTEM_PROMPT_INTROSPECT_USER = """Describe each of the following database tables as a business analyst would.

{tables_block}

Return a JSON object mapping each table name to its description."""


async def build_chat_prompt(
    instance_name: str,
    system_description: str,
    relevant_knowledge: str = "No knowledge loaded yet.",
    relevant_memories: str = "No memories available.",
    page_context: str = "unknown",
    current_datetime: str = "",
    user_info: dict | None = None,
    persona: dict | None = None,
    api_catalog: list[dict] | None = None,
    navigation_routes: list[dict] | None = None,
    domain_topics: list[str] | None = None,
    instance_config: dict | None = None,
    conversation_id: str = "",
    instance_id: str = "",
) -> str:
    """Build the system prompt for chat interactions.

    Prompt-config mechanism (PULSE-CANONICAL §12): ``instance.yaml`` persona /
    domain_facts via ``_fallback_prompt``. PlaybookBlock assembly and PromptVersion
    A/B routing are DEFERRED(F3) — not invoked on the hot path. Filesystem
    ``domain_packs/*/skills`` guidance injection is REMOVED(F1a).

    Prepends a runtime header with per-conversation context (datetime, user,
    page, knowledge, memories) so that every request carries current state.

    ``conversation_id`` / ``instance_id`` are retained for call-site compatibility;
    they no longer drive A/B or PlaybookBlock selection.
    """
    from datetime import datetime, timezone
    from ai.engine.llm.playbook import _fallback_prompt

    # Retained for API compatibility; unused after F1a/F3 convergence.
    _ = (conversation_id, instance_id, system_description, persona, navigation_routes, domain_topics)

    config = instance_config or {}

    # ── Runtime header (per-conversation context) ──────────────────────────
    if not current_datetime:
        now_utc = datetime.now(timezone.utc)
        current_datetime = now_utc.strftime('%A, %B %d, %Y %H:%M UTC')

    identity_directive = ""
    if user_info:
        username = user_info.get("username", "Unknown")
        display_name = user_info.get("display_name") or username
        email = user_info.get("email") or ""
        roles = user_info.get("roles") or []
        email_part = f" <{email}>" if email else ""
        roles_part = f" — Roles: {', '.join(roles)}" if roles else ""
        user_context = f"**{display_name}**{email_part}{roles_part}"
        # Domain subject binding: lets the model resolve first-person requests
        # ("my leave", "اجازاتي") to THIS person and steers it to self-scoped
        # endpoints instead of the org-wide lists (which would leak others' data).
        employee = user_info.get("employee") or None
        if employee:
            emp_bits = [
                str(employee[k]) for k in ("full_name", "job_title", "org_unit")
                if employee.get(k)
            ]
            if employee.get("employee_no"):
                emp_bits.insert(1, f"employee #{employee['employee_no']}")
            emp_line = ", ".join(emp_bits)
            user_context = f"{user_context}\n**Employee identity**: {emp_line}"
            identity_directive = (
                f"**Identity**: You are assisting {emp_line}. When they say "
                "\"my\", \"me\", \"mine\", or \"I\" — or the Arabic اجازاتي / "
                "راتبي / بياناتي / قروضي — it refers to THIS person; never ask "
                "who they are. For first-person questions about their own leave, "
                "leave balance, loans, or profile, call the "
                "self-service endpoints (get_my_profile, list_my_leave, "
                "get_my_leave_balance, list_my_loans). "
                "CRITICAL — Chat mode never submits or stages host writes "
                "(leave/loan/attendance/payroll). If they ask to REQUEST / "
                "SUBMIT leave (\"I want leave\", \"أريد إجازة\", عارضة / "
                "emergency) do NOT call submit_my_leave or any call_host_api "
                "mutation — explain that Chat is advisory and direct them to "
                "Agent (leave.request.lifecycle) or My Leave (/my/leave). "
                "Never create_leave_record (that needs an employee id and is "
                "HR-admin only). For salary / compensation "
                "/ basic pay / راتبي call get_my_profile (or resolve_entity / "
                "get_employee for a named coworker) — NEVER list_my_payslips for "
                "a contractual salary figure; empty payslips are not \"no salary "
                "data\", and a CBAC deny (people:view_compensation) must be "
                "stated plainly. Use list_my_payslips for net pay, take-home, "
                "last month's pay, deductions, GOSI, payslip lines, or قسيمة. "
                "Do NOT use the organisation-wide list endpoints "
                "(list_employees, list_leave_records, …) for a first-person "
                "request — they return the whole population and would expose "
                "other employees' data.\n"
            )
    else:
        user_context = (
            "Anonymous (no Pulse API key configured — user identity unknown; "
            "answers must not expose data beyond what a public user could see)"
        )

    # ── instance.yaml-backed prompt (canonical; PlaybookBlock path DEFERRED F3)
    _cfg = instance_config or {}
    runtime_ctx = {
        "instance_name": instance_name,
        "current_datetime": current_datetime,
        "user_context": user_context,
        "page_context": page_context,
        "relevant_knowledge": relevant_knowledge,
        "relevant_memories": relevant_memories,
        "instance_persona": (_cfg.get("persona") or "").strip(),
        "domain_facts": (_cfg.get("domain_facts") or "").strip(),
    }
    result = _fallback_prompt(runtime_ctx)

    # ── Host API endpoint catalog (appended to every path) — the model can
    # only discover ``call_host_api`` endpoint names here; search_knowledge
    # searches the knowledge graph, not the catalog.
    api_catalog_section = _build_api_catalog_section(api_catalog)
    if api_catalog_section:
        result = f"{result}\n\n{api_catalog_section}" if result else api_catalog_section

    # ── Caller identity directive (per-user) — appended so it is always
    # present regardless of the assembler/fallback path. Lets the model
    # resolve first-person requests to the logged-in employee and steer to
    # self-scoped endpoints instead of org-wide lists.
    if identity_directive:
        result = f"{result}\n\n{identity_directive}" if result else identity_directive

    # ── Tenant organisation grounding — names the whole institution so Chat
    # never treats "GOFSCO" / "AASTMT" / "the company" as an ambiguous person
    # or a missing filter (clarification-loop bug).
    tenant_section = _build_tenant_org_directive(config)
    if tenant_section:
        result = f"{result}\n\n{tenant_section}" if result else tenant_section

    # ── Live-data grounding directive (derived from the catalog) — bridges the
    # semantic gap between "tell me about the live data here" and the
    # matching endpoint, so the S3 planner queries live data
    # instead of lecturing from parametric knowledge.
    grounding_section = _build_grounding_directive(api_catalog)
    if grounding_section:
        result = f"{result}\n\n{grounding_section}" if result else grounding_section

    # ── Capability-scoped access inventory (per-user, appended to every path) ──
    # The assistant may only ever mention items from this inventory — apps,
    # work areas, modules or capabilities the user cannot reach must not leak,
    # not even their existence.  Rendered last so no path can bypass it.
    access_section = _build_access_section(config)
    if access_section:
        result = f"{result}\n\n{access_section}" if result else access_section

    # Compact rendering summary when fallback did not already include it.
    # Filesystem domain-pack skill injection REMOVED(F1a) — do not re-wire.
    if RENDERING_CAPABILITIES_SUMMARY not in (result or ""):
        result = (
            f"{result}\n\n{RENDERING_CAPABILITIES_SUMMARY}"
            if result
            else RENDERING_CAPABILITIES_SUMMARY
        )

    return result


def _build_api_catalog_section(api_catalog: list | None) -> str:
    """Render the host API endpoints into the system prompt.

    ``call_host_api`` resolves an endpoint by its catalog ``name``, but
    ``search_knowledge`` only searches the knowledge graph — so this section is
    the model's only reliable source of the available endpoint names.  Kept
    terse (name + method + one-line description) for prefix-cache stability
    (RULE_25/26).
    """
    if not api_catalog:
        return ""
    any_get_needs_confirm = any(
        (ep.get("method", "GET") or "GET").upper() == "GET" and ep.get("requires_confirmation")
        for ep in api_catalog
    )
    confirm_note = (
        "Confirmation requirements are marked per endpoint below."
        if any_get_needs_confirm
        else "Read-only (GET) endpoints need no confirmation."
    )
    lines = [
        "## Available Host API Endpoints",
        "",
        "Call these live endpoints via `call_host_api(api_name, ...)` — use the "
        f"exact names below. {confirm_note}",
    ]
    for ep in api_catalog:
        name = ep.get("name", "unknown")
        method = (ep.get("method", "GET") or "GET").upper()
        desc = (ep.get("description", "") or "").replace("\n", " ").strip()
        confirm = " [requires user confirmation]" if ep.get("requires_confirmation") else ""
        lines.append(f"- `{name}` ({method}): {desc}{confirm}")
    return "\n".join(lines)


def _endpoint_to_domain_phrase(name: str) -> str:
    """`list_<domain>` → `<domain>` (human-readable domain phrase)."""
    for prefix in ("list_", "get_", "search_", "query_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.replace("_", " ").strip()


def _build_tenant_org_directive(instance_config: dict | None) -> str:
    """Render whole-organisation identity so Chat does not clarify-loop on it.

    Declared in ``instance.yaml`` as ``tenant_org:`` (name + aliases). When the
    user names the tenant / "the company" / asks for "data in the system" about
    it, the model must answer from live tools — never treat the org name as an
    ambiguous identity that needs "what specifically…?".
    """
    tenant = (instance_config or {}).get("tenant_org") if instance_config else None
    if not isinstance(tenant, dict):
        return ""
    name = (tenant.get("name") or "").strip()
    if not name:
        return ""
    short = (tenant.get("short_name") or "").strip()
    aliases = [
        str(a).strip() for a in (tenant.get("aliases") or []) if str(a).strip()
    ]
    # Ensure short_name and primary name are always listed as aliases.
    for extra in (short, name.split("—")[0].strip(), name.split("-")[0].strip()):
        if extra and extra not in aliases:
            aliases.append(extra)
    alias_line = ", ".join(f'"{a}"' for a in aliases) if aliases else f'"{name}"'
    summary = (tenant.get("summary") or "").strip()
    summary_line = f"\n{summary}\n" if summary else "\n"

    return (
        "## Tenant organisation (non-negotiable)\n\n"
        f"You serve **{name}**"
        + (f" (short name: **{short}**)" if short else "")
        + f". Aliases: {alias_line}. "
        "This is the WHOLE organisation / company / institution — NOT a "
        "filterable sub-entity, NOT an employee, NOT a missing record.\n"
        f"{summary_line}"
        "When the user asks about this organisation, \"the company\", \"our "
        "company\", \"the organisation\", or \"data in the system\" / \"what "
        "data do we have\" about it:\n"
        "1. Answer immediately — do NOT ask clarifying questions in a loop "
        "(\"What specifically would you like to know…?\").\n"
        "2. For identity (\"what is the company\"): use the summary above plus "
        "persona/domain facts — never invent external corporate trivia.\n"
        "3. For data-in-system: call live tools right away "
        "(`aggregate_entity` metric=headcount, and when useful "
        "`analyze_employees` or list endpoints) and answer from the results.\n"
        "4. Only ask a clarifying question when they name a specific person, "
        "payroll run, leave record, or other sub-item that is still ambiguous."
    )


def _build_grounding_directive(api_catalog: list | None) -> str:
    """Render a live-data grounding rule derived from the endpoint catalog.

    The model's parametric knowledge is generic textbook reference data; the
    platform's actual records (reference data, calculation summaries, data-quality
    rules, …) live behind ``call_host_api``. This directive names each read
    domain so the model maps a natural-language question ("tell me about
    the live data here") to the matching endpoint instead of lecturing from
    memory. Derived entirely from ``instance.yaml`` (ADR-0017), so it
    generalises to any instance with zero code changes.
    """
    if not api_catalog:
        return ""

    read_domains: list[str] = []
    for ep in api_catalog:
        if (ep.get("method", "GET") or "GET").upper() != "GET":
            continue
        name = ep.get("name", "")
        if not name:
            continue
        read_domains.append(f"- {_endpoint_to_domain_phrase(name)} → `{name}`")

    if not read_domains:
        return ""

    lines = [
        "## Live data grounding (non-negotiable)",
        "",
        "This platform holds LIVE operational data that is NOT part of your "
        "training knowledge — do not answer about it from general knowledge or "
        "textbook reference values. When the user asks about any domain below "
        "(especially with words like \"here\", \"in the system\", \"our\", "
        "\"my\", \"on the platform\", \"what we have\", \"show me\", \"list\"), "
        "call the matching endpoint via `call_host_api` and answer from the "
        "returned data only:",
        "",
    ] + read_domains + [
        "",
        "If a domain maps to more than one endpoint, call the one that answers "
        "the user's specific question. Never invent values; if the data has no "
        "matching rows, say so plainly.",
        "",
        "AGGREGATION RULES (non-negotiable):",
    ]

    # Only instruct the model to use analyze_* endpoints when at least one exists
    # in the catalog — otherwise the instruction references a non-existent tool.
    has_analyze = any(
        ep.get("name", "").startswith("analyze_") for ep in (api_catalog or [])
    )
    if has_analyze:
        lines += [
            "1. For ANY distribution, breakdown, or 'how many X are Y' question, "
            "   use an `analyze_*` endpoint (e.g. `analyze_employees`) — NEVER count "
            "   rows from a `list_*` result. List endpoints are paginated and return "
            "   at most 100 rows; counting them gives WRONG totals. "
            "   NEVER paste raw employee salary rows into the chat — aggregates, "
            "   buckets, and charts only.",
        ]
    lines += [
        "2. When a list endpoint returns `truncated: true`, you MUST say explicitly "
        "   \"Showing first N of TOTAL\" — never present a partial page as the full set.",
    ]
    if has_analyze:
        lines += [
            "3. When `analyze_*` returns `caveats`, you MUST quote them verbatim in your "
            "   answer before presenting any chart or table. Missing data is not an error "
            "   to hide — it is a finding to surface.",
            "4. Use FK-resolved `label` fields from `analyze_*` results for chart axes, "
            "   not `raw_value` IDs. A chart labelled 'Supervisor' is correct; "
            "   a chart labelled '182' is not.",
            "5. CHART TYPE — use the `suggested_chart_type` field from `analyze_*` results "
            "   to choose between pie and bar. NEVER default to pie — pie is only correct "
            "   when the server returns `suggested_chart_type: 'pie'`. "
            "   A 99% / 1% distribution MUST use a bar chart (the server will say 'bar').",
            "6. NORMALIZATION — when `was_normalized: true`, you MUST explain what was merged "
            "   in plain language (e.g. 'Note: \"M\" was merged into \"male\" — this appears "
            "   to be a data-entry variant. Recommend standardising the source data.'). "
            "   Quote each entry in `normalization_notes` verbatim. "
            "   Never silently list merged values as if they were separate categories.",
        ]
    lines += [
        "",
        "ANSWER WITH DEPTH, NOT A DUMP. After calling the endpoint, synthesise "
        "the result into a direct, insightful answer: name the material facts "
        "(the count, the highest/lowest, the specific item they asked about), "
        "cite real values inline, and present the data richly — a clean table "
        "of the meaningful columns plus a chart (see the rich-rendering rules). "
        "Keep it to the relevant rows and columns — never every field of every "
        "record. Never invent values; if the data has no matching rows, say so "
        "plainly.",
    ]
    return "\n".join(lines)


def _build_access_section(instance_config: dict | None) -> str:
    """Render the per-user access inventory into the system prompt.

    Strict no-leak section: the assistant is told it may reference ONLY the
    items listed here and must never describe platform internals (components,
    databases, technologies, or how the assistant itself works) — RULE_23.
    """
    access = (instance_config or {}).get("user_access") if instance_config else None
    if not access:
        return ""

    platform_name = access.get("platform_name") or "the platform"
    apps = access.get("apps") or []
    work_areas = access.get("capabilities") or []
    modules = access.get("modules") or []
    access_level = access.get("access_level") or "unknown"

    parts = [
        f"## Your Access (strict inventory)",
        f"You are the assistant for {platform_name}. The current user's access level: "
        f"{access_level}.",
    ]

    if work_areas:
        lines = [f"- {wa['label']} — {wa['description']}" for wa in work_areas]
        parts.append("Work areas this user can use:\n" + "\n".join(lines))
    if apps:
        lines = [f"- {app['name']} — {app['description']}" for app in apps]
        parts.append("Apps this user can open:\n" + "\n".join(lines))
    if modules:
        lines = [f"- {m['name']}" for m in modules]
        parts.append("Data areas (modules) this user can work with:\n" + "\n".join(lines))

    parts.append(
        "HARD RULES (non-negotiable):\n"
        "- When you list what you can do, mention ONLY items from the inventory "
        "above. Never imply, hint at, or describe anything not listed — not even "
        "its existence.\n"
        "- Never reveal the existence of any app, data area, page, or feature the "
        "user cannot access.\n"
        "- Never mention platform internals: no component names, no database or "
        "technology or stack details, no tool or system names, and no details of "
        "how the assistant itself works.\n"
        "- Describe outcomes in plain user language — never internals.\n"
        "- When asked what you can do, use the capability-list tool so the app "
        "can attach the matching page links as small buttons under your reply."
    )

    return "\n\n".join(parts)


#: Capability instruction block appended to EVERY chat system prompt.  The
#: frontend renders assistant markdown richly (tables, syntax-highlighted
#: code, live mermaid diagrams, KaTeX math, figure captions) — the model must
#: know it can DRAW diagrams and format content instead of saying it cannot.
RENDERING_CAPABILITIES = """## Rich content rendering

Your replies are rendered as rich Markdown documents in the platform UI. Use the
right construct instead of describing things in prose:

- **Tables** — GFM Markdown tables render as styled, striped tables. **Table
  line rules (critical):** leave a blank line before the table, put the header
  row, the `|---|---|` delimiter row, and EVERY data row each on its OWN line.
  NEVER glue a table onto a prose line (e.g. after a colon) and NEVER collapse
  the rows onto one line — a single-line table renders as raw `|` text, not a
  table. Correct form:

  | Position | Employees |
  |----------|-----------|
  | Driver   | 52        |
  | Floorman | 22        |
- **Code** — fenced blocks (```python, ```sql, ```json, ...) render with syntax
  highlighting, a language badge, and a copy button. **Always format JSON with
  proper indentation** (2 spaces per level) and line breaks — never as a single
  line. Example:
  ```json
  {
    "name": "Example Rule",
    "type": "threshold",
    "params": {
      "operator": "gt",
      "value": 0
    }
  }
  ```
- **Diagrams** — a ```mermaid fenced block renders as a live diagram
  (flowchart, sequenceDiagram, stateDiagram-v2, classDiagram, pie, gantt, ...).
  When a workflow, flow, process, relationship or structure is clearer as a
  picture, ALWAYS emit a mermaid diagram instead of prose. You CAN draw
  diagrams — never say you cannot.
- **Mermaid line rules (critical)** — the opening ```mermaid fence MUST start
  on its OWN line, preceded by a blank line; the closing ``` MUST be on its own
  line too. Put EVERY mermaid directive on its OWN line. NEVER place the fence
  inline after prose, and NEVER collapse a diagram to a single line — a
  single-line or inline fence will NOT render as a diagram in the UI.
- **Data charts** — when your answer holds 3+ comparable numeric records, emit a
  Mermaid chart IN ADDITION to a table. Choose the type intelligently:
  - Use ```mermaid pie``` when the values are **parts of a whole** (scope %, category
    shares, breakdowns that add up to 100%). Pie slices must sum to a meaningful total.
  - Use ```mermaid xychart-beta``` with `bar` when comparing **magnitudes across
    independent categories** (module CO₂e, top emitters, year-over-year absolute).
  - Use ```mermaid xychart-beta``` with `line` for **trends over time**.
  - Keep x-axis labels ≤ 14 chars — abbreviate or shorten longer names (the renderer
    truncates them anyway). NEVER include em-dashes (—), angle brackets, or braces in
    axis labels; use a hyphen (-) instead. One `bar` line holds ALL values
    comma-separated. Every directive (`title`, `x-axis`, `y-axis`, `bar`, `line`,
    each `pie` slice) goes on its own line. Example:
  ```mermaid
  pie title Scope breakdown
      "Scope 1" : 2258
      "Scope 2" : 8032
      "Scope 3" : 6
  ```
  ```mermaid
  xychart-beta
      title "CO2e by Module (tonnes)"
      x-axis ["Module A", "Module B", "Module C"]
      y-axis "CO2e tonnes" 0 --> 6000
      bar [5566, 4023, 707]
  ```
  NEVER write `axis x`, `axis y`, or per-point `bar x: 1 y: 2.51` lines —
  those are invalid Mermaid and the chart will NOT render. Use exactly the
  `x-axis [...]` / `y-axis "..." 0 --> N` / `bar [...]` form above.
- **Tables** — every row on its OWN line. NEVER put two data rows on the same line.
  A correctly formed module-breakdown table looks like:

  | Module | Calculations | CO₂e (kg) | CO₂e (t) |
  |--------|-------------|-----------|---------|
  | Module A | 47 | 5,586,304 | 5,566 |
  | Module B | 84 | 4,023,122 | 4,023 |

  One data row per line — NEVER collapse rows.
- **Math** — $inline$ and $$block$$ render with KaTeX.
- **Figures** — images with a title render with a caption below them.
- **Links** — internal platform routes (starting with /) render as in-app links.

Prefer rich constructs over prose lists whenever they make the answer clearer
and easier to scan. Example diagram:

```mermaid
flowchart LR
    A[Start] --> B{Valid?}
    B -- Yes --> C[Activate]
    B -- No --> D[Investigate]
```
"""


#: Compact always-on rendering directive (P4-03 progressive disclosure).
#: The full worked examples in ``RENDERING_CAPABILITIES`` now live in the
#: ``rich-content-rendering`` skill folder's ``references/formatting-examples.md``
#: and are loaded on demand.  This summary stays in the always-on prompt so the
#: model still knows it can draw diagrams and format rich content.
RENDERING_CAPABILITIES_SUMMARY = """## Rich content rendering

Your replies render as rich Markdown. Use the right construct instead of prose:

- **Tables** — GFM tables render as styled tables. Leave a blank line before the table; put the header, the `|---|---|` delimiter, and every data row each on its OWN line.
- **Code** — fenced blocks (```python, ```sql, ```json) render with syntax highlighting and a copy button; indent JSON with 2 spaces per level.
- **Diagrams** — a ```mermaid fenced block renders as a live diagram (flowchart, sequenceDiagram, stateDiagram-v2, classDiagram, pie, gantt). You CAN draw diagrams; when a process or structure is clearer as a picture, emit one.
- **Mermaid line rules** — the opening ```mermaid fence starts on its OWN line preceded by a blank line; the closing fence is on its own line; each directive on its own line.
- **Data charts** — for 3+ comparable numeric records, emit a Mermaid chart IN ADDITION to a table: ```mermaid pie for parts-of-a-whole; ```mermaid xychart-beta with `bar` for magnitudes or `line` for trends.
- **Math** — $inline$ and $$block$$ render with KaTeX.
- **Figures** — images with a title render with a caption below.
- **Links** — internal platform routes (starting with /) render as in-app links.
"""


def build_introspect_messages(
    domain: str,
    instance_name: str,
    instance_description: str,
    tables_block: str,
) -> list[dict]:
    """Build system+user messages for schema introspection."""
    system = SYSTEM_PROMPT_INTROSPECT_SYSTEM.format(
        domain=domain,
        instance_name=instance_name,
        instance_description=instance_description.strip() or f"A {domain} platform.",
    )
    user = SYSTEM_PROMPT_INTROSPECT_USER.format(tables_block=tables_block)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Prompt builder functions (formerly knowledge_graph/prompt_builder.py)
# ══════════════════════════════════════════════════════════════════════════════

import json as _json_import
from typing import TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:
    from ai.engine.knowledge_graph.synthesis import QueryPlan, ResolvedColumn, SuggestedFilter

_PLAN_PREAMBLE = (
    "A query plan has been pre-computed from the database schema graph. "
    "Use it as your primary guide for table selection, joins, and aggregations. "
    "You may adjust column selections or add WHERE clauses based on the user's specific "
    "phrasing, but do not deviate from the join paths unless you have strong reason to. "
    "For inferred (LEFT JOIN) relationships, validate the join makes sense in context."
)


def build_sql_prompt(
    plan,
    question: str,
    dialect: str = "sqlite",
    entity_importances: dict[str, float] | None = None,
    entity_profiles: dict[str, dict] | None = None,
    golden_pairs: list[dict] | None = None,
) -> str:
    """Convert a QueryPlan into a structured prompt block for the LLM."""
    lines: list[str] = []
    lines.append(_PLAN_PREAMBLE)
    lines.append("")
    lines.append("=== QUERY PLAN ===")
    lines.append("")
    lines.append(f'Intent: {plan.intent}')
    lines.append(f'Question: "{question}"')
    lines.append("")

    # ── Target tables ─────────────────────────────────────────────────────────
    if plan.target_entities:
        lines.append("TARGET TABLES:")
        for entity in plan.target_entities:
            imp = (entity_importances or {}).get(entity)
            imp_str = f" (importance: {imp:.2f})" if imp is not None else ""
            lines.append(f"- {entity}{imp_str}")
        lines.append("")
    else:
        lines.append("TARGET TABLES: (none resolved)")
        lines.append("")

    if entity_profiles:
        count_lines = [
            f"- {entity}: {prof.get('row_count_actual', '?'):,} rows"
            for entity, prof in entity_profiles.items()
            if entity in plan.target_entities and prof
        ]
        if count_lines:
            lines.append("ROW COUNTS:")
            lines.extend(count_lines)
            lines.append("")

    if plan.join_paths:
        lines.append("JOIN PATH:")
        for path in plan.join_paths:
            for step in path.steps:
                conf_str = f"confidence: {step.confidence:.1f}"
                rel_str = "FK" if step.join_type == "fk" else "inferred"
                lines.append(
                    f"  {step.from_entity}.{step.from_column} → "
                    f"{step.to_entity}.{step.to_column} "
                    f"({rel_str}, {conf_str})"
                )
        lines.append("")

    if plan.select_columns:
        lines.append("TARGET COLUMNS:")
        for col in plan.select_columns:
            role_str = f" ({col.role})" if col.role else ""
            lines.append(f"- {col.entity}.{col.column} ({col.data_type}){role_str}")
        lines.append("")

    if plan.group_by_columns:
        lines.append("GROUP BY:")
        for col in plan.group_by_columns:
            lines.append(f"- {col.entity}.{col.column}")
        lines.append("")

    if plan.suggested_filters:
        lines.append("SUGGESTED FILTERS:")
        for f in plan.suggested_filters:
            hint = f" (hint: {f.value_hint})" if f.value_hint else ""
            lines.append(f"- {f.entity}.{f.column} {f.operator} ?{hint}")
        lines.append("")

    if plan.order_by_hint:
        lines.append(f"ORDER BY: {plan.order_by_hint}")
        lines.append("")

    lines.append(f"SQL DIALECT: {dialect}")
    lines.append("")

    if golden_pairs:
        lines.append("FEW-SHOT EXAMPLES (verified correct):")
        for gp in golden_pairs[:5]:
            lines.append(f"  Q: {gp.get('natural_language', '')}")
            lines.append(f"  SQL: {gp.get('corrected_sql', '')}")
            lines.append("")

    lines.append("=== END QUERY PLAN ===")
    return "\n".join(lines)


def build_retry_prompt(
    sql: str,
    error_message: str,
    error_hint: str,
    attempt: int = 0,
) -> str:
    """Build the repair request sent to the LLM when SQL execution fails."""
    header = f"SQL correction needed (attempt {attempt + 1}):\n" if attempt > 0 else "SQL correction needed:\n"
    return (
        f"{header}"
        f"The following SQL query failed with a database error:\n"
        f"\n```sql\n{sql}\n```\n\n"
        f"Error: {error_message}\n\n"
        f"Hint: {error_hint}\n\n"
        "Please rewrite the SQL to fix this error. "
        "Keep the original query intent unchanged — only fix what is broken. "
        "Return ONLY the corrected SQL inside a ```sql ... ``` block, nothing else."
    )


def build_fallback_prompt(context_prose: str, question: str) -> str:
    """Fallback prompt when the planner cannot produce a confident plan."""
    return (
        "The following is the relevant schema context for the database. "
        "Use it to identify the correct tables, columns, and relationships "
        "needed to answer the user's question. Infer join conditions from "
        "the relationships described.\n\n"
        f"{context_prose}"
    )
