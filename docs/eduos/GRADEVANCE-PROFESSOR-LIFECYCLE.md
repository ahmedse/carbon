# GradeVance — Professor Lifecycle Plan & UI Architecture

**Status:** Plan + Phase A shipping (continuity UI)  
**Date:** 2026-09-18  
**Instance:** EduOS · App: GradeVance  
**Companion canvases:** *GradeVance Professor Lifecycle* · *Amazing Professor Journey*  
**Vision narrative:** [GRADEVANCE-PROFESSOR-JOURNEY.md](./GRADEVANCE-PROFESSOR-JOURNEY.md)  
**Parent design:** [GRADEVANCE-DESIGN.md](./GRADEVANCE-DESIGN.md) · ADR-0038  

---

## 0. Problem statement

Today GradeVance has a **real execution + HITL backend** (pipeline, packs, ExpertEdit → Proposal → bump → repin) but the **professor UI is thin**: Authoring is one-shot publish, Library is read-only, Student desk doubles as evaluate playground, Marking cannot edit LCT codes in place, and **Course → Assignment(stem) → Submission → Run → Calibration → Proposals** is not one continuous object graph in the shell.

This document defines the **target professor journey**, **information architecture**, **workflows**, and a **phased build plan** so the product matches the design thesis: *measure → judge → coach under governed HITL*.

---

## 1. Goals & non-goals

### Goals
1. A professor can run the **full lifecycle** without leaving GradeVance or inventing CLI steps.
2. Every screen has **one job**; navigation follows the object graph (course → assignment → submission → run).
3. Stems, pack pins, KB refs, and calibration sets are **first-class**, not buried in JSON.
4. HITL is **editable** (SG/SD/rubric), then **promotable** (proposals), never silent.
5. Student desk stays **student-facing**; professors do not evaluate cohorts from the student playground.

### Non-goals (this plan)
- In-app YAML pack authoring (filesystem / git remains SoT for devices & rubrics).
- Full KnowledgeBase CRUD (KB is a pin + browse/link in P1; chunk editor later).
- Live LMS round-trip (separate LMS-SOAK track).
- Appeals / fairness dashboards (QA role; later phase).

---

## 2. Architecture — three planes (product map)

```
┌──────────────── DESIGN PLANE (professor authoring) ──────────────┐
│  Course                                                          │
│    └── Assignment (stem + brief + mode + status)                 │
│          └── pin AssignmentProfile@vN                            │
│                ├── LCT TranslationDevice@v                       │
│                ├── RubricPack@v                                  │
│                ├── KnowledgeBase@v (optional)                    │
│                ├── Calibration / held-out set                    │
│                └── PipelineConfig snapshot (frozen at publish)   │
└──────────────────────────────┬───────────────────────────────────┘
                               │ publish / enroll / ingest
┌──────────────────────────────▼───────────────────────────────────┐
│  EXECUTION PLANE (per submission)                                │
│  Ingest → Segment → Code(LCT SG/SD) → Wave → Rubric → Gate       │
│  → Coach (formative) · artefacts + confidence + evidence         │
└──────────────────────────────┬───────────────────────────────────┘
                               │ needs_review / open ReviewItem
┌──────────────────────────────▼───────────────────────────────────┐
│  REVIEW / LEARNING PLANE (HITL)                                  │
│  Queue → Edit codes/scores → ExpertEdit → ProposalMiner           │
│  → Accept → Pack bump → Profile re-pin → Canary/κ · Release      │
└──────────────────────────────────────────────────────────────────┘
```

| Concern | Home |
|---------|------|
| Typed SoR | `backend/gradevance/` models |
| UI | `carbon-frontend/src/apps/gradevance/` |
| Packs SoT | `domain_packs/eduos/` |
| Brand | EduOS only (`DJANGO_BRAND=eduos`) until explicit multi-instance ADR |

---

## 3. Object model (professor vocabulary)

| Object | What the professor thinks | Persistence |
|--------|---------------------------|-------------|
| **Course** | Module / unit of study | `Course` |
| **Assignment** | Stem + rules + pinned profile | `Assignment` + `brief` JSON |
| **Stem** | Prompt students see | `Assignment.brief.stem` (+ `instructions`, `outcomes`) |
| **Profile pin** | Which engines run | `profile_pack_id` + `version` + `pipeline_config_snapshot` |
| **Pack library** | Available devices/rubrics/gold | YAML + `AssignmentProfileRecord` |
| **KB (optional)** | Grounding corpus for genre | Pin in profile / brief; full SoR later |
| **Submission** | Student (or demo) text | `Submission` |
| **Run** | One LCT+rubric analysis | `AnalysisRun` + segments/codes/wave |
| **Review** | Human accountability | `ReviewItem` + `ExpertEdit` |
| **Proposal** | Engine intelligence change | `Proposal` → bump → repin |
| **Calibration** | Held-out expert vs engine | Gold / `held_out.jsonl` + κ gate |

**Invariant:** published assignments freeze `pipeline_config_snapshot`. Changing intelligence requires **new profile version** via proposals — never silent rewrite of released cohorts.

---

