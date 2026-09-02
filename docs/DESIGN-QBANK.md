# DESIGN — QBank (Medical Question Bank) on the Data Trust Platform

- **Status:** Draft for review (Master Architect)
- **Date:** 2026-09-01
- **App slug (placeholder):** `qbank`
- **Display name (placeholder):** "Question Bank" / "بنك الأسئلة"
- **Scope:** centralized **content** store for medical questions. **No exams, no
  delivery, no psychometrics** (schema is left extensible for those later).
- **Seams:** ADR-0016 (domain AI manifest), ADR-0025 (typed vs dataschema storage),
  ADR-0018 (dual-language), `mdm.OrgUnit` (org spine), `mdm.ReferenceSet`
  (taxonomy), `dq.ModelRuleAssignment` (item-writing rules as data), `catalog.audit_utils`
  (governance events), `ScopedRole` (org-subtree RBAC).

---

## 1. Purpose and positioning

QBank is the **system of record for medical-education questions and the outcomes
they serve**. It is deliberately **not** an exam engine. Its job is to be the
trusted, versioned, auditable place where faculty:

1. author questions (SBA/EMQ/SAQ) against a governed outcome taxonomy,
2. tag every question to competencies, outcomes, standards, cognitive level, and
   Miller level,
3. get structured, standards-grounded **item-writing review** (flaw detection),
4. approve/publish with full provenance and immutable version history, and
5. answer **blueprint-coverage** questions ("is the curriculum covered against
   WFME / ACGME / program outcomes?").

Later apps consume it: OSCE will generate station stems from the bank; Lagna
(exam seating) is orthogonal (logistics) and never touches question content.

> ## 🛑 INVARIANT-0 — Student data is FORBIDDEN in QBank
>
> QBank stores **zero** student / learner / examinee records — no names, no
> registration numbers, no IDs, no enrollments, no results, no logs that could
> re-identify a learner. Student identity is the **most protected data class**
> and lives only where assessment/delivery happens (Lagna seating, and the
> future exam-delivery app), never in the content store.
>
> Enforced by: (a) no `Student`/`Enrollment`/`Result` model exists in `qbank`,
> (b) the API has no student-facing endpoints, (c) RBAC has no learner role, and
> (d) a CI gate asserts `qbank` imports no student-bearing app. A question is
> **content**; the moment it needs a learner it becomes an *assessment* concern
> and lives elsewhere.

---

## 2. Learned wisdom — what the top systems teach, and the flaws to avoid

### 2.1 Reference systems consulted (pattern-level, not copied)

| System | What it does well | What QBank adopts |
|--------|-------------------|-------------------|
| **NBME Item-Writing Guide** | Single-Best-Answer (SBA) format; lead-in question; 3–5 options | SBA-first with mandated lead-in + rationale |
| **Haladyna, Downing & Rodriguez (2002)** | Evidence-based taxonomy of ~31 item-writing rules + validity evidence | The **DQ rule set** (below) is this taxonomy, operationalized |
| **Millman (computerized item banking)** | Item banks need versioning + item IDs that never change + psychometric side-tables | Immutable `QuestionVersion` + stable UUID; stats table deferred |
| **ExamSoft / Speedwell** | Blueprint-to-item tagging, review workflow, content vetting | Blueprint model + role-gated review workflow |
| **AMBOSS / UWorld / Osmosis** | Rich media in stem, per-option rationale, cross-linked learning objectives | Per-option rationale; media asset model; outcome tagging |
| **MedEdPORTAL / AMEE Guides** | Peer review, source attribution, licensing | `QuestionSource` provenance + copyright status |
| **CBME (ACGME/CanMEDS/AAMC EPAs)** | Competency → outcome → milestone hierarchies | Multi-framework `Outcome` tree (below) |

### 2.2 The flaws we refuse to ship (item-writing anti-patterns)

These become **enforced rules**, not guidelines (see §5). Each is a real,
literature-documented validity threat:

1. Stem does **not end in a lead-in question** ("A 54-year-old man… What is the
   most likely diagnosis?").
2. **Negative / "which is NOT" / "which is FALSE"** phrasing.
3. **"All of the above" / "None of the above"** options.
4. **Implausible distractors** (an option no competent examinee would choose).
5. **Grammatical cue** — an option that does not agree grammatically with the stem.
6. **Length cue** — the correct answer is consistently the longest/most specific.
7. **Absolute terms** — "always / never / all / none" in options.
8. **Convergent cue** — correct answer shares most elements with the others.
9. **Unfocused stem** — tests multiple concepts at once.
10. **Overlapping / non-mutually-exclusive options.**
11. **Missing rationale** or **missing reference** (non-negotiable for a bank).
12. **No outcome/competency tag** — an untagged question cannot be blueprinted.
13. **Near-duplicate stem** (same clinical vignette with cosmetic wording changes).
14. **Copy-paste from a single copyrighted source** without attribution (IP risk).

### 2.3 The failures of existing top systems (what we refuse to inherit)

These are the *systemic* flaws — not item-writing rules, but the product and
architecture failures that make incumbent banks painful to own. Each maps to a
QBank decision.

| # | Failure in incumbent systems (ExamSoft / Questionmark / Speedwell / legacy Moodle banks / NBME-style silos) | QBank's answer |
|---|------------------------------------------------------------------------------------------------------------|----------------|
| F1 | **Vendor lock-in** — content trapped in proprietary formats; export is lossy, no clean structured out | Typed Postgres models + a defined import/export format (QTI-friendly JSON); you own the schema |
| F2 | **QTI/IMS fragmentation** — "QTI-compliant" rarely interoperates; 1.x/2.x/3.0 drift | Own canonical schema; QTI is an *adapter*, not the source of truth |
| F3 | **Black-box psychometrics** — item stats hidden behind dashboards, no raw data | Stats deferred, but when they arrive they're **governed measurements in `dataschema`** (own the numbers) |
| F4 | **Closed taxonomies** — cognitive-level list is hardcoded; adding a framework = vendor ticket | Taxonomy is **data** (ReferenceSet + OutcomeFramework), admin-editable, multi-framework |
| F5 | **No real versioning** — editing a live item silently overwrites; can't prove what shipped on exam day | Immutable `QuestionVersion` snapshots + stable UUID + full audit |
| F6 | **Weak provenance / IP** — no source attribution, no license; copied textbook content = legal risk | `QuestionSource` with `copyright_status` + license; AI-generated content is **marked** |
| F7 | **Duplicate explosion** — same vignette re-authored across courses/years; banks bloat | `stem_hash` unique index + fuzzy near-duplicate detection |
| F8 | **Blueprinting is an afterthought** — tagging optional, free-text, unreliable | Mandatory outcome tagging with **exactly one primary**; coverage is countable |
| F9 | **Flaws caught late (or never)** — review is a manual step that gets skipped | Item-writing flaws **enforced at write time** + Pulse review (§5, §7) |
| F10 | **Content siloed per course/exam** — no central bank; reuse across years is impossible | One central bank; `org_unit` scopes access, not storage |
| F11 | **No AI, or ungoverned AI** — none, or AI that auto-publishes unverified content | Pulse drafts/flags only, human approves (RULE_21) |
| F12 | **Multilingual as an afterthought** — Arabic/RTL broken; content model can't separate languages | First-class `language` + additive `QuestionTranslation` (ADR-0018) |
| F13 | **Student PII entangled with content** — a content collaboration becomes a breach surface | **INVARIANT-0**: zero student data in the bank |
| F14 | **No sensitive-content governance** — mature/violent clinical material unflagged | `content_warning` flag + review routing |
| F15 | **Rigid linear approval** — can't parallel-review or route by competency | `QuestionReview` per-reviewer, role-gated, routed by outcome |

---

## 3. Learning-outcomes model (the centerpiece)

Medical education runs on **multiple overlapping competency frameworks**. A
question bank that hardcodes one framework is wrong the day it ships. QBank
models outcomes as a **typed, hierarchical tree** (not a flat `ReferenceSet`,
because outcomes have parents, children, and cross-framework identity).

### 3.1 Framework model

- `OutcomeFramework` — a named competency/outcome standard (ACGME, CanMEDS, GMC
  *Outcomes for Graduates*, AAMC Core EPAs, WFME, or institutional **PLO/ILO** sets).
- `Outcome` — a node in the hierarchy under a framework:
  - `code` (e.g. `PC1`, `2.3`, `MK-4`), `title`, `description`
  - `parent` (self-FK) → competencies decompose into sub-competencies → milestones → objectives
  - optional `cognitive_level` and `miller_level` **defaults** (inherited by child tags unless overridden)
  - `org_unit` — which phase/year/department the outcome applies to

### 3.2 Frameworks to seed (ReferenceSets + OutcomeFrameworks)

**Flat enums → `mdm.ReferenceSet`** (temporal validity, admin-editable):

| ReferenceSet | Values |
|--------------|--------|
| `question_type` | SBA (Single Best Answer), EMQ (Extended Matching), SAQ (Short Answer), MRQ (Multi-Response) |
| `cognitive_level` | Revised Bloom: Remember, Understand, Apply, Analyze, Evaluate, Create |
| `miller_level` | Knows, Knows How, Shows How, Does |
| `question_status` | (workflow — kept as model `choices`, not a set, see §6) |
| `flaw_type` | the item-writing flaws from §2.2 |
| `discipline` | Anatomy, Physiology, Pharmacology, … (curriculum systems) |
| `standard` | WFME, LCME, NARS, … (accreditation bodies) |

**Hierarchical → typed `OutcomeFramework` + `Outcome`** (seeded, not hardcoded).
Because this is **config, not code** (§11), we do **not** have to decide the full
set now — we seed an empty registry and import frameworks on demand.

**Recommended first seed (AASTMT College of Medicine):**

1. **Institutional PLO → ILO → CLO** (the college's own program/intended learning
   outcomes) — **this is the one that drives your own blueprinting and
   accreditation**, seed it first from whatever the college already publishes.
2. **NARS — National Academic Reference Standards (Medicine), NAQAAE** — the
   Egyptian accreditation standard the college reports against. If the college
   maps outcomes to NARS, seed those mappings too.
3. **ACGME Core Competencies** (6) — the global graduate-outcome lingua franca;
   Patient Care, Medical Knowledge, PBLI, Interpersonal & Communication Skills,
   Professionalism, Systems-Based Practice.

**Defer until asked:** CanMEDS (7 roles), AAMC Core EPAs (13), WFME, GMC
*Outcomes for Graduates* — import later as data with zero schema change.

### 3.3 Question ↔ Outcome mapping

`QuestionOutcomeTag` (explicit through-model) carries:

- `is_primary` — exactly one primary outcome per question (the blueprint "counts" it).
- `created_by` / `created_at` — provenance of the tag itself.
- Optional `note` — why this question maps here.

A question may tag **many** outcomes (secondary), but exactly **one** primary —
this is what makes blueprint coverage countable and non-ambiguous.

---

## 4. Data model (typed Django models, `qbank` app — ADR-0025)

QBank is the **system of record** for questions → **typed models** with FKs,
unique constraints, and per-row org scope. Nothing lives in `dataschema`
(questions are owned master data, not governed *measurements*).

### 4.1 Core content

```
Question
├─ uuid              # stable public id (never changes across versions)
├─ stem              # text — the clinical vignette / prompt (authored language)
├─ lead_in           # text — the actual question sentence ("What is the most likely…?")
├─ rationale         # text — why the correct answer is correct
├─ references        # JSON list — citations (APA/Vancouver)
├─ language          # 'en' | 'ar' (authored language)
├─ question_type     # FK ReferenceValue (SBA/EMQ/SAQ/MRQ)
├─ cognitive_level   # FK ReferenceValue (revised Bloom)
├─ miller_level      # FK ReferenceValue (nullable — SAQ/clinical)
├─ status            # choices: draft|in_review|approved|published|retired|revised
├─ version           # int, monotonic
├─ org_unit          # FK mdm.OrgUnit — ownership + RBAC scope
├─ source            # FK QuestionSource (provenance/IP)
├─ stem_hash         # sha256 of normalized stem — duplicate detection index
├─ content_warning   # nullable — sensitive/mature material flag
├─ created_by/at, updated_at, reviewed_by, approved_by, published_at
└─ is_active / is_archived

QuestionOption (SBA/EMQ/MRQ)
├─ question          # FK
├─ position          # int (A/B/C/D/E order)
├─ text              # option text
├─ is_correct        # bool
└─ rationale         # per-distractor rationale (why it's wrong) — optional but recommended

AnswerKey (SAQ — no fixed options)
├─ question          # OneToOne
├─ model_answer      # text
├─ rubric            # text
└─ grading_notes     # text

QuestionTranslation (dual-language, additive)
├─ question          # FK
├─ language          # 'en'|'ar'
└─ stem / lead_in / rationale   # translated content
```

### 4.2 Taxonomy & blueprinting

```
OutcomeFramework    # name, slug, code, version, steward, org_unit, is_active
Outcome             # framework FK, parent FK(self), code, title, description,
                    #   cognitive_level default, miller_level default, org_unit, is_active

Blueprint           # name, org_unit, academic_year, description, framework FK, status
BlueprintItem       # blueprint FK, outcome FK, target_count, weight, phase/year

QuestionOutcomeTag  # question FK, outcome FK, is_primary, note, created_by/at
QuestionTag         # question FK, Tag FK (freeform keywords)
Tag                 # name (unique), type (system|keyword|theme), is_active
```

### 4.3 Versioning, review, provenance

```
QuestionVersion     # question FK, version int, snapshot JSON (full serialization at publish),
                    #   reason (created|edited|reviewed|retired), created_by/at

QuestionReview      # question FK, reviewer FK, review_type (content|psychometric|standard),
                    #   decision (approve|request_changes|reject), comments, created_at

QuestionComment     # question FK, author FK, body, parent FK(self), resolved bool, created_at

QuestionFlaw        # question FK, flaw_type FK(ReferenceValue), severity, note,
                    #   status (open|resolved|dismissed), flagged_by, resolved_by, created_at

QuestionSource      # source_type (textbook|journal|author_original|legacy_import|ai_generated),
                    #   title, citation, copyright_status (owned|licensed|public_domain|needs_permission),
                    #   license, url

MediaAsset          # (deferred) question FK, file FK(mediafiles), alt_text, kind, position
```

### 4.4 Deferred (explicitly out of scope, but schema-ready)

- `ItemStatistic` (n, p-value, difficulty, discrimination) — **governed
  measurements** when exams exist → route through `dataschema` (the ADR-0025
  "measurements" half), not typed. Do **not** build now.

---

## 5. Item-writing rules (DQ as data, not code)

Two enforcement layers, honestly separated:

### 5.1 Scalar-field rules → `dq.ModelRuleAssignment` (bind to `qbank.Question` fields)

| Rule | Field | Verdict |
|------|-------|---------|
| Stem is non-empty and ≥ some minimum | `stem` | error |
| Lead-in is present and ends with a question mark | `lead_in` | error |
| Rationale is present | `rationale` | error |
| References are present and non-empty | `references` | warning |
| Stem has no "NOT / EXCEPT / FALSE" (negative phrasing) | `stem` | warning (flag) |
| Stem/options have no absolute terms ("always/never/all/none") | `stem` | warning |
| Exactly one `cognitive_level` and one `miller_level` set | `cognitive_level` | error |

### 5.2 Relational / cross-field invariants → model `clean()` + service layer

The DQ engine evaluates **per-row scalar fields**; it cannot see "how many
options are correct." These invariants are enforced at write time in
`Question.clean()` / the `QuestionService`, and surfaced in the same review UI
as DQ findings:

- **Exactly one correct option** for SBA (not zero, not two).
- **3–5 options** for SBA (NBME standard).
- **No "all/none of the above"** options.
- **Mutually exclusive options** (no overlap) — heuristic + human review.
- **Distractor plausibility** — AI-assisted review (§7), human confirm.
- **Grammatical agreement** — AI-assisted review, human confirm.
- **`stem_hash` unique** (near-duplicate detection) — DB unique index + fuzzy
  match (AI-assisted) for cosmetic rewrites.
- **≥1 `QuestionOutcomeTag` with `is_primary=True`** before `approved`.

> **Design note (honest seam):** ADR-0025's `ModelRuleAssignment` gives us the
> scalar-field half for free. The relational half stays in `qbank.services`
> + `clean()` because it needs cross-row/cross-table knowledge the DQ engine
> deliberately does not model. Both surface together in one "review gate".

---

## 6. Lifecycle state machine

```
draft ──► in_review ──► approved ──► published ──► retired
  ▲          │             │                          ▲
  │          └── request_changes (back to draft)      │
  └────────────────────────────────────────────────────┘
            (any state → revised = new version, parent linked)
```

Rules:

- **Every transition emits a `GovernanceEvent`** (`entity_type='Question'`,
  `entity_id=...`, `before`/`after` status) — the accreditation-grade audit trail
  (ADR-0025 §3).
- **Publish/approve snapshots a `QuestionVersion`** (immutable JSON) — a
  published question is never silently edited; edits fork a new version.
- **Retire** is soft (never delete a published question — it may be cited in an
  accreditation report).

### RBAC (ScopedRole, org-subtree)

| Role | Can |
|------|-----|
| `qbank:author` | create/edit **own org_unit** questions (draft) |
| `qbank:reviewer` | review, flag flaws, comment, request changes (cross-dept) |
| `qbank:editor` | approve → publish within org subtree |
| `qbank:admin` | blueprints, outcome frameworks, taxonomy, retire, bulk import |

---

## 7. AI surface (Pulse domain manifest — `ai/domain/qbank.py`)

Registered via ADR-0016 `DomainAIOperations` subclass. **RULE_21: AI never
mutates** — every task returns a *draft / flags / suggestions* for human approval.

| task_type | What it does | Output |
|-----------|--------------|--------|
| `generate_item` | vignette/outcome → SBA draft (stem + lead-in + 4 options + rationale) | Draft (not persisted) |
| `generate_distractors` | given stem + correct answer → plausible distractors | Draft |
| `review_item` | score a draft against §2.2 flaw taxonomy + Haladyna rules | `QuestionFlaw[]` (flagged, unresolved) |
| `tag_suggest` | suggest `Outcome`/`cognitive_level`/`Miller` tags | suggestions |
| `blueprint_gap` | which outcomes are under-covered vs `BlueprintItem` targets | report |

- `supported_task_types = ["chat", "generate_item", "generate_distractors",
  "review_item", "tag_suggest", "blueprint_gap"]`
- `entry_points` on `on_entity: "question"` (Generate, Review, Suggest tags).
- `validate_task_payload` rejects `table_id` (typed-model vertical, mirrors
  `people.py`); requires a `question_id` for review/tag tasks.
- `system_prompt_extension` injects NBME SBA conventions, Haladyna rules, and the
  outcome-framework vocabulary.
- **Dual-language (ADR-0018):** generate/review can target `language='ar'` or
  `'en'`; translate-task deferred.

---

## 8. API surface (DRF, under `/carbon-api/qbank/`)

```
outcomes/            OutcomeViewSet          (list/retrieve/create/update — admin)
outcome-frameworks/  OutcomeFrameworkViewSet  (admin)
questions/           QuestionViewSet          (list/retrieve/create/update/archive)
  ├─ @review         (reviewer decision)
  ├─ @approve        (editor)
  ├─ @publish        (editor/admin)
  ├─ @retire         (admin)
  ├─ @clone          (fork new draft version)
  └─ @versions       (list immutable snapshots)
options/             QuestionOptionViewSet
answer-keys/         AnswerKeyViewSet
flaws/               QuestionFlawViewSet
reviews/             QuestionReviewViewSet
comments/            QuestionCommentViewSet
sources/             QuestionSourceViewSet
blueprints/          BlueprintViewSet
blueprint-items/     BlueprintItemViewSet
tags/                TagViewSet
```

Register: `INSTALLED_APPS += ['qbank']`, `APP_REGISTRY += [{id:'qbank',…}]`,
`config/urls.py += path(f'{api_prefix}/qbank/', include('qbank.urls'))`.
Follow `emissions`/`people` structure exactly (models, serializers, services,
views, urls, admin, apps, migrations, tests, signals).

---

## 9. Frontend (`/apps/qbank`)

React 19 + MUI v7 module, same shell as carbon:

- **Question list** — filter by outcome/system/cognitive level/status/org_unit.
- **Question editor** — stem + lead-in, options, rationale, tags, dual-lang toggle.
- **Review gate** — live DQ findings + AI flaws side-by-side, one-click resolve.
- **Blueprint dashboard** — outcome coverage bars vs `BlueprintItem` targets.
- **Outcome browser** — the framework tree, drill into questions per outcome.
- i18n: chrome translated (en/ar), question content authored in-language.

---

## 10. Phasing

| Phase | Deliverable | AI? |
|-------|-------------|-----|
| **0** | Register `qbank` app + `APP_REGISTRY` + urls; seed `ReferenceSet`s + OutcomeFrameworks | no |
| **1** | Typed models + migrations + CRUD (Question/Option/AnswerKey/Outcome/Tag/Source) | no |
| **2** | Versioning + review workflow + `GovernanceEvent` + RBAC | no |
| **3** | DQ item-writing rules + `QuestionFlaw` model + review gate UI | no |
| **4** | Blueprinting + coverage analytics | no |
| **5** | Pulse manifest (`generate_item`, `review_item`, `tag_suggest`, `blueprint_gap`) | **yes** |
| **6** | Media assets + dual-language translation pairs | partial |

---

## 11. Config-not-code (the operating principle)

**Everything domain-specific is data/config; only generic seams are code.** The
moment a medical-education concept becomes a hardcoded `choices` tuple or a
Python constant, we've shipped a maintenance debt. QBank's rule:

| Concept | Lives in | Add/change = |
|---------|----------|--------------|
| Question types (SBA/EMQ/SAQ/MRQ) | `mdm.ReferenceSet` seed | admin edit, no migration |
| Cognitive level (Bloom) / Miller level | `mdm.ReferenceSet` seed | admin edit |
| Disciplines, accreditation standards | `mdm.ReferenceSet` seed | admin edit |
| Flaw taxonomy (§2.2) | `mdm.ReferenceSet` (`flaw_type`) | admin edit |
| Outcome frameworks (ACGME/NARS/PLO…) | `OutcomeFramework`/`Outcome` seed | import data |
| Item-writing rules | `dq.DQRule` + `ModelRuleAssignment` | add a rule row, no code |
| Blueprint targets | `Blueprint`/`BlueprintItem` | add a row |
| Lifecycle transitions | `VALID_LIFECYCLE_TRANSITIONS` config dict | edit one dict |
| RBAC roles | `APP_REGISTRY` roles + `ScopedRole` | register a role |
| AI capabilities | `DomainAIOperations` manifest (declarative) | add a task type |
| **Code** | generic engine only: CRUD, versioning, audit, DQ engine, Pulse, allocation | rare |

**Consequence:** "add a new competency framework", "add a new flaw type", "add a
new item-writing rule" are **operations, not code changes** — a faculty or admin
can do them through the UI. This is what makes QBank an enterprise platform
rather than a bespoke question app.

---

## 12. ADR candidates (to write before Phase 1)

1. **ADR-0027 — QBank storage & taxonomy:** outcomes are a *typed hierarchical
   tree* (`OutcomeFramework`/`Outcome`), not `ReferenceSet`; questions are typed
   SoR models per ADR-0025.
2. **ADR-0028 — Dual-language content model:** `Question.language` + additive
   `QuestionTranslation` (content authored in-language, chrome translated).
3. **ADR-0029 — Review-gate split:** scalar-field DQ rules via
   `ModelRuleAssignment`; relational invariants in `clean()`/service (honest
   seam, avoids overloading the DQ engine).

---

## 13. Decisions (locked 2026-09-01)

1. **Typed-model app** (ADR-0025 SoR) — ✅ confirmed.
2. **Outcomes = hierarchical typed tree** (`OutcomeFramework`/`Outcome`) — ✅ confirmed.
3. **Item-writing rules = data, split two layers** (scalar → DQ, relational → `clean()`/service) — ✅ confirmed.
4. **Flaws enforced, not suggested** — ✅ confirmed; and "flaws" includes the
   **systemic failures of existing top systems** (§2.3), not just item-writing rules.
5. **Accreditation-grade audit** (GovernanceEvent + immutable versions) — ✅ confirmed.
6. **AI = last wave, and it's Pulse** — ✅ confirmed (RULE_21, drafts only).

| Decision | Resolution |
|----------|------------|
| App slug | `qbank` (keep as the slug; display name still open for English + Arabic label) |
| Primary types (Phase 1) | **SBA + EMQ**; SAQ via `AnswerKey` later |
| Frameworks first seed | **Institutional PLO/ILO + NARS (NAQAAE) + ACGME**; CanMEDS/EPAs/WFME deferrable as data |
| Student data | **NEVER in QBank** — INVARIANT-0, top-most protected |

**Remaining open (non-blocking):** the English/Arabic **display label** (slug is
`qbank`), and whether the college has an existing PLO/ILO document to seed from.
