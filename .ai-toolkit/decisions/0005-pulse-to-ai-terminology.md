# 0005 — Terminology: "Pulse" → "AI"

**Date:** 2026-08-12
**Status:** Accepted
**Author:** Master Architect

## Context

The external AI/RAG system was internally codenamed "Pulse." This leaked into:
- User-facing labels (`Pulse NL Check`, `Pulse Suggestion`)
- Documentation, config keys (`PULSE_HOST`, `PULSE_API_KEY`), and code comments
- Architecture descriptions

Users don't know or care what "Pulse" is. They know "AI."

## Decision

**All user-facing and documentation references to "Pulse" become "AI."**

| Layer | Change |
|-------|--------|
| UI labels | `Pulse NL Check` → `AI NL Check`, `Pulse Suggestion` → `AI Suggestion` |
| ai-toolkit docs | `Pulse` → `AI provider` or `AI` |
| Config keys | **Keep as-is** for backward compatibility (`PULSE_HOST` etc.) — internal impl detail |
| Code comments | Replace `Pulse` with `AI provider` where it describes behavior |
| `project.config.md` | `ARCH_PULSE_*` keys → `ARCH_AI_*` keys (value semantics unchanged) |

## Rationale

- **User clarity:** "AI NL Check" tells the user what it does. "Pulse NL Check" is an implementation leak.
- **Vendor neutrality:** The AI provider is swappable (`AI_PROVIDER_CLASS`). Language should reflect that.
- **Consistency:** The architecture is already called "AI Heart." Extend that naming everywhere.

## Consequences

- `carbon-frontend/src/pages/dq/constants.js`: `RULE_TYPE_LABELS.nl_check` → `'AI NL Check'`, `JOB_TYPE_LABELS.nl_check` → `'AI NL Check'`, `JOB_TYPE_LABELS.suggest` → `'AI Suggestion'`
- `carbon-frontend/src/shell/StatusBar.jsx`: Tooltip `"Pulse (Ctrl+\\)"` → `"AI Copilot (Ctrl+\\)"`
- `carbon-frontend/src/shell/KeyboardShortcutsHelp.jsx`: `"Toggle Pulse Copilot"` → `"Toggle AI Copilot"`
- `.ai-toolkit/project.config.md`: `ARCH_PULSE_*` → `ARCH_AI_*`, `ARCH_SUPERSEDED` updated
- `.ai-toolkit/decisions/0005-pulse-to-ai-terminology.md`: This file

### Deferred (non-blocking)
- Component files (`PulsePane.jsx`, `pulseAuth.js`) — rename later, keep internal APIs working
- Env vars (`VITE_PULSE_HOST`) — keep for backward compat, add `VITE_AI_HOST` alias later
- Backend (`PulseService`, `PULSE_API_KEY`) — internal impl, no user impact