## 4. Roles → surfaces

| Role | Primary surfaces | Must not |
|------|------------------|----------|
| **Professor** | Courses, Assignment hub, Calibration, Proposals, Release | Use Student desk as cohort evaluate home |
| **Marker** | Marking queue → Run workbench (edit + resolve) | Publish packs / accept proposals (unless also lead) |
| **Student** | Student desk (linked assignment), released results | See unreleased summative marks |
| **QA** | Calibration κ, audit export, canary | Author stems for live cohorts (optional read) |
| **Admin** | Registered Apps, LTI, groups | Day-to-day marking |

---

## 5. Target information architecture (sidebar)

```
GradeVance
├── Overview                 Cohort pulse + journey shortcuts
├── Courses & stems          DESIGN — create course, author stem, publish
│     └── Assignment hub     Stem · config · submissions · runs
│           └── Run workbench  LCT results · HITL editors · release
├── Marking                  REVIEW — open queue → same Run workbench
├── Calibration              DESIGN/QA — held-out pairs · κ · gold examples
├── Pack library             DESIGN — browse profiles/devices/rubrics/gold (read)
├── Proposals                LEARNING — decide → bump → re-pin
└── Student desk             STUDENT — formative practice / linked submit
```

**Breadcrumb rule:** every deep page shows  
`Course → Assignment → Submission → Run` when those IDs exist.

**Deep-link rule:** Overview metrics never dump professors into Student desk for “runs”.

---

## 6. Workflows (clean, linear)

### W1 — Author a stem (Design)

```
1. Courses & stems → New course (code, name, discipline)
2. New assignment:
   - Course
   - Title
   - Profile pack (discipline × genre × level)
   - Mode: formative | summative | calibration
   - Stem (required for publish)
   - Instructions / success criteria
3. System merges pack brief defaults + stem into Assignment.brief
4. Freezes pipeline_config_snapshot from profile
5. If summative + LCT on → κ publish gate must pass
6. Land on Assignment hub
```

**UX notes:** one form, progressive disclosure for advanced (KB pin, word band). Fail closed on empty stem for published status.

### W2 — Collect & evaluate submissions (Execute)

```
1. Assignment hub → Submissions
2. Add text (paste) or later file upload
3. Analyze → creates AnalysisRun
4. Open Run workbench: SG/SD table + wave + rubric + coaching
```

**UX notes:** row click = select only; deliberate **Open run** / **Analyze** buttons (enterprise row-click rule).

### W3 — HITL review & release (Review)

```
1. Marking queue shows open ReviewItems
2. Open Run workbench
3. Edit SG and/or SD per segment (or rubric band) → ExpertEdit
4. Optional Resolve review item
5. Summative: Release (explicit) → optional AGS preview/passback
6. ProposalMiner may draft Proposal from clustered edits
```

**UX notes:** show before/after; require short rationale on code change; watermark coaching until release.

### W4 — Calibrate before summative (Design/QA)

```
1. Calibration → pick profile
2. See held-out expert SG vs engine SG (+ SD when present)
3. κ / publish_gate status
4. Link “use this profile” → Courses stem form prefilled
5. Failures → Marking / Proposals / pack bump — not silent threshold tweak
```

### W5 — Promote engine intelligence (Learning)

```
1. Proposals list (draft/accepted)
2. Accept (optional canary labels)
3. Bump device pack (versioned dest)
4. Re-pin profile to new device/rubric version
5. New assignments use new pin; old released cohorts unchanged
```

---

## 7. Screen contracts (UI/UX)

Shared rules (`.ai-toolkit` compact UI + design principles):
- Dense tables; `size="small"` controls; no emoji icons; distinct MUI icons per nav item.
- One H1 per page; one primary CTA.
- Status never by color alone (chip + text).
- Skeletons on load; inline errors with retry.
- Brand banner on EduOS must not mention Nibras.

| Screen | Primary job | Primary CTA | Key components |
|--------|-------------|-------------|----------------|
| Overview | Orient + jump | Open Courses | Stats → Courses / Marking / Calibration / Proposals |
| Courses & stems | Create course + publish stem | Publish assignment | Course form · Stem form · Assignment table |
| Assignment hub | Operate one assignment | Analyze submission / Open run | Stem panel · Config chips · Submissions · Runs |
| Run workbench | Read LCT + edit HITL | Save code edit / Release | `LctCodesTable` · WaveChart · Edit drawers · Rubric |
| Marking | Triage queue | Open run | Priority table → workbench |
| Calibration | Trust before summative | Use profile in stem | κ callout · expert/engine table |
| Pack library | Discover packs | Use in assignment | Profile table → Courses with `?pack=` |
| Proposals | Govern learning | Accept → Bump → Re-pin | Proposal table + action buttons |
| Student desk | Student formative | Run analysis | Example picker · results (no cohort admin) |

---

