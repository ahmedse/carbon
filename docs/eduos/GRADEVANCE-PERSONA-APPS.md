# GradeVance — Persona apps: Learn · Teach · Engine

**Status:** Accepted — 2026-09-19 (owner go; naming: learn / teach)
**Companion canvas:** [GradeVance Persona Apps](../../.cursor/projects/home-ahmed-ws-carbon/canvases/GradeVance-Persona-Apps.canvas.tsx)
**Owner seat:** EduOS
**Supersedes stance:** GRADEVANCE-DESIGN §3 "One app, five roles — not five apps" and
ADR-0038 §6 are *refined*, not reversed: still not five apps — **three persona
surfaces over one engine**, the exact shape Nibras uses (`my` / `team` / `people`,
ADR-0030 §8).
**Companion canvas:** *GradeVance Persona Apps* (`gradevance-persona-apps.canvas.tsx`)
**Related:** GRADEVANCE-DESIGN.md · GRADEVANCE-PROFESSOR-JOURNEY.md ·
GRADEVANCE-PROFESSOR-LIFECYCLE.md · ADR-0030 · ADR-0038 · RULE_31 · RULE_33

---

## 0. One-paragraph answer

Yes — split. Today GradeVance is one app whose sidebar is a professor console with a
"Student desk" bolted on. The student desk is actually a *demo tool* (pack picker,
gold examples, ad-hoc assignment creation that 403s for a real student), and the
shared list endpoints let anyone with `gradevance:submit` read **every student's
submission text**. The fix is the Nibras pattern: `learn` ("about me" — the
student), `teach` ("about my courses" — professor, TA/marker), and `gradevance`
("about everyone" — engine room: pack library, QA, proposals governance, LTI admin).
One Django app (`gradevance`) stays the system of record; the persona apps are
frontend manifests plus **self-scoped** and **course-scoped** endpoint namespaces,
just as `my`/`team` sit on `people/me/*` + `correspondence/*`.

---

## 1. What the top systems actually do

| System | Split? | Mechanism | Lesson for GradeVance |
|---|---|---|---|
| **Inspera Assessment** (high-stakes exams) | **Yes** | Two entry surfaces on one tenant: candidate `/` vs staff `/admin` (Author · Deliver · Monitor · Grade · Users). Same DB, different apps. | Precedent for a hard persona split in *assessment* specifically. Candidate UX is calm and single-purpose; staff UX is dense. |
| **PeopleSoft Campus Solutions** | **Yes** | *Student Center* vs *Faculty Center* — two self-service hubs over one SIS. | "Center per persona" is the 20-year enterprise default. |
| **Workday Student** | Persona dashboards, one platform | Role-based dashboards/tasks; explicitly designs for **multi-persona users** (student workers). | Same shell, both apps visible when a user holds both personas. Don't force one identity per person. |
| **Gradescope** | One app, role *per course* | Dashboard shows each course by roster role (Instructor / TA / Reader / Student). No instructor "student view"; account merges collapse to instructor. | **Role must live on the course enrollment, not on the user.** A PhD student is a TA in one course and a student in another. Our global `gradevance:submit` vs `gradevance:manage` cannot express that. |
| **Canvas LMS + Turnitin** | One app, role-adaptive + "Student View" | *Test Student* impersonation breaks external tools (no email / role). | Professors *want* to preview the student surface. Because we own both apps in one codebase, `teach` can render the real `learn` components for a real submission — no fake user. |
| **Turnitin Feedback Studio** | Instructor vs student *views* of one artifact | Instructor controls per-assignment what the student sees (report visibility, release). | Release/visibility is an assignment-level policy, and `learn` renders only what is released. |

Common flaws we refuse:

1. **Global role instead of enrollment role** (Gradescope merge pain).
2. **Fake test user for student preview** (Canvas / Turnitin breakage).
3. **Student surface = admin-lite** (pack pickers, gold samples, cohort stats leaking into a learner's screen).
4. **Shared list endpoints across personas** (our current `/submissions/` leak).
5. **Two apps drifting into two backends** — ADR-0030's whole point is *peer surfaces over one engine*.

---

## 2. Audit of the current GradeVance (as of Phase C)

### 2.1 Frontend

| Finding | Severity | Evidence |
|---|---|---|
| Single manifest, 7 nav items, all `role: '*'`; persona is only expressed by hiding menu items via `MENU_ITEM_CAPABILITIES`. | High | `apps/gradevance/manifest.js` |
| A pure student (`gradevance:submit` only) lands on `/apps/gradevance` → `GRADEVANCE_VIEW` required → blocked; there is no student home. | High | `capabilities.js` ROUTE_CAPABILITIES |
| `StudentDeskPage` shows **pack picker** and **gold/held-out examples** and calls `createAssignment` (`gradevance:manage`) when no LTI assignment is linked → a real student gets 403 on "Run formative analysis". It is a professor demo, not a student desk. | High | `StudentDeskPage.jsx` lines 70–80 |
| No student "my courses / my assignments / my results / appeal" surface. Only LTI deep-link supplies assignment context. | High | routes in `App.jsx` |
| Overview (`GradeVanceHome`) is cohort metrics — correct for professors, wrong as anyone's landing if they are a student. | Medium | RULE_33 already says so |
| Professor pages follow compact-ui (dense, desktop). Students need a mobile-first, calm reading surface (ADR-0035). One app cannot carry two density defaults cleanly. | Medium | ADR-0035 |
| No "preview as student" for a published stem. | Medium | — |

### 2.2 Backend (`backend/gradevance`)

| Finding | Severity | Evidence |
|---|---|---|
| `SubmissionListCreateView.get` returns **all submissions incl. `text`** to anyone passing `GradevanceReadOrSubmit` (GET → view **or submit**). A student can enumerate the cohort's reflective prose (sensitive per DESIGN §10). | **Critical** | `views.py` ~L299–310 |
| `SubmissionAnalyzeView.post` lets any submitter trigger analysis on **any** submission id. | High | `views.py` ~L326 |
| No `Enrollment`/roster model → no per-course role, no "my courses", no course ownership scoping for professors (any `manage` sees all courses). NRPS roster sync creates users but not memberships. | High | `models.py`; `lti/roster_sync.py` |
| `AnalysisRun.released` exists but there is **no student-facing read** that filters summative bands by `released`. Students only see the inline result of their own POST. | High | `views.py` RunDetailView requires `view` |
| `RunDetailView` requires `gradevance:view`; a student cannot reopen their own run later. | Medium | `permissions.py` |
| No appeal / regrade-request object (Phase D placeholder). | Medium | DESIGN §3 lists appeals for Student |
| Deep-link default target is `/apps/gradevance/student?assignment=…` — will move. | Low | `lti/deep_link_views.py` L34 |

Net: the *engine* is sound (pipeline, HITL, packs, gate). The **persona layer is
missing**, and the shared read endpoints are a privacy bug independent of the app
split. Fix 2.2 rows 1–2 regardless of the outcome of this proposal.

---

## 3. Target: three peer surfaces over one engine

```
              ┌────────────── shell (EduOS brand) ──────────────┐
              │  Learn (/learn)   Teach (/teach)   GradeVance    │
              │  "about me"       "about my        (/apps/       │
              │                    courses"         gradevance)   │
              │                                    "about        │
              │                                     everyone"    │
              └───────┬───────────────┬─────────────────┬────────┘
                      │               │                 │
              gradevance/me/*   gradevance/teach/*   gradevance/*  (existing)
                      └───────────────┴─────────────────┘
                              backend app `gradevance`  (one SoR, one pipeline,
                              one HITL, one pack engine — unchanged)
```

Mapping to Nibras (ADR-0030 §8):

| Nibras | EduOS | Scope rule | Capability |
|---|---|---|---|
| `my` — ESS "About me" | **`learn`** — the student | `Submission.student_user == request.user`; courses via `Enrollment(role=student)` | `learn:access` (implied by `gradevance:submit`) |
| `team` — MSS "About my reports" | **`teach`** — professor + TA/marker | `Enrollment(role in instructor, ta)` on the course → its assignments, submissions, runs, queue | `teach:access` (implied by `gradevance:manage` or `gradevance:mark`) |
| `people` — domain admin "About everyone" | **`gradevance`** (kept) — engine room | global | `gradevance:view/qa/manage` |

### 3.1 `learn` — student app ("My studies")

Nav (calm, mobile-first, ≤4 items):

- **Home** — due soon, latest coaching, released results. No cohort numbers, ever.
- **My assignments** — by course; status: open / drafted / submitted / released.
- **Assignment** `/learn/assignments/:id` — brief + rubric bands as *expectations*, draft
  editor (autosave), "Get formative coaching" (advisory watermark), submit for marking,
  released result view (only if `released`), **Request review** (appeal) when released.
- **My progress** — wave-over-drafts, band trajectory for *me only*.

Removed from the student surface: pack picker, gold/held-out examples, profile version,
any `createAssignment`. Practice mode = professor-published *practice assignments*
(`mode=formative`, open enrollment), not student-created ones.

### 3.2 `teach` — professor / marker app ("My classes")

Exactly the RULE_33 spine, scoped to my courses:

Courses & stems → Assignment hub → Run workbench (HITL) → Marking queue →
**Stems console** (FilteredDataGrid) → Stem master-detail → Submission master-detail → Run workbench → Marking queue →
Calibration → Proposals (mine / my packs). Plus:

- **Preview as student** on Assignment hub: renders the real `learn` assignment view for
  a chosen submission (own-codebase advantage; no Test Student).
- **Roster** tab per course: `Enrollment` rows (manual, entry-code, NRPS), role per row.
- Marker persona = `teach` with `gradevance:mark` and TA enrollment; queue filtered to
  their courses. Not a fourth app (Gradescope: TA/Reader are course staff).

### 3.3 `gradevance` — engine room (kept, trimmed)

Pack library · Profile detail · Calibration (cross-course) · Proposals governance
(accept → bump → canary) · QA console (κ/α, bias, drift) · LTI admin · Accessibility
checklist. Audience: pack leads, QA, admins. Overview stays cohort/engine metrics.

### 3.4 Backend additions (all inside `backend/gradevance`)

1. `Enrollment(course, user, role: student|ta|instructor, source: manual|code|nrps, active)`;
   `Course.entry_code` optional. NRPS sync writes memberships, not just users.
2. `gradevance/me/` namespace (mirror of `people/me/*`): `courses/`, `assignments/`,
   `assignments/<id>/`, `submissions/` (own only; POST creates draft/submit),
   `runs/<id>/` (own only; summative fields stripped unless `released`), `appeals/`.
3. `gradevance/teach/` namespace or — cheaper — **course-scope filter mixin** on existing
   manage/mark views: `Course ∈ my instructor/ta enrollments` unless `gradevance:qa`
   or admin. Recommend the mixin first; a separate prefix only if the API shapes diverge.
4. Fix now (independent of split): `SubmissionListCreateView.get` and
   `SubmissionAnalyzeView.post` scope to own submissions when caller lacks
   `gradevance:mark|manage`.
5. `Appeal(run, student_user, reason, status, resolution, resolved_by)` — Phase D.
6. Capabilities: add `learn:access`, `teach:access`; backend `CAPABILITY_IMPLIES`
   `gradevance:submit → learn:access`, `gradevance:manage|mark → teach:access`;
   mirror in frontend `capabilities.js`. Enrollment role gates data, capability gates the
   app tile — same two-layer rule as Nibras.
7. Deep link target → `/learn/assignments/<id>`; LTI role claim `Learner` → student
   enrollment, `Instructor` → instructor enrollment.

### 3.5 Frontend additions

- `src/apps/learn/manifest.js` (`routePrefix: '/learn'`, `apiPrefix: '/gradevance/me/'`)
  and `src/apps/teach/manifest.js` (`routePrefix: '/teach'`, `apiPrefix: '/gradevance/'`).
  Register in `registry.js` and backend `APP_REGISTRY`; enable on `eduos` only
  (`PLATFORM_APPS['eduos'] = {gradevance, learn, teach}`) — RULE_31.
- `Shell.studioFromPath`: add `/learn`, `/teach` (same as `/my`, `/team`).
- Move pages: `CoursesPage`, `AssignmentHubPage`, `RunWorkbenchPage`, `MarkingPage`,
  `CalibrationPage` → `apps/teach/`; `ProposalsPage` stays in `gradevance` with a
  "my proposals" filter surfaced in `teach`. Old `/apps/gradevance/*` professor routes
  become `<Navigate>` redirects (same pattern as `/authoring`).
- New `apps/learn/`: `LearnHome`, `MyAssignmentsPage`, `AssignmentPage` (draft/coach/
  submit/result/appeal), `ProgressPage`. Shared `WaveChart`, `LctCodesTable`,
  `PackDetailDrawer` move to `src/components/gradevance/` (shared, no cross-app import).
- Density: `teach` keeps compact-ui defaults; `learn` uses the mobile-first shell
  profile from ADR-0035 (larger tap targets, single column, reading width).
- Each new page gets the RULE_29 9-artifact screen spec (backfill the professor pages
  at the same time — this is the debt from Phases A–C).

---

## 4. Why not the alternatives

| Option | Verdict | Why |
|---|---|---|
| Keep one app, harder menu filtering | Reject | Doesn't fix landing, density, deep links, or the missing self-scoped API; persona stays implicit. The current bugs are the proof. |
| One app with a persona switcher ("View as student") | Reject as *primary* | Good for preview inside `teach`, wrong as architecture — Canvas/Turnitin show the impersonation edge cases. |
| Five apps (admin/prof/marker/student/QA) | Reject | ADR-0038 §6 still stands; marker and QA are capability facets of `teach` and `gradevance`. |
| Separate backend app per persona | Reject | Violates ADR-0030 lesson; one SoR, one audit trail, one pipeline. |
| **Three peer surfaces over one engine** | **Adopt** | Mirrors `my`/`team`/`people`; matches Inspera + PeopleSoft precedent; enrollment-role model fixes the Gradescope flaw; enables real student preview. |

---

## 5. Phased plan

| Phase | Scope | Exit |
|---|---|---|
| **P0 — privacy hotfix** ✅ shipped 2026-09-19 | Scoped `/submissions/` GET and `/submissions/<id>/analyze/` to own rows unless mark/manage (`_is_course_staff`); `tests/test_persona_scope.py`. | Student cannot read another student's text (pytest, 3 tests; suite 90/90). |
| **P1 — model + me/ API** ✅ shipped 2026-09-19 | `Enrollment`, `gradevance/me/*`, `released` stripping, capabilities `learn:access`/`teach:access`, NRPS → enrollments, deep-link target. | Backend tests: student sees own courses/assignments/runs only; instructor scope filter (97/97). |
| **P2 — `learn` app** ✅ shipped 2026-09-19 | Manifest, 4 pages, redirect `/apps/gradevance/student`. | Real student path wired under `/learn`. |
| **P3 — `teach` app** ✅ shipped 2026-09-19 | Manifest, professor pages under `/teach`, redirects from legacy `/apps/gradevance/*`. | Professor journey under `/teach`. |
| **P4 — engine room + enable** ✅ shipped 2026-09-19 | `gradevance` nav trimmed; `learn`/`teach` in APP_REGISTRY + eduos BRAND_APP_PRESETS; seats.md. | Apps enabled on eduos. |
| **P5 — roster + join** ✅ shipped 2026-09-19 | `EnrollmentSerializer`; `courses/<id>/enrollments/`; `me/join/`; seed `gv_student` + `DEMO-LCT` entry code; teach Roster UI; learn join form. | Manage can roster; student joins by code and sees assignments. |
| **P6 — Phase D enterprise** ✅ shipped 2026-09-19 | Appeal model + me/teach APIs; draft/submit lifecycle; my_status; me/progress; preview-as-student; audit export UI; QA/A11y/LTI engine pages; RULE_29 specs in `docs/eduos/screens/PHASE-D-SCREEN-SPECS.md`. | 109+ tests; student draft→coach→appeal; teach resolve; audit JSON. |
| **Stems console IA** ✅ shipped 2026-09-19 | Teach `/teach/stems` FilteredDataGrid multitab → stem master-detail → submission master-detail → run workbench. Legacy `/teach/courses` + `/teach/assignments/:id` redirect. | QA+Master dual refresh; suite 109 green. |
| Docs | Amend DESIGN §3/§11, LIFECYCLE, JOURNEY; ADR-0042 Accepted; RULE_33 learn/teach. | Toolkit consistent. |

Naming is the one open call: `learn` / `teach` (verbs, short, brand-neutral, match the
`my` / `team` register) vs `student` / `faculty` (PeopleSoft register) vs
`studies` / `classes`. Recommendation: **`learn` / `teach`**; the sidebar section titles
can still read "My studies" / "My classes".

---

## Changelog

- 2026-09-19 — Initial audit + proposal (enterprise research: Inspera, PeopleSoft CS,
  Workday Student, Gradescope, Canvas/Turnitin).
- 2026-09-19 — P0–P4 shipped (privacy, Enrollment + me/*, learn/teach apps, engine enable).
- 2026-09-19 — P6 Phase D: appeals, draft/submit, progress, preview-as-student,
  audit UI, RULE_29 specs, QA/A11y/LTI pages; suite 109 green.
  Specs: docs/eduos/screens/PHASE-D-SCREEN-SPECS.md.
- 2026-09-19 — Stems first-class console (QA+Master refresh): `/teach/stems`
  FilteredDataGrid → stem multitab → submission master-detail cascade.