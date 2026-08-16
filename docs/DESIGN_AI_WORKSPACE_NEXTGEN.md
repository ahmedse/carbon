# DESIGN — Carbon AI Workspace, Next-Generation (v3)

**Status:** Active design — Phases 0–2 backend implemented (Sprints 13–16); Phases 3–5 pending
**Author:** Master Architect
**Date:** 2026-08-16 (v3 — comprehensive UX/workflow/phased expansion)
**Audience:** Backend Worker, Frontend Worker, QA Validator, DevOps Worker
**Supersedes:** v2 (2026-08-15) — same architecture decisions kept; extended with full UX/IA/workflow spec
**Binding contract reference:** `.ai-toolkit/shared/ai-contract.md` (v2.0.0)

---

## Changelog (v3)

| What changed | Why |
|---|---|
| Added §8 — Information Architecture (fixed tabs, thread rail, IA rules) | Prevent UI tab explosion; establish stable wayfinding |
| Added §9 — UX Principles and Interaction Contracts | First-principles for every worker to follow before touching the shell |
| Added §10 — Workflow Choreography (all 8 conversation types) | Gaps between phases were leaving workflows unspecified |
| Added §11 — Thread Lifecycle State Machine (full FSM) | Workers need a canonical reference for every state and transition |
| Added §12 — Context Transparency & Provenance UX | "Why this answer" is not optional in enterprise software |
| Added §13 — Error Taxonomy & Recovery Patterns | Error handling was scattered; centralize to one reference |
| Added §14 — Accessibility & Keyboard Contract | WCAG AA is baseline; keyboard contract unambiguous |
| Added §15 — Metrics & Observability Contract | Instrumentation spec so UX decisions are data-driven |
| Replaced §9 Phased Roadmap → §16 | Expanded with explicit acceptance criteria, file lists, gates |
| Old §10–§11 renumbered → §17–§18 | No content change |

---

## 0. TL;DR

The current AI Workspace is a **correctly-architected but thin** implementation. The
backend seam (`CarbonIntelligence` → `GuardChain` → stateless engine) is professional
and must be **kept**. What is naive is the *conversation-management layer*: sessions
are not durably manageable (close-tab is client-side only), messages are unpaginated
and single-shot (no edit/regenerate/interrupt), non-chat responses use 2s polling, and
the tab UI is index-based and fragile.

This document specifies a **hybrid** evolution:

1. **Keep** the backend seam: `CarbonIntelligence`, `GuardChain`, `ai/engine/`, models
   `AIConversation`/`AIMessage`, and the REST/SSE API surface (extended).
2. **Rewrite** the frontend shell (`AIWorkspace.jsx`, `AIConversationTabs.jsx`,
   `AIConversationView.jsx`, `AIMessageBubble.jsx`) around durable, manageable,
   budgeted, interruptible sessions.

The reference model is synthesized from **VS Code Copilot** (session management,
queue/steer/stop, checkpoints, context mentions), **Cursor** (composer, multi-file diff
trail), **Claude Code / Anthropic** (memory tiers, budget discipline, "start simple"),
and **ChatGPT** (thread management, projects) — weighted equally.

---

## 1. Current-State Audit (honest)

### 1.1 What is already right (keep, do not re-architect)

| Asset | Verdict |
|-------|---------|
| `CarbonIntelligence` single entry point (AI Contract §0.6) | ✅ Correct |
| `GuardChain` (Scope/Access/Isolation/Mutation/RateLimit) | ✅ Correct |
| Conversation FSM `pending→working→needs_input→completed/failed` | ✅ Professional |
| SSE via `fetch`+`ReadableStream` (POST-capable, not `EventSource`) | ✅ Correct |
| Fail-visible: `except → _save_assistant_message(status="failed")`, never stuck in `working` | ✅ Correct |
| Feedback flywheel `outcome → learn_from_message → KgFeedbackRecord` | ✅ Real learning loop |
| `WorkspaceContext` spec (Contract §11) as a structured, auditable alternative to screenshots | ✅ Right shape |
| Scope frozen at create, re-built fresh at send | ✅ Correct security posture |

### 1.2 The gaps (naive dimensions)

