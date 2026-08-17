# SPRINT 18 — AI Workspace UX Polish (VSCode Copilot-inspired)

> **Author:** qa-validator (evidence-only)
> **Audience:** Master Architect (implementer)
> **Source of truth:** live Playwright session + `carbon-frontend/src/shell/{AIMessageBubble,AIConversationView,AIWorkspace,AIConversationTabs,AIInputBar}.jsx`
> **Status:** SPEC — awaiting implementation. Hand back to qa-validator for re-validation after.

---

## 1. North Star

The AI Workspace should feel like **VSCode Copilot Chat**: minimal, focused, *chic*.
Every pixel earns its place. Actions are **iconic and hover-revealed**, not always-on
button rows. No technical noise (raw ms / token counts) in the message stream.
Sessions are first-class, persistent, and organized — not a flat row of tabs.

---

## 2. Current pain points (evidence-grounded)

| # | Symptom | Root cause (file) |
|---|---------|-------------------|
| P1 | Bare **"3886ms"** chip under every AI reply | `AIMessageBubble.jsx` → `buildUsageLabel()` renders `model · tok · $ · ms`; when only `latency_ms` exists it shows a naked `3886ms` |
| P2 | **"You" bubble** has a `PersonIcon` + "You" caption, looks like a form, not a chat | `USER_BUBBLE_SX` + `META_SX` + `Icon = PersonIcon` in `AIMessageBubble.jsx` |
| P3 | **Every** AI reply shows 4 buttons (Accept/Reject/Correct/Promote) — meaningless for a plain answer | `showFeedback = !isUser && (outcome \|\| onAccept \|\| onReject \|\| onCorrect \|\| onPromote)` — handlers always passed |
| P4 | **Bulky text buttons** in header: `Share` (GroupIcon + text), `Export` (DownloadIcon + text + caret), `Execute Mode ON/OFF` | `AIConversationView.jsx` (header Box ~L780) + `AIInputBar.jsx` (Execute Mode toggle) |
| P5 | **"Archived (0)"** always surfaced as a toggle button even when empty | `AIWorkspace.jsx` → `Archived ({archivedIds.length})` button ~L494 |
| P6 | **No session organization**: flat MUI `Tabs`, no datetime grouping, no expand/collapse, no counts/type icons | `AIConversationTabs.jsx` |
| P7 | **No copy / retry / stop / model-picker** in the message stream or input bar | (stop exists only as a `Select` "Send mode" when working — `AIInputBar.jsx`) |
| P8 | Sessions live in **left tabs**, not a dedicated side panel with rename/delete/archive/pin on hover | rename/delete/archive/pin exist only in a per-tab `MoreVert` menu |

---

## 3. Design principles (non-negotiable)

1. **Minimal**: default view shows *content only*. Actions appear on hover.
2. **Iconic**: `IconButton` + tooltip for everything chrome; text buttons only for
   semantically meaningful actions (DQ "Accept rule", "Save Rule").
3. **Chic**: consistent 8px spacing grid, muted secondary colors, `borderRadius` 2,
   theme tokens only (`bgcolor: 'action.hover'`, `'text.secondary'`, etc. — **no raw hex/px**).
4. **Persistent**: every session/action survives reload (already backed by the
   `aiWorkspace` API — preserve it, just re-skin + re-organize).
5. **Accessible**: keep `aria-label` on every interactive control so E2E selectors
   stay stable (see §7 — I will re-verify selectors after this lands).

---

## 4. Work items

### A. Message bubbles (`AIMessageBubble.jsx`)

- **A1** — Remove `PersonIcon` + "You" caption from user bubble. User message =
  right-aligned, filled accent bubble, no label, no icon.
- **A2** — Remove `SmartToyIcon` + "AI" caption from assistant bubble (keep a
  subtle status chip **only** when `failed`→"Error" or `stopped`→"Interrupted").
- **A3** — Collapse the 4 feedback buttons into a **hover toolbar** (appears on
  hover of the assistant bubble): `ThumbUp` (accept), `ThumbDown` (reject),
  `ContentCopy` (copy — new), `MoreVert` (→ Correct / Promote). Keep the outcome
  chip ("Accepted"/"Rejected"/"Corrected") when set.
- **A4** — Move the usage chip (`3886ms` / tokens / cost) **out of the stream**:
  show it as a tooltip on a tiny `ⓘ`/`MoreVert` item, or a single muted caption
  revealed on hover. Never a naked `3886ms`.
- **A5** — Add a **copy** action (`navigator.clipboard.writeText(message.content)`)
  with a "Copied" toast.
- **A6** — Add **retry** (re-run the last user turn) for the *latest* assistant
  message only.
- **A7** — Keep structured cards (dq_suggestions / nl_rule_test / investigation /
  report / anomalies) but apply the same hover-reveal + iconic treatment to their
  chrome. DQ **Accept/Reject/Test live** stay explicit (meaningful actions), but
  tighten to icons + tooltip where space allows.

