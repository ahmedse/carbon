# ADR-0010 — Domain App AI Contract: Manifest-Driven Extension Model

**Date:** 2026-08-16
**Status:** Accepted
**Author:** Master Architect
**Supersedes:** None (new decision)
**Referenced by:** `docs/DESIGN_AI_WORKSPACE_V4.md §19`

---

## Context

Carbon is a **general platform** that hosts domain apps (Carbon Emissions today;
Academic KPI Portfolio planned). The AI workspace must be a platform-level capability
that any domain app can participate in **without modifying the core AI workspace code**.

Prior to this ADR, the AI workspace was implicitly emissions-specific:
- `CONVERSATION_TYPES` in `workspace.py` listed emissions-domain types
- Structured output cards were hardcoded in `AIConversationView`
- `WorkspaceContext` had no domain-specific enrichment hook
- The frontend had no way to discover what AI capabilities an app offers

The `DomainAIOperations` ABC (`ai/domain_protocol.py`) existed but only carried
vocabulary/knowledge for LLM prompt injection — not the full capability manifest
a frontend needs.

---

## Decision

**Extend `DomainAIOperations` to serve as the complete Domain App AI Manifest.**

Every domain app's `DomainAIOperations` subclass now also declares:

| Attribute | Type | Purpose |
|-----------|------|---------|
| `supported_task_types` | `list[str]` | Which platform task types this app enables |
| `entry_points` | `list[dict]` | Buttons to render on domain app pages |
| `starter_prompts` | `dict[str, list[dict]]` | Context-aware starters per entity type |
| `system_prompt_extension` | `str` | Domain vocabulary injected into T0 |
| `build_workspace_context(user, entity_type, entity_id)` | instance method | Live domain context for T1 tier |
| `validate_task_payload(task_type, payload)` | instance method | Fast validation before dispatch |
| `to_manifest_dict()` | instance method | Serialized for the API |

**A manifest API is exposed:**

```
GET /carbon-api/ai/pulse/apps/                   → all registered manifests
GET /carbon-api/ai/pulse/apps/{app_identifier}/  → single manifest
```

Authentication: `IsAuthenticated` (no admin gate — all users need their app's capabilities).
`system_prompt_extension` is never returned as raw text (only a boolean `true/false`).

---

## Consequences

### Positive

1. **Zero core changes** when adding a new domain app's AI capabilities. A developer:
   - Creates `ai/domain/{app}.py` with a `DomainAIOperations` subclass.
   - Fills in the manifest attributes.
   - Calls `register_domain(app_identifier, cls)` at module bottom.
   - Adds `import ai.domain.{app}` to `AppConfig.ready()`.
   - The frontend discovers the new app's capabilities from the manifest API.

2. **Frontend is data-driven** — entry points, starter chips, and card routing
   all come from the manifest. No hardcoded domain-specific logic in the shell.

3. **Each domain owns its context** — `build_workspace_context` is called per-turn
   by the context assembler; the domain app controls what live data enriches T1.

4. **Payload validation is domain-specific and centralized** — `validate_task_payload`
   gives the domain app early veto before any LLM call is made.

### Negative / Trade-offs

1. **Manifests are Python classes, not YAML/JSON.** If future apps are deployed
   as external services (not Django apps in the monorepo), the manifest model must
   evolve. For the current monorepo model this is the right trade-off.

2. **Base structured cards are platform-defined.** Domain apps do not ship custom
   React components. This means a domain app's AI output is limited to the platform's
   card repertoire (`dq_validate`, `nl_query`, `anomaly`, `report_draft`, etc.).
   A domain-specific card that doesn't map to any base card would require a new
   platform card (separate ADR required).

3. **`system_prompt_extension` is static.** If a domain needs a dynamic T0 extension
   (e.g., "today's live KPI numbers"), it must put that in `build_workspace_context`
   (T1), not `system_prompt_extension` (T0). T0 is always static text.

---

## Rejected Alternatives

| Alternative | Reason rejected |
|-------------|-----------------|
| Domain apps ship custom React cards | Requires frontend bundling per domain app; complex deployment |
| Central registry file (`ai/app_registry.py`) lists all apps | Fragile: requires platform-level edit for every new domain app |
| Frontend-first manifest (route config declares AI caps) | Splits the contract across Python and JS; harder to test |
| MCP tools per domain app | Over-engineered for the current scale; MCP adds transport complexity |

---

## Example: Adding "Academic KPI Portfolio" domain app AI

```python
# backend/academic_kpi/ai_manifest.py  (future)

from ai.domain_protocol import DomainAIOperations, DomainContext, register_domain

class AcademicKPIDomainAI(DomainAIOperations):
    app_identifier    = "academic_kpi"
    app_display_name  = "Academic KPI & Portfolio"

    supported_task_types = ["chat", "nl_query", "investigate", "report_draft"]

    entry_points = [
        {"label": "Analyze KPIs",      "task_type": "investigate",  "on_entity": "dept",    "icon": "Analytics"},
        {"label": "Draft eval report", "task_type": "report_draft", "on_entity": "faculty",  "icon": "Description"},
        {"label": "Ask about this",    "task_type": "chat",         "on_entity": "*",        "icon": "Chat"},
    ]

    starter_prompts = {
        "dept": [
            {"label": "Compare to last semester", "prompt": "Compare KPIs for @{entity_name} vs last semester", "task_type": "nl_query"},
        ],
        "faculty": [
            {"label": "Draft annual review", "prompt": "", "task_type": "report_draft"},
        ],
        "default": [
            {"label": "What KPIs are tracked?", "prompt": "List the KPIs tracked in the academic portfolio system.", "task_type": "chat"},
        ],
    }

    system_prompt_extension = (
        "You are analyzing academic KPI data for AASTMT faculty and departments. "
        "Metrics include publications, student outcomes, research funding, and teaching load."
    )

    def get_domain_context(self) -> DomainContext:
        return DomainContext(app_identifier="academic_kpi", domain_knowledge={}, domain_config={})

register_domain("academic_kpi", AcademicKPIDomainAI)
```

```python
# backend/academic_kpi/apps.py
from django.apps import AppConfig

class AcademicKPIConfig(AppConfig):
    name = "academic_kpi"
    def ready(self):
        import academic_kpi.ai_manifest  # noqa: F401
```

That is the **complete** integration. No changes to `ai/`, `workspace_api.py`, or any frontend file.
