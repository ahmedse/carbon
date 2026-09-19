# GradeVance on EduOS — Comprehensive Design

**Status:** Accepted design (v1.1 — multi-domain scope lock)  
**Date:** 2026-09-18  
**Instance:** ClearTurn · **EduOS** (`eduos.clearturn.tech`)  
**App:** **GradeVance**  
**ADR:** [.ai-toolkit/decisions/0038-eduos-gradevance.md](../../.ai-toolkit/decisions/0038-eduos-gradevance.md)  
**Professor journey (vision):** [GRADEVANCE-PROFESSOR-JOURNEY.md](./GRADEVANCE-PROFESSOR-JOURNEY.md)  
**Professor lifecycle (UI/UX plan):** [GRADEVANCE-PROFESSOR-LIFECYCLE.md](./GRADEVANCE-PROFESSOR-LIFECYCLE.md)  
**First gold (not product identity):** `/home/ahmed/ws/gradevance2/raw/` NAA reflective pack  
**Also in prior art:** medicine OSCE/OSPE fixtures + medicine prompt variants in `ahmedse/gradevance2`  
**Prior art:** `ahmedse/gradevance2` (standalone FastAPI prototype — IP to port, not to fork as runtime)

---

## 0. One-line thesis

> **GradeVance** is EduOS’s **multi-domain** assessment + coaching app: config-pluggable
> engines that **measure** (LCT and related devices where theory applies), **judge**
> (declarative rubrics — qualitative and quantitative), and **coach** under **mandatory
> HITL** that **continuously improves engine intelligence** (anchors, devices, rubrics,
> disambiguations — governed, versioned, never silent) — for medicine (OSCE/OSPE/case-based),
> articles, and many other fields — never “academic English only,” never unaccountable
> auto-grades at summative stake.

---

## 1. Product placement (locked)

```
ClearTurn Trust Platform + Pulse
 └── Instance: EduOS          ← education OS (parallel to medOS)
      └── App: GradeVance     ← multi-domain assessment + coaching
           ├── Engine pack: LCT Semantics (plugin; genre×discipline devices)
           ├── Engine pack: Rubric Assessment (plugin; analytic / checklist / hybrid)
           └── (later packs: Specialization, Autonomy, domain-specific scorers, …)
 └── Instance: Tectona        ← AI showcase (Healthy, …) — NOT EduOS
 └── Instance: Nibras         ← ERP — NOT GradeVance home
```

**Development logistics:** work may happen in this monorepo while other masters
build Nibras. That does **not** enable GradeVance on Nibras.

---

## 1.1 Scope lock — multi-domain (not Academic English Writing)

The `gradevance2/raw/` NAA pack is **reflective academic writing used as first
gold** for LCT wave fidelity. It is **not** the product definition.

| Domain / genre (examples) | Typical submission | Engine mix |
|---------------------------|--------------------|------------|
| **Medicine — OSCE / OSPE** | Station write-up, checklist performance notes | Rubric quantitative checklists + optional LCT on reflective parts |
| **Medicine — case-based / CBL** | Case discussion, differential, management plan | Rubric qualitative + KB grounding + LCT (clinical reasoning waves) |
| **Articles / essays** (any faculty) | Argumentative / explanatory article | Rubric analytic + LCT Semantics (or later Specialization) |
| **Reflective practice** (NAA-style) | WHAT–SO WHAT–NOW WHAT | LCT reflective device + analytic rubric (first gold) |
| **Engineering / law / business / …** | Design rationale, opinion, case memo | New **packs** only — same engines |

**Invariant:** `discipline × genre × level` selects **TranslationDevice + RubricPack +
PipelineConfig**. No hardcoded “English writing product.” New field = new packs.

---

## 2. Vision & commitments

### 2.1 What GradeVance is
- **Multi-domain** assessment OS for universities and professional programmes.
- Theory-grounded **measurement** (LCT Semantics first where waves/codes apply) before **judgment** (rubric).
- **Hybrid rubrics:** qualitative bands *and* quantitative checklists (OSCE/OSPE).
- **HITL-first:** humans remain accountable; AI drafts, triage, and scales judgment.
- **Learning engines:** every expert correction compounds into better devices/rubrics
  (inspectable config intelligence — not opaque weight updates).