### B. Header actions (`AIConversationView.jsx`)

- **B1** — Replace text `Share` / `Export` buttons with `IconButton`s:
  - Share: `GroupIcon` (or `GroupAdd`) → toggles shared/private, tooltip "Share"/"Unshare".
  - Overflow `MoreVert` menu containing: **Export Markdown (.md)**, **Export JSON (.json)**, **Rename**, **Clear conversation**, **Archive**.
- **B2** — Move `Execute Mode` toggle to the header as a compact `Switch`/`IconButton`
  (Bolt icon, `aria-pressed`), **only rendered when the active conversation is a
  DQ context** (dq_suggest / nl_rule_test / investigate / anomaly), not always.
- **B3** — Add a **model/provider selector** in the header or input bar
  (e.g., a muted `Chip`/`Select`: "gpt-4o ▾" → POE models), persisted per-user.

### C. Session management (`AIWorkspace.jsx` + `AIConversationTabs.jsx`)

- **C1** — Replace flat `Tabs` with a **session list panel** (right side, or keep
  left but as a proper list). Each item shows: type icon, title, **relative
  datetime** (`formatDistanceToNow`), message/type badge, pinned indicator.
- **C2** — **Group sessions by time**: `Today` / `Yesterday` / `Previous 7 days` /
  `Older`, each group collapsible (expand/collapse chevron), state persisted.
- **C3** — **Hover actions** per item: rename, pin/unpin, archive/restore, delete
  — as inline icons or a `MoreVert` menu (reuse existing handlers).
- **C4** — **"Archived (N)"** button: hide entirely when `N === 0`; otherwise show
  as a muted filter chip (not a prominent toggle).
- **C5** — Clicking a session **restores context** (existing `activeId` behavior —
  keep). Visually indicate the active session.
- **C6** — Keep **persistence** (backend list/update/delete APIs unchanged).

### D. Input bar (`AIInputBar.jsx`)

- **D1** — Increase comfortable typing area: `minRows={1} maxRows={8}`, larger
  font/padding, `borderRadius 2`, focus ring via theme.
- **D2** — Convert the `Select` "Send mode" (queue/steer/stop) shown while working
  into a **Stop/Interrupt `IconButton`** (Square icon) that appears only while
  streaming, with a **retry** icon after completion.
- **D3** — Keep the mention picker (`#table` / `#field` / `#rule` / `#module`) as-is.
- **D4** — Enter=send / Shift+Enter=newline (already correct — preserve).

### E. Feedback & provenance

- **E1** — Keep the "Why this answer" provenance tooltip but as a small `ⓘ` icon
  (hover), not always-visible noise.
- **E2** — Follow-up question chips: keep, but render as subtle outlined chips
  with hover state (already close — minor polish).

---

## 5. Explicit non-goals (do NOT touch)

- **Backend bugs** found during QA are filed separately — NOT part of this sprint:
  - `AttributeError: '_DjangoSession' object has no attribute 'execute'` (Pulse
    agent/skills registries) — "Fan-out attempt failed" / "Skill search failed".
  - `Pipeline start user=None` despite authenticated user (possible §1 ScopeGuard issue).
  - Naive datetime on `LLMCallLog.created_at` (timezone anti-pattern).
  - Weak secrets `PULSE_SECRET_KEY` / `STUDIO_PASSWORD` = `change-me`.
- **No product behavior changes** to DQ validation, rule creation, or RBAC/CBAC logic.
- **No raw `fetch()`** — all API through `apiFetch` / existing `apiWorkspace` helpers.
- **No raw hex/px** — theme tokens only.

---

## 6. Definition of Done

- [ ] User bubble: no icon, no "You" label; right-aligned accent bubble.
- [ ] Assistant bubble: no "AI" label; status chip only on Error/Interrupted.
- [ ] Feedback: hover toolbar (thumb up/down, copy, …→Correct/Promote), outcome chip persists.
- [ ] Usage chip: not visible in stream by default (tooltip/menu only); no bare "3886ms".
- [ ] Header: Share/Export/Execute-Mode are icons; Export + secondary actions in `MoreVert` menu.
- [ ] Session panel: grouped (Today/Yesterday/7d/Older), collapsible, per-item hover actions, datetime shown.
- [ ] "Archived (0)" hidden when empty.
- [ ] Copy, retry, stop/interrupt, and model/provider selector all present.
- [ ] Execute Mode toggle only on DQ-context conversations.
- [ ] All state persistent across reload.
- [ ] `npm test -- --run`, `npm run lint`, `npm run build` green.

---

## 7. Hand-back to qa-validator

After implementation, hand back. I will:
1. Re-verify every `aria-label`/role used by `journey-11-ai-coworker-dq.spec.ts`
   and update selectors if changed.
2. Re-run the live browser walkthrough (login → chat → DQ suggest/accept →
   NL rule test → investigate) and confirm the new UX + no regressions.
3. Re-run the Playwright gate + regression sweep (`npm test`, `lint`, `build`).
