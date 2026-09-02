# PULSE 0.3 & 0.4 — Complete Phased Roadmap

> **Status:** CANONICAL PLAN · **Owner:** Master Architect · **Date authored:** 2026-09-01
> **Companion to:** [`PULSE-MASTER.md`](./PULSE-MASTER.md) · [`PULSE-UX.md`](./PULSE-UX.md)
> **Closes out:** [`PULSE-0.2-ROADMAP.md`](./PULSE-0.2-ROADMAP.md) (all 8 north-star items proven,
> commit `741514a`, ADR-0026).
> **Feature vision source:** session research (Sep 2026) benchmarking GitHub Copilot Agent,
> Claude Code, VS Code MCP, MCP 2026-07-28 spec, Workday AI, SAP Joule, Project Padawan.
> **Audience:** Workers running **DeepSeek V4-Flash** (RULE_24).

---

## Honest baseline (what already exists as of 0.2 close)

Before writing a phase, workers MUST read this. Many features a naive reading of the gap table
suggests "building" are already shipped. Do not rebuild.

| Area | Already exists | Key files |
|------|---------------|-----------|
| Plans + consent | Full plan lifecycle: create/approve/run/pause/resume/fork/stop/ledger/QoS | `ai/plans_api.py`, `ai/plans_service.py` |
| Durable execution | Crash-resume, replay, timeline (Sprint W3-E) | `ai/durable_service.py`, `ai/durable_api.py` |
| Flight director | In-loop supervisor, acceptance checks, working memory ledger (Phase 25-B/C) | `ai/flight_director.py` |
| MCP client | Connects Pulse to external tool servers at startup | `ai/engine/agent/mcp_client.py` |
| Budget | Per-run token budget, graceful degradation, worker sub-allocation | `ai/engine/agent/budget.py` |
| Memory API | Read + forget: facts, episodes, relationship (Phase 23-A) | `ai/memory_api.py`, `ai/memory_urls.py` |
| Usage service | Token usage, cost (Phase 21-A), per-conversation breakdown | `ai/usage_service.py`, `ai/usage_views.py` |
| Observability API | 13 inventory panels + model row counts (read-only) | `ai/observability_api.py` |
| Checkpoints | Model, create, list, restore, fork endpoints (Sprint 20 W1-B) | `ai/models/workspace.py:ConversationCheckpoint`, `ai/workspace_api.py` |
| Daily briefing | Engine logic: `generate_daily_briefing`, `run_daily_briefing` | `ai/engine/proactive/insight_generator.py`, `ai/engine/proactive/loop.py` |
| Worker subagents | Infrastructure: `is_worker` guard, mutation block for worker calls | `ai/engine/agent/guardrails.py` |
| Mermaid + rich markdown | MarkdownMessage renders ```mermaid → SVG, GFM tables, KaTeX, syntax highlight | `carbon-frontend/src/shell/MarkdownMessage.jsx` |
| Workspace frontend | AIWorkspace (tabbed), PulsePane, ActivityBar, MemoryTab, UsageTab, LearntTab, RelationshipTab, SettingsTab, TaskPanel | `carbon-frontend/src/shell/AI*.jsx` |
| Conversation tabs | AIConversationTabs, AIConversationView | `carbon-frontend/src/shell/AIConversation*.jsx` |
| Plan frontend | AITaskPanel, AITaskPlanCard, PlanDiffReviewDialog, AITaskAuditCard, AIActionRunner | `carbon-frontend/src/shell/` |
| Confidence + provenance | ConfidenceIndicator, ReasoningTrace, SuggestionDiff, AIGeneratedBadge (Wave C/D3) | `carbon-frontend/src/shell/` |
| Optimistic CRUD | useOptimisticList, useOptimisticItem (Wave D2) | `carbon-frontend/src/hooks/` |
| Presence + drafts | PulsePresence, useDraftPersistence, usePresence (Wave D4) | `carbon-frontend/src/shell/`, `src/hooks/` |
| Progress SSE | OperationProgress, useOperationProgress (Wave D1) | `carbon-frontend/src/components/`, `src/hooks/` |

---

## The true gaps (what 0.3 and 0.4 must build)

| Gap | Why it matters | Target version |
|-----|---------------|----------------|
| **WorldModel + ToolCatalog seam** | Engine expertise is implicit (buried in system prompt). Making it a typed, CBAC-filtered, per-user object is the architectural prerequisite for everything below | 0.3 |
| **Domain tool implementations** | `DomainAIOperations` has manifest + context injection but no `get_tools()` returning typed `ToolDef` objects. Tools exist as `call_host_api` strings, not first-class registered objects | 0.3 |
| **Entity chips in answer bubbles** | MarkdownMessage renders rich markdown but has no `EntityChip` component. Entity refs in answers are plain text, not clickable records | 0.3 |
| **@-mention + context chips** | Input bar has no `@` typeahead. Users can't pin entities as session context from the composer | 0.3 |
| **Cross-domain synthesis** | KG exists. Plans + multi-tool calls exist. But there is no first-class `cross_synthesize` tool that joins results from two domain servers via the KG | 0.3 |
| **Checkpoint UI** | Backend checkpoint API (Sprint 20 W1-B) is fully built. The conversation UI has no "Checkpoint ⊕" button or restore picker | 0.3 |
| **User-configurable anomaly watches** | Engine generates `daily_briefing` insights. Users cannot configure custom watches (KPI name, threshold, recipients) with persistence and UI | 0.3 |
| **Pulse Console (admin room)** | `observability_api.py` + `usage_service.py` exist. There is no dedicated admin console frontend room with dashboard, audit viewer, skills pipeline, budget panel | 0.3 |
| **Auto-memory (self-learning)** | Facts and episodes are stored. There is no path where Pulse automatically extracts and saves a preference/feedback from a correction the user gives in conversation | 0.3 |
| **Platform as MCP server (multi-app)** | MCP client (Pulse consuming external servers) exists. The platform exposing **every app's** domain tools via MCP HTTP endpoints for external clients does not exist (Carbon = first app, Nibras/GOFSCO + others follow the same server contract) | 0.4 |
| **Code execution sandbox** | No sandboxed Python/pandas executor. GPT-4/Claude Code gap | 0.4 |
| **Web search built-in tool** | MCP client can wire to Brave/Bing external server. A first-class `web_search` tool registered in the domain catalog with provenance labeling does not exist | 0.4 |
| **Subagent dispatch UI** | Worker subagent infrastructure exists (guardrails, isolation). Users cannot dispatch a named subagent from the conversation with progress tracking | 0.4 |
| **PII server-side gate** | `logger.js` redacts client-side. Memory entries and audit logs have no server-side PII pattern detection and masking | 0.4 |

---

## How to use this roadmap

Same contract as Pulse 0.2 — read the 0.2 header for the full protocol. Short version:

1. One phase = one worker session = one domain. Master copies phase into `TASKS.md`.
2. Phase is NOT done until the Acceptance Gate is proven with real terminal output.
3. Every phase lists a **Shallow-implementation trap** — matching it = rejected.
4. Anti-drift laws L1–L7 (from 0.2 roadmap) remain in force for every phase.
5. Every UI phase must pass the **UX Acceptance Rubric** (`PULSE-UX.md §10`).

### New global gates for 0.3+

```bash
./.ai-toolkit/scripts/verify.sh all          # existing gate, must stay green
./.ai-toolkit/scripts/audit-imports.sh        # I1 boundary, must stay green

