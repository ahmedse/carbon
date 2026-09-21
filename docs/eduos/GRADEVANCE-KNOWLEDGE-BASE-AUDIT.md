# GradeVance Knowledge Base — External Audit Pack

**Purpose.** Self-contained briefing for an external model (Fable, Sol, or similar) to audit and critique GradeVance on EduOS — especially **Learn (student)**, and the **algorithms / AI methodologies** for segmentation, LCT coding, HITL learning, and trust gates.

**Audience.** A strong independent reviewer who has *not* seen the repo. This document is the source of truth for that review.

**Repo snapshot.** ClearTurn Carbon monorepo; EduOS brand (`DJANGO_BRAND=eduos`). Primary SoR: `backend/gradevance/`. Packs: `domain_packs/eduos/`. Design: `docs/eduos/`.

**How to use this pack.**  
1. Read §§1–8 end-to-end.  
2. Answer the **Audit charge** in §10 without assuming unstated claims.  
3. Flag inventions, overclaims, and methodological risks.  
4. Prefer concrete alternatives over generic “use ML.”  
5. For **UI/UX** (consistency, reproducibility, expectations, student ease) with **live screenshots**, see `docs/eduos/ux-audit/GRADEVANCE-LEARN-UIUX-AUDIT.md`.

---

## 0. One-sentence product

**GradeVance** is a multi-domain assessment and coaching application on **EduOS** (ClearTurn’s education operating system): measurement (LCT Semantics where enabled) precedes judgment (declarative rubrics); **HITL is mandatory for summative release**; formative coaching is **advisory** and watermarked; engine intelligence improves only via **versioned pack promotions**, never silent fine-tunes or silent cohort regrades.

---

## 1. Platform map

| Layer | Meaning |
|--------|---------|
| ClearTurn | Trust Platform + Pulse (agent) |
| EduOS | Education OS instance / brand |
| GradeVance | Assessment + coaching **domain app** (not Nibras HR, not Tectona factory) |

**One Django SoR**, three persona UIs:

| Surface | Routes | API | Who |
|---------|--------|-----|-----|
| **Learn** | `/learn` | `/carbon-api/gradevance/me/` | Student — “about me” |
| **Teach** | `/teach` | `/carbon-api/gradevance/` (course-scoped) | Professor / marker — “about my courses” |
| **GradeVance** (engine) | `/apps/gradevance` | `/carbon-api/gradevance/` | Packs, QA, proposals, LTI, a11y |

Roles are enrollment-scoped (Admin, Professor, Marker, Student, QA) — not five separate apps.

**Modes**

| Mode | Student sees | Release |
|------|----------------|---------|
| Formative | Coaching + wave (advisory watermark) | Soft; appeals allowed on finished runs |
| Summative | Bands withheld until release | HITL release ceremony |
| Calibration | Never student-facing | Gold / instrument trust |

**Invariant.** `discipline × genre × level` → TranslationDevice + RubricPack + AssignmentProfile. NAA Academic English reflection is **first gold**, not product identity. Medicine OSCE/CBL and article packs exist as **seeded drafts** until faculty-coded gold.

---

## 2. Learn (student) — deep dive

### 2.1 UX surfaces

| Path | Job |
|------|-----|
| `/learn` | Join by entry code; due soon; latest coaching |
| `/learn/assignments` | My published assignments by course |
| `/learn/assignments/:id` | Desk: draft, coach/analyze, submit, released result, appeal |
| `/learn/progress` | Self-only trajectory of waves/bands |

### 2.2 Student APIs (`/gradevance/me/`)

