# ADR 0035 — Responsive Shell IA + Mobile Density Exceptions

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** Master Architect (Pulse); human override for full MOB program incl. Nibras ESS/People
- **Area:** frontend | cross-cutting

## Context
Carbon’s shell is a desktop IDE (pinned sidebar ~200px + activity bar 48px + Allotment Pulse pane). On ~375px phones the content strip is unusable. Compact-ui mandates dense desktop controls (24px buttons) that fail touch. ESS lists are tables-in-cards; SystemDialog minWidth 420 blocks leave/forms.

## Decision
1. **Breakpoint:** MUI defaults; phone = `theme.breakpoints.down('sm')` (&lt;600). Desktop compact density unchanged from `md` up.
2. **Under `sm`:** sidebar is **temporary** (hamburger); ActivityBar rail **hidden** (studio switcher in header overflow); Pulse and Notes are **fullscreen overlays** (no dual-pane Allotment); StatusBar collapses to overflow menu.
3. **Mobile density exceptions** live in `shared/compact-ui.md` §Mobile — touch targets ≥40px, dialogs `fullScreen`, no raw hex/px.
4. **ESS lists under `sm`:** card/list primary; tables remain `md+`.
5. **SystemDialog under `sm`:** `fullScreen`, no drag/resize.
6. **Agent run under `sm`:** list-first; graph via fullscreen only.
7. Seat ownership unchanged (RULE_30): Pulse = shell/AI; Nibras = my/team/people; SystemDialog shared via COMMS.

## Alternatives Considered
- **Separate mobile app / PWA** — rejected for now (cost); responsive shell first.
- **Always-overlay drawer on all breakpoints** — rejected; desktop users need pinned IDE chrome.
- **Scale compact density globally** — rejected; enterprise desktop density remains binding for `md+`.

## Consequences
- **Positive:** phones get usable content width; ESS P0 flows completable; toolkit density preserved on desktop.
- **Negative / trade-off:** two layout modes to maintain; localStorage `pinned` ignored under `sm`.
- **Do NOT re-try:** forcing Allotment dual-pane mins (280+320) on narrow viewports; inventing per-page mobile CSS outside compact-ui tokens.

## References
- Plan: Mobile-Friendly Frontend (MOB-0…E)
- `shared/compact-ui.md` §Mobile
- `carbon-frontend/src/shell/{Shell,useShellState,ActivityBar,AIWorkspace}.jsx`
- `carbon-frontend/src/components/SystemDialog.jsx`
