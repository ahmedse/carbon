# DESIGN — Carbon AI Workspace, Next-Generation (v2)

**Status:** Proposed architecture (design + phased roadmap) — NOT yet implemented
**Author:** Master Architect
**Date:** 2026-08-15
**Audience:** Backend Worker, Frontend Worker, QA Validator, DevOps Worker
**Supersedes:** the current `backend/ai/workspace_*` + `carbon-frontend/src/shell/AI*` implementation
**Binding contract reference:** `.ai-toolkit/shared/ai-contract.md` (v2.0.0)

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
| `GET` | `conversations/{id}/export/` | transcript as JSON or Markdown (`?format=`) | 4 |
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

## 8. Enterprise Governance (Phase 4)

- **Cost/usage attribution**: `AIMessage.token_usage_json` + link to `LLMCallLog`;
  aggregated by conversation in the existing `/ai/pulse/usage/` surface.
- **Transcript export**: JSON + Markdown; Markdown preserves structured cards as
  fenced JSON blocks + SQL blocks. Owner-only unless `visibility="shared"`.
- **Provenance**: every assistant message carries `app_identifier`, `scope` snapshot
  (already in conversation), and (for suggestions) the persisted suggestion/rule id —
  surfaced as a "why this answer" tooltip.
- **Audit**: extend the existing audit trail to conversation CRUD (archive/pin/rename/
  delete) via `GovernanceEvent`/`AICallLog`-style entries.
- **CBAC**: accept/reject already gated on `dq:manage_rules`. Archive/pin/rename are
  owner-only always; delete of a `shared` conversation requires `ai:manage_console`.
  No new capabilities until shared conversations ship.

---

## 9. Phased Roadmap

Each phase is independently shippable and gated. Files listed are authoritative; a
worker may add tests but not scope.

### Phase 0 — Foundation (backend models + serializers + pagination)
**Files:** `backend/ai/models/workspace.py`, `backend/ai/serializers.py`, migration.
**Scope:** add fields (§4.1, §4.2), `AIGeneration` model, list filters (`q/archived/
pinned/type/cursor`), message cursor pagination.
**Gate:** `cd backend && ../.venv/bin/python -m pytest ai -q` green; `manage.py check`;
`makemigrations --check` no drift; verify.sh backend.

### Phase 1 — Session lifecycle API + shell rewrite (G1, G6)
**Backend:** `PATCH/DELETE conversations`, list filters, auto-title on create.
**Frontend:** rewrite `AIWorkspace.jsx` (normalized id-keyed store, SessionList,
persistent archive/pin/rename/search), `AIConversationTabs.jsx` (id-based, keyboard,
groups), `AIWorkspaceHeader.jsx`.
**Gate:** backend pytest; `npm test`; `npm run build`; browser checklist (rename →
reload persists; close → archived; reopen; search).

### Phase 2 — Streaming + interrupt + message management (G2, G3, G4, G7)
**Backend:** generalize stream to all types (progress frames) in
`engine_runtime.py`/`providers/pulse.py`/`intelligence.py`; `stop/`, `regenerate/`,
`edit`; `GenerationRegistry`.
**Frontend:** `AIConversationView.jsx` (stream-all, queue/steer/stop, infinite scroll,
progress rendering), `AIInputBar.jsx` (send-dropdown), `AIMessageBubble.jsx` (wire
follow-ups, stopped marker, usage chip).
**Gate:** backend pytest (incl. cancellation + progress-frame tests); frontend test for
follow-up onClick; browser checklist (interrupt mid-chat; steer; progress on dq).

### Phase 3 — Context engineering & memory tiers (G5)
**Backend:** `context_assembler.py`, `summary` field + `summary/` endpoint, token
budgeting, RAG/KG retrieval feed.
**Frontend:** `#`-mentions in `AIInputBar`, per-turn token transparency.
**Gate:** pytest for assembler (budget respected, summary memoized, no cross-app leak);
smoke with live LLM for compaction.

### Phase 4 — Enterprise governance (G8)
**Backend:** `export/`, usage attribution to `LLMCallLog`, provenance metadata, shared
conversations + `ai:manage_console` gate on shared delete.
**Frontend:** export buttons, "why this answer" tooltip, usage rollup view.
**Gate:** pytest; `npm test`; verify.sh full; E2E journey update.

---

## 10. Explicit Non-Goals (defer, do not build now)

- **Autonomous multi-step agent orchestration** (Anthropic orchestrator-workers) —
  only after single-turn quality + streaming + interruption are proven. Carbon's
  engine already has the KG/planner; this doc does *not* expose autonomous mode.
- **Multi-user real-time collaboration** (shared-editing sessions) — Phase 4 ships
  read-only `visibility="shared"`; co-editing is a separate effort.
- **Redis-backed horizontal-scale generation registry** — in-process registry + durable
  `AIGeneration` row first; flag Redis when multi-worker streaming is needed.
- **pgvector** — out of scope; the engine's JSON-field vectors + ChromaDB degradation
  path stay as-is.
- **Screenshots / computer-use context** — rejected by Contract §11 in favor of
  `WorkspaceContext`; this doc doubles down on that decision.

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Streaming structured outputs is hard (JSON over SSE) | Emit `progress` events, not token deltas, for non-chat; single `done` carries the full structured result |
| Cancellation leaves partial rows | `status="stopped"` message persisted atomically; conversation never left `working` |
| Compaction is a hidden LLM cost | Cheap model + memoized by `last_summarized_message_id`; budget telemetry exposed |
| Frontend rewrite regresses existing behavior | Rewrite per-phase with the existing test suite (`npm test`) as a regression harness; browser checklist per phase |
| Breaking the AI Contract | All changes route through `CarbonIntelligence`; `context_assembler.py` owned by Carbon, not engine (§0.4) |
