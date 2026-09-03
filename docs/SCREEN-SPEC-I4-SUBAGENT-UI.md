# Screen Spec — Subagent Result Card + Progress (I4-F)
# Canonical per `.ai-toolkit/shared/frontend-ready.md` (RULE_29 — Frontend Definition of Ready).
# Consumed by TASKS.md Phase I4-F. A worker does NOT code this view before all 9 artifacts below are complete.

---

## Artifact 1 — User Story + Acceptance

**Story:** As an AI-workspace user, when I dispatch a named subagent for a complex read-only task,
I want to watch its individual progress nested under the parent task and see its result summary as
a distinct card in the task panel — so I know what each subagent did and what it found.

**Acceptance (Given/When/Then):**

- **Dispatch:** Given a conversation and a subagent `{name, brief}` (optionally `scope_restriction`),
  when I dispatch it, then `POST …/subagents/` returns the created subagent (`status="pending"`,
  `is_worker=true`) and the UI immediately shows a `SubagentResultCard` in the task panel.
- **Progress:** Given a dispatched subagent, when it runs, then the card reflects
  `pending → running → completed|failed` (via polling, no new SSE) with a status indicator.
- **Result:** Given `status="completed"`, then the card shows `name`, `scope_restriction` (if any),
  `result_summary` (first 200 chars) and an expandable `result_detail` (up to 2000 chars).
- **Failure:** Given `status="failed"`, then the card shows the `error` string (friendly, not a
  stack trace) with a distinct failed state.
- **Nested progress:** Given a conversation that dispatches subagents, then the task panel shows a
  `subagents` sub-list of nested items (each: name + status), never flattened into the run-steps
  list. Subagents are conversation-scoped (no step/plan link exists on `AISubagent`), so they nest
  under the panel's "Subagents" section — NOT under an individual `StepCard`.
- **Hydration:** Given a conversation with previously-dispatched subagents, then on open the panel
  lists them via `GET …/subagents/` (newest first).
- **No subagents:** Given a conversation with no subagents, then rendering is exactly as today
  (zero regression).

---

## Artifact 2 — Journey Map

```
Task panel (AITaskPanel) → dispatch subagent (name + brief [+ scope])
   └─ POST …/subagents/ → 201 subagent (pending, is_worker)
        └─ render SubagentResultCard in the "Subagents" section (optimistic "running")
             └─ poll GET …/subagents/{id}/ every ~1.5s
                  ├─ running  → status chip "Running" (spinner)
                  ├─ completed → result_summary + expandable result_detail
                  └─ failed    → error (friendly), failed chip
   On panel open → GET …/subagents/ hydrates the section (newest first)
```
Friction points: (1) poll must stop when the card unmounts or the subagent reaches a terminal
state (`completed`/`failed`) — never leak a setInterval; (2) poll interval ~1.5s, back off after
the first few polls; (3) no SSE exists for subagents — do NOT invent a stream seam (that is a
separate backend follow-up, out of I4-F scope).

---

## Artifact 3 — IA Placement

- **Result card:** in the task panel (`AITaskPanel.jsx`), inside a dedicated "Subagents" section,
  rendered by the NEW `SubagentResultCard.jsx`. **Not** in `AIMessageBubble`: I4-B stores the
  subagent result only on the `AISubagent` row and creates **no** `AIMessage` with
  `metadata.type === "subagent_result"` — so a conversation-message branch would never fire.
  (A future backend message seam is explicitly out of I4-F scope.)
- **Progress sub-list:** the "Subagents" section in `AITaskPanel.jsx` (below the run-steps /
  plan detail), not a new route. Each item is a full `SubagentResultCard` (name + status +
  result_summary + expandable detail), nested under the section heading.
- **Dispatch trigger:** a small "Dispatch subagent" affordance in `AITaskPanel` (ONE button/action
  in the selected-plan header actions row), opening a `SystemDialog` form (name + brief + optional
  scope). **Not** a new sidebar item.

---

## Artifact 4 — Composition Spec (reuse, never invent)

```
SubagentResultCard  (NEW: carbon-frontend/src/shell/SubagentResultCard.jsx)
 ├─ Header  → AIGeneratedBadge(label="Subagent") + name + status chip (StatusChip pattern)
 ├─ Scope   → (if scope_restriction) KeyValueOutput  ← StepOutputRenderer.jsx
 ├─ Summary → Typography (result_summary, markdown-safe)
 ├─ Detail  → collapsible (PlanningHeader-style) → result_detail (<pre dir="ltr"> if raw)
 └─ Error   → Alert (severity="error") when status==="failed"

AITaskPanel (Run tab, selected-plan detail)
 └─ "Subagents" section (below run steps / plan detail)
      ├─ header: section title + "Dispatch subagent" Button (opens SystemDialog form)
      └─ per subagent: <SubagentResultCard key={id} subagent={s} /> (nested, never flattened)
```

**Reuse audit (mandatory):**
- [x] Status chip = existing `AITaskPanel` `STEP_STATUS_ICON`/`StepStatusIcon` pattern
      (pending/running/completed/failed) — do NOT invent a new one.
- [x] Badge = `AIGeneratedBadge` (`src/shell/AIGeneratedBadge.jsx`).
- [x] Key/value + raw = `StepOutputRenderer.jsx` `KeyValueOutput`/`RawJson`.
- [x] Collapse = `PlanningHeader` pattern (Button + chevron + `aria-expanded`, default collapsed).
- [x] Dialog = `SystemDialog` (`src/components/SystemDialog.jsx`) — never raw Drawer.
- [x] Feedback = `useNotification().notify`/`notifyFromError` for dispatch errors.
- [x] API = `src/api/aiWorkspace.js` — add `dispatchSubagent` + `getSubagent` + `listSubagents`
      (via `apiFetch`, base `ai/workspace/`). No raw fetch.

