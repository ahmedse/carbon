# Gold provenance — EduOS LCT / rubric expert corpus

**Status:** Frozen inventory (Instrument Trust T1) — 2026-09-19  
**Rule:** Word/PDF are **extraction sources only**. Runtime scoring never opens `.docx`/`.pdf`. Labels live in versioned JSON/JSONL under `domain_packs/eduos/`.

---

## External source of truth (not in carbon runtime)

Sibling repo `/home/ahmed/ws/gradevance2/raw/`:

| File | Role |
|------|------|
| Reflective writing - 2 cycles (ss writing and LCT visualisation).docx/.pdf | Student reflective waves + expert LCT visualisation (Cycle 1–2) |
| Legitimation Code Theory - Criteria for Reflective Waves.docx/.pdf | Expert criteria examples (Categories 1–4) used as **anchors** |
| Writing briefs for both Cycles.docx/.pdf | Assignment briefs → `gold/naa/writing_briefs.yaml` |
| FEEDBACK.docx/.pdf | Tutor feedback examples — **not** full rubric band sheets |

Prior audit docs (gradevance2/docs): `audit-sonnet-vs-expert-cycle1.md`, `lct-post-fix-comparison-report-v1.md`.

---

## What is frozen inside carbon

| Path | Provenance | Expert marks present |
|------|------------|----------------------|
| `gold/naa/AR-CYCLE1-18-week1.json` | Extracted from Reflective writing PDF (participant AR-CYCLE1-18 / ali) | SG wave + segments; **no** tutor rubric bands |
| `gold/naa/writing_briefs.yaml` | Summarized from Writing briefs docx | Briefs only |
| `engines/lct_semantics/naa_reflective_v1/anchors.yaml` | LCT Criteria doc Categories + AR-CYCLE1 S1–S3 | Anchor spans for coder |
| `engines/lct_semantics/naa_reflective_v1/held_out.jsonl` | **Disjoint test set** (Instrument Trust T2+) — IELTS-speaking, reading-routine, **AR-CYCLE1-03 (hani)** expert-coded; **not** AR-CYCLE1-18/ali | SG + SD per segment; `expert_rubric_bands` |
| `gold/naa/faculty_mark_sheet_cycle1_week1.json` | Reflective writing workbook Cycle1 Week 1/2 **Tutor’s mark** (TA/CC/Gr) | Real NAA tutor letter bands |
| `gold/naa/AR-CYCLE1-03-week1.json` | Reflective writing docx Cycle1 week1 + audit expert wave + tutor bands | SG+SD expert; tutor rubric |
| `engines/lct_semantics/naa_reflective_v1/held_out_legacy_overlap.jsonl` | Pre-T2 held_out (AR-CYCLE1-18) archived — **overlaps anchors**; do not use for publish gate | SG only |
| `gold/naa/provenance.json` | Machine-readable inventory of this freeze | — |

Medicine / article `held_out.jsonl` rows are **`gold_status: seeded_draft`** (Instrument Trust B4). Soft κ floors only; **summative publish is blocked** until promoted to expert (see `gold/medicine/provenance.json`, `gold/article/provenance.json`). Do not treat circular κ (held_out ∩ anchors) as expert agreement.

---

## B4 — Medicine / article seeded packs

| Pack | Status | Why not expert |
|------|--------|----------------|
| `medicine_cbl_v1` | **instrument_coded_disjoint** | Biliary + pneumonia held_out (disjoint); soft floors; not clinical faculty yet |
| `medicine_clinical_reflection_v1` | seeded_draft | OSCE test fixture, overlaps anchors |
| `article_argumentative_v1` | seeded_draft | Seeded sample; overlaps anchors |

**Promotion:** replace held_out with faculty-coded disjoint spans → set `reliability_gate.held_out_status: expert_disjoint` → document in provenance → re-run publish gate.

---

## Explicit gaps (honest)

1. **No live PDF parser** in FormativePipeline or CI.
2. **Rubric expert bands** — Cycle1 Week1 **tutor letter bands** frozen in `faculty_mark_sheet_cycle1_week1.json` (on AR-CYCLE1-03 held_out + ali gold). Synthetic held_out essays remain `dual_reviewed_soft`.
3. Pre-T2 NAA κ = 1.0 was **circular** (held_out ≈ anchors). Gate now uses disjoint held_out (≥3 essays including AR-CYCLE1-03/hani).
4. Circular AR-CYCLE1-18/ali retained only as **demo gold text** + archived overlap file.
5. **SD κ** — heuristic distinguishes emotion-report (SD−) from evaluation (SD+); soft floor 0.4; summative publish still fail-closes on **SG κ**.

---

## T4 — Faculty rubric-band protocol

**Schema:** `domain_packs/eduos/schemas/gold_essay.schema.json` → `expert_rubric_bands: { <criterion_id>: <band> }`.

**NAA analytic criteria** (`engines/rubric/naa_reflective_analytic_v1`):

| criterion_id | Bands |
|---|---|
| `task_achievement` | F…A |
| `coherence_cohesion` | F…A |
| `lexis_grammar_academic_style` | F…A |

**Coding steps**

1. Same essay text as held_out / gold JSON (never invent bands from LCT SG alone).
2. Faculty assigns one band per criterion; record `expert_rubric_meta` (`_coder`, `_date`, `_protocol`).
3. Agreement via `reliability.adjacent_band_agreement` (exact + adjacent) inside `gradevance_gold_eval` — **same stack**, not a parallel harness.
4. Publish gate: summative packs may require rubric agreement once N≥threshold; formative remains advisory watermark until then.
5. First set (2026-09-19): tutor sheet for Cycle1 week1 participants; held_out uses real tutor bands for `AR-CYCLE1-03-HANI`; synthetic essays stay `dual_reviewed_soft`.

**Do not** claim Learn marks match experts until independent faculty double-code lands.

---

## Extraction procedure (repeat when adding essays)

1. Open source PDF/docx in gradevance2/raw (human).
2. Copy full essay text + expert SG/SD segment labels into a new `held_out.jsonl` row **or** `gold/naa/*.json`.
3. Ensure no held_out segment `text` is a near-duplicate of any `anchors.yaml` `span_text` (pytest enforces).
4. Update this file + `provenance.json` with `source_path`, `expert`, `date`, `notes`.
5. Run `pytest gradevance/tests/test_held_out_kappa.py` and `manage.py gradevance_gold_eval`.