| Method | Path | Behavior |
|--------|------|----------|
| GET | `courses/` | Enrolled courses only |
| POST | `join/` | `{entry_code}` → student enrollment |
| GET | `assignments/` | Published; optional `?course=`; includes `my_status`, due dates |
| GET | `assignments/<uuid>/` | Detail |
| GET/POST | `submissions/` | Own only; POST `{assignment,text,analyze?}` may run pipeline |
| PATCH | `submissions/<uuid>/` | Draft autosave / submit; no revert submitted→draft |
| GET | `runs/<uuid>/` | Own run; **summative bands redacted until released** |
| GET | `progress/` | Wave + redacted bands for self |
| GET/POST | `appeals/` | Own appeals; formative/summative rules differ |
| POST | `appeals/<uuid>/withdraw/` | Withdraw open |

### 2.3 Trust rules on Learn

1. **Coaching ≠ tutor expert mark.** Watermark: advisory. Smoke checklist forbids claiming coaching equals faculty gold.
2. **Summative privacy.** Unreleased summative → `advisory_bands.withheld` / empty rubric scores for student.
3. **Scope.** Students never see other students’ runs or course-wide queues.
4. **Appeals.** Summative: released run required. Formative: finished run (`complete` / `needs_review`).

### 2.4 What Learn deliberately does *not* do

- No student-facing pack editing or ExpertEdit.
- No student-initiated pack bump / κ gate bypass.
- No silent re-analysis of released summative cohorts when packs bump.

---

## 3. Pack architecture (config-as-intelligence)

Root: `domain_packs/eduos/`

```
schemas/                 translation_device, rubric_pack, assignment_profile, gold_essay
engines/lct_semantics/   device.yaml + anchors + boundary_pairs + segmentation + held_out
engines/rubric/          rubric.yaml + bands + action_templates
profiles/                pin device + rubric + pipeline + hitl
gold/{naa,medicine,article}/
scripts/validate_packs.py
```

### 3.1 TranslationDevice (LCT)

- Declares **scale**: product default **Maton binary SG± × SD±**.
- Files: `anchors.yaml`, `boundary_pairs.yaml`, `segmentation.yaml`, `held_out.jsonl`.
- `reliability_gate`: e.g. min κ SG 0.6, SD soft 0.4; `held_out_status: expert_disjoint` (NAA) vs `seeded_draft` (medicine/article).
- Legacy `SG++`/`SG--` in some anchors **collapsed at load** to `SG+`/`SG-` (`lct_scale.canonicalize_sg`).

### 3.2 RubricPack

Declarative criteria, band descriptors, action templates (Strengths / Diagnosis / Action). Analytic for NAA; checklist/quantitative for OSCE-style packs.

### 3.3 AssignmentProfile

Pins device pack_path + version, rubric, pipeline flags (`lct_enabled`, stages, `coder`), HITL thresholds. Runtime may honor `Assignment.pipeline_config_snapshot`.

### 3.4 Activation rule

New intelligence becomes live for **new runs only** after: ExpertEdit → Proposal → Accept → Pack bump → Profile re-pin (draft assignments). **Never** silent regrade of released cohorts.

---

## 4. Measurement theory (LCT + Reflective Wave)

### 4.1 Maton Semantics (product coding)

| Code | Reflective Wave criteria label | Pedagogic gloss |
|------|--------------------------------|-----------------|
| **SG+** | specific / personal | Stronger semantic gravity — lived episode, first-person specifics |
| **SG-** | general | Weaker gravity — transferable claims, others’ examples, principles |
| **SD+** | reflective | Condensed evaluation / self-analysis / critical interpretation |
| **SD-** | descriptive | Report / depict / narrate without deeper evaluation |

Source of truth for wave criteria:  
`raw/gradevance2-audit/raw-deep/Legitimation Code Theory - Criteria for Reflective Waves.txt`  
(adapted from Maton & Chen, 2016).

### 4.2 Wave Y-axis = SG×SD quadrant (not gravity-only)

| Level (top→bottom) | Codes | Meaning |
|--------------------|-------|---------|
| **4** | SG+ / SD+ | specific + reflective |
| **3** | SG− / SD+ | general + reflective |
| **2** | SG+ / SD− | specific + descriptive |
| **1** | SG− / SD− | general + descriptive |

