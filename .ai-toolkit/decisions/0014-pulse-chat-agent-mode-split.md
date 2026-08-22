# ADR-0014 — Pulse Chat / Agent Mode Split

- **Status:** Accepted
- **Date:** 2026-08-22
- **Deciders:** Master Architect
- **Area:** frontend + backend (cross-cutting)

## Context

Pulse currently presents a single unified workspace where:
- Chat (Q&A) and agentic task execution share the same surface
- Mode is a small `Ask / Agent` toggle pill buried inside `AIInputBar`
- Users cannot tell from the UI what will or will not execute when they type
- The safety contract ("advisory only" vs "will execute with consent gates") is invisible
- The Tasks panel is hidden behind an activity-bar icon, equal weight to Sessions/Artifacts

This causes two real problems:
1. **Trust confusion** — users do not know whether sending a message might trigger an execution
2. **UX mismatch** — chat and agent workflows have completely different lifecycle shapes; forcing them into the same surface makes both worse

Evidence from top systems:
- GitHub Copilot: Chat vs Workspace (separate entry points)
- Cursor: Ask / Edit / Agent in the sidebar header — mode sets the UI shape
- Claude: Standard chat vs Computer Use — different safety contracts, different surfaces
- Devin / SWE-agent: pure agent, no mixed chat
- OpenAI Assistants API: Thread (chat) vs Run (agent) — separate lifecycle objects
- Temporal / Dagster: workflow canvas vs query console — separate layouts

Universal lesson: **mode is a workspace-level concern, not a composer-level concern.**
The mode sets the trust contract. The trust contract must be legible at all times.

## Decision

### 1. Mode is workspace-level, not composer-level

The `Ask / Agent` ToggleButton pill is removed from `AIInputBar`.
Instead, `AIWorkspaceHeader` gains two top-level mode buttons: `💬 Chat` and `🤖 Agent`.
Mode persists in `localStorage` under key `carbon-ai-mode`.

### 2. Chat mode = advisory, no side effects, conversational

Chat mode renders:
- `AIConversationView` as the main area (current default)
- Sessions drawer, Context drawer, Memory, Artifacts, Usage, Settings — unchanged
- Input bar shows only the `Ask` affordance (no plan/agent UI)
- Header shows: `💬 Chat — Answers and advice only. Nothing is created or changed.`
- Suggestions rail, investigate, artifacts — all still available

Chat mode never shows: Tasks panel, Plan approval UI, Step consent gates, Run stream, Audit ledger.

### 3. Agent mode = planning + execution + consent + audit, structured surface

Agent mode replaces the main content area with a 5-view agent workflow surface:

| View | Purpose | Route within agent mode |
|---|---|---|
| **Brief** | Outcome input + guided discovery conversation + plan proposal | default |
| **Plan** | Structured plan, phases, approval gate, edit/fork | after plan created |
| **Run** | Live execution graph, step stream, pause/stop | after approved + running |
| **Monitor** | Live metrics, token burn, step health | during/after run |
| **Results** | Artifacts, structured outputs, rerun/fork | after completion |
| **Audit** | Full provenance ledger, event timeline | always accessible |

The activity bar in agent mode shows only agent-relevant icons:
`📋 Tasks` (plan list) · `▶ Run` · `📊 Monitor` · `📦 Results` · `🔍 Audit`

### 4. The safety contract is always visible in the header

Header text changes with lifecycle state:

| State | Header text |
|---|---|
| Agent — idle | `🤖 Agent — Describe an outcome. The AI will plan before doing anything.` |
| Agent — plan pending approval | `🤖 Agent — Review the plan. Nothing runs until you approve.` |
| Agent — running | `🤖 Agent ● Running — Step N of M · Pause anytime.` |
| Agent — awaiting consent | `🤖 Agent ⏸ Approval needed — A step requires your confirmation.` |
| Agent — completed | `🤖 Agent ✓ Done — Results are ready.` |
| Chat | `💬 Chat — Answers and advice only. Nothing is created or changed.` |

### 5. Input bar adapts to mode

- Chat mode: composer with `Ask` placeholder, no agent affordances
- Agent mode — Brief view: discovery conversation input, natural language
- Agent mode — Run view: interrupt/steer input ("redirect the agent")
- Agent mode — other views: no input bar (they are read-only)

### 6. Discovery conversation is the Agent mode entry point (F-23)

When the user types in Agent mode Brief view, Pulse first engages in a
multi-turn discovery conversation to gather requirements, then proposes a
structured plan. This replaces the current "brief → immediate decompose" flow.

Backend: new `conversation_type = 'agent_brief'`; `PlansService.create_plan_with_discovery`
holds the conversation until the user confirms "generate plan".

## Alternatives Considered

- **Keep the pill toggle in the composer** — rejected; mode is invisible, safety contract is
  not legible, users routinely don't notice it.
- **Single surface, agent affordances gated by plan existence** — rejected; two different
  lifecycle shapes cannot share a clean surface without one degrading the other.
- **Separate routes (`/pulse/chat` vs `/pulse/agent`)** — rejected; Pulse is a panel/drawer,
  not a full page. Mode switch inside the header is the right scope. Deep links can be
  added later.

## Consequences

- **Positive:** safety contract is always legible; chat users never see agent complexity;
  agent users get a structured lifecycle view; both modes can evolve independently.
- **Negative / trade-off:** users with existing muscle memory for the activity-bar `Tasks`
  icon need to learn the top-level `Agent` button. Mitigated by the mode persisting.
- **Do NOT re-try:** putting mode back in the composer; merging agent views into the chat
  conversation list; making the safety contract text a tooltip instead of persistent header text.

## References

- `carbon-frontend/src/shell/AIWorkspace.jsx` — mode routing
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — mode buttons + contract text
- `carbon-frontend/src/shell/AIInputBar.jsx` — mode pill removal
- `carbon-frontend/src/shell/AITaskPanel.jsx` — agent mode views
- `backend/ai/plans_service.py` — discovery conversation + plan creation
- TASKS.md W5-A / W5-B / W5-C / W5-D / W5-E
- ADR-0013 (gap closure), ADR-0012 (enterprise graph canvas)