# New for 0.3: tool catalog integrity check (added in Phase E2)
python manage.py check_tool_catalog           # every registered tool has CBAC metadata + schema
```

---

## Multi-app guarantee (GOFSCO/Nibras + every registered app)

Pulse is the AI brain of a **multi-tenant data-trust platform**, not of Carbon alone. Carbon is
just the first hosted app. Every phase in this roadmap is **app-agnostic**: it must work for any
domain app that declares a `DomainAIOperations` subclass and a manifest — with **zero engine and
zero frontend edits** for a newly-installed app (already proven for `water`).

**The app universe at authoring time** (`ai/domain/`, keyed by `app_identifier`):

| `app_identifier` | App / source | Notes |
|---|---|---|
| `emissions` | Carbon | First app; GHG scope 1/2/3, factors, calc |
| `people` | **Nibras / GOFSCO** | PII-heavy (civil IDs, passport, KOC/Gulf) — I5 + H1 are load-bearing |
| `hr` | HR / Nibras | employee, certifications, org |
| `finance` | Finance | budgets, cost |
| `customer` | Customer | accounts, EOSI service history |
| `water` | Water | utility data (scope 3) |
| `data_product` | Data products | catalog/metadata surfaces |
| `mdm` | MDM | org units, reference data |
| `admin` | Platform admin | governance, RBAC |

Plus frontend apps already shipped (`apps/healthy/`, `apps/people/`) and any app installed later.

**Hard rules this guarantee imposes on every phase:**

1. **No Carbon-specific hardcoding.** `E1`'s adapter is `HostAdapterContract` (abstract), not
   `CarbonHostAdapter`-only; `CarbonHostAdapter` is *one* implementation reading the domain
   registry, and a Nibras/GOFSCO deployment supplies its own adapter or reuses the registry-driven
   default. The engine imports nothing above `ai/adapter/`.
2. **`app_identifier` is the isolation key** (AI CONTRACT §3). Every tool, memory fact, audit row,
   and MCP server is namespaced by `app_identifier`. `I1` therefore exposes **one MCP server per
   app**, not one "Carbon" server.
3. **PII gate is app-aware, not Carbon-aware.** `I5` redacts patterns from `backend/people/models.py`
   (civil ID, passport, email) for *any* app that emits them — Nibras is the primary but not the
   only source.
4. **CBAC is per-app.** A user's tool catalog (`E2`) and MCP discovery (`I1`) are filtered by the
   user's capabilities *for that app*, so a GOFSCO HR user never sees Carbon's DQ tools and a
   Carbon analyst never sees Nibras' civil-ID fields.

**What this means for "other ready at the time apps":** a new app is onboarded by (a) adding a
`DomainAIOperations` subclass + manifest (already the contract), (b) registering its CBAC
capabilities, and (c) optionally adding its PII patterns to `pii_guard.py`. Phases E2, E3, F1, G1,
H1, I1, and I5 all pick it up automatically because they read the registry, never a hardcoded list.

---

# PULSE 0.3 — "Expert & Observable"

> **0.3 North-Star (3 items):**
> 1. **Pulse is expert** — it knows Carbon's entities, tools, and business rules through a typed
>    seam, not a wall of prompt text. Every tool is CBAC-registered; every domain exposes a
>    `ToolDef` catalog.
> 2. **Pulse is observable** — there is a dedicated admin console room where any admin can see what
>    Pulse knows, what it costs, what it delivered, what it learned, and what it changed.
> 3. **The conversation is rich** — entity references are clickable chips; users pin context with
>    `@`-mention; the "Considered…" header is a one-line collapsible pill; checkpoints are
>    one-click.

---

## WAVE E — Expert Foundation (backend · architectural)

> The engine already reasons. Wave E makes the engine *knowledgeable* — through a typed seam,
> not implicit system-prompt stuffing. Backend-heavy; no user-visible UX until Wave F uses it.

### Phase E1 — WorldModel + ToolCatalog seam

- **Goal:** introduce `ai/adapter/` with a `HostAdapterContract` ABC, `WorldModel`, `ToolCatalog`,
  and `SessionContext` dataclasses. Wire `CarbonHostAdapter` as the concrete implementation that
  reads from Carbon models. The engine receives expertise through this contract, never through
  direct ORM imports above `ai/adapter/`.
- **Why:** `ai/context_assembler.py` currently imports `core.models`, `dq.models`, `dataschema.models`
  directly. This makes the engine untestable without a running Django server. The Host Adapter is the
  typed seam that makes expertise injectable and the engine provably portable.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/context_assembler.py`, `ai/protocol.py` (Scope, WorkspaceContext),
  `ai/intelligence.py`, `ai/domain_protocol.py` (DomainAIOperations ABC),
  `accounts/capabilities.py` (CBAC capability keys), `ai/engine/agent/plugins.py` (ToolPlugin ABC),
  `ai/engine/agent/tools.py` (_CHAT_STATIC_TOOLS).
- **Tasks:**
  1. ADD `ai/adapter/__init__.py`, `ai/adapter/contract.py` — `HostAdapterContract` ABC with four
     abstract methods: `get_world_model() → WorldModel`, `get_tool_catalog(user, scope) → ToolCatalog`,
     `assemble_context(query, user, scope, page_context) → SessionContext`,
     `get_org_memory_seeds(instance_id) → list[MemorySeed]`.
  2. ADD `ai/adapter/types.py` — pure dataclasses: `EntityDef`, `VocabularyTerm`, `BusinessRule`,
     `WorldModel`, `ToolDef`, `ToolCatalog`, `SessionContext`, `MemorySeed`. Zero Django imports.
  3. ADD `ai/adapter/carbon.py` — `CarbonHostAdapter(HostAdapterContract)` that implements the
     contract using Carbon's ORM. Moves the ORM imports out of `context_assembler.py` into here.
     `context_assembler.py` delegates its T3/T4 assembly to this adapter.
  4. MODIFY `ai/intelligence.py` — accept an optional `adapter: HostAdapterContract` on init;
     default to `CarbonHostAdapter()`. Thread it through to `context_assembler`.
  5. DO NOT change any public API, endpoint, or model. This is additive only.