- **Coaching** that closes the gap (Strengths → Diagnosis → Action → revise) where formative.
- **Enterprise education product**: LMS, SSO, audit, fairness, accessibility.

### 2.2 What GradeVance is not
- Not an “Academic English Writing” app (that is one pack among many).
- Not a fire-and-forget autograder (HITL is core product, not a bolt-on).
- Not a plagiarism detector (may integrate one later).
- Not a grammar-only scorer (linguistic criteria are explicit rubric rows when needed).
- Not “one LLM call = grade.”
- Not a Nibras or Tectona app.
- Not medicine-only either — medicine is a **priority vertical**, not the ceiling.
- Not silent self-training that changes marks without professor activation.

### 2.3 Philosophical rails (from GradeVance2 Conceptual v0.2)
1. Measurement before judgment; reproducibility ≠ validity.  
2. Expert corrections accepted; system surfaces inconsistency respectfully.  
3. Transparency: every score → evidence pointers.  
4. Learning continuous but **governed** (proposals → publish → no silent regrade).  
5. Scoring student-invariant; personalization feedback-only.  
6. Privacy by design (clinical reflection and student prose are sensitive).
---

## 3. Actors & RBAC

One app, five roles (ScopedRole / groups — not five apps):

> **Accepted (ADR-0042, 2026-09-19):** three persona surfaces over this one engine —
> `learn` (student), `teach` (professor + marker), `gradevance` (engine room) — mirroring
> Nibras `my`/`team`/`people`. Roles live on course `Enrollment`. See
> [GRADEVANCE-PERSONA-APPS.md](./GRADEVANCE-PERSONA-APPS.md).

| Role | Capabilities |
|------|----------------|
| **Admin** | Org/instance setup, LMS/SSO, retention/erasure, pack library enablement, global QA dashboards |
| **Professor** | Author stems, publish AssignmentProfiles, calibrate devices, release marks, cohort teaching pulse |
| **Marker** | Review queue, edit segments/codes/scores, reuse Action templates, escalate |
| **Student** | Submit drafts, self-assess, receive coaching, revise, view released results + appeals entry |
| **QA** | Held-out κ/α, bias audits, canary/drift, moderation sampling, accreditation exports |

---

## 4. Architecture — three planes

```
┌──────────────── DESIGN PLANE (authoring) ────────────────┐
│  AssignmentProfile@vN (immutable when published)         │
│  ├── RubricPack ref + snapshot                           │
│  ├── LCT TranslationDevice ref + version                 │
│  ├── KnowledgeBase ref (optional)                        │
│  ├── Calibration / held-out sets                         │
│  └── PipelineConfig (stage strategies, models, policies) │
└──────────────────────────┬───────────────────────────────┘
                           │ bind
┌──────────────────────────▼───────────────────────────────┐
│  EXECUTION PLANE (per submission / draft)                │
│  Ingest → Normalize → Segment → [Ground] → Code(LCT)     │
│  → Profile/Wave → RubricScore → Gate → Explain/Coach     │
│  Typed artefacts + confidence + EvidencePointers         │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│  REVIEW / LEARNING PLANE (HITL)                          │
│  Queue → ExpertEdit → Proposals → ProfileBump            │
│  Reliability + Bias + Canary + Appeals                   │
└──────────────────────────────────────────────────────────┘
```

**ClearTurn mapping**
| Concern | Home |
|---------|------|
| Domain SoR | `backend/gradevance/` typed Django models |
| UI | `carbon-frontend/src/apps/gradevance/` |
| AI assist / HITL | Pulse + `ai/domain/gradevance.py` |
| Config packs | `domain_packs/eduos/` (or `domain_packs/gradevance/`) YAML |
| Evidence / audit | platform Evidence + GradeVance run manifests |
| Brand | `src/brands/eduos.js`, `DJANGO_BRAND=eduos` |

---

## 5. Engine plugin model (config-first)

### 5.1 Contract
An **engine pack** is a versioned, validated config bundle + optional prompt
templates. The runtime is shared Python stages registered in a strategy
registry. **New discipline = new pack, not new codebase.**