---

## Artifact 5 — Complete State Matrix

### Page (SubagentResultCard — poll lifecycle)
| State | Rendering |
|-------|-----------|
| `idle` | Card rendered with initial `status` (pending) |
| `running` | Status chip "Running" + inline spinner (no result yet) |
| `completed` | result_summary + expandable result_detail |
| `failed` | `Alert` with `error` (friendly) |
| `partial` | *(n/a — single subagent card)* |
| `error` (poll failed) | Non-blocking "couldn't refresh status" note; keep last known state |

### Page (AITaskPanel sub-list)
| State | Rendering |
|-------|-----------|
| `empty` | No `subagents` → render exactly as today |
| `loaded` | Nested `SubagentResultCard`s under the "Subagents" section |
| `partial` | Per-subagent status (some running, some done) |

### Component (interaction)
| State | Where |
|-------|-------|
| `default/hover/focus/focus-visible` | dispatch button, detail toggle, status chips |
| `expanded/collapsed` | result_detail disclosure (default collapsed) |
| `submitting` | dispatch dialog button disabled + progress |
| `success` | toast on dispatch → card appears |
| `error` | dispatch failure toast (form preserved) |

---

## Artifact 6 — Data Contract

All via `apiFetch`, base `ai/workspace/` (mirror existing `aiWorkspace.js` `BASE = 'ai/workspace/'`).

| Op | Endpoint | Request | Response |
|----|----------|---------|----------|
| Dispatch | POST `conversations/{id}/subagents/` | `{ name, brief, scope_restriction?, tool_budget? }` | `201` `serialize_subagent` |
| Status | GET `conversations/{id}/subagents/{sub_id}/` | — | `serialize_subagent` |
| List | GET `conversations/{id}/subagents/` | — | `200` `[serialize_subagent, …]` (newest first) |

`serialize_subagent` (from `backend/ai/subagent_service.py`):
```jsonc
{
  "id", "parent_conversation_id", "name",
  "status": "pending"|"running"|"completed"|"failed",
  "is_worker": true,
  "scope_restriction": {},        // JSONField, {} when empty
  "tool_allowlist": [],           // JSONField, [] when empty
  "result_summary": str|null,     // first 200 chars
  "result_detail": str|null,      // first 2000 chars
  "error": str|null,
  "tokens_used": int, "latency_ms": float|null,
  "created_at": iso|null, "completed_at": iso|null
}
```

- **Transport decision (I4-F): POLL.** `dispatchSubagent` returns the pending subagent; the card
  then polls `getSubagent` every ~1.5s until `status ∈ {completed, failed}`. **No SSE** — subagent
  dispatch in I4-B is a `threading.Thread` single-shot `route_chat` with no stream; do NOT invent a
  push seam (future backend follow-up).
- `404` on status = subagent gone → show a terminal "not found" note and stop polling.
- `403` = CBAC-scoped (subagent belongs to another user) → show "not found" (do not leak existence).

---

## Artifact 7 — Accessibility (WCAG AA)

- [x] Status never color-alone: chip = icon + label ("Running"/"Completed"/"Failed").
- [x] Detail toggle keyboard-reachable + `aria-expanded`.
- [x] `result_detail` raw text `dir="ltr"` where it is code/pre.
- [x] Dispatch form: label tied to each field; errors via `Alert` (`role="alert"`).
- [x] Poll updates announced politely where meaningful (`aria-live="polite"` on status).

---

## Artifact 8 — Performance Envelope

- [x] Poll interval ~1.5s, **cleared** on unmount and on terminal status (no leaked timer).
- [x] Back off: after ~5 polls, stretch interval (e.g. 1.5s → 3s) to bound chatter.
- [x] `useMemo` for sub-list derivation; stable callbacks for dispatch handlers.
- [x] No new bundle weight (reuses `AIGeneratedBadge`/`StepOutputRenderer`/`SystemDialog`).
- [x] Card already lazy within the message list; no route split needed.

---

## Artifact 9 — i18n / RTL

- [x] New strings via `t()` (`useTranslation('ai')`): "Subagent", "Dispatch subagent", "Name",
      "Brief / instructions", "Scope restriction", "Running"/"Completed"/"Failed"/"Pending",
      "Result", "No output", "Couldn't refresh subagent status". Keys in BOTH `en` and `ar`
      `ai.json` (+ `shell.json` if the dispatch trigger lives there).
- [x] `dir="ltr"` on IDs/raw result_detail.
- [x] `node scripts/check-i18n-keys.js` → 0 missing keys.
- [x] Chevron/detail icons mirrored in RTL via `useLanguage().isRtl`.

---

## Anti-patterns (instant reject — do NOT ship these)

- Inventing an SSE/websocket seam for subagent progress (poll only — out of scope).
- Leaking a `setInterval` on unmount / terminal status.
- Rendering `error` as a stack trace; rendering raw ISO `created_at`.
- Raw `Drawer` instead of `SystemDialog` for dispatch.
- Flattening subagents into the run-steps list (must nest under the "Subagents" section).
- Hardcoded English strings not `t()`-wrapped.

*Source: `docs/SCREEN-SPEC-I4-SUBAGENT-UI.md` — authored by Master Architect under RULE_29.*