## 8. API surface (professor continuity)

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/gradevance/courses/` | List / create |
| GET/PATCH | `/gradevance/courses/<id>/` | Detail + assignments |
| GET/POST | `/gradevance/assignments/` | List (`?course=`) / create with stem in `brief` |
| GET/PATCH | `/gradevance/assignments/<id>/` | Hub payload: assignment + submissions + runs + counts |
| GET/POST | `/gradevance/submissions/` | List (`?assignment=`) / create (+ `analyze`) |
| POST | `/gradevance/submissions/<id>/analyze/` | Re-run pipeline |
| GET | `/gradevance/runs/` | List (`?assignment=` `&submission=`) |
| GET | `/gradevance/runs/<id>/` | Full LCT + rubric + coaching |
| POST | `/gradevance/runs/<id>/edits/` | ExpertEdit (lct_code / rubric_score) |
| POST | `/gradevance/runs/<id>/release/` | Summative release |
| GET | `/gradevance/calibration/?profile_pack_id=` | Held-out pairs + κ |
| GET | `/gradevance/examples/` | Gold/held_out texts for demos |
| GET/POST… | `/gradevance/proposals/…` | Decide / bump / repin |
| GET | `/gradevance/profiles/` | Pack catalog |

---

## 9. Gap vs target (honest)

| Area | Backend today | UI today | Target |
|------|---------------|----------|--------|
| Course CRUD | ✅ | ✅ Courses & stems | Done Phase A |
| Stem authoring | `brief` JSON | ✅ stem + instructions on create | PATCH draft = Phase C |
| Assignment hub | ✅ detail API | ✅ hub page | Done Phase A |
| Evaluate | Pipeline solid | ✅ hub Analyze | Done Phase A |
| LCT results | Serializer solid | ✅ Run workbench | Done Phase A |
| HITL code edit | `ReviewService.apply_edit` | ✅ SG/SD editors | Done Phase A |
| Calibration | held_out + κ services | ✅ Calibration page | Done Phase A |
| Proposals | API + page | ✅ linked from Cal/Marking | Done |
| KB | Design only | — | Pin + browse P1; CRUD later |
| File upload | — | — | P1 |

---

## 10. Phased build plan

### Phase A — Continuity (P0) — “professor can live in the graph”
1. Courses & stems page (create course, create assignment with stem).
2. Assignment hub (`GET assignments/<id>/`) with submissions + analyze + run links.
3. Run workbench route `/apps/gradevance/runs/:runId` (results + LCT edit + release).
4. Marking queue opens Run workbench (not a dead-end list).
5. Overview CTAs → Courses / Marking / Calibration / Proposals.
6. Nav IA update (Courses & stems, Calibration; Authoring merges into Courses).

### Phase B — Trust (P0.5)
1. Calibration page (expert vs engine + κ). ✅
2. Publish gate visible on stem form for summative. ✅ (`as_mode=summative`)
3. Seed stems on demo assignments. ✅
4. ~~In-page breadcrumbs~~ removed — shell owns breadcrumbs (compact-ui).

### Phase C — Depth (P1)
1. PATCH stem/instructions on draft assignments. ✅
2. File upload submissions (.txt/.md). ✅
3. KB pin picker + read-only pack detail drawer. ✅
4. Batch analyze cohort. ✅
5. Role-gated nav (`gradevance:manage` vs `submit` vs `mark`). ✅

### Phase D — Enterprise (P2+)
1. Appeals, fairness, audit UI.
2. Live LMS soak.
3. Optional in-app pack proposal diffs beyond bump/repin.

---

## 11. Acceptance criteria (professor happy path)

A professor on EduOS can, in the UI only:

1. Create a course and an assignment with a **non-empty stem**, pinned to `naa_cycle1_exam_prep` (or medicine/article profile).
2. Paste a gold/held_out example as a submission and **analyze**.
3. Open the run and see **SG and SD per segment** plus wave metrics.
4. Change an SG or SD code with rationale; see ExpertEdit land and optionally a draft Proposal.
5. Open **Calibration** for that profile and read κ / expert–engine pairs.
6. From **Proposals**, accept → bump → re-pin without CLI.
7. Never need Student desk to administer the cohort.

---

## 12. Related docs

- [GRADEVANCE-PROFESSOR-JOURNEY.md](./GRADEVANCE-PROFESSOR-JOURNEY.md) — enterprise wisdom + amazing journey narrative  
- [GRADEVANCE-DESIGN.md](./GRADEVANCE-DESIGN.md) — product thesis & engines  
- [LMS-SOAK.md](./LMS-SOAK.md) — LTI integration  
- [ENTERPRISE-INTEGRATION.md](./ENTERPRISE-INTEGRATION.md) — SSO/LMS enterprise  
- ADR-0038 EduOS + GradeVance · RULE_33 professor journey IA  

---

## 13. Changelog

| Date | Change |
|------|--------|
| 2026-09-18 | Initial professor lifecycle plan + UI architecture (this doc) |
| 2026-09-18 | Linked amazing-journey doc; Phase A continuity UI (Courses → hub → Run workbench → Calibration) |
| 2026-09-18 | Phase B2: summative publish-gate on stem form; removed in-page breadcrumbs; PageHeader actions |
| 2026-09-18 | Phase C: draft stem PATCH, .txt upload, KB pin, pack drawer, batch analyze, role-gated nav |