- **Do not touch:** `ai/engine/` (must stay import-clean), any migration, any URL route.
- **Shallow-implementation trap:** ❌ putting the adapter behind a feature flag and leaving the old
  ORM imports as the live path (both paths then exist → the coupling isn't removed); ❌ making
  `ToolCatalog` a thin wrapper that still hardcodes tool names instead of reading from domain
  registrations; ❌ importing Django models inside `ai/adapter/types.py`.
- **Acceptance gate:**
  ```bash
  # Boundary check: adapter/types.py has zero Django imports
  python -c "import ai.adapter.types; print('OK')"
  # Engine testable without Django: mock adapter, no DB
  python -m pytest ai/tests/ -k "adapter" -q --disable-warnings
  # Full suite still green
  python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider | tail -5
  ```
- **North-star link:** Expert foundation; unblocks E2, E3, F3.

---

### Phase E2 — Domain tool catalog

- **Goal:** every `DomainAIOperations` subclass gains a `get_tools() → list[ToolDef]` method. The
  `CarbonHostAdapter.get_tool_catalog(user, scope)` assembles a per-user, CBAC-filtered `ToolCatalog`
  from all registered domains. A management command `check_tool_catalog` validates integrity.
- **Why:** tools currently live as string names in `_CHAT_STATIC_TOOLS` and `call_host_api` endpoint
  names in the system prompt. There is no machine-readable registry the engine can query. The LLM
  sees all endpoint names even if the user can't use them.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/domain_protocol.py` (DomainAIOperations ABC), `ai/domain/emissions.py`,
  `ai/domain/dq.py` (if exists, else `ai/domain/admin.py`), `accounts/capabilities.py`,
  `ai/adapter/types.py` (ToolDef — from E1), `ai/engine/agent/plugins.py` (ToolPlugin ABC).
- **Tasks:**
  1. MODIFY `ai/domain_protocol.py` — add abstract `get_tools() → list[ToolDef]` to the
     `DomainAIOperations` ABC. Each tool declares: `id`, `description`, `required_capability`,
     `is_mutation`, `domain`, `input_schema`, `output_description`.
  2. IMPLEMENT `get_tools()` in each existing domain class: `emissions.py`, `admin.py`, `mdm.py`,
     `data_product.py`, `hr.py`, `finance.py`, `customer.py`, `people.py`. Each returns the tools
     that already exist as `call_host_api` endpoint names, but now typed with CBAC metadata.
     (Example: `emissions.query` → required_capability `"carbon:view_data"`, is_mutation=False.)
  3. MODIFY `CarbonHostAdapter.get_tool_catalog(user, scope)` — iterate all registered domain
     instances, call `get_tools()`, filter by `has_capability(user, tool.required_capability, scope)`,
     return the filtered `ToolCatalog`. Write-permission tools are only included if user has write cap.
  4. ADD `management/commands/check_tool_catalog.py` — for each registered tool: verify it has
     a non-empty description, a valid capability key in `CAPABILITY_REGISTRY`, and a JSON schema.
     Exits non-zero on any violation. Wire into `verify.sh` as a `tools` target.
  5. MODIFY `ai/intelligence.py` — when building the system prompt, use
     `adapter.get_tool_catalog(user, scope)` to inject only the user-accessible tools into the
     "Available Host API Endpoints" section. Never inject tools the user can't use.
- **Do not touch:** `ai/engine/` (RULE_20); existing endpoint implementations; CBAC model.
- **Shallow-implementation trap:** ❌ returning ALL tools for ALL users without CBAC filtering (the
  LLM would then offer forbidden tools); ❌ duplicating the tool definition between `get_tools()` and
  the system prompt (they must come from the same source); ❌ leaving `_CHAT_STATIC_TOOLS` as a
  parallel definition that overrides the catalog.
- **Acceptance gate:**
  ```bash
  python manage.py check_tool_catalog   # exits 0 = all tools valid
  # CBAC test: user with only carbon:view_data sees emissions tools, NOT write tools
  python -m pytest ai/tests/ -k "tool_catalog" -q --disable-warnings
  # Full suite still green
  python -m pytest ai dq -q --maxfail=5 --disable-warnings -p no:cacheprovider | tail -5
  ```
- **North-star link:** Expert (#1); foundation for F1, F3, J1.

---

### Phase E3 — Cross-domain synthesis

- **Goal:** add a `cross_synthesize` core tool (Platform Core, always active) that takes the already-
  fetched results from two or more domain tool calls and performs a KG-based join to produce a
  unified answer with separate provenance from each domain.
- **Why:** "Why did South Valley's emissions spike the same week DQ failures peaked?" requires data
  from two domains. Today Pulse can call tools from multiple domains sequentially, but there is no
  first-class synthesis step that uses the KG to find causal/temporal connections across them.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/engine/knowledge_graph/models.py`, `ai/engine/knowledge_graph/`
  (query + traversal), `ai/engine/agent/plugins.py` (ToolPlugin ABC), `ai/engine/agent/tools.py`,
  `ai/protocol.py` (Scope), `ai/domain_protocol.py`.
- **Tasks:**
  1. ADD `ai/engine/agent/synthesis.py` — `CrossDomainSynthesisTool(ToolPlugin)`: accepts
     `{results: [{domain, data, entity_ids}], question}`, traverses the KG to find shared entity
     nodes across the result sets, builds a temporal/causal alignment, returns a structured synthesis
     with per-source provenance citations.
  2. REGISTER `CrossDomainSynthesisTool` via `register_plugin()` — it appears in the tool catalog
     as a core tool (no domain-specific capability required beyond base auth; the per-domain CBAC was
     already enforced when each domain tool ran).
  3. ADD `ai/tests/test_cross_domain_synthesis.py` — test: feed two domain results that share an
     OrgUnit entity; assert the synthesis output cites both sources and identifies the shared node.
  4. MODIFY `ai/intelligence.py` system prompt — add the `cross_synthesize` tool to the tool list
     when two or more domain tool results are in the current turn context.
- **Do not touch:** domain MCP servers; existing KG query paths.
- **Shallow-implementation trap:** ❌ prompting the LLM to "combine" the results in text (the synthesis
  must go through the KG traversal, not just LLM summarization — the KG is what provides verifiable
  provenance); ❌ querying domain databases inside the synthesis tool (it must work only on the
  already-fetched results + KG node lookups — CBAC was enforced upstream).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_cross_domain_synthesis.py -v --disable-warnings
  # Live proof: ask a cross-domain question, inspect the response for dual provenance
  # Response must contain two provenance sources, each from a different domain
  ```
- **North-star link:** Expert (#1); the unique moat no external system can match.

---

## WAVE F — Rich Conversation Surface (frontend)

> Wave E made the engine expert. Wave F makes the conversation reflect that expertise: entities
> become clickable, context is pinnable, and the thinking trace becomes the "Considered…" pill.

### Phase F1 — Entity chips in answer bubbles

- **Goal:** when Pulse's answer references a Carbon entity (OrgUnit, Employee, DQRule, DataTable,
  EmissionRecord), that reference is rendered as a clickable `<EntityChip>` component instead of
  plain text. Clicking opens the Inspector panel (ADR-0019) pre-loaded with that entity's detail.
- **Why:** this is the core of the "Considered…" behavior in the screenshots — inline entity
  references are the difference between a text dump and a working coworker. Without chips, the
  answer is prose; with chips, it is actionable.
- **Domain:** Frontend Worker.
- **Files to read first:** `carbon-frontend/src/shell/AIMessageBubble.jsx`,
  `carbon-frontend/src/shell/MarkdownMessage.jsx`, `carbon-frontend/src/shell/ReasoningTrace.jsx`,
  `carbon-frontend/src/shell/AIContextPanel.jsx` (the existing Inspector/context panel),
  `carbon-frontend/src/api/aiWorkspace.js` (API helpers), `.ai-toolkit/shared/ux-patterns.md`.
- **Tasks:**
  1. ADD `carbon-frontend/src/shell/EntityChip.jsx` — a small MUI `Chip` variant with a type icon
     (OrgUnit=AccountTree, Employee=Person, DQRule=FactCheck, DataTable=TableChart). Props:
     `{type, id, label}`. On click → dispatches to open `AIContextPanel` with entity detail.
     Uses theme tokens only (RULE_8). Has loading/error state.
  2. MODIFY `MarkdownMessage.jsx` — add a remark plugin that detects the serialized entity ref
     format `[[EntityType:id:label]]` (e.g., `[[OrgUnit:42:South Valley]]`) in the markdown source
     and replaces it with an `<EntityChip>` component. The backend (E2) must emit this format;
     the frontend parses it here.
  3. MODIFY backend: `ai/intelligence.py` or the answer post-processor — after the LLM produces an
     answer, run a lightweight entity mention extractor that scans for known entity names (from the
     `WorldModel.entities` list) and annotates them with `[[EntityType:id:label]]` format using a
     KG lookup. Inject the annotated answer into the response payload.
  4. ADD `carbon-frontend/src/__tests__/EntityChip.test.jsx` — renders chip with each entity type,
     correct icon, correct click handler.
- **Do not touch:** `ai/engine/` (RULE_20); AITaskPanel; existing Inspector panel logic.
- **Shallow-implementation trap:** ❌ hardcoding a regex for entity names in the frontend (entity
  names change; the annotation must come from the backend KG lookup); ❌ opening a new page on chip
  click instead of the Inspector panel (breaks the three-room information architecture); ❌ always-
  visible entity type label on every chip (defeats content-first density — show on hover only).
- **Acceptance gate:**
  ```bash
  cd carbon-frontend && npx vitest run src/__tests__/EntityChip.test.jsx
  npm run lint && npm run build
  # Manual: ask "What org units does GOFSCO have?" → OrgUnit chips appear inline
  # Clicking a chip → Inspector opens with that OrgUnit's data (no new page)
  # UX rubric: chips use theme tokens; hover tooltip shows type; screen-reader label set
  ```
- **North-star link:** Expert conversation richness.

---

### Phase F2 — @-mention routing + context chips

- **Goal:** typing `@` in the input bar opens a typeahead autocomplete over Carbon entities
  (OrgUnits, Employees, DQRules, DataTables). Selecting one pins it as a `ContextChip` below the
  input bar, scoping the session to that entity. Chips persist until removed.
- **Why:** this is the `#south-valley` / `@dq` pattern from the feature vision. It lets users
  declare context explicitly, not just hope Pulse infers it. Direct port of VS Code Copilot's
  `@workspace` / `@file` pattern to the domain.
- **Domain:** Frontend Worker.
- **Files to read first:** `carbon-frontend/src/shell/AIInputBar.jsx`,
  `carbon-frontend/src/api/aiWorkspace.js`, `carbon-frontend/src/shell/EntityChip.jsx` (from F1),
  `carbon-frontend/src/hooks/useDraftPersistence.js` (existing input state), `.ai-toolkit/shared/ux-patterns.md`.
- **Tasks:**
  1. ADD `carbon-frontend/src/hooks/useEntityTypeahead.js` — debounced API call to a new
     `GET /carbon-api/ai/entities/resolve/?q={query}&types={type_list}` endpoint (backend: add to
     `workspace_api.py`, queries KG + ORM, returns `[{type, id, label, secondary_label}]`). Returns
     `{suggestions, loading}`.
  2. MODIFY `AIInputBar.jsx` — detect `@` keystroke; show a compact `<Autocomplete>` popover with
     `useEntityTypeahead` results; selecting an entity creates a `ContextChip` in a chip row below
     the text area. Chips are stored in component state and included in the request payload as
     `entity_context: [{type, id}]`.
  3. ADD `carbon-frontend/src/shell/ContextChipRow.jsx` — renders the list of pinned context chips;
     each chip has a remove ✕ button; shows freshness indicator ("data as of 3h ago · ↺").
  4. MODIFY `ai/intelligence.py` / `ai/workspace_api.py` — accept `entity_context` in the request;
     inject the resolved entities into `SessionContext.page_entity` and the prompt context.
  5. ADD `carbon-frontend/src/__tests__/useEntityTypeahead.test.js` — mock the API, verify
     debounce, verify result shape.
- **Do not touch:** existing `DomainAIOperations` entry_points (separate from @-mention); AITaskPanel.
- **Shallow-implementation trap:** ❌ storing context chips in localStorage across sessions (they are
  session-scoped, per-conversation — a stale context chip from yesterday is worse than no context);
  ❌ sending the raw entity object in the request body instead of `{type, id}` (PII risk for People
  entities); ❌ blocking the text input while the typeahead is open.
- **Acceptance gate:**
  ```bash
  cd carbon-frontend && npx vitest run src/__tests__/useEntityTypeahead.test.js
  npm run lint && npm run build
  # Manual: type @South → typeahead shows OrgUnit matches → select → chip appears
  # Chip freshness shown; remove works; chip included in next request payload
  # UX rubric: typeahead dismisses on Escape; focus returns to text area; AA contrast
  ```
- **North-star link:** Expert conversation; scope-aware queries.

---

### Phase F3 — Planning header + tool-use summary pill

- **Goal:** every multi-step response (any turn where ≥2 tool calls fire) opens with a collapsible
  **"Considered…"** pill (one-line summary, click to expand full step trace). This is the behavioral
  pattern shown in the Copilot screenshots — the thinking becomes visible before the answer.
- **Why:** `ReasoningTrace` (D3) exists as a click-expand on the *message*. The gap is the *pre-answer*
  planning header — a one-line "here's what I'm doing" pill that appears while the answer is still
  streaming, before the full trace is available.
- **Domain:** Frontend Worker.
- **Files to read first:** `carbon-frontend/src/shell/ReasoningTrace.jsx` (D3),
  `carbon-frontend/src/shell/AIMessageBubble.jsx`,
  `carbon-frontend/src/shell/AIConversationView.jsx`,
  `carbon-frontend/src/hooks/useInsightStream.js` (SSE hook for ops events),
  `docs/pulse/PULSE-UX.md §3` (Beat 2 — Think out loud).
- **Tasks:**
  1. ADD `carbon-frontend/src/shell/PlanningHeader.jsx` — a compact collapsible pill:
     collapsed state shows "Considered: {one-line summary}" (e.g., "Considered: reading South Valley
     records + checking DQ rules"). Expanded state shows a step list (step name, tool used, duration)
     from the `tool_trace` payload. Uses theme tokens (RULE_8). Respects `prefers-reduced-motion`.
  2. MODIFY `AIMessageBubble.jsx` — for assistant messages that have a `tool_trace` array in their
     payload, render `<PlanningHeader trace={tool_trace} />` above the message body. The header
     is collapsed by default for the Operator (one-line pill); expanded by default in the Analyst
     view (or if the user previously expanded it — store preference in `localStorage`).
  3. MODIFY backend `ai/intelligence.py` / `ai/workspace_api.py` — include a `tool_trace`
     field in the response: array of `{step_label, tool_id, duration_ms}` in outcome language
     (RULE_23: "Read South Valley records", not "S2 retrieve returned 412 rows"). Derive from the
     existing `TurnLedger` step rows.
  4. ADD `carbon-frontend/src/__tests__/PlanningHeader.test.jsx` — collapsed/expanded states,
     correct summary text, keyboard expand/collapse.
- **Do not touch:** existing `ReasoningTrace` (it serves the deeper analyst view; `PlanningHeader`
  is the compact surface); `AITaskPanel` plan cards (those are for agentic tasks, not chat turns).
- **Shallow-implementation trap:** ❌ making the planning header always-expanded (defeats content-first
  density — the Operator never asked for a trace); ❌ showing raw tool call JSON instead of outcome
  language (RULE_23); ❌ emitting the header as a separate SSE frame that the frontend has to
  reconcile separately from the answer (it must arrive as part of the same message payload).
- **Acceptance gate:**
  ```bash
  cd carbon-frontend && npx vitest run src/__tests__/PlanningHeader.test.jsx
  npm run lint && npm run build
  # Manual: ask a multi-tool question → "Considered: …" pill appears before the answer
  # Clicking pill expands to show step list in outcome language (no engine terms)
  # UX rubric: outcome language only; collapsed by default; keyboard-accessible; AA contrast
  ```
- **North-star link:** Transparency → trustworthy; closes the "Considered…" screenshot gap.

---

## WAVE G — Memory & Auto-Learning (backend + frontend)

> The engine already writes facts and episodes. Wave G closes the loop: Pulse learns from
> corrections *automatically*, and users can see + manage what Pulse knows about them.

### Phase G1 — Auto-memory: self-learning from corrections

- **Goal:** after each turn, if the user's message contains a correction ("actually, that's a yard,
  not a division") or an explicit preference ("I always want 30-day windows, not 7"), Pulse
  automatically extracts a `MemoryEntry` and saves it to long-term memory — without the user
  writing anything or saying "remember this."
- **Why:** Claude Code's auto-memory is one of the biggest perceived intelligence gaps vs. Pulse.
  The engine already has episodic memory write paths; what's missing is the *correction/preference
  classifier* that decides what's worth remembering.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/engine/memory/long_term.py`, `ai/engine/memory/episodic.py`,
  `ai/memory_api.py`, `ai/engine/cognition/trajectory.py` (trajectory + learning path),
  `ai/engine/cognition/consolidation.py` (episodic→semantic distill),
  `ai/engine/llm/router.py` (lanes — use `eval` lane for classification).
- **Tasks:**
  1. ADD `ai/engine/cognition/auto_memory.py` — `AutoMemoryExtractor`: a post-turn hook that
     receives the user's message. Uses the `eval` lane to classify whether it contains: a
     `preference` ("I always want…"), a `feedback` ("actually, that's wrong…" / "no, use…"),
     a `context` entry (ongoing work the user declared), or nothing. If classified, extracts the
     structured entry `{type, content, domain}` and writes it to `long_term.py`.
  2. MODIFY `ai/engine/cognition/turn/runner.py` — call `AutoMemoryExtractor.try_extract(user_msg,
     turn_context)` as a post-S6-ledger step (never before the answer is delivered — never
     auto-mutation during the turn, only after the turn completes).
  3. ADD `ai/tests/test_auto_memory.py` — test: a correction message → entry classified as
     `feedback` and written; a preference message → classified as `preference` and written; a
     neutral message → no write.
  4. ADD a `memory_type` field (`preference | feedback | context | reference`) to the
     existing `AILongTermMemory` model (if it doesn't already have it) — migration required.
- **Do not touch:** `ai/engine/` public interface; the existing `ai/memory_api.py` read/forget paths.
- **Shallow-implementation trap:** ❌ classifying EVERY user message as a memory entry (the eval lane
  must return `none` for routine queries — over-learning fills memory with noise faster than it
  fills it with signal); ❌ writing to memory *during* the turn (must be post-turn, L3 no
  auto-mutation during reasoning); ❌ writing without a TTL (add `ttl_days=90` for preferences,
  7 for context entries — stale memory is worse than no memory).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_auto_memory.py -v --disable-warnings
  # Live proof: correct Pulse in a conversation → GET /ai/memory/facts/ shows the new entry
  # Entry has correct type, content, and ttl
  python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider | tail -5
  ```
- **North-star link:** Learning → expert over time.

---

### Phase G2 — Memory console UI

- **Goal:** a user-accessible Memory panel in the AIWorkspace (a new tab in the existing memory
  section alongside `AIMemoryTab`) shows all four memory tiers: working (current session),
  short-term (this session), long-term (per user, per instance), org memory (shared, admin only).
  Users can browse, edit, and delete entries. Admins can view and promote to org scope.
- **Why:** `AIMemoryTab` (Phase 23-B) shows episodic events. The gap is a **management console**
  that shows the classified memory entries (preference/feedback/context/reference), lets users
  verify what Pulse knows about them, and lets admins manage org-level memory seeds.
- **Domain:** Frontend Worker.
- **Files to read first:** `carbon-frontend/src/shell/AIMemoryTab.jsx` (existing episodic tab),
  `carbon-frontend/src/shell/AIWorkspace.jsx` (tab structure), `carbon-frontend/src/api/aiWorkspace.js`,
  `ai/memory_api.py` (existing read + forget endpoints),
  `.ai-toolkit/shared/ux-patterns.md` (list patterns).
- **Tasks:**
  1. ADD `carbon-frontend/src/shell/AIMemoryConsole.jsx` — tabbed panel with four sub-tabs:
     "Learned" (long-term facts, classified by type), "Episodes" (reuse existing `AIMemoryTab`
     component), "Session" (working + short-term, read-only), "Org" (admin-only, org memory seeds).
     Each entry row: type badge, content (truncated), domain, timestamp, delete button.
  2. ADD inline edit: clicking an entry body opens it for in-place editing (MUI TextField,
     Save/Cancel). PATCH request to a new `PATCH /carbon-api/ai/memory/facts/{pk}/` endpoint
     (backend: add to `memory_api.py`).
  3. ADD delete with 30s undo: delete sends `DELETE /carbon-api/ai/memory/facts/{pk}/` but shows
     a snackbar "Entry deleted · Undo" for 30s. Undo calls `POST .../restore/` (backend: add).
  4. ADD org memory tab (admin only, gated by `ai:manage_console` capability): reads from a new
     `GET /carbon-api/ai/memory/org/` endpoint that returns org-scoped memory seeds.
  5. ADD `carbon-frontend/src/__tests__/AIMemoryConsole.test.jsx`.
- **Do not touch:** `AIMemoryTab.jsx` (reuse, don't replace); `ai/engine/memory/` (never import from frontend).
- **Shallow-implementation trap:** ❌ allowing users to edit the memory type (users can edit content,
  only admins can change scope); ❌ showing all users' memory to non-admins (each user sees only
  their own entries); ❌ auto-refreshing on a timer instead of user-triggered (stale cache for
  memory is fine — refreshing on a timer wastes queries).
- **Acceptance gate:**
  ```bash
  cd carbon-frontend && npx vitest run src/__tests__/AIMemoryConsole.test.jsx
  npm run lint && npm run build
  # UX rubric: all 5 data states; edit/delete with undo; admin-only org tab; AA contrast
  # Manual: create a memory via G1 auto-write → appears in console → edit → delete → undo
  ```
- **North-star link:** Observable (#2 — users see what Pulse learned).

---

### Phase G3 — Checkpoint UI

- **Goal:** wire the existing `ConversationCheckpoint` backend (Sprint 20 W1-B) to a visible UI:
  a "⊕ Checkpoint" button in the conversation toolbar; a restore picker dropdown. The backend API
  already exists; the UI does not.
- **Why:** the model, migration (0017), and API endpoints (`/checkpoint/`, `/checkpoints/`,
  `/restore/`, `/fork/`) are all built (Sprint 20 W1-B). The gap is purely UI — users have no
  way to discover or invoke this capability.
- **Domain:** Frontend Worker.
- **Files to read first:** `carbon-frontend/src/shell/AIWorkspaceHeader.jsx`,
  `carbon-frontend/src/shell/AIConversationView.jsx`, `carbon-frontend/src/api/aiWorkspace.js`,
  `ai/workspace_api.py` (checkpoint/restore/fork endpoints), `docs/pulse/PULSE-UX.md §1.3`.
- **Tasks:**
  1. MODIFY `AIWorkspaceHeader.jsx` — add a "⊕" icon button labeled "Checkpoint" in the
     conversation header. On click → POST to `/checkpoint/` with an auto-generated name
     (`Sep 1 · 10:42`). Show a success snackbar "Checkpoint saved · {name}".
  2. ADD `carbon-frontend/src/shell/CheckpointPicker.jsx` — a dropdown/popover that lists the
     conversation's checkpoints (GET `/checkpoints/`), newest first. Each row: name, timestamp,
     note (if any). Two actions per row: "Restore" (reseed working context) and "Fork" (clone
     into new conversation). Shows a confirmation dialog before restore (destructive: overwrites
     current context).
  3. Wire `CheckpointPicker` into `AIWorkspaceHeader.jsx` — a second icon button ("↩ Restore")
     opens the picker.
  4. ADD `carbon-frontend/src/__tests__/CheckpointPicker.test.jsx`.
- **Do not touch:** the backend checkpoint/restore/fork implementation (it works); any engine code.
- **Shallow-implementation trap:** ❌ silently overwriting context on restore without a confirmation
  (must warn: "Restoring will replace your current context with the saved state. Continue?");
  ❌ auto-checkpointing on every message (creates noise; checkpoints are deliberate user actions);
  ❌ naming checkpoints with internal IDs instead of human timestamps.
- **Acceptance gate:**
  ```bash
  cd carbon-frontend && npx vitest run src/__tests__/CheckpointPicker.test.jsx
  npm run lint && npm run build
  # Manual: create checkpoint → list shows it → restore → context reseeded → fork → new conversation
  # UX rubric: confirmation before restore; keyboard-accessible; outcome-language copy
  ```
- **North-star link:** Trustworthy — user can always go back.

---

## WAVE H — Pulse Console (backend + frontend)

> Observability is not optional for an enterprise AI coworker. Wave H builds the admin destination
> where the platform's health, usage, skills, and changes are all visible in one room.

### Phase H1 — Audit trail model + API

- **Goal:** every Pulse action that touches data (tool call, consent decision, mutation, DQ run,
  memory write, skill promotion) is written to an `AIPulseAuditLog` model: immutable, append-only.
- **Why:** the `observability_api.py` reads from existing models. What's missing is a single,
  normalized audit table that captures *all AI-initiated state changes* with their consent trail,
  confidence, and cost. This is the compliance requirement for GOFSCO/KOC context.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/models/core.py` (existing models), `ai/plans_service.py` (consent
  patterns), `ai/engine/agent/plugins.py` (ToolPlugin), `accounts/capabilities.py`,
  `ai/engine/agent/guardrails.py` (mutation guards).
- **Tasks:**
  1. ADD `AIPulseAuditLog` to `ai/models/core.py` (+ migration): fields: `timestamp`, `user`,
     `instance`, `action_type` (choices: `tool_call | consent_approved | consent_declined |
     memory_write | memory_delete | skill_promoted | skill_demoted | mutation_applied`),
     `tool_id` (nullable), `domain`, `input_summary` (hashed + truncated), `output_summary`,
     `confidence`, `cost_cents`, `consent_token` (nullable), `scope_org_units`,
     `source` (`chat | plan | proactive | mcp_external`). No `update_or_delete` permissions.
  2. ADD `ai/audit_service.py` — `AuditService.log(...)` write-only helper; called from
     `ai/intelligence.py` after every tool call and consent decision.
  3. MODIFY `ai/intelligence.py` — call `AuditService.log()` after each tool call completion and
     after each RULE_21 consent resolution (approved or declined).
  4. ADD `GET /carbon-api/ai/audit/` (admin-only, CBAC `ai:view_audit`) — paginated, filterable
     by date range / action_type / user / domain. Returns non-PII-leaking summary fields.
  5. ADD `ai/tests/test_audit_trail.py` — test: tool call → row written; consent decline → row
     written; non-admin user gets 403 on the API.
- **Do not touch:** existing `observability_api.py` (it continues to work alongside); engine internals.
- **Shallow-implementation trap:** ❌ using a soft-delete or update on audit rows (must be immutable
  — use `db_table` + override manager to prevent `delete()`/`update()`); ❌ storing the full
  input/output (PII risk + size — store a SHA-256 hash of the input + a 200-char truncated
  summary); ❌ logging inside the engine (the audit write must happen in `ai/*.py`, not `ai/engine/`).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_audit_trail.py -v --disable-warnings
  python manage.py migrate --check   # migration applied cleanly
  # Live proof: perform a tool call → GET /carbon-api/ai/audit/ → row appears
  # DELETE request on an audit row → 405 Method Not Allowed
  ```
- **North-star link:** Observable + Compliant (#2); foundation for H3 audit viewer.

---

### Phase H2 — Pulse Console frontend

- **Goal:** a dedicated `/ai/console` route (admin-only, lazy-loaded) — the "Admin's room" from
  PULSE-UX §4. Dashboard + audit log viewer + skills pipeline + budget panel + tools panel.
- **Why:** `AIWorkspace` is the Operator's and Analyst's home. Admins need a separate destination
  where they see the AI's health, usage, skills in the pipeline, and every change it made.
  `observability_api.py`, `usage_service.py`, `audit_service.py` (H1) are the backend; the
  frontend room is the gap.
- **Domain:** Frontend Worker.
- **Files to read first:** `carbon-frontend/src/shell/AIWorkspace.jsx`,
  `carbon-frontend/src/shell/AIUsageTab.jsx` (reuse cost/usage components),
  `carbon-frontend/src/shell/AILearntTab.jsx` (reuse skills components),
  `carbon-frontend/src/shell/AITaskAuditCard.jsx` (reuse audit card pattern),
  `ai/observability_api.py`, `ai/audit_service.py` (H1).
- **Tasks:**
  1. ADD `carbon-frontend/src/pages/ai/PulseConsolePage.jsx` — gated by `ai:manage_console`
     capability. Layout: left nav with 5 sections: Overview / Audit / Skills / Budget / Tools.
  2. **Overview panel**: real-time SSE-driven mini-dashboard — queries today, insights delivered,
     skills pipeline counts (draft/gate/promoted/reused), avg confidence, LLM error rate. Uses
     existing `/ai/pulse/inventory/` endpoint.
  3. **Audit log viewer**: paginated table from `GET /carbon-api/ai/audit/` — columns: timestamp,
     user, action, domain, confidence, cost_cents. Filters: date range, action_type, domain.
     CSV export button. Click row → expand details.
  4. **Skills pipeline panel**: existing `AILearntTab` data + promote/demote actions (CBAC
     `ai:manage_console`). Shows `drafted → gate → promoted → reused (N times)` funnel.
  5. **Budget panel**: reuse `AIUsageTab` components for cost/token totals. Add budget threshold
     config (input fields + PATCH to `/ai/users/profile/` or admin settings endpoint).
  6. **Tools panel**: list all registered tools from `GET /carbon-api/ai/pulse/inventory/?panel=tools`
     — tool id, domain, last used, success/failure rate from audit log. Per-tool enable/disable
     toggle (admin only).
  7. ADD route to `carbon-frontend/src/App.jsx` (`/ai/console`, lazy, admin-guarded).
  8. ADD `carbon-frontend/src/__tests__/PulseConsolePage.test.jsx` — renders each section,
     gate check (non-admin → redirect).
- **Do not touch:** AIWorkspace (the Operator/Analyst home — separate route, separate audience).
- **Shallow-implementation trap:** ❌ reusing AIWorkspace layout (the Console is a different room
  with different density — use the standard `PageContainer` primitives, not the workspace chrome);
  ❌ showing PII in the audit viewer (user column shows username, not civil ID or contact info);
  ❌ real-time auto-refresh on the audit log table (it should be a manual refresh; only the
  Overview mini-dashboard is SSE-driven).
- **Acceptance gate:**
  ```bash
  cd carbon-frontend && npx vitest run src/__tests__/PulseConsolePage.test.jsx
  npm run lint && npm run build
  # Manual: admin navigates to /ai/console → all 5 sections load; non-admin → 403
  # Audit viewer shows H1 rows; CSV export works; skills funnel shows current state
  # UX rubric: 5 data states per section; no PII in audit view; keyboard-accessible
  bash .ai-toolkit/scripts/verify.sh all   # gate must stay green
  ```
- **North-star link:** Observable (#2 — the Admin's room is complete).

---

### Phase H3 — User-configurable anomaly watches

- **Goal:** users and admins can configure named KPI watches ("alert me if South Valley Scope 1
  > 200 tCO2e / month") that run async and deliver insights via the existing SSE notification
  channel. The engine already generates insights; what's missing is the user-configurable
  subscription + persistent watch model.
- **Why:** today the proactive loop fires on system-defined conditions. Users cannot say "watch
  THIS specific KPI for ME." Closing this gap completes the G2 proactivity arc with user ownership.
- **Domain:** Backend Worker + Frontend Worker (split across two sub-phases if large).
- **Files to read first:** `ai/engine/proactive/loop.py`, `ai/engine/proactive/trigger_evaluator.py`,
  `ai/engine/proactive/insight_generator.py` (`generate_daily_briefing`),
  `ai/insights_api.py`, `ai/insights_urls.py`, `ai/models/core.py`.
- **Tasks:**
  1. ADD `AIAnomalyWatch` model to `ai/models/core.py` (+ migration): fields: `user`, `instance`,
     `name`, `kpi_expression` (plain English — evaluated via the trigger evaluator), `threshold`,
     `comparison_window_days`, `recipients` (M2M to users), `enabled`, `last_fired_at`,
     `fire_count`.
  2. ADD CRUD API: `GET/POST /carbon-api/ai/watches/`, `PATCH/DELETE /carbon-api/ai/watches/{id}/`.
     Create/update require `ai:manage_insights` capability; list requires `ai:view_insights`.
  3. MODIFY `ai/engine/proactive/loop.py` — add a `run_user_watches(db, instance)` function that
     evaluates all enabled `AIAnomalyWatch` rows against the trigger evaluator and fires insights
     for any that cross their threshold. Call from the existing proactive loop schedule.
  4. ADD frontend: a "Watches" section in the Pulse Console (H2 Phase H3 is additive to H2) —
     a simple create/edit form: KPI name, threshold, window, recipients. Uses the new watch API.
  5. ADD `ai/tests/test_anomaly_watches.py` — test: watch configured → condition met → insight
     generated + `last_fired_at` updated.
- **Do not touch:** the existing system-defined proactive trigger paths; the insights SSE delivery.
- **Shallow-implementation trap:** ❌ evaluating watches on every request (must be on a schedule —
  every 15 minutes max, async, not blocking the request cycle); ❌ allowing arbitrary Python/SQL
  in `kpi_expression` (security hole — must be evaluated through the existing `trigger_evaluator`
  which uses the governed host API, not raw DB access).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_anomaly_watches.py -v --disable-warnings
  python manage.py migrate --check
  # Live proof: configure watch → manually invoke run_user_watches → insight appears in SSE stream
  bash .ai-toolkit/scripts/verify.sh all
  ```
- **North-star link:** Proactive (#7.2 in feature vision); user owns their watches.

---

# PULSE 0.4 — "Autonomous & Connected"

> **0.4 North-Star (3 items):**
> 1. **Connected** — the **platform** exposes every app's tools (Carbon, Nibras/GOFSCO, water, HR,
>    finance, …) via MCP to external clients; Pulse can call external MCP servers as first-class tools.
> 2. **Self-executing** — Pulse can run Python/pandas code against query results in a sandboxed
>    subprocess and render the output inline.
> 3. **Web-aware** — a `web_search` tool lets Pulse cite external sources (regulatory standards,
>    benchmarks) with provenance, always labeled "External · not from your data."

---

## WAVE I — External Connectivity

### Phase I1 — Platform as MCP server — every app, not just Carbon (HTTP endpoints)

- **Goal:** the platform exposes **each registered app's** domain tools via MCP 2026-07-28
  compliant HTTP endpoints. One MCP server per `app_identifier` (Carbon `emissions`, Nibras/GOFSCO
  `people`, `water`, `hr`, `finance`, `customer`, `data_product`, `mdm`, `admin`), built from the
  same registry `E2` produces. An external client (VS Code Copilot, another AI agent) discovers
  *the app servers it's allowed to see* and calls them with a valid JWT.
- **Why:** `engine/agent/mcp_client.py` exists for Pulse consuming external servers. The inverse —
  the platform being a server — is the gap. `listDomainManifests` already enumerates apps
  (`GET /carbon-api/ai/apps/`); I1 turns that manifest list into MCP servers. Enables VS Code
  Copilot to call `dq.list_rules` against Carbon **and** Nibras' people tools against GOFSCO data,
  each CBAC-scoped to the caller.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/engine/agent/mcp_client.py` (client pattern to mirror),
  `ai/adapter/types.py` (ToolDef from E2), `ai/domain_protocol.py` (registry + manifests),
  `ai/ops_api.py` (`listDomainManifests`), `accounts/capabilities.py`,
  `ai/engine/agent/guardrails.py` (mutation guards).
- **Tasks:**
  1. ADD `ai/mcp/` package: `__init__.py`, `server_views.py`, `server_urls.py`.
  2. ADD `GET /carbon-api/mcp/` — discovery: returns the list of MCP servers for the
     authenticated user, **one per `app_identifier` in the domain registry** (CBAC-filtered: only
     apps whose `view_capability` the user has). Response:
     `{servers: [{id, app_identifier, name, description, tools_url}]}`.
  3. ADD `GET /carbon-api/mcp/{app_identifier}/tools/` — list tools for that app's domain server
     (CBAC-filtered, RULE_20: only the user's accessible tools *for that app*).
  4. ADD `POST /carbon-api/mcp/{app_identifier}/tools/call/` — execute a tool call. Validates:
     JWT auth, capability for the tool, `Scope` from the user's profile, consent token for
     mutations (RULE_21). All calls logged to `AIPulseAuditLog` with `source=mcp_external` **and
     the app's `app_identifier`**.
  5. ADD `ai/tests/test_mcp_server.py` — test: discovery returns one server per registered app;
     a GOFSCO `people` user sees `people` but NOT `emissions`; tool call without capability → 403;
     mutation without consent token → 428; PII-bearing `people` tool output is never returned
     without the I5 redaction applied.
- **Shallow-implementation trap:** ❌ hardcoding a single `carbon` server and skipping the domain
  registry (Nibras/GOFSCO and other apps would then silently not appear); ❌ returning all tools
  to all users regardless of CBAC (discovery is the first CBAC gate — filter by per-app capability);
  ❌ skipping RULE_21 for mutations called via MCP (external callers must provide a consent token
  for any `is_mutation=True` tool — no exceptions).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_mcp_server.py -v --disable-warnings
  # Live: curl discovery with an emissions user → only emissions server
  # curl with a GOFSCO people user → only people server; curl admin → all app servers
  bash .ai-toolkit/scripts/verify.sh all
  ```

---

### Phase I2 — Code execution sandbox

- **Goal:** Pulse can generate Python/pandas code to analyze a query result and execute it in a
  sandboxed subprocess (10s timeout, read-only data access, no network, no file write). Output
  is an inline chart image, a computed table, or a scalar — rendered in the answer bubble.
- **Why:** "Plot the South Valley emissions trend for the last 12 months" is impossible today. GPT-4
  and Claude Code have this; Pulse doesn't. The gap is a code interpreter over Carbon's data.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/engine/agent/plugins.py` (ToolPlugin ABC),
  `ai/engine/agent/tools.py`, `ai/engine/agent/guardrails.py` (mutation guard — code executor
  must be read-only), `ai/adapter/types.py` (ToolDef).
- **Tasks:**
  1. ADD `ai/code_sandbox.py` — `CodeSandbox.execute(code: str, data: dict) → SandboxResult`:
     spawns a restricted subprocess (`subprocess.run` with `timeout=10`, no network via
     `os.environ` overrides, no file write via chroot or restrictions). Passes `data` as JSON
     via stdin. Captures stdout, stderr, and a base64-encoded PNG if `matplotlib` was used.
     Returns `{stdout, error, image_b64, table_rows}`.
  2. ADD `CodeExecuteTool(ToolPlugin)` registered as `code.execute` — calls `CodeSandbox.execute`
     with the query result from the current turn as `data`. `is_mutation=False` (read-only).
     Requires `ai:code_execute` capability (new capability key in `capabilities.py`).
  3. MODIFY `AIMessageBubble.jsx` (frontend) — if response payload contains `code_result.image_b64`,
     render an `<img>` tag (base64 PNG); if `code_result.table_rows`, render as a MUI DataGrid.
     Show the code in a collapsed `<PlanningHeader>`-style "Code used" section.
  4. ADD `ai/tests/test_code_sandbox.py` — test: valid pandas code → returns table; timeout → error;
     import os; os.system('rm -rf /') → blocked; network call → blocked.
- **Shallow-implementation trap:** ❌ running the code in the main Django process (must be a
  subprocess with restrictions); ❌ passing the full DB connection string to the subprocess
  (must pass only the pre-fetched result JSON, never DB credentials).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_code_sandbox.py -v --disable-warnings
  # Security: confirm network + file-write are blocked in subprocess
  # Manual: "plot emissions trend" → chart renders inline in answer bubble
  ```

---

### Phase I3 — Web search tool

- **Goal:** a first-class `web_search(query, max_results=5)` tool registered in the domain catalog
  with outcome-labeled provenance. Results are always labeled "External · not from your data" in
  the Inspector. Used for regulatory standards, industry benchmarks, KOC spec lookups.
- **Why:** Pulse should be able to say "The GHG Protocol defines Scope 3 category 4 as…" citing
  the actual standard — not relying on training data. The `mcp_client.py` can wire to an external
  Brave/Bing MCP server, but there is no built-in `web_search` tool with Carbon-native provenance
  labeling.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/engine/agent/mcp_client.py` (how external tools are called),
  `ai/engine/agent/plugins.py` (ToolPlugin), `ai/engine/agent/tools.py`,
  `ai/adapter/types.py` (ToolDef, ProviderSource).
- **Tasks:**
  1. ADD `WebSearchTool(ToolPlugin)` — `name="web_search"`, calls the configured search provider
     (Brave API key from instance config, fallback to DuckDuckGo HTML scrape). Returns `{results:
     [{title, url, snippet, retrieved_at}]}`. Always tags the result with
     `source="external_web"` in provenance. Requires `ai:web_search` capability.
  2. ADD provenance enforcement in `ai/intelligence.py` — any answer citing a `web_search` result
     must include the `[Ext]` provenance tag; the serializer must never strip it (RULE_23 inverse:
     external sources must be labeled, not silenced).
  3. MODIFY the Inspector panel (frontend) — `ExternalSourceBadge` label shown on any provenance
     entry with `source=external_web`: "External · Brave search · {retrieved_at}". Use the
     `AIGeneratedBadge` pattern (D3) as a model.
  4. ADD `ai/tests/test_web_search_tool.py` — mock the external API; test result shape; test that
     provenance tag is set; test that `ai:web_search` capability gates access.
- **Shallow-implementation trap:** ❌ returning web results without provenance (the user must always
  know a result is external — mislabeling is a RULE_23 violation); ❌ caching web results in long-
  term memory (external content changes — TTL of 24h max in short-term memory only).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_web_search_tool.py -v --disable-warnings
  # Manual: "What does GHG Protocol say about Scope 3 cat 4?" → answer cites external source
  # Inspector shows "External · Brave search" label; no mislabeling
  bash .ai-toolkit/scripts/verify.sh all
  ```

---

### Phase I4 — Subagent dispatch UI

- **Goal:** users can dispatch a named subagent for a complex task ("audit all 200 DQ rules and
  fix P0 violations"). The subagent infrastructure already exists (guardrails, is_worker, mutation
  block). The gap is the user-facing dispatch flow and aggregated result presentation.
- **Why:** the worker subagent infrastructure was built for internal engine use. Users cannot
  initiate a subagent task from the conversation and watch its coordinated progress.
- **Domain:** Frontend Worker + Backend Worker (small).
- **Files to read first:** `ai/engine/agent/guardrails.py` (is_worker + mutation block),
  `ai/engine/agent/workers.py` (worker dispatch), `ai/plans_api.py` (plan run with SSE),
  `carbon-frontend/src/shell/AITaskPanel.jsx` (existing task panel),
  `carbon-frontend/src/components/OperationProgress.jsx` (D1 progress component).
- **Tasks:**
  1. ADD backend `ai/subagent_service.py` — wraps the existing worker dispatch with a
     named subagent model: `AISubagent(parent_conversation, name, scope_restriction, tool_budget,
     status, result_summary)`. The subagent runs as a plan with `is_worker=True`.
  2. ADD API: `POST /carbon-api/ai/conversations/{id}/subagents/` (dispatches),
     `GET /carbon-api/ai/conversations/{id}/subagents/{sub_id}/` (status + result).
  3. MODIFY `OperationProgress.jsx` — add a `subagents` sub-list: when a parent plan dispatches
     subagents, their individual progress frames appear as nested items under the parent task.
  4. ADD `carbon-frontend/src/shell/SubagentResultCard.jsx` — when a subagent completes, renders
     its result summary in the conversation as a distinct card with the subagent's name and scope.
  5. ADD `ai/tests/test_subagent_dispatch.py` — test: dispatch → subagent created with
     is_worker=True → mutation tools blocked → result aggregated.
- **Shallow-implementation trap:** ❌ giving subagents access to mutation tools (guardrails.py
  already blocks this — confirm it holds under the new dispatch path); ❌ running all subagents
  synchronously (must be async with individual SSE progress frames).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_subagent_dispatch.py -v --disable-warnings
  # Manual: dispatch subagent → nested progress in OperationProgress → result card in conversation
  bash .ai-toolkit/scripts/verify.sh all
  ```

---

### Phase I5 — PII server-side gate

- **Goal:** memory writes, audit log entries, and SSE frames that contain PII (names, civil IDs,
  passport numbers, email addresses) are detected and either masked or blocked before persistence.
  Mirrors the `logger.js` client-side redaction (D4) on the server.
- **Why:** `logger.js` redacts `{token,secret,password,api_key}` keys client-side. On the server,
  memory entries derived from People data (certifications, employee names) may contain civil IDs
  or passport numbers. These must never be stored in plaintext in memory tables.
- **Domain:** Backend Worker.
- **Files to read first:** `ai/engine/cognition/auto_memory.py` (G1), `ai/audit_service.py` (H1),
  `ai/insights_api.py` (SSE delivery), `backend/people/models.py` (PII field names).
- **Tasks:**
  1. ADD `ai/pii_guard.py` — `PIIGuard.redact(text: str) → str`: pattern-based redaction (civil ID
     format for Kuwait: 12 digits; passport: letter + 8 digits; email regex). Returns text with
     matched patterns replaced by `[REDACTED:{type}]`. Tests: each pattern redacted; non-PII pass-through.
  2. MODIFY `auto_memory.py` (G1) — pass extracted memory content through `PIIGuard.redact()`
     before writing.
  3. MODIFY `audit_service.py` (H1) — pass `output_summary` through `PIIGuard.redact()` before
     writing to `AIPulseAuditLog`.
  4. MODIFY `insights_api.py` — pass `narrative` field through `PIIGuard.redact()` before
     delivering over SSE.
  5. ADD `ai/tests/test_pii_guard.py` — test: civil ID, passport, email → redacted; normal text
     → unchanged; nested JSON → redacted at key level.
- **Shallow-implementation trap:** ❌ blocking the write instead of redacting (GDPR requires the
  right to erasure but not the right to block recording — redact, don't drop); ❌ using a single
  catch-all regex that redacts numeric sequences (phone numbers → `[REDACTED]` is fine, but
  emission values like 142 should NOT be redacted).
- **Acceptance gate:**
  ```bash
  python -m pytest ai/tests/test_pii_guard.py -v --disable-warnings
  # Live: write a memory entry containing a civil ID → stored value is [REDACTED:civil_id]
  # Audit entry for a people tool call → output_summary has no civil ID patterns
  bash .ai-toolkit/scripts/verify.sh all
  ```

---

## Sequencing summary

```
PULSE 0.3 — Expert & Observable (Waves E–H, 9 phases)
  E1 → E2 → E3          Expert Foundation (backend, no visible UX)
  F1 → F2 → F3          Rich Conversation (frontend, uses E1/E2 output)
  G1 → G2 → G3          Memory + Console (backend then frontend)
  H1 → H2 → H3          Pulse Console (backend model first, then UI, then watches)

  Critical path: E1 → E2 must precede F1 (entity chips need typed entity refs from E2)
                 E1 must precede G1 (auto-memory uses SessionContext from the adapter)
                 H1 must precede H2 (audit viewer needs the audit model)

PULSE 0.4 — Autonomous & Connected (Wave I, 5 phases, independent of each other)
  I1 Carbon MCP server      — unblocks external integration
  I2 Code execution sandbox — unblocks data analysis
  I3 Web search tool        — unblocks regulatory grounding
  I4 Subagent dispatch UI   — unblocks coordinated agent tasks
  I5 PII server-side gate   — compliance hardening
```

## Gap table: post-0.3/0.4 state

| Capability | 0.2 State | 0.3 Target | 0.4 Target |
|------------|-----------|------------|------------|
| WorldModel + ToolCatalog seam | ❌ (implicit in prompt) | ✅ E1/E2 | — |
| Domain tool catalog (typed, CBAC) | ❌ | ✅ E2 | — |
| Cross-domain synthesis | ❌ | ✅ E3 | — |
| Entity chips inline | ❌ | ✅ F1 | — |
| @-mention + context chips | ❌ | ✅ F2 | — |
| Planning header pill | ❌ | ✅ F3 | — |
| Auto-memory (self-learning) | ❌ | ✅ G1 | — |
| Memory console UI | Partial (AIMemoryTab) | ✅ G2 | — |
| Checkpoint UI | ❌ (API exists) | ✅ G3 | — |
| Audit trail model | ❌ | ✅ H1 | — |
| Pulse Console (admin room) | ❌ | ✅ H2 | — |
| User-configurable anomaly watches | ❌ | ✅ H3 | — |
| Carbon as MCP server | ❌ | — | ✅ I1 |
| Code execution sandbox | ❌ | — | ✅ I2 |
| Web search tool (built-in) | ❌ | — | ✅ I3 |
| Subagent dispatch UI | ❌ (infra exists) | — | ✅ I4 |
| PII server-side gate | Partial (client-side) | — | ✅ I5 |
| Mermaid + rich markdown | ✅ | — | — |
| Plans + consent + durable execution | ✅ | — | — |
| Checkpoints backend | ✅ | — | — |
| Daily briefing (engine) | ✅ | — | — |
| MCP client (outbound) | ✅ | — | — |
| Budget tracking | ✅ | — | — |
| Memory API (read/forget) | ✅ | — | — |
| Usage service + cost | ✅ | — | — |
| Confidence + provenance (D3/C2) | ✅ | — | — |
| Presence + drafts + progress (D4/D1) | ✅ | — | — |

## North-star sentence for Pulse 0.3+

> **Pulse is the most capable enterprise AI coworker in any data-trust platform: it knows
> Carbon's entities and rules through a typed expert seam, every action it takes is observable in
> an audit trail, every answer is traceable to real records, and it learns from every correction —
> while Copilot and Claude Code will never know what a Kuwaitization ratio, a DQ pass rate, or an
> EOSI service history means.**

Those two things — domain-native intelligence and an immutable audit chain — are the moat.
Waves E through I are the infrastructure to make that moat impenetrable.
