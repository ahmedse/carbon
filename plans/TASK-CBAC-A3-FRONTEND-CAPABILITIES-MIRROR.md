# TASK-CBAC-A3 — Frontend capabilities mirror: evidence caps

> **Status**: ⏸️ OPEN
> **Type**: Report-only task card (documented, NOT changed in swap commit)
> **Depends on**: TASK-CBAC-TRUST-CORE-SWAP (committed `cc196da`)
> **Owner**: Frontend dev
> **Opened**: 2026-08-11 (QA verification, deviation #7)

## Problem Statement

Backend `backend/accounts/capabilities.py` now defines and grants **EVIDENCE_VIEW /
EVIDENCE_MANAGE** capabilities (DD-2/DD-3), and trust-core views declare them
(`evidence:view`, `evidence:manage` — see `backend/evidence/views.py`).

The frontend capability mirror `carbon-frontend/src/capabilities.js` declares catalog,
dq, mdm, connections, importexport, dataschema caps — but **no evidence caps**.

Current frontend mirror (excerpt):

```js
// ── DQ ─────────────────────────────────────────────────────────────
export const DQ_VIEW         = 'dq:view';
export const DQ_MANAGE_RULES = 'dq:manage_rules';
// ── MDM ────────────────────────────────────────────────────────────
export const MDM_VIEW   = 'mdm:view';
export const MDM_MANAGE = 'mdm:manage';
// ... no EVIDENCE section
```

## Impact

- Frontend `can(user, action, resource, ctx)` / `hasCap` logic cannot reference
  `EVIDENCE_VIEW`/`EVIDENCE_MANAGE` constants (they don't exist).
- Evidence UI gating must either hardcode strings (bad) or is missing capability-aware
  gating entirely.
- The `cbac.test.jsx` mirror-consistency test may not cover evidence caps.

## Work Items

- [ ] Add evidence capability constants to `carbon-frontend/src/capabilities.js`:
      `EVIDENCE_VIEW = 'evidence:view'`, `EVIDENCE_MANAGE = 'evidence:manage'`
- [ ] Add to IMPLIES map if the backend defines implications for evidence caps
      (verify against `backend/accounts/capabilities.py` IMPLIES dict).
- [ ] Map evidence route(s) to `EVIDENCE_VIEW` in the route→capability mapping
      (see `/evidence` route in capabilities.js / authz.js).
- [ ] Mirror-consistency test: extend `carbon-frontend/src/__tests__/cbac.test.jsx`
      (or equivalent) to assert evidence caps exist and mirror backend keys exactly.
- [ ] Verify against backend truth: keys must match `Capability.key` strings
      (single source of truth = `backend/accounts/capabilities.py`).

## Constraints

- **Report-only in this card**: no backend changes.
- Keys must be string-identical to backend `Capability.key` values.
- Follow existing section style in capabilities.js (── APP ── header, aligned `=`).

## DoD

- [ ] Evidence caps defined in frontend mirror
- [ ] Route gating uses the constants (no hardcoded `'evidence:…'` strings in components)
- [ ] Frontend tests pass (`npx vitest run`)
- [ ] No backend diff
