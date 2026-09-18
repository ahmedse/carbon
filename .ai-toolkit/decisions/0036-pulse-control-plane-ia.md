# ADR 0036 — Pulse Control Plane IA (admin remake)

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** Master Architect
- **Area:** frontend | cross-cutting
- **Extends:** ADR-0031 D8, ADR-0011 (Workspace = engage; Admin = manage/observe)
- **Plan:** `docs/pulse/PULSE-ADMIN-REMAKE.md`

## Context

`/admin/ai/*` grew into a ~29-item panel farm (noun inventory). Eight surfaces are thin
`PulseDataPanel` read grids. Chat/workspace sat as peers of governance. ADR-0031 D8 called for
**7 screens + 6 roles**; the live console ignored that and sprawled. Steward jobs (contain, define,
evidence, learn) were not the IA.

## Decision

1. **Replace the panel farm with a Pulse Control Plane** of **six destinations**:
   - Command Center (`/admin/ai`)
   - Domain (`/admin/ai/domain`)
   - Assets (`/admin/ai/assets`)
   - Evidence (`/admin/ai/evidence`)
   - Learning (`/admin/ai/learning`)
   - Platform (`/admin/ai/platform`)
2. **D8 modules map into these destinations** (not seven flat peers plus twenty more):
   Process Registry + Policy + Conformance → Domain; Review Queue + Evals admission → Learning;
   Spend → Platform; Audit Explorer → Evidence.
3. **Engage ≠ govern.** Workspace and Conversations leave the Control Plane nav (routes may remain
   during migration; product home is the shell AI workspace).
4. **Freeze:** no new top-level `/admin/ai/<noun>` nav peers. New capability = tab or object page
   under one of the six, or an ADR exception.
5. **Legacy URLs redirect** via `pulseControlIa.js` for at least one release.
6. **`AI_VIEW_CONSOLE` never implies publish** (unchanged from D8).

## Alternatives Considered

- **Nav trim only (hide items, keep 29 routes as peers).** Rejected — preserves inventory theater.
- **Strict flat D8 seven screens as the only nav.** Rejected — omits Command Center and Assets;
  D8 modules still belong as depth inside Domain/Evidence/Learning/Platform.
- **Keep chat inside admin.** Rejected — violates ADR-0011 engage/observe split.

## Consequences

- **Positive:** Steward IA matches control-plane jobs; D8 honored as modules; redirects preserve
  bookmarks/e2e during remake; freeze stops further sprawl.
- **Negative / trade-off:** Phase 1 mounts existing panels in hubs (not yet deep object pages);
  Evidence/Assets write depth lands in later remake phases.
- **Do NOT re-try:** one sidebar link per engine module; counting panels as progress; fake
  dashboards; mining as authoritative without Learning admission.

## References

- `docs/pulse/PULSE-ADMIN-REMAKE.md`
- `carbon-frontend/src/pages/admin/ai/control/pulseControlIa.js`
- `docs/pulse/archive/PULSE-UNIFIED-REMEDIATION-PLAN.md` §2 (D8 target)
