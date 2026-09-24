# ADR 0050 — Pulse core is domain-free; domains are self-contained, versioned packs

- **Status:** Proposed
- **Date:** 2026-09-24
- **Deciders:** Pulse Master
- **Area:** backend · domain_packs · eval

## Context

Pulse is a coworker for many domain apps (Nibras HRMS today; EduOS, Carbon, and future brands). ADR-0049 moved understanding into the model and routing into the catalog, but the engine still *knows HR*: measured on 2026-09-24, `backend/ai/engine` has **846 source lines** carrying host-domain vocabulary (leave, payslip, loan, GOSI, إجازة, قرض …) across 64 files, **281 module-level phrase tables**, and **11 brand-name literals**. None of this was metered; `harness_budget` counted only `re.compile`, which is why the 2026-09-24 Discuss→apply incident (a phrase allowlist deciding a turn) was invisible to the budget gate.

Packs exist (`domain_packs/nibras|eduos|carbon`) and ADR-0044 pins pack↔instance catalog parity, but packs have no manifest, no version, and nothing stops core from reaching into them by name.

## Decision

1. **Core is domain-free.** `backend/ai/engine/**` (turn pipeline, state, Decision, consent, surfaces, budget, ContextPack) must not carry host-domain vocabulary or brand names. Vocabulary lives in the pack: `instance.yaml` catalog (`description`, `not_for`, `examples`, `empty_render`), process YAML, `vocabulary.yaml`, and per-instance eval banks.
2. **A pack is self-contained and versioned.** `domain_packs/<id>/pack.yaml` declares `id` (== directory), integer `version ≥ 1`, `domain`, `instance`, `compat.engine`, and `owns:` paths that resolve inside the pack (only `banks` may name eval evidence). Core addresses packs through the registry by `id`, never by literal name.
3. **Three gates, all measured from the tree:**
   - `ai.eval.harness_budget` gains `routing_phrase_sets`, `domain_terms_in_core`, `brand_literals_in_core`. Ceilings ratchet down only (`PV2.1-budget-ceiling.json`).
   - `ai.eval.pack_contract --gate` fails on a missing/invalid manifest, duplicate id, or an `owns` path outside the pack.
   - `ai.eval.pulse_gauge --gate` is the ratchet: any budget meter above its previous snapshot, any ladder level regressing, or any pack violation fails. It writes `PV2-gauge-<date>.json` and appends to `PV2-gauge-series.json` (the trend the canvas renders).
4. **Intelligence is defined as two curves.** Engine meters trend to zero while per-instance behaviour (ladder, G5, G6, soak) holds. The gauge is instance-scoped; a second pack gets its own banks and its own column. The scorer reads live measurements and the newest evidence file, never a dated file pinned in code.
5. **Fixes land in the pack.** A failing transcript becomes a golden in that pack's banks and a change to catalog description / flow / Decision schema — never a new phrase table in core (ADR-0049 P11 extended with the new meters).

## Alternatives Considered

- **Keep vocabulary in core behind `*_i18n.py`** — rejected: relocation, not deletion; the meter counts i18n files on purpose.
- **Brand-specific engine forks** — rejected: one engine, many packs, or Pulse is not a coworker.
- **Version only `instance.yaml`** — rejected: processes, vocabulary and banks change together; the pack is the unit of release.

## Consequences

- **Positive:** portability is a number that must fall; a new brand is a pack plus banks, and the gauge shows whether Pulse understands it.
- **Negative / trade-off:** 846 lines of HR vocabulary in core is a multi-phase cleanup; until then the ceiling holds it flat and every PR that touches routing must lower it.
- **Do NOT re-try:** adding `"nibras"`/`"eduos"` literals in engine code; per-brand regex or phrase tables; scoring L6/L7 from a dated file.

## Rollout (2026-09-24)

| Step | Artefact | Result |
|---|---|---|
| Manifests | `domain_packs/{nibras,eduos,carbon}/pack.yaml` v1 | `pack_contract --gate` pass 3/3 |
| Meters | `harness_budget`: phrase 281 · domain 846 · brand 11 | ceiling ratcheted to measured |
| Gauge | `pulse_gauge --seed-history --write --gate` | first snapshot `PV2-gauge-2026-09-24.json`; series has 2026-09-23 history |
| Ladder | L6/L7 read newest G6 file and live budget | L6 partial (parity 0.946; `forced_call_misses` never produced — scorer defect, open), L7 partial (`re_compile` 61 > 60) |
| Incident golden | `ai/tests/test_plan_revision_state.py` | Discuss→apply is typed state + Agent handoff; apply allowlist deleted |

## References

- ADR-0044 (pack ↔ instance parity) · ADR-0046 · ADR-0047 · ADR-0049
- `backend/ai/eval/{harness_budget,pack_contract,pulse_gauge}.py`
- Canvas: Pulse 2.1 plan + principles registry (P15 · gauge section)
