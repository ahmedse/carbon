# Sprint 28 — R5: Polish backlog (P2/P3 — F-11, F-12, F-15, F-16, F-18) + deferred P2s

**Owner:** Master Architect · **Status:** 📋 BACKLOG — dispatch when P1 remediation (R1–R4) lands
**Source:** `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md` findings register.

## A. Cheap wins (ready to dispatch, small)

| ID | Sev | Surface | File | Fix |
|----|-----|---------|------|-----|
| F-11 | P2 | frontend | `src/components/…/MarkdownMessage.jsx` `a` renderer | Intercept bare-hash hrefs (`#rules`) and route via the same navigation as `/`-prefixed hrefs; never open a blank external tab |
| F-12 | P2 | backend | workspace message save path | Bump conversation `last_message_at` (or `updated_at`) on every new message so the session list orders correctly |
| F-15 | P3 | frontend | `src/components/…/Breadcrumbs.jsx` `ROUTE_CONFIG` | Add `/admin/ai/*` entries so the trail shows "Home › Admin › AI › <Panel>" with correct `aria-current` |
| F-16 | P3 | frontend | theme + header IconButtons | Add a visible `focus-visible` outline (WCAG 2.4.7) — a single theme `focusVisible` override |
| F-18 | P3 | backend | usage `by_day` aggregation | Fill missing days (zero-filled) so "Last 7 days" always shows 7 entries |

Dispatch split (backend/frontend never share a phase):
- **R5-frontend** = F-11, F-15, F-16.
- **R5-backend** = F-12, F-18.

## B. Deferred P2s (larger / ambiguous — do NOT auto-dispatch)

| ID | Finding | Why deferred |
|----|---------|--------------|
| F-08 | `#table/#rule/#field/#module` mentions never resolve to entity ids (`TODO(mentions)` in `AIConversationView.jsx:272-274`) | Needs an entity-resolution design decision |
| F-09 | Follow-up suggestion chips dead code (`_finalize_response`/`_generate_follow_ups`, 0 call sites) | Either wire it or delete it — needs a product call |
| F-10 | "Remember X" accepted but no durable fact (`learn_fact` contract violation) | Overlaps Phase 23-A memory work; triage against that |
| F-13 | Provenance payload mismatch (`T3_retrieval=0` vs ledger chunks=1) | Needs provenance-schema audit |
| F-14 | `dq.validate` clarifies instead of executes (critic veto on `tool_calls=0`) | Same critic family as F-04 — revisit after R2 lands |
| F-17 | Provenance tooltip missing Conversation/App lines | Cosmetic; fold into F-13 pass |
| F-19/F-20 | Workspace RBAC design note + hygiene (raw fetch/print) | Document, don't code, until a role matrix is ratified |

## Verification Gate (per sub-task)
Backend: `manage.py check` + `python -m pytest <app> -q`. Frontend: `npm run lint` + `npx vitest run <tests>` + `npm run build`.

## Notes for the Master
- Revisit F-14 **after** R2 (empty replies) — they share the critic-veto-on-tool-turn root cause.
- F-08/F-09/F-10 are candidates for a future "mentions & memory contract" sprint, not patches.
