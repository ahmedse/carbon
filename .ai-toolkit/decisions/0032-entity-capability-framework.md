# ADR-0032 — Entity Capability Framework (ECF)

**Date:** 2026-09-16  
**Status:** Accepted  
**Owner:** Master Architect  
**Supersedes:** ad-hoc entity remediation in ADR-0031  
**References:** ADR-0002 (command pattern), ADR-0016 (domain-app AI contract), ADR-0017 (instance.yaml seam), ADR-0031 (unified remediation plan)

---

## Context

Entity access is artisanal and unreliable. `list_employees` caps at 100/530 with no search filter; `get_employee` resolves only PK not employee_no; truncation is surfaced as ground truth producing confident false-negatives ("no such employee" over 100/530 rows); FK ids leak to users (position 170, org_unit 28); `basic_salary` is masked to `0.000` (false data) rather than "hidden"; "Kuwaiti" count returns two contradictory numbers depending on which field the model picks. Ten days of real user sessions prove the same failures recur with zero automated detection.

Root causes:
1. **Artisanal capabilities** — each entity gets bespoke, hand-authored tools; coverage is accidental.
2. **No contracts** — nothing at the boundary forbids existence claims over truncated sources, raw FK ids, or false masking.
3. **No eval flywheel** — failures are never captured as tests; the same bug survives indefinitely.

## Decision

Introduce the **Entity Capability Framework (ECF)**:

1. **Entity Registry** — declarative per-entity descriptor (identifiers, search fields with language/normalization, FK label resolvers, masking policy, canonical metric definitions). Lives in `instance.yaml` `entities:` block (ADR-0017) or contributed by `ai/domain/{app}.py` plugins (ADR-0016). Engine stays domain-neutral (RULE_20).

2. **Generic `resolve(entity_type, query)`** — one algorithm, descriptor-driven; complete-scan, bilingual-normalized (reuse `navigation.py` normalizer), fuzzy + transliteration-aware. Returns `match | disambiguate | grounded-none(searched N of N)`. Supersedes the partial `slug_resolution` + `_find_entity_config` paths which are folded into descriptors.

3. **Boundary contracts** — four invariants hooked into the command-boundary pipeline (ADR-0002): no-truncation-as-truth; label-resolution-always; honest-masking; grounded-refusal.

4. **Golden-eval CI gate** — every failure becomes a permanent golden test; CI blocks regression. Trajectory→correction auto-nominates new golden cases (MAPE-K feedback, Tier-1 auto-heal, Tier-2 propose-and-human-gate).

All new code ships behind `settings.ECF_ENABLED = False`. Cutover only after shadow-parity and golden-set fully green.

## Consequences

- **Positive:** Any new entity needs only a descriptor; contracts + evals apply automatically. Failures become fuel rather than recurrence.
- **Positive:** Fixes the canonical "Kuwaiti" / headcount inconsistency permanently via metric definitions.
- **Risk:** Adds a new module layer in `backend/ai/engine/cognition/entity/`. Mitigated by the flag-gated rollout.
- **Constraint:** Engine module (`backend/ai/engine/`) must never import host-domain apps; descriptor knowledge arrives via instance_config only.
