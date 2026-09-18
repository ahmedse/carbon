# Screen Specs — MOB Mobile Program (ADR-0035)

**RULE_29 gate.** Frontend Workers code only against this spec.  
**Owners:** Pulse (MOB-A/B/D), Nibras (MOB-C/E). Shared SystemDialog = Pulse lead.

Phone viewport: **375×812**. Breakpoint: `theme.breakpoints.down('sm')`. Desktop `md+` unchanged.

---

## Shared artifacts (all phases)

| # | Artifact | Content |
|---|----------|---------|
| 1 | Story | As a staff user on a phone, I can navigate and complete leave/approvals/chat without sideways page scroll or unusable crushed panes. |
| 2 | Journey | Open app → hamburger nav → ESS list (cards) → open item → fullScreen dialog → act → return. Pulse: open AI → fullscreen chat → list-first agent → optional graph modal. |
| 3 | IA | Shell chrome adapts under `sm`; ESS routes `/my`, `/my/leave`, `/my/requests`, `/team`; People admin secondary. |
| 6 | Data | No new APIs; existing my/team/people/ai contracts. |
| 7 | a11y | 40px+ targets under `sm`; focus trap in fullScreen dialogs; RTL mirrored. |
| 8 | Perf | No extra network; lists virtualize only if already present; graphs deferred to modal on `sm`. |
| 9 | i18n | EN+AR; use existing namespaces; no RULE_23 jargon. |

---

## MOB-A — Shell chrome (Pulse)

**Composition:** Header hamburger → temporary Drawer; hide ActivityBar rail; under `sm` Pulse/Notes = fullscreen Dialog/Drawer overlays; StatusBar overflow menu.

**States:** desktop pinned | mobile temporary open | mobile temporary closed | Pulse fullscreen open | Notes fullscreen open.

**Acceptance:** At 375px, main content width ≥300px with sidebar closed; no permanent 200px sidebar; no Allotment dual-pane.

---

## MOB-B — SystemDialog (Pulse)

**Composition:** Under `sm`, MUI Dialog `fullScreen`; title + scroll content + sticky actions; no drag handle / resize grip.

**States:** open desktop windowed | open mobile fullScreen | closed.

**Acceptance:** Leave request dialog usable at 375px without horizontal clip.

---

## MOB-C — ESS lists (Nibras)

**Composition:** `ResponsiveList` — `sm`: stacked cards (title, status chip, one meta); `md+`: existing Table.

**Screens:** RequestTable, TeamInbox, LeaveHistoryTable, MyDashboard leave/payslips/loans tables; WorkflowGraph vertical under `sm`.

**States:** empty | loading | rows | error (existing).

**Acceptance:** `/my`, `/my/requests`, `/team` completable without page-level H-scroll.

---

## MOB-D — Pulse AI (Pulse)

**Composition:** Single column under `sm`; sessions/context = bottom Drawer sheets; AgentRun list-first; graph fullscreen only; Envelope pie legend bottom.

**Acceptance:** Opening Pulse on phone does not crush editor; chat fills viewport.

---

## MOB-E — People admin (Nibras)

**Composition:** Employee detail header stacks under `sm`; dialogs fullScreen via SystemDialog; DataGrid keeps H-scroll with identity column flex.

**Acceptance:** Employee detail header does not overflow; create dialog fullScreen on phone.
