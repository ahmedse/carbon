# Pulse Remediation — Pilot Process (P0-10)

> **Status:** DECISION · **Owner:** Master Architect · **Date:** 2026-09-13

## Decision

The pilot process for the Pulse remediation plan is **`dq.rule.release`**:

> validate (read-only) → review (human task) → publish (mutation, consent required) → verify.

This is the same pilot named in `PULSE-UNIFIED-REMEDIATION-PLAN.md` §6 (the 16-step demonstration).

## Rationale

- DQ rules are already the platform's most-governed entity: standalone rules exist (ADR-0006),
  release is a real human workflow today, and the host services for `validate`/`publish` already
  exist in `backend/dq/services.py`.
- The workflow exercises every Phase 3/4 primitive the plan must prove: read-only capability,
  a durable **human task** (review), a **mutation requiring consent** (publish), a **postcondition
  verification** (`active_revision == approved_revision`), and a natural place for approval grants
  + revision invalidation.
- It maps 1:1 onto the 16-step acceptance demonstration (§6 steps 1–15) without inventing new host
  services.

## Owner (separation of duties)

| Role | Named by | Notes |
|------|----------|-------|
| `process_owner` | platform admin (pending role wiring in P3-05b) | authors the definition + answers the interview kit |
| `publisher` | platform admin | reviews + publishes; must differ from `process_owner` |

Until P3-05b lands (role capabilities), these are **provisional** role bindings recorded in the
definition's `owner` field; the author≠publisher enforcement is a P3-05a registry test.

## Existing host endpoints (to be contracted in P3-02)

| Capability | Kind | Host service | Notes |
|-----------|------|--------------|-------|
| `dq.rule.validate` | read-only | `backend/dq/services.py` | no side effects |
| `dq.rule.review` | human task | human inbox (P3-09) | produces an approval grant |
| `dq.rule.publish` | mutation | `backend/dq/services.py` | consent required (RULE_21) |
| `dq.rule.active_revision_matches_approved_revision` | assertion/predicate | host predicate module (P3-02) | read-only |

## Gaps to close before P3-12 (pilot e2e)

- Capability contracts (`api_catalog.yaml` entries) with typed inputs/effects — P3-01/P3-02.
- Human Task Inbox + `ApprovalGrant` bound to exact revision — P3-06/P3-09.
- Durable run machine (9-state) + reconciliation for `outcome_unknown` — P3-07/P3-08.
- `process_interview.py` kit so the owner's answers fill the definition — P3-04.
