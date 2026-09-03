# ADR-0027 — Governed lookups are FK to `ReferenceValue` (drop the code string)

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** Master Architect
- **Area:** backend — `people` + `mdm` (cross-app reference governance)

## Context

The Trust Platform has a governed reference-data core (`mdm.ReferenceSet` +
`mdm.ReferenceValue` with steward, domain, version, lifecycle, and temporal
validity). The `people` domain routes only 4 fields through it, and does so as
plain `CharField`s storing a code string validated at write-time by
`_validate_reference_code()`. Many other metadata fields are free-text
CharFields or hardcoded `choices` — several duplicating reference sets that
already exist (`gender`, `rotation_pattern`, `leave_type`, `benefit_category`).

A string code gives no referential integrity, no temporal binding, no governance
lineage, and silently accepts drift. The correct enterprise pattern is a real
foreign key to the governed value.

## Decision

Every governed lookup on a `people` record becomes a **`ForeignKey` to
`mdm.ReferenceValue`**. The `*_code` CharFields are **removed**, not mirrored as
denormalized strings.

- **Write:** record stores the `ReferenceValue` PK; the `code` is resolved via join.
- **Read:** serializers expose `{ id, code, label, set }` via a single shared
  `GovernedValueField` (one implementation, reused by all 17 governed fields).
- **Delete:** `on_delete=PROTECT` — governed values in use are deprecated/archived
  via `transition_to()`, never deleted (preserves bitemporal history).
- **Temporal:** the FK pins to a specific `ReferenceValue` row, so historical
  records keep their value after the set evolves.

## Alternatives Considered

- **FK + denormalized code mirror (hybrid)** — rejected: the mirror is a second
  source of truth that can drift and must be reconciled by a DQ rule; FK-only
  removes the drift surface entirely. The code is one join away.
- **Code-only + tightened validation (no schema change)** — rejected: still no
  referential integrity and no temporal binding; the four weaknesses remain.

## Consequences

- **Positive:** referential integrity, bitemporal correctness, governance lineage,
  no drift surface.
- **Negative / trade-off:** a schema migration + read-shape change; every consumer
  (frontend, exports, AI lineage) must read the nested value. One join per field is
  cheap and `select_related`-able.

## Related

- Canonical spec: `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md`
- `TASKS.md` Phases NIR-5A / NIR-5B / NIR-5C (backend) and NIR-5D (frontend).