X-axis: **TIME / number of words** (cumulative segment end).  
Oscillation of the profile across segments is the “reflective wave.”

**Important consistency note for auditors.** Device YAML historically mentioned SG numeric for wave Y; **runtime wave Y is the quadrant 1–4** above. UI (`WaveChart`) labels rails with SG±/SD± codes.

### 4.3 Reflective stages (segmentation metadata)

Heuristic stage guess on segments: **WHAT** / **SO WHAT** / **NOW WHAT** via discourse cues — used for coaching/rubric features, not a substitute for SG/SD codes.

---

## 5. Algorithms & methodologies (implementation)

### 5.1 Pipeline entry

`FormativePipelineService.analyze_submission`:

1. Load AssignmentProfile (+ snapshot)
2. Normalize text
3. **`segment_text(policy)`**
4. **Code each segment** (coder registry; default `heuristic_anchor`)
5. **`build_wave`** → `profile_level` from SG×SD
6. **`score_rubric`** (heuristic bands / checklists + action templates)
7. Gate → ReviewItem if needed
8. Persist coaching (watermarked)

### 5.2 Segmentation (`segment_text`)

**Method class:** rule-based epistemic-move segmentation from pack policy — **not** neural sentence segmentation.

| Knob | Typical NAA |
|------|-------------|
| `min_words` | 8 |
| `max_words` | 60 |
| `target_median_words` | 25 |
| Discourse markers | e.g. `later`, `however`, `therefore`, `for example`, `thus`, `so I` |

**Algorithm sketch**

1. Tokenize on whitespace.
2. Grow chunks; soft-split when length ≥ target and (sentence punctuation **or** marker hit), or hard-split at `max_words`.
3. Merge trailing chunks shorter than `min_words`.
4. Assign `stage_guess` from marker lists.

**HITL override.** Expert can replace spans via `ExpertEdit` kind `segment_boundary` → rebuild segments + re-code + rebuild wave. Visual painter (continuous colored spans + click-to-split) in Teach.

**Calibration metric.** Span-overlap F1 (`segmentation_metrics.align_segment_f1`) of engine re-segmentation vs expert held-out spans — **separate from coding κ**.

**Limits (honest).** Marker-at-chunk-end logic is brittle; auto-segmenter often under-segments long essays. Demo `seed_wave10_demo` uses **expert spans** to guarantee a 10-move wave for UI demos.

### 5.3 Coding (`code_segment`)

**Method class:** retrieval-of-anchors + lexical heuristics; optional LLM assist with hard fallback.

**Step A — Anchors**

- For each dimension, score pack anchors: Jaccard(token sets) and containment; take max blend.
- **SG:** use anchor if score ≥ 0.5, or ≥ 0.25 **and** label agrees with heuristic.
- **SD:** use anchor if score ≥ 0.35.
- Evidence includes `anchor_id`, overlap, span, justification prose.

**Step B — Heuristics (if no trusted anchor)**

- **SG+ cues:** concrete episode phrases, first-person past action, “when I / for example / I spent / I completed…”.
- **SG− cues:** abstract/strategy framing (“principle”, “strategy”, “in general”, NOW WHAT without episode).
- **SD+ cues:** evaluation / realization / “not good enough” / critical / reflective framing.
- **SD− cues:** narrative routines, emotion report (“I feel…”) without condensed judgment.

Evidence includes matched cues + natural-language **justification** for Teach expand UI.

**Step C — Optional `llm_assist`**

- Gated by `GRADEVANCE_LLM_CODER_ENABLED` + Pulse sync.
- On failure → heuristic with `evidence.llm: unavailable_fallback_heuristic` and capped confidence.

**Canonicalization.** Labels forced into device level set; doubles collapse to ±.

### 5.4 Wave build

For each segment with SG/SD codes:

- `profile_level = f(SG, SD)` using §4.2 table.
- Point: `progress=end_word`, codes, text, move (up/down/flat vs previous level).
- Metrics: transitions, level range, stages present, segment count.

### 5.5 Rubric scoring

**Method class:** feature → band heuristics + keyword checklists (OSCE), not trained classifiers.

- Inputs: wave metrics (range, transitions, stages), word count bounds, checklist keyword hits.
- Outputs: criterion band/score, rationale, evidence_bindings.
- Coaching: Strengths / Diagnosis / Action from templates + wave diagnosis.

### 5.6 Release gate

- Formative: may auto-complete or open ReviewItem if mean confidence low or wave flat.
- Summative: always review path; publish blocked without Instrument Trust (below).

---

## 6. HITL & learning loop

### 6.1 ExpertEdit (append-only)

Kinds: `segment_boundary` | `lct_code` | `rubric_score` | `coaching` | `other`.  
API: `POST /gradevance/runs/<id>/edits/` with rationale required.

### 6.2 ProposalMiner

Clusters recent edits → draft `Proposal`:

| Edit kind | Proposal kind |
|-----------|---------------|
| `lct_code` | `anchor` |
| `segment_boundary` | `segmentation_policy` |
| `rubric_score` | `rubric_note` |
| `coaching` | `action_template` |

Professor: Propose → Accept → **Bump pack** → **Re-pin profile** (new runs / draft assignments only).

### 6.3 Segmentation promote path (recent)

1. Calibration shows weak Seg F1 essays.
2. Visual resegment → draft `segmentation_policy` proposal.
3. Accept → bump writes discourse markers into forked `segmentation.yaml`.
4. Re-pin profile for new assignments.

Pulse may call **`suggest_splits`** (draft cues only; never mutates SoR).

### 6.4 Instrument Trust

| Mechanism | Role |
|-----------|------|
| Cohen’s κ (SG, optional SD) | Coding agreement on held-out expert-presegmented atoms |
| Publish gate | Summative + LCT → canary + not `seeded_draft` + no held_out∩anchor circularity |
| Segmentation F1 | Boundary fidelity (separate from κ) |
| Band agreement | Adjacent-band soft metric for rubric |

**NAA:** `held_out_status: expert_disjoint` (post T2 fix; archived overlap file must not drive publish).  
**Medicine/article:** `seeded_draft` → summative publish **fail-closed**.

---

## 7. Pulse / AI role (locked)

Pulse on EduOS is **advisory**:

- Explain instruments, draft coaching language, triage notes, suggest split cues.
- **Must not:** release marks, publish packs, invent κ, auto-bump, silent regrade.

Domain tools (read-oriented): calibration, review queue, QA summary, proposals list, suggest_splits.

Coder LLM path is optional assist with mandatory heuristic fallback — not the SoR.

---

## 8. Teach surfaces tied to methodology

| Surface | Methodological role |
|---------|---------------------|
| Run workbench | LCT table + justification expand; rich SG×SD wave; ExpertEdit; Resegment painter |
| Calibration | Held-out κ + Seg F1 essays → propose segmentation_policy |
| Proposals | Accept / bump / re-pin governance |
| Marking queue | HITL review items |
| Progress (Learn) | Student-visible wave trajectory only for self |

---

## 9. Known gaps (do not paper over)

1. **No live PDF/docx parser in production pipeline** — Word/PDF are provenance/extraction sources.
2. **Heuristic coder + anchors**, not a trained sequence model; LLM path optional and fail-open to heuristic.
3. **Segmentation auto-policy is weak** on long essays; expert spans / painter close the gap.
4. **SD κ soft**; summative fail-closes primarily on **SG κ**.
5. **Medicine/article gold** still `seeded_draft` — do not claim expert agreement.
6. **Pack bump canary** can use synthetic labels in scaffold paths — auditors must verify production never accepts that silently.
7. **P2 learning loop PARTIAL** — miner→bump→repin exists; scheduled drift/bias jobs and prompt disambiguation injection may still be incomplete.
8. **LTI / VPAT** near but live LMS soak + formal VPAT TBD.
9. **Do not claim Learn coaching ≡ faculty marks.**

