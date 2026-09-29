---
name: tool-guidance
description: When and how to use call_host_api and search_knowledge to ground answers in live data
allowed-tools: []
when_to_use: [tools, live-data, grounding, aggregation]
---
## Tool Heuristics

- Use `call_host_api` for LIVE platform data. Endpoint names are listed in the "Available Host API Endpoints" section of the system prompt — call them by exact name.
- Use `search_knowledge` for the knowledge graph (concepts, entities, relationships) — it does NOT search the live API catalog.
- Answer live-data questions from the returned data only. If a domain maps to more than one endpoint, call the one that answers the user's specific question. Never invent values; if the data has no matching rows, say so plainly.
- For any distribution or "how many X are Y" question, use an `analyze_*` endpoint — never count rows from a paginated `list_*` result (lists return at most 100 rows).
- When a list result returns `truncated: true`, say "Showing first N of TOTAL".
- When `analyze_*` returns `caveats` or `normalization_notes`, quote them verbatim before any chart or table.
- Use FK-resolved `label` fields (not raw IDs) for chart axes, and follow `suggested_chart_type` instead of defaulting to pie.

The full aggregation rules are in `references/live-data-grounding.md`.

## AASTMT inventory onboarding (benchmark O1)

- A kilogram or tonne figure is legal only when that same number is in the `get_calculation_summary` or `get_chairman_overview` payload for the reporting period the user named.
- When that payload has no number, say the period is opening. Do not use the July 2026 deployment sketch as a quantity.
- The open leaf is Smart Village electricity (scope 2, kWh) and Smart Village diesel (scope 1, litre). Other campuses stay declared or excluded.
- Do not call a non-GET host tool from Chat. Inventory changes happen on `/carbon/onboarding` and the host screens, or in Agent after a person approves.
