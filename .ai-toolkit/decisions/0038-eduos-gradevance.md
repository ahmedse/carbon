# ADR 0038 — EduOS instance + GradeVance app + config engines

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** Master Architect (product naming lock with owner)
- **Area:** cross-cutting

## Context
ClearTurn ships one codebase as multiple instance brands (AASTMT, Nibras, medOS,
Tectona). Education assessment (GradeVance, LCT/Rubric) needs a permanent product
home. Working in the carbon monorepo while Nibras masters are active caused
confusion that GradeVance might live on Nibras. Tectona is the AI showcase, not
the education OS. Spelling variants (EdOS / Eduos / EduOS) risk registry drift.

## Decision
1. **Instance brand = EduOS** (locked spelling). Slug `eduos`. Canonical
   `eduos.clearturn.tech`. Parallel to medOS.
2. **Domain app = GradeVance** — **multi-domain** assessment + coaching (medicine
   OSCE/OSPE/case-based, articles, reflection, and other faculties via packs).
   Enabled on EduOS only (until an explicit future multi-instance enablement
   decision). The NAA academic-English reflective corpus is **first gold**, not
   product identity.
3. **Engines = config packs (plugins), not code forks:** LCT Semantics engine and
   Rubric Assessment engine (qualitative + quantitative/checklist), versioned
   YAML/JSON under domain packs / profile bindings. Binding key =
   `discipline × genre × level`. Later LCT dimensions and domain scorers are
   additional packs.
4. **Tectona** remains the **AI showcase instance** (Healthy + future AI apps).
   Pulse runs everywhere; Tectona hosts AI *products*.
5. **Nibras** remains GOFSCO ERP. Developing GradeVance in this repo is logistics
   only — not product placement on Nibras.
6. RBAC/CBAC roles inside GradeVance: Admin, Professor, Marker, Student, QA — not
   five separate apps.
7. **HITL + governed engine learning are mandatory product pillars.** Summative
   marks require human accountability. Expert edits promote into versioned
   TranslationDevices / RubricPacks / profiles (config intelligence), with κ/canary
   gates — never silent weight updates or silent cohort regrades. Closing the
   learning loop (ProposalMiner → bump → activate) is required for “engine
   intelligence,” not optional polish.

## Alternatives Considered
- **Host GradeVance on Nibras** — rejected: wrong customer domain; conflates ERP
  with education.
- **Host GradeVance on Tectona** — rejected: Tectona is AI showcase; education OS
  needs its own brand parallel to medOS.
- **Name EdOS / Eduos** — rejected: EduOS matches medOS casing and readability.
- **Hardcode LCT/rubric in Python per discipline** — rejected: violates
  config-first engine policy; prevents multi-discipline packs.

## Consequences
- **Positive:** crystal product-line map; procurement-ready naming; pluggable
  packs; masters can seat EduOS without touching Nibras tracks.
- **Negative / trade-off:** another brand/DB/Redis slot to operate (`eduos`).
- **Do NOT re-try:** enabling GradeVance on Nibras “for convenience”; renaming
  EduOS mid-flight without ADR supersession; shipping GradeVance as an
  Academic-English-only product; hardcoding medicine/English in app code instead
  of packs.

## References
- `docs/CLEARTURN-PLATFORM-ARCHITECTURE.md`
- `docs/eduos/GRADEVANCE-DESIGN.md`
- `docs/eduos/GRADEVANCE-PROFESSOR-JOURNEY.md`
- `docs/eduos/GRADEVANCE-PROFESSOR-LIFECYCLE.md`
- `carbon-frontend/src/brands/eduos.js`
- `backend/ai/engine/instances/eduos/instance.yaml`
- `.ai-toolkit/project.config.md` RULE_31 · RULE_32 · RULE_33
- Prior art: `ahmedse/gradevance2` + `gradevance2/raw/` NAA gold corpus