```
domain_packs/eduos/
  engines/
    lct_semantics/
      naa_reflective_v1/           # first gold — NOT product identity
      medicine_cbl_v1/             # planned
    rubric/
      naa_reflective_analytic_v1/  # first gold
      medicine_osce_abdominal_v1/  # planned (from gradevance2 OSCE fixture)
      medicine_ospe_urinalysis_v1/ # planned
      article_analytic_generic_v1/ # planned
  profiles/
    naa_cycle1_exam_prep_v1.yaml
    medicine_osce_abdominal_v1.yaml
```

### 5.2 Pack lifecycle
`draft → validated → published → archived`  
Publish requires: schema validate, dry-run on exemplars, (for summative) κ ≥ threshold on held-out.

### 5.3 Binding
`AssignmentProfile` pins:
- `lct_device_id` + `version`
- `rubric_pack_id` + `version`
- `pipeline_config_snapshot` (honored at runtime — never cosmetic)
- `kb_id` + `version` (optional)

`AnalysisRun` stores the pin set + stage/model/prompt hashes (**RunManifest**).

---

## 6. LCT Semantics engine

### 6.0 Role in multi-domain GradeVance
LCT is a **measurement plugin**, not the whole product. Some profiles use it heavily
(reflection, article knowledge-building); some use it lightly (OSCE reflection
clause); some use **rubric-only / checklist-only** (pure OSPE station) with LCT
optional or off. PipelineConfig selects stages per profile.

### 6.1 Theory (operationalized)
**Legitimation Code Theory — Semantics** (Maton):
- **Semantic Gravity (SG):** context-dependence continuum.  
- **Semantic Density (SD):** condensation — **meaning depends on genre** (reflective
  vs descriptive in NAA; technical condensation in clinical/science writing).  
- Pedagogic object when enabled: **semantic wave / profile** — not a single cell.

**First gold — NAA reflective** (`gradevance2/raw`) uses a **4-cell reflective grid**:

| | SD− descriptive | SD+ reflective |
|--|-----------------|----------------|
| **SG− general** | General & descriptive | General & reflective |
| **SG+ specific** | Specific & descriptive | Specific & reflective |

Expert coding uses **4-point ordinal SG** at **word-offset boundaries** with wave
charts. Scales are **per device**, not global:

```yaml
# device.yaml (excerpt) — reflective pack
id: naa_reflective_semantics
dimension_set: [semantic_gravity, semantic_density]
scale:
  semantic_gravity: { type: ordinal, levels: [SG++, SG+, SG-, SG--], numeric: [1,2,3,4] }
  semantic_density: { type: binary, levels: [SD-, SD+], map: { descriptive: SD-, reflective: SD+ } }
genre: academic_reflection
discipline: academic_english   # ONE pack — not the product
level: ug_foundation
```

```yaml
# device.yaml (excerpt) — medicine case / clinical reasoning (illustrative)
id: medicine_cbl_semantics_v1
genre: case_based_learning
discipline: medicine
level: ug_y3
# SD = clinical concept condensation; SG = case-particular vs principle
```

Binary SG+/− packs remain valid for lighter formative use; **NAA summative
acceptance uses 4-point gold**. Medicine packs use their own held-out sets.
### 6.2 Stages (LCT pack owns policy; runtime owns code)

| Stage | Responsibility | Pack configures |
|-------|----------------|-----------------|
| Preprocess | NFC, whitespace | — |
| Chunk | Coverage-invariant atoms | max sizes, discourse markers |
| **Segment** | Epistemic moves (clause/move), not paragraphs | split policy, min/max words, markers |
| Ground (opt) | KB citations | grounding policy |
| **Code** | SG / SD per segment | anchors, boundary pairs, prompts, consensus N |
| **Profile** | Wave metrics, transitions, range | expected wave patterns |
| Gate | Confidence → auto / review / withhold | thresholds |

### 6.3 TranslationDevice schema (core)
- Anchors per (dimension, level) with span + rationale  
- Boundary pairs (contrast rationale — always injected)  
- Negatives / common miscodes  
- Wave exemplars (full-submission trajectories)  
- Held-out expert set for κ  
- Embeddings for top-k anchor retrieval at code time  

### 6.4 Segmentation fidelity (non-negotiable)
Acceptance oracle: Ali / AR-CYCLE corpus word offsets.  
**Fail if** median segments ≫ expert length or waves flatten (no oscillation).