---

## 10. Audit charge (for Fable / Sol)

Please respond as a senior assessment-methodology + ML auditor. Structure your answer as:

### A. Verdict
Is this architecture **sound / sound-with-conditions / unsound** for (1) formative coaching, (2) summative release, (3) multi-domain expansion?

### B. Learn critique
- Privacy & redaction adequacy  
- Student mental model risks (wave vs grade)  
- Appeal / formative coaching failure modes  

### C. Algorithm critique
For each of **segmentation**, **SG/SD coding**, **wave quadrant**, **rubric heuristics**, **κ/F1 gates**:

- Method class (rules / retrieval / classical stats / LLM)  
- Failure modes on multilingual / short / gamed essays  
- What would be the **next responsible upgrade** (data, metrics, model) without breaking HITL/pack governance  

### D. HITL / learning-loop critique
Does ExpertEdit → Proposal → bump → re-pin actually compound intelligence, or only archive it? What is missing for a closed loop?

### E. Theory fidelity
Does the SG×SD Reflective Wave mapping match Maton & Chen / NAA criteria practice? Any mis-label risks (e.g. SG+ as “specific” vs “strong gravity” training confusion)?

### F. Overclaim detector
List any claims in this document that a vendor deck might overstate relative to the implementation honesty in §9.

### G. Priority roadmap
Top 7 changes ranked by **trust impact** for Learn + summative readiness (not shiny demos).

### H. Questions back to the team
≤10 sharp questions that require repo/prod evidence (κ numbers, canary config, encryption, LMS soak).

---

## 11. Appendix — key paths

| Area | Path |
|------|------|
| Design | `docs/eduos/GRADEVANCE-DESIGN.md` |
| Personas | `docs/eduos/GRADEVANCE-PERSONA-APPS.md` |
| Gold | `docs/eduos/GOLD-PROVENANCE.md` |
| Smoke Learn | `docs/eduos/SMOKE-LEARN-TRUST.md` |
| Wave criteria (raw) | `raw/gradevance2-audit/raw-deep/Legitimation Code Theory - Criteria for Reflective Waves.txt` |
| Pipeline | `backend/gradevance/services/pipeline.py` |
| LCT scale | `backend/gradevance/services/lct_scale.py` |
| Seg F1 | `backend/gradevance/services/segmentation_metrics.py` |
| Learning | `backend/gradevance/services/learning.py`, `pack_bump.py` |
| Learn API | `backend/gradevance/me_views.py`, `me_urls.py` |
| Pulse domain | `backend/ai/domain/gradevance.py` |
| Wave UI | `carbon-frontend/src/components/gradevance/WaveChart.jsx` |
| Resegment UI | `carbon-frontend/src/components/gradevance/SegmentationEditor.jsx` |
| Packs | `domain_packs/eduos/` |
| Wave-10 seed | `manage.py seed_wave10_demo` |

---

## 12. Appendix — glossary

| Term | Meaning here |
|------|----------------|
| SoR | System of Record (Django GradeVance) |
| HITL | Human-in-the-loop ExpertEdit + release |
| TranslationDevice | Versioned LCT coding instrument pack |
| Held-out | Expert gold not used as circular anchors |
| κ | Cohen’s kappa on coding agreement |
| Seg F1 | Boundary span-overlap F1 |
| Pulse | ClearTurn agent — advisory on EduOS |
| Profile re-pin | New AssignmentProfile version → new runs only |

---

*End of audit pack. Upload this file as-is to Fable/Sol; attach the Reflective Wave criteria TXT if the tool accepts a second file.*
