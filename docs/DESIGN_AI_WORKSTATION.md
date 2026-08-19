# DESIGN — AI Workstation (Agent / MCP / Tool surface + context lifecycle)

**Status:** Ratified design — dispatch contracts live in `TASKS.md` under
**AI WORKSTATION TRACK** (Phase W1-A → W2-C).
**Owner:** Master Architect (Carbon).
**Scope:** Turn the existing Pulse AI Workspace from a *chat pane* into a
*workstation*: user can run agent actions / MCP commands / tools with
controllable verbosity and clean abort, manage conversation context
(clear / restore / checkpoint / fork), collapse past chats, and scroll large
content. All user-facing copy = outcomes, never internals (RULE_23).

---

## 1. Completion audit — what already exists (backend engine)

The engine under `backend/ai/engine/` already implements the full cognitive
stack. The table below is the truth for "are agents/mcp/tools/rag/memory/
decay/learning/graphs/growth/scopes done?".

| Capability | Where it lives | Status |
|---|---|---|
| **Agents** | `engine/agent/registry.py` (AgentRegistry: register/get/can_handoff/get_workers_for), `models/core.py:384 Agent`, `AgentHandoff` | ✅ Implemented + durable (DjangoStore). 5 seeded agents. Handoffs = declared edges only (ADR-001). |
| **Agent execution + confirm** | `engine/agent/executor.py` `HostAPIExecutor` (`requires_confirmation`, `create_pending_execution`, `confirm_execution`, `decline_execution`, `call_api_direct`) | ✅ Implemented. Confirmation gating = RULE_21 (no auto-mutation). |
| **Tools** | `engine/agent/tools.py`, `engine/agent/registry.py` (tool_set), `models/core.py:188 ToolExecution` | ✅ Implemented + durable execution log. |
| **MCP** | `engine/agent/mcp_client.py` (`MCPToolRegistry.connect_all`, `MCPTool`, `MCPServer`) | ✅ Implemented (lazy `mcp` import, graceful degrade on empty `MCP_SERVERS`). |
| **RAG / context** | `ai/context_assembler.py` (T2 history / T2b summary / T3 KG / T4 memory), `engine/ingestion/` | ✅ Implemented. Four-tier assembly closed end-to-end (Phase 6-T3). |
| **Memory** | `engine/memory/` (episodic / long_term / short_term / manager), `ai/memory_api.py` | ✅ Implemented + durable. |
| **Memory decay / compaction** | `engine/memory/compactor.py`, `engine/cognition/distill/decay.py` | ✅ Implemented (de-SQLAlchemy'd in Pulse Phase D). |
| **Learning** | `ai/learning.py` + `ai/learning_api.py` (Sprint 10 feedback flywheel → `KgFeedbackRecord` + `LongTermMemory`) | ✅ Implemented. Idempotent via `AIMessage.learned_at`. |
| **Knowledge graph** | `engine/knowledge_graph/` (cluster migrated), `ai/graph_api.py`, D3 viz panel | ✅ Implemented. Schema KG bootstrapped + retrieved into every turn. |
| **Growth / proactive** | `engine/proactive/` (loop, insight_generator, delivery, suppression, trigger_*) | ✅ Implemented + durable (`list_proactive_suggestions`, suggestion rail). |
| **Scopes / guards** | `ai/guards.py` (ScopeGuard/AccessGuard/DataIsolationGuard/MutationGuard/RateLimiter), `ai/access_manifest.py`, `accounts/ai_scoping.py` | ✅ Implemented. CBAC-partitioned store + read/write rails. |
| **Stream + abort** | `ai/generation_registry.py` (per-conversation `threading.Event`), `ai/engine_runtime.dispatch_task_stream`, `workspace_api` SSE | ✅ Implemented for **chat** streaming; abort primitive exists but is NOT threaded through the agent/tool loop yet. |

**Verdict:** the *engine* is done for all nine domains. What is **missing** is
the **user-facing workstation surface** — there is currently no way to (a)
invoke an agent action / MCP command / tool directly and watch its verbosity /
streamed output with a clean abort button, (b) clear/restore/checkpoint/fork a
conversation's context, (c) collapse past chats, or (d) scroll large output
properly. The 19-panel `ai-admin` console exposes a *read-only inventory* of
these objects (Agents/MCP/Tools panels are `PulseDataPanel` list views), but
that is admin inventory, not an interactive execution surface.

---

## 2. Deep research — patterns from top AI systems

Synthesised from VS Code Copilot Chat (agent mode), Cursor, Windsurf,
JetBrains AI Assistant, Cline / Roo Code, Continue.dev, Aider, OpenHands
(Devin-style "command center"), and Palantir / Ataccama (enterprise).

### 2.1 Activity bar / navigation
- **VS Code Copilot / JetBrains**: *one icon per conceptual surface*, not one
  per object. Copilot groups all chat sessions behind a single icon; JetBrains
  uses a few top-level icons + flyouts.
- **Cursor**: one icon per surface (Chat / Composer / Agent), internal tabs for
  sub-views.
- **Windsurf**: single "Cascades" icon, everything else inside.
- **Cline / Roo Code / OpenHands**: a dedicated **agent/tool activity** surface
  that is *always visible during a run* — a left "task list" + a collapsible
  "tool call log" timeline.
- **Takeaway for Carbon**: the existing 7-icon Pulse bar (Sessions / Context /
  Investigate / Artifacts / Usage / Memory / Settings) already follows the
  "one icon per surface" rule. We **do not** add four flat icons for
  Agents/MCP/Tools/Logs. We add **one** "Agent" surface icon whose internal
  `<Tabs>` are *Agents | MCP | Tools | Logs* (RULE_17, matches the grouped
  Memory surface already shipped in Phase 23-C).

### 2.2 Running agent actions / tools / MCP with verbosity + abort
- **OpenHands / Cline**: every tool call renders as a *collapsible card*
  (icon + name + status chip + expandable JSON). Verbosity = a 3-state control
  (Concise / Normal / Full) that only changes *how much* of each tool call's
  input/output is expanded by default.
- **Cursor / Copilot agent mode**: streaming tool events arrive as discrete
  frames (`tool_start` → `tool_arg` → `tool_result` → `tool_end`) and the UI
  appends them to a timeline *without* re-rendering the whole transcript.
- **Abort**: all systems use an idempotent **Stop** button that (1) sends a
  cancel signal, (2) immediately flips the run to a `stopped` state, (3) marks
  any already-completed tool side-effects as *done* (never half-rolled-back),
  and (4) surfaces "Stopped by user" — not an error. Abort must never leave the
  conversation stuck in `working`.
- **Takeaway**: reuse `generation_registry.cancel(conversation_id)` (already
  exists) and thread the event into the agent/tool loop. Emit tool frames over
  the *existing* SSE channel (`streamJsonPost` already consumes it).

### 2.3 Context clear / restore / checkpoint / fork
- **Cursor "Restore" / Windsurf**: the context bundle (memory + summaries +
  history + KG) is treated as a *checkpoint*: named, snapshot-able, restorable.
  "Fork from here" = clone the conversation seeded from a checkpoint at a given
  message boundary (Cursor's "Fork conversation" is the canonical precedent).
- **Clear context** (Copilot "New chat" / Cline "Reset"): clears the *working
  context* (history / summary / KG / memory injection) but **never** deletes the
  durable conversation row or learned facts.
- **Takeaway**: `context_snapshot_json` (already persisted on `AIMessage`) is
  the natural checkpoint payload. Backend needs a `ConversationCheckpoint`
  model + `checkpoint`/`restore`/`fork`/`clear-context` endpoints.

### 2.4 Past chats accordion + scroll containment
- **VS Code Copilot sessions / Slack threads**: past sessions collapse into an
  accordion grouped by time (Today / Yesterday / 7d / Older) — the *group
  header* toggles, individual items expand inline. Carbon's Phase 23 already
  ships grouped sections; the gap is the *collapsible accordion* behaviour and
  virtualization for long lists.
- **Scrolls**: Cursor / Copilot give the *message list* its own vertical
  scroll container (independent of the input bar and header); wide output
  (JSON, terminal, tables) gets `overflow: auto` on the X axis inside its
  card, never widening the page. `LongContent.jsx` already exists as the
  starting point.

### 2.5 Clustered output — the Copilot / Cursor / Cline task-and-tool model

Top systems never render a run as a flat wall of text. They render it as a
**two-level collapsible cluster**, and Carbon adopts exactly this shape:

- **L1 — Turn cluster** (outer). One user action = one collapsible *task*
  group. Copilot shows a single summary line — "Working…" then
  "Finished · 3 tools" — and the whole group collapses to that one line.
  Cline / OpenHands show the same as a left "task list".
- **L2 — Step cluster** (inner). Each tool / MCP command / agent action = one
  collapsible *card*. Header = status icon + name + status chip; body =
  expandable args (input) and result (output), both redacted.

**Frame protocol** (backend emits, frontend nests — the contract for W1-A):

```
turn_start   { turn_id, label, verbosity }
tool_start   { turn_id, step_id, tool, category }   # category ∈ agent|mcp|tool
tool_arg     { step_id, args }                       # full verbosity only
tool_result  { step_id, result }                     # partial → streaming
tool_end     { step_id, status }                     # completed|failed|stopped
turn_end     { turn_id, status, summary }
```

**Clustering rules:**
1. `concise` verbosity → turn header + step *headers* only (status chips);
   args/results collapsed by default but still expandable per-card.
2. `full` verbosity → step bodies auto-expanded.
3. Each card toggles independently; the turn header toggles the whole group.
4. Failed/stopped steps surface the error or "Stopped by you" *inside the
   card body* — never a red full-width banner (Copilot behaviour).
5. Wide result payloads (JSON / terminal / table) scroll on X inside the card
   (shared with the §2.4 scroll-containment rule).
6. Collapse state is per-run and in-memory only (not localStorage) — a new run
   starts fresh; the durable `ToolExecution` rows are the log of record.

---

## 3. Phase map

| Phase | Worker | Delivers | Depends on |
|---|---|---|---|
| **W1-A** | backend | Agent/Tool/MCP execution seam + clustered streamed events (`turn_*`/`tool_*` frames keyed by `turn_id`/`step_id`) + verbosity + clean abort | chat SSE + `generation_registry` |
| **W1-B** | backend | `ConversationCheckpoint` + `checkpoint`/`restore`/`fork`/`clear-context` endpoints | W1-A (abort seam reused by fork) |
| **W2-A** | frontend | Agent surface icon (Agents/MCP/Tools/Logs tabs) + clustered execution timeline (turn cluster → collapsible step cards) + verbosity + abort + logs | W1-A |
| **W2-B** | frontend | Accordion past-chats + scroll containment (vertical per-pane, horizontal for wide output) | (independent) |
| **W2-C** | frontend | Context clear/restore + checkpoint/fork UI | W1-B |

Dispatch order: **W1-A → W2-A** (execution) and **W1-B → W2-C** (context) can be
parallel; **W2-B** is independent frontend polish and may run anytime.

---

## 4. Non-negotiables (inherit from toolkit rules)

- RULE_18 AI contract binding — new endpoints go under `/carbon-api/ai/…`,
  `IsAuthenticated` + CBAC (`ai:view_console` for reads; `ai:manage_console`
  for mutations), GET-only where read-only.
- RULE_21 NO AUTO-MUTATION — agent/tool actions that write Carbon state stay
  `requires_confirmation=True`; the surface renders a confirm gate, never a
  silent write.
- RULE_23 NO IMPLEMENTATION LEAKAGE — copy says "Running check…", "Tool
  finished", never "MCP stdio session", "HostAPIExecutor", or engine class names.
- RULE_17 tabs-in-localStorage; RULE_8 theme tokens only; RULE_10 apiFetch
  (the existing SSE `streamJsonPost` helper is the approved stream seam).
- Output is **clustered**, never a flat wall (Copilot/Cursor/Cline): a turn
  cluster collapses to a summary line; each step is its own collapsible card
  with a status chip. Failed/stopped state lives inside the card, not a banner.
- No new Django apps (ADR-0008); no learning inside the engine (RULE_6).
- Backend and frontend are **never** combined into one phase.
