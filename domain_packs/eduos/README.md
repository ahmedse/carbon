# EduOS Domain Pack — GradeVance engines

Config-first packs for **GradeVance** on ClearTurn **EduOS**.

> Multi-domain assessment OS. NAA reflective English is **first gold**, not product
> identity. Medicine OSCE / OSPE / CBL / articles land as additional packs.
> HITL learning promotes corrections into versioned packs (RULE_32).

## Layout

```
domain_packs/eduos/
  schemas/                 # TranslationDevice, RubricPack, AssignmentProfile
  engines/
    lct_semantics/         # LCT Semantics devices (optional per profile)
    rubric/                # Analytic / checklist / hybrid rubrics
  profiles/                # Binds device + rubric + pipeline + HITL policy
  gold/                    # Acceptance oracles (waves, briefs)
  scripts/validate_packs.py
```

Bump scratch dirs (`*_bump_v*`) under `engines/lct_semantics/` are HITL draft forks —
do not treat as published gold; prune when stale.

## Validate

```bash
.venv/bin/python domain_packs/eduos/scripts/validate_packs.py
```

## Profiles

| Profile | Status | Role |
|---------|--------|------|
| `naa_cycle1_exam_prep` | validated | Formative NAA reflective |
| `naa_cycle1_calibration` | validated | Calibration + `gold_oracle` coder |
| `medicine_osce_abdominal` | draft | Hybrid OSCE checklist + LCT |
| `medicine_ospe_urinalysis` | draft | Checklist-only (LCT off) |
| `medicine_cbl_appendicitis` | draft | CBL analytic + LCT |
| `article_generic_formative` | draft | Article Semantics + analytic rubric |

## Devices / rubrics

| Pack | Status |
|------|--------|
| `lct_semantics/naa_reflective_v1` | validated |
| `lct_semantics/medicine_clinical_reflection_v1` | draft (anchors + held_out seeded) |
| `lct_semantics/medicine_cbl_v1` | draft |
| `lct_semantics/article_argumentative_v1` | draft |
| `rubric/naa_reflective_analytic_v1` | validated |
| `rubric/medicine_osce_abdominal_v1` | draft |
| `rubric/medicine_ospe_urinalysis_v1` | draft |
| `rubric/medicine_cbl_analytic_v1` | draft |
| `rubric/article_analytic_generic_v1` | draft |

## Binding key

`discipline × genre × level` → device (optional) + rubric + pipeline.
LCT can be disabled for checklist-only stations; HITL learning still applies.
