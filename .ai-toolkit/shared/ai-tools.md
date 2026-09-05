# AI Tools — Design Contract & Common Tool Library

**How every AI assistant in every project defines, names, and wires its tools.**
Applies to any agentic surface: chat assistants, "Pulse"-style brains, MCP servers,
function calling, tool plugins.

## The One Law

> **One tool per *capability*, never one tool per *question* or per *intent*.**

Variations are **parameters** (arguments), not tools. Backend dispatch is
**deterministic code**, not tool selection.

| Granularity | What | Example |
|---|---|---|
| Intent zone | kind of answer (routing) | `platform` / `concept` / `real_time` / `general` |
| Tool | one capability / permission / system boundary | `web_research`, `search_knowledge`, `code_exec` |
| Dispatch | deterministic code inside a tool | weather→Open-Meteo, facts→Wikipedia, math→eval |

`web_research` already covers weather — `get_weather` is **not** a new tool; it is a
query-type *inside* `web_research` that routes to a weather API.

## Why (cost is real)

- Every tool schema is billed as **input tokens** on every turn (OpenAI and Anthropic both confirm this).
- Each redundant tool is an extra **classification decision** the model can get wrong.
- OpenAI: *"Keep the number of initially available functions small for higher accuracy …
  aim for fewer than 20."*
- Anthropic + OpenAI both ship `tool_search` to **defer** rarely-used tools instead of
  exposing them all up front.
- LangChain: *"Too many tools may overwhelm the model (overload context) and increase
  errors; too few limit capabilities."*

## When you SHOULD split a tool

Split only when these differ across capabilities:
1. **Side effects / permission** — read vs write.
2. **Confirmation requirement** — `requires_confirmation` true vs false.
3. **External system / security boundary** — DB query vs internet vs sandbox.
4. **Composability** — you need it independently traced or authorized.

"Explain GHG Protocol" (concept) and "list DQ rules" (platform) differ in *zone*, not in
*tool capability* — they stay zero-tool or reuse one retrieval tool.

## The Common Tool Library (canonical schemas)

Every AI assistant converges on this small set. Reuse these names + schemas across
projects; add project-specific tools only at real boundaries.

### 1. `web_research(query, max_results=5)`
Keyless internet research. Search the open web and/or fetch a page.
**Internal dispatch** (deterministic, NOT separate tools):
- weather / forecast / temperature query → Open-Meteo geocode + forecast
- otherwise → Wikipedia search + DuckDuckGo instant answer
- a URL was supplied → fetch that page
Returns `{query, results[], count, source}`.

### 2. `search_knowledge(query, limit=10)`
Internal knowledge base / vector / document search. Returns ranked hits with citations.

### 3. `calculator(expression)`
Deterministic arithmetic/expression evaluation. Use for math; never let the LLM
"reason" a number it can compute exactly.

### 4. `code_exec(code, language="python")`
Sandboxed execution for analysis. `requires_confirmation=False` for pure compute,
`True` when it touches state.

### 5. `query_data(domain, filters)`  ← project-specific, parameterized
Platform data lookup (emissions, payroll, inventory…). ONE tool, `domain` as a
parameter — never `query_emissions`, `query_payroll`, `query_inventory`.

> Reference implementation: Carbon `backend/ai/plugins/web_research.py`
> (weather dispatch via `_is_weather_query` → `_weather`, Open-Meteo, keyless).

## Ad-hoc / dynamic tools — when the system may invent a tool

Creating a tool **at runtime** is legitimate ONLY as a **retrieval optimization**, not
as a way to dodge the one-capability rule:

- **Static + defer (recommended):** define the full catalog once, expose a small subset,
  and let `tool_search` load the rest on demand (OpenAI `tool_search`, Anthropic
  `tool_search` server tool, LangChain dynamic-tool middleware). The schema is authored,
  reviewed, and tested once.
- **Runtime-generated tools:** allowed when tools are genuinely data-driven (an MCP server
  advertises tools; a plugin registry; user-defined workflows). The tool is then a *schema
  emitted by a trusted source* executed by a generic dispatcher — it is NOT the model
  free-handing a new function per query.

**Never** let the model invent a new tool *as an alternative to a parameter*. "Weather in
Cairo" and "weather in London" are the same tool with different arguments — not two tools,
and not "generate an ad-hoc Cairo weather tool."

The test: **would a competent intern pick the right tool from your catalog?** If the
answer requires per-question tools, your catalog is wrong, not your tooling.

---

*Source: ~/ai-toolkit/shared/ai-tools.md (mirrored into carbon/.ai-toolkit/shared/)*
