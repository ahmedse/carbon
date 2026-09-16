# Sprint 21 — W2-A: Agent/MCP/Tools/Logs surface + execution panel + verbosity + abort

**Owner:** Master Architect · **Worker Role:** frontend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch (after W1-A)
**Design:** `docs/DESIGN_AI_WORKSTATION.md` §2.1, §2.2, §2.4, §2.5
**Master index:** `TASKS.md` Phase W2-A (lines 1873–1938)
**Depends on:** W1-A (execution SSE `actions/stream` + enriched catalog `getSettings`).

## Goal
Add ONE "Agent" activity-bar icon that opens a grouped surface (Agents / MCP / Tools / Logs
internal tabs) with an interactive **clustered execution timeline** (run a tool/agent action,
see progress, toggle verbosity, abort) — not four flat icons.

## Current state (verified facts — do NOT re-discover)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — activity bar ~lines 635–660 with 7 icons
  (sessions/context/investigate/artifacts/usage/memory/settings) + New chat; `activePanel`
  state; `togglePanel`. `MEMORY_TAB_KEY='carbon-ai-memory-tab'` and the grouped Memory
  surface (internal MUI `<Tabs>`) is the precedent for grouped surfaces (RULE_17).
- `carbon-frontend/src/api/aiWorkspace.js` — `streamJsonPost(token, path, body, {onChunk,
  onProgress, onDone, onStopped, onError})` parses `chunk|progress|done|stopped|error`.
  `stopGeneration`, `confirmToolExecution`, `declineToolExecution` already exist.
- `carbon-frontend/src/api/aiPulse.js` — `getSettings(token)` → `ai/pulse/settings/` already
  returns `{mcp_servers, tools_catalog, agents}` (W1-A enriches with `parameters`).
- `carbon-frontend/src/shell/PulseDataPanel.jsx` (in `pages/admin/ai/`) — read-only generic
  panel using `getPulseData` + `PulseDetailDrawer`; reuse this pattern for the Logs tab.
- `carbon-frontend/src/shell/LongContent.jsx` — `LONG_CONTENT_THRESHOLD=1600`,
  `COLLAPSE_MAX_HEIGHT=320`, "Show more/less" toggle.

## Files to Change
- `carbon-frontend/src/shell/AIAgentPanel.jsx` — ADD (Agents/MCP/Tools/Logs internal `<Tabs>`,
  tab persisted via `localStorage` key `carbon-ai-agent-tab`).
- `carbon-frontend/src/shell/AIActionRunner.jsx` — ADD (clustered streaming timeline: turn
  cluster → collapsible step cards, verbosity Select, Stop button).
- `carbon-frontend/src/api/aiWorkspace.js` — MODIFY: `runActionStream(...)` wrapper.
- `carbon-frontend/src/shell/AIWorkspace.jsx` — MODIFY: one "Agent" activity-bar icon (hub
  icon, e.g. `HubOutlined`) opening `AIAgentPanel`; do NOT add 4 flat icons.
- `carbon-frontend/src/__tests__/AIAgentPanel.test.jsx` — ADD.

## Tasks

### 1. One icon, four tabs (RULE_17)
`AIAgentPanel` renders four internal `<Tabs>`:
- **Agents** — list from `getSettings().agents` (id/name/role/tool_set), select + "Run".
- **MCP** — servers + tools from `getSettings().mcp_servers` (read-only).
- **Tools** — built-ins from `getSettings().tools_catalog` (name/description/kind/
  requires_confirmation/parameters), select + "Run" with an args form.
- **Logs** — `ToolExecution` + `LLMCallLog` timeline (reuse `getPulseData(token,'tools')` /
  `getPulseData(token,'logs')`), expandable JSON in a `PulseDetailDrawer`-style row.

### 2. `runActionStream` wrapper
Add to `aiWorkspace.js` a `runActionStream(token, conversationId, {action_type, tool?, agent?,
args, verbosity}, handlers)` that reuses a frame parser extended for the clustered frames.
It must deliver `onTurnStart`, `onToolStart`, `onToolArg`, `onToolResult`, `onToolEnd`,
`onTurnEnd`, `onDone`, `onStopped`, `onError`. Do NOT fork `streamJsonPost` for auth/refresh —
share its auth + SSE-read loop, or extract a reusable frame-dispatch helper.

### 3. Clustered timeline (design §2.5 — no flat wall)
`AIActionRunner` nests frames by `turn_id`/`step_id`:
- A **turn cluster** = one collapsible group header: "Working…" → "Finished · N tools" or
  "Stopped by you". Collapsing the group collapses the whole run to one line.
- Each **step** = its own collapsible card (status icon + tool name + status chip), with
  args/result body expandable. Append frames incrementally (do not re-render the whole
  transcript; use a stable keyed list per step).
- `verbosity` (Concise/Full Select) only sets default expansion — every card stays
  individually toggleable.
- Wide output (JSON/terminal/tables) scrolls on X **inside** its card; never widen the page.

### 4. Stop
- **Stop** button → `stopGeneration(token, conversationId)`. The run flips to `stopped`,
  shows "Stopped by you" **inside** the turn/step card (not an error banner), re-enables input.

### 5. Confirm gate + copy
- Host-mutating actions (`requires_confirmation`) render a confirm gate (RULE_21) reusing
  `confirmToolExecution`/`declineToolExecution` — never a silent run.
- Copy must be outcomes, not internals: "Running…", "Finished", "Stopped" — never engine
  class names. Theme tokens only (no raw hex/sx). MUI v7 Grid uses `<Grid size={{...}}>`.

## DO NOT TOUCH
- Backend files.
- `AIConversationView.jsx` / `AIMessageBubble.jsx` chat rendering (separate surface).

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIAgentPanel.test.jsx src/__tests__/AIWorkspace.shell.test.jsx
npm run build
```

## Hard rules
- `apiFetch` / `streamJsonPost` only (never raw `fetch`) — RULE_10. Theme tokens only — RULE_8.
- MUI v6 Grid `<Grid size={{...}}>` (never `<Grid item xs=...>`).

## Output contract
Append to `TASK-RESULTS.md`.

## Notes for the Master
- Acceptance: a 3-tool run collapses to a single "Finished · 3 tools" summary line, each
  tool toggles independently, and a stopped run shows "Stopped by you" inside the card —
  never a stuck spinner, never a red banner. Test the stop path explicitly.