| # | Dimension | Gap | Severity |
|---|-----------|-----|----------|
| G1 | Session lifecycle | Close-tab is client-side only (`setConversations(prev.filter…)`); no rename/archive/pin/delete/search; sessions vanish from the tab bar on reload | **CRITICAL** |
| G2 | Message management | `getConversation` returns ALL messages; no pagination, no edit/regenerate, no per-message token/cost | HIGH |
| G3 | Streaming | Only `chat` streams; `dq_validate`/`dq_suggest`/`nl_query`/`anomaly` use 2s polling | HIGH |
| G4 | Interrupt | Input disabled while `working`; no stop/queue/steer (VS Code Copilot's core UX) | HIGH |
| G5 | Context | Full history sent every turn; no token budgeting, no compaction/summary, no RAG/KG grounding feed | HIGH |
| G6 | Tabs | `value={conversations.indexOf(conv)}` (index-based); 20-char truncation; no keyboard nav/grouping/auto-title | MEDIUM |
| G7 | Follow-up chips | Rendered `clickable` with **no `onClick`** — inert | BUG |
| G8 | Enterprise | No per-turn cost attribution to a conversation, no transcript export, no provenance surface, no shared conversations | MEDIUM |

### 1.3 Files under change

```
backend/ai/models/workspace.py        # extend AIConversation + AIMessage (+ new tables)
backend/ai/serializers.py             # extend request/response shapes
backend/ai/workspace_api.py           # new endpoints (lifecycle, pagination, stop, export)
backend/ai/intelligence.py            # ContextAssembler, compaction, generation registry
backend/ai/engine_runtime.py          # progress-stream + cancellation for non-chat tasks
backend/ai/providers/pulse.py         # chat_stream → generalized stream (progress frames)
carbon-frontend/src/api/aiWorkspace.js  # new API functions
carbon-frontend/src/shell/AIWorkspace.jsx       # REWRITE (durable session manager)
carbon-frontend/src/shell/AIConversationView.jsx # REWRITE (stream all, interrupt, paginate)
carbon-frontend/src/shell/AIConversationTabs.jsx # REWRITE (id-based, keyboard, groups)
carbon-frontend/src/shell/AIMessageBubble.jsx    # fix follow-ups, usage chips, checkpoints
carbon-frontend/src/shell/AIInputBar.jsx         # context mentions, queue/steer/stop
```

---

## 2. Design Principles (from SOTA synthesis)

1. **A session is a durable, first-class object** — not a tab. It persists, is
   rename-able, archivable, pinnable, searchable, and exportable. (Copilot + ChatGPT)
2. **The user never loses agency mid-turn** — queue, steer, or stop. Blocking input is
   an anti-pattern. (Copilot's send-dropdown)
3. **Context is explicit, budgeted, and tiered** — working → rolling summary →
   retrieval → long-term memory. Nothing is sent "because it's in the DB". (Anthropic
   "building effective agents", MemGPT/Letta memory tiers)
4. **Stream what is genuinely streamable; show progress for what is not.** Token deltas
   for chat/report; structured progress events for structured outputs (DQ/NL/anomaly).
   Never fake token streaming for JSON.
5. **Transparency is a feature** — show model, token count, cost, latency per turn.
6. **Start simple, add complexity only when it earns its cost.** Every phase below is
   independently shippable and gated.
7. **Carbon owns state; the engine stays stateless.** All persistence in Django models;
   engine remains stateless reasoning (AI Contract §0.4).

---

## 3. Target Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  FRONTEND SHELL (rewritten)                                           │
│                                                                       │
│  AIWorkspace (session manager)                                        │
│   ├─ SessionList (virtualized sidebar: pinned / active / archived)    │
│   ├─ AIConversationTabs (id-based, keyboard, grouped)                 │
│   ├─ AIConversationView (stream all, interrupt, paginate)             │
│   │    ├─ AIMessageBubble (usage chip, checkpoint, wired follow-ups)  │
│   │    └─ AIInputBar (mentions #table #rule #field, queue/steer/stop) │
│   └─ ContextProvider (WorkspaceContext serialization, mentions)       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ apiFetch / SSE (fetch+ReadableStream)
┌──────────────────────────────▼───────────────────────────────────────┐
│  BACKEND API (workspace_api.py — extended)                            │
│   list/search/filter · create · retrieve · partial-update (rename/   │
│   pin/archive) · destroy · paginated messages · send · send-stream · │
│   stop · regenerate · edit · export · feedback                        │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│  CarbonIntelligence (ai/intelligence.py — extended)                   │
│   ├─ ContextAssembler  (tiered prompt + token budgeting + compaction) │
│   ├─ GenerationRegistry (cancellation tokens, one per conversation)   │
│   └─ GuardChain (unchanged)                                           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ in-process
┌──────────────────────────────▼───────────────────────────────────────┐
│  ai/engine/ (stateless — progress-aware)                              │
│   TurnPipelineRunner (chat) · KG/analytics handlers (query.nl, etc.) │
│   dispatch_task_stream extended → progress frames for non-chat        │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 4. Domain Model Changes

### 4.1 `AIConversation` — extend (migration)

| Field | Type | Purpose |
|-------|------|---------|
| `is_archived` | `BooleanField(default=False)` | Soft-archive; excluded from default list |
| `is_pinned` | `BooleanField(default=False)` | Pin to top of list |
| `summary` | `TextField(blank=True)` | Rolling compaction summary of older turns |
| `last_message_at` | `DateTimeField(null=True)` | Sort/group key (denormalized from AIMessage) |
| `visibility` | `CharField(default="private")` | `private` | `shared` (Phase 4) |
| `context_snapshot_json` | `JSONField(default=dict)` | Last-assembled context budget telemetry (tokens in/out per tier) |

Keep: `id`, `user`, `title`, `app_identifier`, `conversation_type`, `status`,
`scope_json`, `task_payload_json`, `created_at`, `updated_at`, ordering `-updated_at`.

Add indexes: `(user, is_archived, is_pinned, -last_message_at)`,
`(user, app_identifier)`, `(user, conversation_type)`.

### 4.2 `AIMessage` — extend (migration)

| Field | Type | Purpose |
|-------|------|---------|
| `token_usage_json` | `JSONField(default=dict)` | `{model, prompt_tokens, completion_tokens, total_tokens, cost_usd, latency_ms}` |
| `parent_message_id` | `UUIDField(null=True)` | Branching: which message this edited/regenerated/replaced |
| `status` | `CharField(default="completed")` | `completed` | `partial` | `stopped` | `failed` (stream lifecycle) |
| `provider_model` | `CharField(max_length=64, blank=True)` | Model that answered (transparency) |

Keep: `id`, `conversation`, `role`, `content`, `metadata_json`, `created_at`,
`outcome`, `correction_text`, `learned_at`.

Add index: `(conversation, created_at)` (cursor pagination), `(conversation, role)`.

> **Note on `LLMCallLog`:** the engine already writes aggregate `LLMCallLog`
> (model/total_tokens/cost_usd/duration_ms/conversation_id). Phase 4 links `AIMessage`
> to `LLMCallLog` for per-turn attribution; until then `token_usage_json` on `AIMessage`
> carries the per-turn split (which `LLMCallLog` currently lacks — input/output split).

### 4.3 New model: `AIGeneration` (in-process + durable lease)

```python
class AIGeneration(models.Model):
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4)
    conversation  = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="generations")
    token         = models.CharField(max_length=64)     # cancellation token
    started_at    = models.DateTimeField(auto_now_add=True)
    cancelled_at  = models.DateTimeField(null=True)
    status        = models.CharField(default="running")  # running | cancelled | completed | failed
```

Rationale: an in-process `GenerationRegistry` (dict + `threading.Event`) is enough for
single-process dev; the durable `AIGeneration` row makes cancellation survive across
worker processes (Redis-backed registry is the horizontal-scale upgrade path — flag, do
not build yet).

---

## 5. API Surface (extensions to `workspace_api.py`)

Existing (kept): `POST/GET conversations`, `GET conversations/{id}`,
`POST conversations/{id}/messages`, `POST .../messages/stream`, `POST .../messages/{id}/feedback`.

| Method | Path | Purpose | Phase |
|--------|------|---------|-------|
| `PATCH` | `conversations/{id}/` | rename (`title`), `is_pinned`, `is_archived`, `visibility` | 1 |
| `DELETE` | `conversations/{id}/` | hard delete (owner) / soft-archive fallback | 1 |
| `GET` | `conversations/` | add `?q=`, `?is_archived=`, `?is_pinned=`, `?conversation_type=`, cursor `?cursor=` | 1 |
| `GET` | `conversations/{id}/messages/` | **paginated** — `?limit=&before=&after=` (cursor by `created_at`+`id`) | 2 |
| `POST` | `conversations/{id}/messages/{message_id}/regenerate/` | branch: new assistant reply from parent | 2 |
| `PATCH` | `conversations/{id}/messages/{message_id}/` | edit user message (creates branch) | 2 |
| `POST` | `conversations/{id}/stop/` | set cancellation token for the running turn | 2 |
| `POST` | `conversations/{id}/summary/` | force compaction / regenerate `summary` | 3 |
| `GET` | `conversations/{id}/export/` | transcript as JSON or Markdown (`?fmt=`) | 4 |
| `POST` | `conversations/{id}/messages/stream` | **extended** — progress frames for all types | 2 |

### 5.1 Extended SSE protocol

```
data: {"type":"chunk","content":<delta>}                     # text delta (chat/report)
data: {"type":"progress","stage":<k>,"message":<str>}        # structured progress (dq/nl/anomaly)
data: {"type":"progress","stage":<k>,"partial":<json>}       # partial structured result
data: {"type":"done","conversation":{...},"usage":{...}}     # terminal success + usage
data: {"type":"error","error":<msg>}                          # terminal error
data: {"type":"stopped","conversation":{...}}                 # user interrupted
```

Frame rules:
- `chunk` is only emitted for genuinely streamable ops (`chat`, `report.draft`).
- `progress` stages map to the existing type labels (`dq_suggest` → "analyzing table
  profile" → "generating suggestions" → "ranking confidence"). This replaces the
  frontend's `AIWorkingIndicator` static label + 2s polling with server-driven truth.
- `done` always carries `usage` (model, tokens, cost, latency) so the bubble can render
  a transparency chip without a second fetch.
- `stopped` is terminal and persists a `status="stopped"` assistant message so the
  conversation is never stuck in `working`.

### 5.2 Cancellation semantics

`send_message_stream` registers a `threading.Event` in `GenerationRegistry` keyed by
`conversation_id`. The generator checks `event.is_set()` between frames and, if set,
persists the partial content as `status="stopped"` and yields `stopped`. `POST /stop/`
sets the event and marks the `AIGeneration` row cancelled. If no running generation
exists, `stop` returns `204` (idempotent). This is WSGI-compatible (no ASGI migration
required) and matches the existing `queue.Queue`+daemon-thread bridge in
`dispatch_task_stream`.

---

## 6. Context Engineering & Memory Tiers

New module `backend/ai/context_assembler.py` (kept out of `ai/engine/`, owned by Carbon
per §0.4). `CarbonIntelligence` calls it before every turn.

### 6.1 Tiered prompt assembly

| Tier | Source | Budget | Notes |
|------|--------|--------|-------|
| T0 system | static per-operation prompt + role | fixed, small | unchanged |
| T1 workspace | `WorkspaceContext` (Contract §11) + explicit `#mentions` | ~1-2k tokens | deterministic, scoped, auditable |
| T2 history | recent N turns verbatim | `RECENT_TURNS` (default 8) | oldest collapsed into `summary` |
| T2b summary | `AIConversation.summary` (rolling) | `SUMMARY_BUDGET` (default 1.5k) | regenerated on threshold |
| T3 retrieval | engine KG + vector store, queried by the turn | `RETRIEVAL_BUDGET` (default 2k) | only when `RAG_ENABLED` |
| T4 memory | long-term facts for user + org scope | `MEMORY_BUDGET` (default 1k) | from `LongTermMemory` |

### 6.2 Token budgeting & compaction

```
budget(model) = MODEL_CONTEXT_WINDOW[model] * CONTEXT_BUDGET_RATIO   # default 0.8
assemble():
  used = len(T0 + T1)
  reserve T3 + T4, then fill T2b summary, then fill T2 recent turns
  if history tokens > threshold:
      new_summary = summarize(previous_summary + spilled_turns)   # 1 LLM call, cached
      persist AIConversation.summary; emit AIConversationAuditEvent
```

Compaction uses a **cheap** model (`LLM_SUMMARY_MODEL`, default a Haiku-class or POE
equivalent) and is memoized by `(conversation_id, last_summarized_message_id)` so it
does not re-run per turn. The `context_snapshot_json` on the conversation stores the
per-tier token counts for transparency/debugging.

### 6.3 Frontend mentions (T1 made explicit)

`AIInputBar` parses `#table`, `#rule`, `#field`, `#module` triggers, autocompletes from
`WorkspaceContext`, and serializes selected entity ids into the `mentions` array of the
`workspace_context`. The engine receives resolved entity names + ids, never raw text
guesses. This is the Cursor `@`/Copilot `#` pattern, adapted to Carbon's structured
model.

---

## 7. Frontend Shell (rewrite)

### 7.1 `AIWorkspace.jsx` — durable session manager

- State moves from a flat `conversations` array to a normalized store:
  `{ byId, order, pinnedIds, archivedIds, activeId, cursor, hasMore, query }`.
- **Tabs are id-keyed** (never index). Closing a tab = archive (PATCH `is_archived`)
  → survives reload. `Ctrl+Shift+T` reopens most-recently-archived.
- **Sidebar `SessionList`** (virtualized) grouped: Pinned → Active → Archived, with
  search + type filter. Horizontal tabs remain as a thin strip for the *open* subset.
- Auto-title: after the first assistant reply, set `title` from a heuristic truncation
  of the first user message (no extra LLM call in Phase 1; optional LLM title in Phase 4).
- Keyboard: `Ctrl+\` toggle, `Ctrl+1..9` switch, `Ctrl+W` close (archive), `Ctrl+Shift+T`
  reopen, `Ctrl+F` search.

### 7.2 `AIConversationView.jsx` — stream-all + interrupt + paginate

- `handleSend` routes **all** types through `sendMessageStream` (removed 2s polling path
  entirely). The input is **not** disabled while `working`; it becomes a
  queue/steer/stop dropdown (Copilot pattern): default "queue" (buffer client-side,
  send on `done`), "steer" (call `stop` + send immediately), "stop" (call `stop` only).
- Infinite scroll: load messages via `GET .../messages/?before=<cursor>` when the top
  of the list is reached; newest messages appended from stream frames.
- Render `progress` frames as a live status line (`AIWorkingIndicator` fed by server
  truth, not a static label); `partial` frames progressively fill structured cards.
- `usage` from `done` renders a per-turn chip: `gpt-4o · 1.2k tok · $0.003 · 1.8s`.

### 7.3 `AIConversationTabs.jsx` — id-based, keyboard, grouped

- `value` = conversation `id`; no `indexOf`. Grouped by `conversation_type` with
  `CONVERSATION_TYPE_LABELS`; pinned tabs sort first; status dot + close (archive) +
  context menu (Pin/Rename/Archive/Delete/Export).

### 7.4 `AIMessageBubble.jsx` — fixes + transparency + checkpoints

- **Fix G7**: wire `onClick` on follow-up `Chip`s → `handleSend(question)`.
- Add `usage` chip (model/tokens/cost/latency) from `token_usage_json`.
- Add checkpoint affordance: after accepting a `dq_suggestions` action, show a
  reversible "Applied · Undo" trail (roll back via the DQ suggestion reject path).
- `status="stopped"` renders as an "Interrupted" marker with a "Continue" button.

---

---

## 8. Information Architecture (IA)

### 8.1 The single most important rule

> **Conversations are records, not tabs.**
> Tabs are modes. Records live inside a mode.

The tab-strip must never grow dynamically per conversation. A user with 40 threads
must have the same shell navigation as a user with 1 thread.

### 8.2 Shell zones

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SHELL HEADER                                                            │
│  [Title: AI Workspace]  [Scope chip]  [New thread ▼]  [Search]  [✕]    │
├──────────────────────┬──────────────────────────────────────────────────┤
│  THREAD RAIL (left)  │  MAIN PANEL                                       │
│  ┌─────────────────┐ │  ┌────────────────────────────────────────────┐  │
│  │ 📌 Pinned (2)   │ │  │  FIXED MODE TABS                           │  │
│  │  > DQ Check     │ │  │  [Chat] [Tasks/Runs] [Artifacts] [Audit]  │  │
│  │  > Oct Report   │ │  ├────────────────────────────────────────────┤  │
│  ├─────────────────┤ │  │  MODE CONTENT                              │  │
│  │ 💬 Active (8)   │ │  │                                            │  │
│  │  > Electricity… │ │  │  [Current thread view / task list /       │  │
│  │  > Fleet anal…  │ │  │   artifact browser / audit log]           │  │
│  │  > Why Scope 3… │ │  │                                            │  │
│  ├─────────────────┤ │  └────────────────────────────────────────────┘  │
│  │ 🗂 Archived ▶   │ │                                                   │
│  └─────────────────┘ │                                                   │
└──────────────────────┴───────────────────────────────────────────────────┘
```

### 8.3 Fixed mode tabs (never dynamic)

| Tab | Content | Creates what |
|-----|---------|--------------|
| **Chat** | Thread view of selected conversation | Message record |
| **Tasks / Runs** | List of async operations (DQ validate, anomaly, NL query, report draft) | Task record |
| **Artifacts** | Promoted outputs: reports, rule sets, query results | Artifact record |
| **Audit** | Read-only `GovernanceEvent` log for AI operations | — |

These four tabs are fixed. Workers must **never** add a fifth without a Master Architect ADR.

### 8.4 Thread rail

- Sections: Pinned (max 5) → Active (sorted by `last_message_at` desc) → Archived (lazy-loaded, initially collapsed).
- Each row: type icon + title (truncated) + status dot + relative time.
- Right-click or `⋮` → Pin / Rename / Archive / Delete.
- Search above the rail filters all sections simultaneously.
- Rail is collapsible (chevron toggle, persisted in `localStorage`).

### 8.5 Deduplication rule

When the user triggers "Ask AI" from any workspace page and a conversation matching
`(app_identifier, entity_type, entity_id)` already exists and is `active` or `pending`,
focus that conversation instead of opening a new one. Show a "Continue existing?" banner
with a "New thread anyway" escape hatch.

### 8.6 Conversation cap and auto-archive policy

- Hard display cap: max 50 active threads in the rail (enforcement: `limit=50` on
  `listConversations`; threads beyond 50 auto-archive server-side on creation).
- Auto-archive threshold: 30 days since `last_message_at` with no pin; configurable
  via `settings.AI_AUTO_ARCHIVE_DAYS`.
- Hard delete: only by owner, only from the Archived section, with confirm dialog.

---

## 9. UX Principles and Interaction Contracts

### 9.1 The seven rules for every worker

1. **The user never loses agency.** Input is always present; when a generation is
   running it changes to queue/steer/stop mode — it does not disable.
2. **Every action gets immediate feedback.** Optimistic local state first, reconcile
   from server on `done`/error. Never block the whole panel for a loading state.
3. **Clarity over novelty.** Use MUI primitives. No custom components without a design
   decision. One pattern per interaction.
4. **Status by label + color, never color alone.** Every chip has text.
5. **Destructive actions confirm; reversible ones do not.** Archive = no confirm. Delete
   = confirm dialog. Clear the conversation = confirm.
6. **Tab ordering is stable.** Pinned tabs sort first; within a section, sort is
   `last_message_at` desc. Never re-sort while the user is interacting.
7. **No empty states without guidance.** Every empty state names the action to take.

### 9.2 Input bar state machine

```
IDLE ──[type]────────────────────────────────────► COMPOSING
COMPOSING ──[send]──────────────────────────────► SENDING
SENDING ──[first chunk received]────────────────► STREAMING (chat) or PROGRESSING (structured)
STREAMING ──[done frame]────────────────────────► IDLE (reconcile messages)
STREAMING ──[stop clicked]──────────────────────► STOPPING
STOPPING ──[stopped frame]──────────────────────► IDLE (interrupted marker shown)
PROGRESSING ──[done frame]──────────────────────► IDLE
COMPOSING/IDLE ──[type while STREAMING]─────────► QUEUED (buffered, sent on done)
QUEUED ──[done frame]───────────────────────────► SENDING (flush queue)
```

Visible affordances per state:

| State | Send button | Input | Extra |
|-------|-------------|-------|-------|
| IDLE | "Send" enabled | enabled | — |
| COMPOSING | "Send" enabled | enabled | char count (>200) |
| SENDING | spinner | enabled + grey text | — |
| STREAMING | mode selector (queue/steer/stop) | enabled | live chunk |
| PROGRESSING | mode selector | enabled | progress stage label |
| STOPPING | spinner, disabled | disabled | "Stopping…" |
| QUEUED | "Queued" badge | enabled | queue count |

### 9.3 Message bubble anatomy

```
┌──────────────────────────────────────────────────────────┐
│ [role icon]  [role label]  [timestamp]          [⋮ menu] │
│                                                           │
│  [content — text, structured card, code block]            │
│                                                           │
│  [Follow-up chips (if follow_up_questions)]               │
│                                                           │
│  [Usage chip: gpt-4o · 1.2k tok · $0.003 · 1.8s]        │
│  [Status chip: Interrupted | Error | — ]                  │
│                                                           │
│  [Feedback: 👍 Accept  👎 Reject  ✏️ Correct]  [↩ Why?] │
└──────────────────────────────────────────────────────────┘
```

- `⋮ menu` → Copy, Regenerate, Edit (user messages), Report, Export thread.
- `↩ Why?` → provenance tooltip: model, scope snapshot, latency, session id.
- Usage chip is a `<Tooltip>` with the full breakdown on hover.
- Follow-up chips are `clickable` `Chip` components; `onClick` calls `handleSend(q)`.

### 9.4 Structured output card types

Each `conversation_type` has an expected card renderer. Workers must render the correct
card and must NOT fall back to a JSON dump as the primary UI.

| Type | Card component | Key data | Actions |
|------|---------------|----------|---------|
| `dq_validate` | `DQValidationCard` | passed/failed rule list, violation count | Re-run, Export |
| `dq_suggest` | `DQSuggestionCard` | N suggestions with confidence, rule text | Accept All, Reject All, Accept/Reject per row |
| `nl_query` | `NLQueryCard` | generated SQL + result table (first 100 rows) | Copy SQL, Download CSV |
| `anomaly` | `AnomalyCard` | anomaly list with field, severity, evidence | Accept, Dismiss, Investigate |
| `report_draft` | `ReportDraftCard` | markdown narrative, GHG totals | Edit inline, Export PDF/MD |
| `chat` | `ChatBubble` | plain text + optional follow-ups | — |

All structured cards must render a skeleton while `status === "working"` or
`streamingText === null` (loading). Never a blank panel.

### 9.5 Context mention contract (`#` trigger)

| Trigger typed | Entity kind | Resolved to | Sent as |
|---|---|---|---|
| `#table` | `DataTable` | `{id, name, module_id}` | `workspace_context.mentions` array |
| `#rule` | `DQRule` | `{id, name, rule_type}` | same |
| `#field` | `DataField` | `{id, label, type, table_id}` | same |
| `#module` | `Module` | `{id, name, org_unit_id}` | same |

The autocomplete list is fetched from `GET /carbon-api/dataschema/tables/?q=…` etc.
on `#` trigger + first character. The `mentions` array is serialized into
`workspace_context.mentions`; the backend `ContextAssembler` resolves them by id and
injects their descriptors into T1 context. The text token in the message content is
replaced with `@Name` (display-only) before send.

---

## 10. Workflow Choreography

### 10.1 Standard chat workflow

```
User → types message → [#mention resolve] → send
Server ← SSE: chunk… chunk… done(conv)
UI: streaming text in bubble → reconcile → follow-up chips appear
Feedback affordance shown after 2s idle
```

### 10.2 DQ Validate workflow

```
Entry: user clicks "Validate with AI" from DQ Rules tab on a table
  → WorkspaceContext: {workspace:'dq', entity_type:'table', entity_id:X, intent:'validate'}
  → createConversation(type:'dq_validate', task_payload:{table_id:X})
  → focus AI workspace → Chat tab
Server ← SSE: progress("Analyzing table schema")
        progress("Running N rules")
        progress("Scoring results")
        done(conv + validation_result)
UI: DQValidationCard renders with pass/fail counts
Actions: Re-run, Export (downloads JSON report), Accept findings
```

### 10.3 DQ Suggest workflow

```
Entry: "Suggest DQ Rules" from table detail
  → createConversation(type:'dq_suggest', task_payload:{table_id:X})
Server ← SSE: progress("Profiling columns")
        progress("Generating candidate rules")
        done(conv + suggestions[])
UI: DQSuggestionCard — each row: rule text, confidence bar, field, type
Actions:
  Accept row → POST /dq/rules/ (create) + record_feedback(accepted)
  Reject row → record_feedback(rejected)
  Accept All → sequential create (show progress)
  Bulk accept state: "Accepted 3/5 · 2 pending"
```

### 10.4 NL Query workflow

```
Entry: "Ask a question" from emissions dashboard or any data module
  → WorkspaceContext: {workspace:'emissions', entity_type:'module', intent:'explore'}
Server ← SSE: progress("Parsing query")
        progress("Generating SQL")
        progress("Executing query")
        done(conv + {sql, rows, row_count})
UI: NLQueryCard — SQL block (syntax-highlighted) + result grid (paginated, 100 rows)
Actions: Copy SQL, Download CSV, Follow-up question (auto-populates input)
Error path: if SQL execution fails → "Query failed" + raw SQL shown + "Edit and retry" button
```

### 10.5 Anomaly Detection workflow

```
Entry: "Detect anomalies" from DQ workspace or data entry page
  → task_payload:{table_id:X, profile:{…}}
Server ← SSE: progress("Scoring row distributions")
        progress("Flagging outliers")
        done(conv + anomalies[])
UI: AnomalyCard — severity-sorted list, field + evidence + confidence
Actions:
  Accept → writes DQ finding (requires dq:manage_rules)
  Dismiss → record_feedback(rejected)
  Investigate → opens NL Query with pre-filled prompt about that field
```

### 10.6 Report Draft workflow

```
Entry: "Draft GHG Report" from emissions dashboard
  → createConversation(type:'report_draft', task_payload:{period:X, scope_filter:Y})
Server ← SSE: progress("Gathering emissions data")
        progress("Calculating totals")
        progress("Drafting narrative")
        done(conv + {markdown, totals})
UI: ReportDraftCard — rendered markdown preview + raw toggle
Actions:
  Edit inline → contenteditable overlay on the card
  Export Markdown → download .md
  Export PDF → browser print dialog (no server-side PDF in Phase 4)
  Save as Artifact → promote to Artifacts tab with stable id
```

### 10.7 Interrupt and Resume workflow

```
User sends message → STREAMING/PROGRESSING
User clicks Stop (or selects "Stop" from send-mode) →
  POST /conversations/{id}/stop/ → 200
  Server sets AIGeneration.status = "cancelled" + persists partial AIMessage(status='stopped')
  SSE emits: {"type":"stopped","conversation":{…}}
  UI: "Interrupted" chip on the partial bubble, "Continue" button
User clicks Continue →
  Input pre-filled with last user message
  streamSend(lastUserContent) → new generation
```

### 10.8 Thread search and resume workflow

```
User opens AI Workspace → Thread rail renders (pinned + active + archived collapsed)
User types in search box → client-side filter over byId (title match)
If no match → refetch with ?q=term → merge into store
User clicks thread → load conversation (getConversation) → messages rendered
  If conversation has >50 messages → infinite scroll from bottom; "Load older" at top
  If conversation status = 'working' → attach to live generation (GET stream resume — Phase 3)
```

---

## 11. Thread Lifecycle State Machine (full FSM)

### 11.1 Conversation status FSM

```
[CREATE]
    │
    ▼
 PENDING ──[first user message sent]──► WORKING
    │                                      │
    │                              ┌───────┼───────┐
    │                         [done]   [needs_input] [error]
    │                              │         │         │
    │                         COMPLETED  NEEDS_INPUT  FAILED
    │                              │         │
    │                              │     [user replies]
    │                              │         │
    │                              └────► WORKING
    │
[archive] → is_archived=True (status unchanged)
[delete]  → hard delete (owner only)
```

### 11.2 Archive / Restore lifecycle

```
active thread
  │
  ├── [Ctrl+W or Archive]          ──► is_archived=True  (removed from rail, reversible)
  │                                      │
  │                                 [Ctrl+Shift+T or Restore] ──► is_archived=False
  │
  ├── [Pin]                         ──► is_pinned=True, sorted to top of rail
  │
  ├── [Rename]                      ──► PATCH title
  │
  └── [Delete]                      ──► confirm dialog → hard delete
```

### 11.3 Message status FSM

```
[streaming begins] → local-{timestamp} optimistic record (role='user')
[done frame]       → local record replaced by persisted canonical records
[stopped frame]    → assistant message status='stopped', partial content preserved
[error frame]      → local user record removed, error notification
[regenerate]       → new AIMessage(parent_message_id=old_id) branches the thread
[edit user msg]    → PATCH message content + status='completed', thread visually rebases
```

### 11.4 Generation status FSM

```
[send] → AIGeneration created (status='running')
[done frame received] → AIGeneration(status='completed')
[POST /stop/] → AIGeneration(status='cancelled'), SSE emits stopped frame
[error]       → AIGeneration(status='failed')
[server restart] → orphaned generations (no stopped frame); cleanup job marks
                   AIGeneration older than 5 min still 'running' as 'failed',
                   conversation.status reset from 'working' to 'completed' with
                   a system message "Generation interrupted (server restart)"
```

---

## 12. Context Transparency and Provenance UX

### 12.1 Per-turn transparency chip

Every assistant message renders:

```
[gpt-4o · 1,248 tok · $0.0031 · 1.84s]  ← clickable chip
```

On click/hover → `Tooltip` with breakdown:

```
Model:            gpt-4o
Prompt tokens:    912   ($0.0027)
Completion tokens: 336  ($0.0010)
Total:            1,248 ($0.0037)
Latency:          1,840ms
Conversation ID:  6c2c5c81…
```

Source: `AIMessage.token_usage_json`. If empty → chip is hidden (never "N/A tokens").

### 12.2 "Why this answer?" provenance

Every assistant message has a `↩ Why?` affordance. Expands to:

```
Conversation:    "DQ Check — Electricity" (created 2026-08-16)
Type:            dq_validate
Scope:           Org: AASTMT / Module: Abu Qeer Electricity
User:            ahmed (superuser)
App:             platform
Engine turn ID:  b54f7ce2
Guard chain:     ScopeGuard ✅ AccessGuard ✅ IsolationGuard ✅
Context tiers:   T0 (system) 120 tok · T1 (workspace) 340 tok · T2 (history) 420 tok
```

Source: `AIMessage.metadata_json.provenance` (populated by `intelligence.py` from
`scope_json` + `context_snapshot_json`).

### 12.3 Context panel (Phase 3)

A collapsible "Context" sidebar in `AIConversationView` shows:

- Active scope (org, module, app).
- Detected `#mentions` for the current thread.
- T1/T2/T3/T4 token budget bar (visual progress bar per tier).
- "Clear context" button to reset to T0 only (useful for off-topic questions).

---

## 13. Error Taxonomy and Recovery Patterns

### 13.1 Error types and their UX

| Type | Example | UI treatment | User action |
|------|---------|-------------|-------------|
| **Network / offline** | `ERR_CONNECTION_REFUSED` | `AIOfflineBanner` full-width, yellow | Retry button |
| **Auth expired** | `401` | Toast "Session expired" + auto-refresh-token attempt | If refresh fails → redirect to login |
| **Scope guard rejection** | `403 "ScopeGuard: empty user_identifier"` | Error bubble in thread with message text | Contact admin (message displayed) |
| **Streaming error** | `error` SSE frame | Error chip on bubble + notification | "Retry" button re-sends same content |
| **Structured result error** | SQL execution fail, rule parse fail | Error state inside structured card with detail | "Edit prompt" / "Retry" |
| **Rate limit** | `429` | Toast with retry-after seconds | Countdown timer on send button |
| **Server error** | `500` | Toast "Something went wrong" + correlation id | Copy correlation id for support |
| **Partial stream** | server restart mid-stream | "Generation interrupted" system message | "Continue" button with last user content |

### 13.2 Never do

- Never leave `conversation.status = 'working'` without a terminal frame.
- Never show a raw stack trace or Django exception detail in the UI.
- Never swallow errors silently (no `catch {}` without `notifyFromError`).
- Never disable the entire workspace panel on a single conversation error.

### 13.3 Offline mode

`AIOfflineBanner` renders when `providerOffline === true`. It must:
- Allow the user to browse existing threads (read-only).
- Disable send/new-thread actions (not hide them).
- Poll `/carbon-api/ai/workspace/conversations/` every 30s and auto-recover.

---

## 14. Accessibility and Keyboard Contract

### 14.1 Keyboard bindings (all must be implemented and tested)

| Binding | Action | Scope |
|---------|--------|-------|
| `Ctrl+\` | Toggle AI Workspace open/close | Global |
| `Ctrl+N` | New chat thread | Workspace open |
| `Ctrl+W` | Archive active thread | Thread focused |
| `Ctrl+Shift+T` | Restore last archived thread | Workspace open |
| `Ctrl+1`–`9` | Switch to thread by position in rail | Workspace open |
| `Ctrl+F` | Focus thread search | Workspace open |
| `Enter` | Send message | Input focused, not IME composing |
| `Shift+Enter` | New line in input | Input focused |
| `Esc` | Cancel composing / close overlay | Composing or overlay open |
| `↑` / `↓` | Navigate thread list | Rail focused |
| `F2` | Rename focused thread | Thread in rail focused |

### 14.2 ARIA requirements

- `AIWorkspace` root: `role="complementary"` `aria-label="AI Workspace"`.
- Thread rail: `role="navigation"` `aria-label="Conversation threads"`.
- Active thread: `aria-current="page"` on the selected rail item.
- Message list: `role="log"` `aria-live="polite"` `aria-relevant="additions"`.
- Input: `aria-label="Message input"` `aria-multiline="true"`.
- Send button: `aria-label="Send message"`.
- Send-mode select: `aria-label="Send mode"`.
- Loading state: `aria-busy="true"` on the message list.
- Status chips: `aria-label="{status} status"` not just color.

### 14.3 Focus management

- When new thread is created → focus moves to input bar.
- When thread is archived → focus moves to next visible thread in rail.
- When modal opens → focus trap inside modal.
- When modal closes → focus returns to trigger element.

---

## 15. Metrics and Observability Contract

### 15.1 Frontend instrumentation events

All events use a `trackEvent(name, props)` wrapper. In the current codebase this maps
to `AppFeedback`. Workers MUST emit the following events at the named points:

| Event | Trigger | Key props |
|-------|---------|-----------|
| `ai_workspace_open` | Workspace shown | `{ source: 'nav_button' | 'task_transfer' | 'ask_ai_button' }` |
| `ai_thread_created` | `handleNewChat` resolves | `{ conversation_type, entry_source }` |
| `ai_message_sent` | `streamSend` called | `{ conversation_type, send_mode, has_mentions, content_len }` |
| `ai_stream_done` | `onDone` frame | `{ conversation_type, latency_ms, token_count, model }` |
| `ai_stream_stopped` | `onStopped` frame | `{ conversation_type, partial_token_count }` |
| `ai_stream_error` | `onError` frame | `{ error_type, conversation_type }` |
| `ai_follow_up_clicked` | follow-up chip `onClick` | `{ conversation_type }` |
| `ai_suggestion_accepted` | Accept on DQSuggestionCard | `{ rule_type, confidence }` |
| `ai_suggestion_rejected` | Reject on DQSuggestionCard | `{ rule_type }` |
| `ai_thread_archived` | `handleArchive` called | `{ was_active }` |
| `ai_thread_restored` | `handleRestore` called | — |
| `ai_mention_used` | mention resolved and inserted | `{ kind }` |
| `ai_artifact_promoted` | "Save as Artifact" clicked | `{ conversation_type }` |
| `ai_export` | Export downloaded | `{ format: 'json' | 'markdown' }` |

### 15.2 Backend instrumentation (already live)

- `AI_AUDIT` log in `guards.py` → `latency_ms`, `status`, `operation`, `scope_snapshot`.
- `LLMCallLog` → model, tokens, cost per provider call.
- `AIMessage.token_usage_json` → per-turn usage.
- `GovernanceEvent` → archive/pin/rename/delete audit trail.

### 15.3 Key product metrics to monitor

| Metric | Target / alert threshold | Source |
|--------|--------------------------|--------|
| `threads_per_user_per_week` | Baseline week 1; alert if >50 (saturation) | DB aggregate |
| `median_time_to_resume_thread` | < 10s | Frontend event |
| `duplicate_thread_rate` | < 20% (same entity/intent within 24h) | DB query |
| `interrupt_rate` | < 15% of sends | `ai_stream_stopped` count |
| `follow_up_click_rate` | > 10% of assistant messages with chips | Frontend event |
| `suggestion_accept_rate` | > 40% of DQ suggest sessions | `ai_suggestion_accepted` |
| `p95 streaming latency` | < 5s for chat, < 30s for structured | `AI_AUDIT` |
| `error_rate` | < 2% of sends | `ai_stream_error` count |

---

## 16. Phased Roadmap (detailed)

Each phase is independently shippable, gated, and assigned a role. A phase is **Done**
only when its gate commands pass AND its browser checklist is verified by QA.

---

### Phase 0 — Foundation Models (DONE — Sprint 13)

**Role:** Backend Worker
**Status:** ✅ Implemented, migration applied (`ai.0007`)
**Scope:** `AIConversation` field extension, `AIMessage` field extension, `AIGeneration`
model, `ConversationUpdateSerializer`, `MessageListSerializer`, list filters, message
cursor pagination.

**Gate (regression):**
```bash
cd backend && ../.venv/bin/python -m pytest ai/tests/test_workspace_lifecycle.py -q
cd backend && ../.venv/bin/python manage.py check
cd backend && ../.venv/bin/python manage.py makemigrations --check --dry-run
```

---

### Phase 1 — Session Lifecycle API (DONE — Sprint 13)

**Role:** Backend Worker
**Status:** ✅ Implemented
**Scope:** `PATCH/DELETE conversations/`, `GET messages/` (cursor pagination), list
filter params (`q`, `is_archived`, `is_pinned`, `conversation_type`), `update_conversation`,
`delete_conversation`, `list_messages` in `intelligence.py`, auto-title.

**Open finding (F3/F4 from QA sim):** pinned conversations excluded from default list;
first-page `has_more` always false. Fix before Phase 2 ships.

**Gate (regression):**
```bash
cd backend && ../.venv/bin/python -m pytest ai -q
```

---

### Phase 2 — Stream-all + Interrupt + Message Management (DONE — Sprints 14–16)

**Role:** Backend Worker + Frontend Worker
**Status:** ✅ Backend implemented; ✅ Frontend shell rewrite implemented
**Scope:** All conversation types stream via SSE; `stop/`, `regenerate/`, `edit`
endpoints; `GenerationRegistry` (in-process); `AIConversationView` stream-all + queue/
steer/stop; `AIMessageBubble` follow-up fix (G7), usage chip, stopped chip; thread
lifecycle shell (normalized store, id-based tabs, archive/restore/pin/rename/search).

**Open findings (from QA sim):**
- F1 (P1): non-superuser create/send → 500 (ScopedRole.is_read_only missing). Fix target: pre-Phase 3.
- F2 (P2): export `?format=markdown` → 404 (DRF URL format override collision).
- F4 (P2): first-page `has_more` always false.

**Gate:**
```bash
cd backend && ../.venv/bin/python -m pytest ai -q
cd carbon-frontend && npm test -- --run
cd carbon-frontend && npm run lint
cd carbon-frontend && npm run build
```

**Browser checklist:**
- [ ] Close active tab → archived, next tab activates, no MUI Tabs error.
- [ ] Send message while streaming → queued, sent on done.
- [ ] Interrupt mid-stream → "Interrupted" chip on bubble.
- [ ] Follow-up chip click → sends that question.
- [ ] Usage chip renders with model/tokens/cost/latency.

---

### Phase 2.5 — Bug Sprint (pre-Phase 3 mandatory)

**Role:** Backend Worker (Debugger/Fixer)
**Status:** 🚀 Ready to dispatch
**Scope:** Fix exactly the open findings from Phase 2 QA. No new features.

**Files:**
- `backend/ai/intelligence.py` — F1: remove/replace `role.is_read_only` (use group-name check, same pattern as `build_scope`)
- `backend/ai/workspace_api.py` — F2: rename `format` param to `export_fmt` to avoid DRF collision
- `backend/ai/intelligence.py` — F3: `list_conversations` — do not pass `is_pinned=False` by default; filter only when explicitly given
- `backend/ai/intelligence.py` — F4: `list_messages` — compute `has_more` on the unpaginated count, not only in `before`/`after` branches

**Gate:**
```bash
cd backend && ../.venv/bin/python -m pytest ai -q  # must include regression for each fix
cd backend && ../.venv/bin/python manage.py check
```

**Tests required:** one failing test per finding → patch → passing test (classic regression).

---

### Phase 3 — Context Engineering and Memory Tiers

**Role:** Backend Worker then Frontend Worker
**Status:** 📋 Specced, not started
**Dependencies:** Phase 2.5 complete

#### 3-A Backend — Context Assembler

**Files:**
```
backend/ai/context_assembler.py   (new)
backend/ai/intelligence.py        (wire assembler into _send_chat_message)
backend/ai/models/workspace.py    (AIConversation.summary already exists)
backend/ai/workspace_api.py       (add POST conversations/{id}/summarize/)
backend/ai/tests/test_context_assembler.py  (new)
```

**Tasks:**

1. `context_assembler.py` — implement `assemble_context(conversation, user_message, scope)`:
   - T0: static system prompt (existing, unchanged).
   - T1: `WorkspaceContext.from_dict` from `task_payload_json.workspace_context` + resolved `mentions` from user message.
   - T2: last `RECENT_TURNS` (default 8) messages verbatim; older turns omitted.
   - T2b: if `conversation.summary` is non-empty and `used_tokens` would exceed threshold, prepend summary and drop the oldest turns.
   - T3: if `RAG_ENABLED` (settings flag, default False) → query engine KG for top-k relevant facts.
   - T4: stub (empty) — long-term memory is Phase 5.
   - Returns: `(assembled_messages: list[dict], snapshot: dict)` where `snapshot` carries per-tier token counts.
   - `snapshot` is saved to `AIConversation.context_snapshot_json` after each turn.

2. Compaction: `summarize_conversation(conversation_id, user)`:
   - Loads all messages before the current rolling window.
   - Calls LLM with `LLM_SUMMARY_MODEL` (cheap model, configurable).
   - Saves result to `conversation.summary`.
   - Memoized by `(conversation_id, last_summarized_message_id)` — skip if message set unchanged.

3. `POST conversations/{id}/summarize/` endpoint — triggers compaction on demand.

**Acceptance criteria:**
- 40-turn conversation stays under budget (test with mock LLM).
- Summary is not re-generated if no new messages since last summary.
- Cross-app data never appears in T1/T2 (verified by scoped test).
- `context_snapshot_json` has correct per-tier counts after send.

**Gate:**
```bash
cd backend && ../.venv/bin/python -m pytest ai/tests/test_context_assembler.py -q
cd backend && ../.venv/bin/python manage.py check
```

#### 3-B Frontend — Mentions and Context Panel

**Files:**
```
carbon-frontend/src/shell/AIInputBar.jsx
carbon-frontend/src/shell/AIContextPanel.jsx   (new)
carbon-frontend/src/shell/AIConversationView.jsx
carbon-frontend/src/api/aiWorkspace.js         (summarizeConversation)
```

**Tasks:**

1. `AIInputBar` — `#` trigger autocomplete:
   - On `#` typed → open `Popper` menu with entity kinds.
   - On kind selected → type-ahead search: `GET /carbon-api/dataschema/tables/?q=…` etc.
   - On entity selected → insert `@Name` display token into input, append to `mentions` array.
   - `mentions` sent as `workspace_context.mentions` in `streamSend`.

2. `AIContextPanel` — collapsible right panel in `AIConversationView`:
   - Scope chip row (org, module, app).
   - Mentions list for this thread.
   - Token budget bar (T0–T4 from `context_snapshot_json`).
   - "Summarize now" button → `summarizeConversation(token, conversationId)`.

**Browser checklist:**
- [ ] Type `#` → menu opens.
- [ ] Type `#table ele` → shows tables matching "ele".
- [ ] Select "Electricity" → `@Electricity` inserted, chip in context panel.
- [ ] Context panel shows budget bar after message sent.
- [ ] "Summarize now" → success toast, summary appears in context panel.

**Gate:**
```bash
cd carbon-frontend && npm test -- --run   # test mention insertion + context panel render
cd carbon-frontend && npm run lint
cd carbon-frontend && npm run build
```

---

### Phase 4 — Enterprise Governance and Artifacts

**Role:** Backend Worker then Frontend Worker
**Status:** 📋 Specced, not started
**Dependencies:** Phase 3-A complete

#### 4-A Backend

**Files:**
```
backend/ai/workspace_api.py       (export, shared visibility)
backend/ai/intelligence.py        (export_conversation, promote_to_artifact)
backend/ai/models/workspace.py    (AIArtifact model — new)
backend/ai/tests/test_governance.py  (new)
```

**Tasks:**

1. **Export** — `GET conversations/{id}/export/?fmt=markdown|json`:
   - JSON: full conversation dict with messages array.
   - Markdown: messages rendered as `## User` / `## Assistant` blocks; structured cards as fenced JSON; SQL blocks as ```sql```.
   - Owner-only unless `visibility="shared"`.
   - Fix F2 (rename `export_fmt` param).

2. **Shared conversations** — `PATCH conversations/{id}/ {visibility:"shared"}`:
   - Shared conversations visible to all users in same org (read-only for non-owners).
   - Delete of shared conversation requires `ai:manage_console` capability.
   - `AIConversation.visibility` already exists.

3. **AIArtifact model** (new):
   ```python
   class AIArtifact(models.Model):
       id             = UUIDField(primary_key=True)
       conversation   = ForeignKey(AIConversation, on_delete=CASCADE)
       message        = ForeignKey(AIMessage, null=True, on_delete=SET_NULL)
       title          = CharField(max_length=255)
       artifact_type  = CharField(max_length=30)   # 'report' | 'rule_set' | 'query' | 'analysis'
       content_json   = JSONField(default=dict)
       visibility     = CharField(default='private')
       created_at     = DateTimeField(auto_now_add=True)
       created_by     = ForeignKey(User, on_delete=SET_NULL, null=True)
   ```
   CRUD API under `GET/POST /ai/workspace/artifacts/` + `GET/PATCH/DELETE /artifacts/{id}/`.

4. **Provenance metadata** — extend `_serialize_message` to include:
   `provenance: { model, scope_snapshot, context_snapshot, guard_results, engine_turn_id }`.
   Populated from `metadata_json` + `token_usage_json`.

#### 4-B Frontend

**Files:**
```
carbon-frontend/src/shell/AIWorkspace.jsx          (add Artifacts tab)
carbon-frontend/src/shell/AIArtifactBrowser.jsx    (new)
carbon-frontend/src/shell/AIArtifactCard.jsx       (new)
carbon-frontend/src/shell/AIConversationView.jsx   (export menu, "Promote to Artifact")
carbon-frontend/src/shell/AIMessageBubble.jsx      (provenance tooltip complete)
```

**Tasks:**

1. Add **Artifacts tab** to `AIWorkspace` (the fourth fixed tab).
2. `AIArtifactBrowser` — filterable list of artifacts; card per artifact with type icon, title, created date, "Open" action.
3. "Promote to Artifact" → `POST /artifacts/` with `{conversation_id, message_id, title, artifact_type, content_json}`.
4. Export menu in `AIConversationView` header: `[⬇ Export ▾]` → `Markdown (.md)` / `JSON (.json)`.
5. Provenance tooltip on `↩ Why?` — use `message.provenance` from API.

**Browser checklist:**
- [ ] Export JSON → downloads `conversation-{id}.json`.
- [ ] Export Markdown → downloads `conversation-{id}.md`.
- [ ] Promote to Artifact → artifact appears in Artifacts tab.
- [ ] "Why?" tooltip shows model, scope, guard results.
- [ ] Shared conversation readable by another user in same org.

**Gate:**
```bash
cd backend && ../.venv/bin/python -m pytest ai -q
cd carbon-frontend && npm test -- --run
cd carbon-frontend && npm run lint && npm run build
```

---

### Phase 5 — Long-Term Memory and Proactive Intelligence

**Role:** Backend Worker
**Status:** 🔭 Future — not specced for implementation yet
**Dependencies:** Phase 4 complete + LongTermMemory engine tables populated

**Scope:**

1. **T4 memory** in ContextAssembler — query `LongTermMemory` for user + org facts.
   Example facts: "This org's electricity table has seasonal anomalies in Q3", "Ahmed
   prefers concise answers with SQL".

2. **Learning loop closure** — `AIMessage.outcome` → `learn_from_message` (already
   scaffolded in `intelligence.py`) → `KgFeedbackRecord` → KG update → T3/T4 richer.

3. **Proactive triggers** — engine's `ProactiveSystem` dispatches suggestions based on
   data events (new DQ violations, schema changes, unusual emissions). Surfaces in a
   `🔔 Suggestions` section at the top of the thread rail.

4. **Workspace Resume** — when user returns to a thread after >24h, display a "catch-up"
   summary pinned at the top of the conversation: "Since your last visit: 3 new DQ
   violations, 1 anomaly detected."

**Non-goals (Phase 5):**
- Multi-user co-editing threads.
- Autonomous multi-step agent orchestration without human confirmation gates.
- Full pgvector migration (keep JSON vector fields until scale demands it).

---

## 17. Explicit Non-Goals (defer, do not build now)

- **Autonomous multi-step orchestration** without confirmation gates — only after
  single-turn quality + streaming + interruption are proven.
- **Multi-user real-time collaboration** — Phase 4 ships read-only `visibility="shared"`;
  co-editing is a separate effort.
- **Redis-backed horizontal-scale generation registry** — in-process registry + durable
  `AIGeneration` row first; flag Redis when multi-worker streaming is needed.
- **pgvector** — out of scope; engine JSON vectors + ChromaDB path stay as-is.
- **Screenshots / computer-use context** — rejected by Contract §11; `WorkspaceContext`
  is the canonical approach.
- **Dynamic top-level mode tabs per conversation type** — confirmed anti-pattern; four
  fixed tabs maximum.

---

## 18. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Streaming structured outputs is hard (JSON over SSE) | Emit `progress` events for non-chat; single `done` carries full structured result |
| Cancellation leaves partial rows | `status="stopped"` persisted atomically; conversation never stuck in `working` |
| Compaction is a hidden LLM cost | Cheap model + memoized by `last_summarized_message_id`; budget telemetry exposed |
| Frontend rewrite regresses existing behavior | Per-phase test harness (`npm test`) as regression gate; browser checklist per phase |
| Breaking the AI Contract | All changes route through `CarbonIntelligence`; `context_assembler.py` owned by Carbon (§0.4) |
| UI tab explosion (conversations as tabs) | Hard architectural rule §8.1: tabs are modes only; threads live in the rail |
| Old threads lost / "where did it go?" | Archive is soft + reversible; auto-archive only after 30 days; `Ctrl+Shift+T` restores |
| LLM cost surprises | Per-turn usage chip makes cost visible; `LLMCallLog` aggregates; budget ratio cap |
| Scope guard rejection for non-superuser (F1) | Phase 2.5 fix: remove `role.is_read_only` reference |
| Export param collision (F2) | Phase 2.5 fix: rename param |
