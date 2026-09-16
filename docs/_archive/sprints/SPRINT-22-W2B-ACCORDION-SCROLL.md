# Sprint 22 — W2-B: Past-chat accordion + scroll containment

**Owner:** Master Architect · **Worker Role:** frontend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch (independent — can run anytime)
**Design:** `docs/DESIGN_AI_WORKSTATION.md` §2.4
**Master index:** `TASKS.md` Phase W2-B (lines 1940–1981)
**Depends on:** none (independent).

## Goal
Collapse the past-chat list into an **accordion** (group headers toggle collapse/expand) and
contain scrolling so the message list scrolls independently of the fixed header/input, with
wide content scrolling horizontally inside its card.

## Current state (verified facts — do NOT re-discover)
- `carbon-frontend/src/shell/AIConversationTabs.jsx` — grouped session list (Today/7d/Older).
- `carbon-frontend/src/shell/AIWorkspace.jsx` — drawer + pane layout.
- `carbon-frontend/src/shell/AIConversationView.jsx` — message list render.
- `carbon-frontend/src/shell/LongContent.jsx` — existing long-output container
  (`LONG_CONTENT_THRESHOLD=1600`, `COLLAPSE_MAX_HEIGHT=320`, Show more/less).

## Files to Change
- `carbon-frontend/src/shell/AIConversationTabs.jsx` — MODIFY: collapsible accordion groups
  (header toggle + per-item inline expand).
- `carbon-frontend/src/shell/AIConversationView.jsx` — MODIFY: message list gets its own
  vertical scroll container (independent of header/input).
- `carbon-frontend/src/shell/LongContent.jsx` — MODIFY: `overflow:auto` X for wide
  JSON/terminal/table content.
- `carbon-frontend/src/__tests__/AIConversationTabs.accordion.test.jsx` — ADD.

## Tasks
1. **Accordion**: each group (Today/7d/Older) gets a header toggle to collapse/expand its
   list; per-item inline expand still works when the group is expanded. Collapse state
   persisted via `localStorage` key `carbon-ai-accordion-{group}`. Long lists virtualized.
2. **Scroll containment**: message list = one vertical scroll region; input bar + header stay
   fixed (do not scroll with the list).
3. **Wide content**: JSON/terminal/table output scrolls horizontally inside its card —
   never widen the page.

## DO NOT TOUCH
- Backend files.
- `AIInputBar.jsx` growth behaviour (Phase 23-C).

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIConversationTabs.accordion.test.jsx
npm run build
```

## Hard rules
- Theme tokens only (RULE_8). MUI v6 Grid `<Grid size={{...}}>`. `apiFetch` only (RULE_10).

## Output contract
Append to `TASK-RESULTS.md`.

## Notes for the Master
- Acceptance: collapsed group persists across reload (localStorage), the message list scrolls
  under a fixed header/input, and wide content never widens the viewport.