### 6.5 Later LCT packs (same plugin slot)
- Specialization (ER/SR — knowledge vs knower codes)  
- Autonomy (positional/relational)  
Each is a **new engine pack type**, not a fork of Semantics.

---

## 7. Rubric Assessment engine

### 7.1 Rubric as a small program
Not a PDF. Versioned schema:

```yaml
# rubric.yaml (excerpt — NAA reflective)
id: naa_reflective_analytic_v1
mode: analytic
criteria:
  - id: task_achievement
    weight: 0.40
    scoring: qualitative
    bands: [F, E, D, C, B, A]   # % bands from raw pack
    evidence_bindings:
      - wave_features: [stages_present, specificity, perspectives_count]
      - segment_codes: [{ dim: SG, min_range: 2 }]
    gates:
      fail_if: missing_reflective_stage
  - id: coherence_cohesion
    weight: 0.30
    scoring: qualitative
  - id: lexis_grammar_academic_style
    weight: 0.30
    scoring: qualitative
aggregation:
  type: weighted_mean
  word_count_penalty: { outside: [200, 300], delta: -0.05 }
fairness_variants: [l2_english, extended_time]
```

### 7.2 Evidence bindings
Scoring stages **must not** read raw text except via declared bindings
(LCT codes, wave features, checklist hits, grounding). Lineage = auditability.

### 7.3 Hybrid scoring types (first-class for medicine)
- **Qualitative:** LLM judges 0–100 / band with required evidence segments (articles, reasoning).  
- **Quantitative:** checklist / keyword+fuzzy / OSCE–OSPE station items (prior art:
  `osce_abdominal_exam.json`, OSPE urinalysis fixtures in gradevance2).  
- **Hybrid profiles:** e.g. OSCE = checklist criteria + qualitative differential /
  reflection criterion bound to LCT codes where useful.

Medicine is a **priority vertical**: station authoring, checklist rubrics, clinical KB
grounding policy (`strict_grounded`), and formative coaching for clinical reflection.
### 7.4 Coaching layer (same pack)
Action templates derived from FEEDBACK gold:
- Strengths (criterion-linked)  
- Diagnosis (D1…)  
- Action (A1…) — feedforward, specific  

Student path (Nicol + Hattie):
1. Clarify standards (brief + exemplars + bands)  
2. Self-eval (WHAT / SO WHAT / NOW WHAT)  
3. Formative analysis (wave + criteria)  
4. Strengths / Diagnosis / Action  
5. Revise → delta report  
6. Summative only after human **release** when mode = summative  

---

## 8. AssignmentProfile & modes

| Mode | AI | Release |
|------|----|---------|
| **Formative** | Coaching + advisory bands | May auto-show with watermark “advisory” |
| **Summative** | Draft scores only | `needs_review` → marker/professor `released` |
| **Calibration** | Gold runs | Never student-facing |

Profile publish checklist:
- [ ] Rubric schema compiles  
- [ ] Device κ ≥ gate (summative)  
- [ ] Exemplar dry-run band distribution OK  
- [ ] Pipeline snapshot frozen  

---

## 9. HITL & engine intelligence (first-class pillar)

HITL is **not** an optional moderation UI. It is how GradeVance stays valid,
accountable, and **gets smarter** over time. Engine “intelligence” improves by
**accumulating articulable expert judgment into versioned config** — TranslationDevice
anchors, boundary pairs, rubric disambiguations, KB corrections, coaching Action
templates — gated by reliability, never by silent model fine-tunes that rewrite history.

### 9.1 Principles
1. **Human accountable** for every summative release (accept / edit / override).  
2. **Every correction is a learning event** (typed `ExpertEdit`, append-only).  
3. **Learning = promote into packs**, not only into one assignment’s memory.  
4. **Governed activation:** proposals → review → Profile/Device bump → canary → activate.  
5. **No silent regrades** of a released cohort when intelligence improves.  
6. **Pulse assists; host executes** (RULE_21).  
7. **Fairness & κ ride along** — smarter must not mean more biased.

### 9.2 What “improving engine intelligence” means

