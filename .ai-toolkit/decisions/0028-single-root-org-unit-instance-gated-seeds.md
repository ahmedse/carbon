# ADR-0028 — Single root OrgUnit = deployment anchor; seeds are instance-gated

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** Master Architect
- **Area:** backend + frontend — `mdm` org scoping

## Context

`mdm.OrgUnit` is one global self-referencing tree (no tenant field — by design,
RULE_1 / ADR-0015 "one deployment = one organisation"). But two independent root
trees are seeded into the same table: `seed_aastmt_org.py` (root `AAST`) and
`seed_gofsco_org.py` (root `GOFSCO`), both `parent=None`. `OrgUnitViewSet` lets a
global admin see the entire table, and `fetchOrgUnits` returns the whole flat
list — so the AASTMT deployment shows GOFSCO's tree in its org-unit dropdowns.
Two organisations' trees mingle.

## Decision

1. **One deployment = one root `OrgUnit`** — the tenant anchor. Exactly one active
   `parent=None` unit per deployment; every other unit descends from it.
2. **No `tenant_id`** anywhere (RULE_1). Isolation stays the deployment/database
   boundary (ADR-0015).
3. **Seeds are instance-gated** on `settings.INSTANCE_NAME`
   (`DJANGO_INSTANCE_NAME`) / `DJANGO_BRAND`. `seed_aastmt_org` runs only on the
   AASTMT instance; `seed_gofsco_org` only on GOFSCO. They never both run on one DB.
4. **All org-unit queries default to the deployment root subtree**
   (`get_descendant_ids(include_self=True)`), not the flat global list.

## Alternatives Considered

- **Single "Platform" root with AASTMT + GOFSCO as children in one DB** — rejected:
   violates the single-tenant cell model (ADR-0015); re-introduces in-DB mingling.
- **Re-introduce a `Tenant` model** — rejected: RULE_1 (tenant fully removed).

## Consequences

- **Positive:** provable per-org data isolation; no cross-org leakage in one DB;
  frontend dropdowns only ever show the deployment's own tree.
- **Negative / trade-off:** seeds and the org-unit API need a deployment-identity
  check; a single-root invariant must be enforced at model + seed + query layers.

## Related

- Canonical spec: `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md`
- `TASKS.md` Phases NIR-6A (backend) and NIR-6B (frontend).
