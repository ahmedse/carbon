# ADR 0037 — Modest global typography bump (compact readability)

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** Master Architect
- **Area:** frontend | cross-cutting
- **Updates:** `.ai-toolkit/shared/compact-ui.md`, `carbonTheme.js`, `themeTokens.js`

## Context

Carbon’s compact density (`fontSize: 10`, `htmlFontSize: 14`, body ~11px) was hard to
read on high-DPI / WSL displays while remaining intentional per `compact-ui.md`.
A consumer-scale redesign or per-page `sx` font overrides would violate RULE_8 and
the design-system constitution.

## Decision

Apply a **modest global readability bump (~+2px)** while keeping the compact enterprise
look. Update the theme, `FONT` tokens, sidebar contract, and `compact-ui.md` together.

| Axis | Before | After |
|------|--------|-------|
| `htmlFontSize` | 14 | **15** |
| `typography.fontSize` | 10 | **12** |
| CssBaseline body | 11px | **13px** |
| `body1` / `body2` | 0.75 / 0.6875 rem | **0.875 / 0.8125 rem** |
| Caption | 0.625rem | **0.75rem** |
| Sidebar label | 0.65rem | **0.75rem** |
| Sidebar group | 0.575rem | **0.6875rem** |
| Nav row height | 28px | **30px** |
| DataGrid | 0.65rem / row 36 | **0.75rem / row 40** |

RULE_8 unchanged: no ad-hoc page `fontSize` overrides — use variants / theme.

## Alternatives Considered

- **Comfortable density user toggle.** Deferred — more product surface; modest bump first.
- **Page-local font overrides.** Rejected — RULE_8 / design-system violation.

## Consequences

- **Positive:** Better readability system-wide; toolkit and theme stay aligned.
- **Negative / trade-off:** Slightly less information density per viewport.
- **Do NOT re-try:** Random `sx={{ fontSize }}` on feature pages to “fix” readability.

## References

- `.ai-toolkit/shared/compact-ui.md`
- `carbon-frontend/src/theme/carbonTheme.js`
- `carbon-frontend/src/theme/themeTokens.js`
- `carbon-frontend/src/shell/ShellSidebar.jsx`