| Layer | What experts teach the engine | Effect on next runs |
|-------|------------------------------|---------------------|
| L0 Device | New/edited anchors, boundary pairs, negatives | Better SG/SD (or other) coding |
| L1 Calibration | Exemplars, held-out gold | Better κ; publish gates |
| L2 KB | Grounding corrections | Better clinical/article evidence |
| L3 Rubric | Disambiguation notes, band boundary tests | Clearer scoring / less override rate |
| L4 Coaching | Strength / Diagnosis / Action templates | Better formative feedforward |
| L5 Profile | Pins L0–L4 + pipeline snapshot | Reproducible, versioned intelligence |

Intelligence lives in **inspectable packs**, so a professor can ask “why did coding
change?” and get a device/profile version answer — not a black-box weight diff.

### 9.3 Closed loop (must ship — P2 is not optional forever)

```
Run → confidence gate (auto formative | needs_review)
    → Marker/Professor: accept | edit segment/code/score | annotate
    → ExpertEdit stream (append-only)
    → ProposalMiner (cluster by kind/span/direction) — scheduled + on-edit
    → Proposal queue (professor / QA)
    → ProfileBump / DeviceBump vN+1
    → Reliability (κ/α) + Canary on held-out
    → Delta report (“κ +0.04; 12 anchors added”)
    → Activate for *new* runs only (never silent cohort rewrite)
    → DriftMonitor + BiasAudit continuous
```

**Summative default:** AI draft → HITL required → release.  
**Formative default:** AI coach allowed; low-confidence still escalates; corrections
still feed the same learning loop.

### 9.4 Active learning for the queue
Prioritize review by: low confidence, consensus disagreement, ungrounded-when-required,
stake-weighted band-flip risk, random sentinels (QA), coverage gaps vs exemplar diagonal.

### 9.5 Pulse role
- Triage / draft coaching / suggest anchor promotions  
- Never auto-publish devices or release summative marks  
- Domain ops in `ai/domain/gradevance.py`

### 9.6 Services (port from GradeVance2; close the loop)
`ReviewQueue` · `ExpertEdit` · `ProposalMiner` · `ProfileBump` · `Reliability` (κ/α) ·
`DriftMonitor` · `BiasAudit` · `Canary` · `Appeals` · `RunManifest` · `Replay`

**Done definition for “learning”:** proposals auto-mined; publish requires κ gate;
`pipeline_config_snapshot` honored at runtime; disambiguation notes injected into
coders/rubric prompts; drift jobs scheduled. Until then, HITL records expertise but
does not yet compound it — that state is explicitly incomplete.

---

## 10. Data model (typed Django — RULE_27)

Core entities (illustrative):
`Course` · `Assignment` · `AssignmentProfile` · `TranslationDevice` · `Anchor` ·
`BoundaryPair` · `RubricPack` · `Submission` · `AnalysisRun` · `Segment` ·
`LCTCode` · `WaveProfile` · `RubricEvaluation` · `ExpertEdit` · `ReviewItem` ·
`Proposal` · `Appeal` · `KnowledgeBase` / `KbChunk` (optional)

Student PII minimized; reflective text encrypted at rest; erasure =
pseudonymize measurements per Conceptual v0.2.

---

## 11. Frontend IA (EduOS · GradeVance)

| Studio | Audience |
|--------|----------|
| Library | Packs, devices, rubrics |
| Authoring | Stems, profiles, calibration |
| Marking workbench | Queue, segment/code/score edit, wave viz |
| Student desk | Briefs, drafts, coaching, progress |
| QA console | κ, bias, canary, audit export |
| Admin | LMS, roles, retention |

Wave visualization must match raw pack charts (ordinal Y, word-offset X).

---

## 12. Enterprise readiness bar

| Capability | Requirement |
|------------|-------------|
| LMS | LTI 1.3 Advantage (launch, AGS, Deep Linking) |
| Identity | SSO (SAML/OIDC); role mapping |
| Privacy | Tenant isolation, DPA, erasure, residency options |
| Security | Access audit logs; SOC2-oriented controls; HECVAT-ready |
| Accessibility | WCAG 2.2 AA + VPAT |
| Integrity | Optional partner; not conflated with grading |
| Governance | Modes, moderation, appeals, immutable audit PDF |

---

## 13. Success metrics

| Layer | Metrics |
|-------|---------|
| Measurement | Segment boundary F1 vs gold offsets; SG/SD κ; wave-shape distance |
| Judgment | Trait QWK + severity/halo; ELL/L1 fairness; canary Δ |
| Learning | Draft→revision gain; Action uptake; delayed transfer task |
| Ops | Time-to-release; % auto vs review; override rate; appeals |
| Trust | Explainability completeness; criteria literacy; faculty NPS |

