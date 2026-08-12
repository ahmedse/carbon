# ADR 0006 — DQ Rules Are Standalone; Bindings Are Separate

- **Status:** Accepted
- **Date:** 2026-08-12
- **Deciders:** Master Architect
- **Area:** backend, frontend — cross-cutting

## Context

`DQRule` was always designed as a standalone entity — no FK to `DataTable` or `DataField`.
Binding happens through the `RuleFieldAssignment` M2M through table, which allows one rule
to apply to many tables and fields. The REST API supports creating rules without bindings
(`field_assignments_write` is `required=False`).

However, the v1 JSON `definition` schema (`rule_schema.py`) and the client-side mirror in
`RuleJsonEditor.jsx` both require `bindings` to be a **non-empty** list. This forces every
new rule to specify a table at creation time — conflating two separate concerns:

1. **Rule authoring** (what does this rule check? at the DQ Workspace)
2. **Rule assignment** (where does this rule apply? at the Data Product / table level)

## Decision

**DQ rules are authored standalone. Bindings are applied separately at the data product level.**

| Component | Change |
|-----------|--------|
| `backend/dq/rule_schema.py` | `bindings` becomes optional (empty or absent = standalone rule) |
| `frontend RuleJsonEditor.jsx` | `validateDefinitionClient()` removes non-empty bindings check |
| `frontend RuleJsonEditor.jsx` | `EMPTY_DEFINITION_TEMPLATE` drops `bindings` or inits as `[]` |
| `backend/dq/models.py` | No change — `DQRule.save()` doesn't touch bindings |
| `backend/dq/serializers.py` | No change — `field_assignments_write` already `required=False` |

**Rule JSON authoring upgrades to Monaco Editor** (Phase C) — replacing the plain `<textarea>`
with a professional code editor that provides syntax highlighting, bracket matching,
JSON Schema–driven autocomplete, and inline validation.

## Alternatives Considered

- **Keep bindings mandatory, add a "Standalone" pseudo-table** — rejected. Adds indirection.
  A standalone rule should just not have bindings.
- **Separate endpoint for binding** — deferred. `PATCH /dq/rules/{id}/` with
  `field_assignments_write` already handles binding. No new endpoint needed yet.
- **Form-based rule builder (dropdowns, not JSON)** — rejected for now. JSON-first authoring
  is more flexible and portable. Monaco Editor gives us the best of both worlds.

## Consequences

- **Positive:** Rules are reusable policies. Create once, bind to many tables later.
  Cleaner mental model matching Ataccama / Collibra / data governance platforms.
- **Negative / trade-off:** A standalone rule with zero bindings never executes (no table
  to run against). This is correct behavior — the rule isn't "active" until bound.
- **Do NOT re-try:** Making `bindings` required at the API level. The serializer already
  supports omitting them. Don't reintroduce the requirement.

## References

- `backend/dq/models.py` — `DQRule`, `RuleFieldAssignment`
- `backend/dq/rule_schema.py` — `validate_definition()` (line ~105: bindings check)
- `backend/dq/serializers.py` — `DQRuleSerializer` (line 100: `required=False`)
- `carbon-frontend/src/components/dq/RuleJsonEditor.jsx` — client validation + template
- `carbon-frontend/src/pages/dq/DQWorkspacePage.jsx` — Rule creation dialog
- `TASK-DQ-RULE-UNBIND.md` — phased execution plan