---

## 14. Anti-patterns (banned)

1. Single LLM call as grade  
2. Grammar/length as proxy for depth / clinical competence  
3. One global SG/SD prompt for all genres / disciplines  
4. Treating GradeVance as “Academic English Writing” product  
5. Coarse paragraph segmentation that flattens waves (when LCT on)  
6. Binary codes when gold is 4-point without an explicit pack choice  
7. Score-only feedback (no Diagnosis→Action) on formative paths  
8. Ignoring published `pipeline_config_snapshot`  
9. Auto-release summative AI marks  
10. Silent model/prompt drift  
11. Direct AI critique before student self-eval (default coaching path)  
12. Hardcoding medicine or English paths in app code instead of packs  
13. Treating HITL as optional moderation instead of the learning engine  
14. “Improving intelligence” via silent fine-tunes without versioned pack promotion
---

## 15. Implementation phases

| Phase | Deliverable |
|-------|-------------|
| **P0** | Schemas (Device, Rubric, Profile) **discipline×genre agnostic**; NAA reflective as **first** gold; medicine OSCE pack skeleton from gradevance2 fixtures | **DONE** — `domain_packs/eduos/` + `validate_packs.py` |
| **P1** | `backend/gradevance` + FE on **EduOS**; formative path; marker review; profile can bind LCT-off / checklist-only | **DONE** — SoR + pack loader + formative pipeline + `/apps/gradevance` studios + CBAC |
| **P2** | Close learning loop (auto proposals, κ publish gates, honor snapshots) | **PARTIAL** — miner → bump → **profile re-pin**; summative κ publish gate; coder registry wired |
| **P3** | LTI 1.3, SSO, WCAG pass, audit export, formative/summative modes | **NEAR** — OIDC+JWKS, User provision, AGS HTTP (dry-run), Deep Link sign+JWKS, NRPS sync, tool-config, WCAG checklist+skip links; live LMS soak + formal VPAT TBD |
| **P4** | **Medicine OSCE/OSPE packs live** (proves multi-domain); then article / CBL packs | **PARTIAL** — OSCE/OSPE/CBL/article packs + held_out; pipeline tests for OSCE/OSPE/CBL; article Semantics device |
| **P5** | Additional faculties via packs only (law, engineering, business, …) | planned |
---

## 16. File map (target)

```
backend/gradevance/           # SoR + formative pipeline + HITL learning ✅
backend/ai/domain/gradevance.py  # Pulse domain adapter ✅
backend/ai/engine/instances/eduos/instance.yaml   # ✅
domain_packs/eduos/           # ✅ P0 schemas + NAA gold + OSCE packs
carbon-frontend/src/brands/eduos.js               # ✅
carbon-frontend/src/apps/gradevance/              # ✅ engine room
carbon-frontend/src/apps/learn/                   # ✅ student (ADR-0042)
carbon-frontend/src/apps/teach/                   # ✅ professor (ADR-0042)
docs/eduos/GRADEVANCE-DESIGN.md                   # this file
docs/eduos/GRADEVANCE-PERSONA-APPS.md             # Learn · Teach · Engine
docs/eduos/GRADEVANCE-PROFESSOR-LIFECYCLE.md      # professor UX plan
.ai-toolkit/decisions/0038-eduos-gradevance.md    # ✅
.ai-toolkit/decisions/0042-gradevance-persona-apps.md  # ✅
```

---

## 17. References

- Maton — LCT Semantics; Maton & Chen (2016) translation devices  
- Nicol & Macfarlane-Dick — seven principles of good feedback  
- Hattie & Timperley — feed-up / feed-back / feed-forward  
- GradeVance2 Conceptual & Design v0.2; assessment-platform-design v1; lifelong-learning v1  
- Raw NAA pack (briefs, LCT grid, 2-cycle texts+waves, FEEDBACK)  
- Competitive: Gradescope, Cadmus, FeedbackFruits Acai, Inspera Graide, ETS Criterion  
- ClearTurn: CLEARTURN-PLATFORM-ARCHITECTURE.md · RULE_31 · ADR-0038
