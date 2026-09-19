# GradeVance Phase D — Screen Specs (RULE_29)

**Status:** Approved for implementation — 2026-09-19 (Master Architect / EduOS)
**Scope:** Complete remaining Phase D + ADR-0042 product commitments that were thin or missing.
**Primitives (reuse only):** `PageContainer`, `PageHeader`, `LoadingSkeleton`, `ErrorAlert`, `EmptyState`, MUI `size="small"`, compact-ui density for teach/engine; learn uses same primitives with slightly larger tap targets (`minHeight` via `size="small"` buttons still).
**No raw `alert()`.** Mid-flow errors: `ErrorAlert` or inline `Alert` with retry. Forms: **SystemDialog** (never raw Drawer/Dialog). HITL ExpertEdit on Run workbench uses SystemDialog.

---

## Screen: `/learn/assignments/:assignmentId` — Assignment desk (COMPLETE)

**Owner:** Student (learn:access) · **IA:** My studies → My assignments → Assignment

### Story
As a student, I draft a reflection, get formative coaching, submit for marking when ready, see released results, and request a review (appeal) after release.

### Journey
Open assignment → read brief/expectations → draft (autosave) → Get coaching (optional) → Submit for marking → (marker releases) → view released bands → Request review.

### Acceptance
1. Load shows brief/stem; loading skeleton; error+retry; forbidden empty.
2. Draft autosaves (debounce ~800ms) via PATCH own submission `status=draft`.
3. Explicit **Save draft** and **Get formative coaching** (analyze, keeps draft or submitted policy: coaching allowed on draft).
4. **Submit for marking** sets `submitted`; creates ReviewItem for summative.
5. Released summative shows bands; unreleased shows withheld callout.
6. **Request review** enabled only when latest run is released (or formative complete); creates Appeal.
7. PageHeader actions: Save draft | Coaching | Submit (primary) — compact.

### Composition
```
PageContainer
 └─ SkipToMain
 └─ PageHeader (title=assignment.title, actions=Save|Coach|Submit)
 └─ Chip row: my_status, mode, released?
 └─ Paper: brief/stem + band_expectations (from profile if present)
 └─ TextField multiline draft
 └─ ErrorAlert (load or action errors)
 └─ Paper result: coaching + LctCodesTable + WaveChart | withheld Alert
 └─ Paper appeal: reason TextField + Request review | appeal status + Withdraw when open
```

### State matrix
idle→loading→loaded|empty(no asg)|error|forbidden; draft dirty; saving; coaching; submitting; appeal_submitting; appeal_withdrawing; success toast via msg Alert.

### Data contract
- GET `me/assignments/:id/` → assignment + `my_status`, `course_title`, `brief`, `band_expectations?`, `due_at?`
- GET `me/submissions/?assignment=` → latest sub
- POST `me/submissions/` `{assignment,text,analyze?,status?}` 
- PATCH `me/submissions/:id/` `{text?,status?}` own only
- GET `me/runs/:id/`
- POST `me/appeals/` `{run,reason}` ; GET `me/appeals/?assignment=` ; POST `me/appeals/:id/withdraw/`

### A11y / Perf / i18n
main landmark; labels on fields; buttons aria-busy; LCP draft field <2.5s; English strings (i18n keys later).

---

## Screen: `/learn` — Home (COMPLETE + L1 coaching)

### Composition
PageHeader · Join-by-code Paper · Due soon list · Released results list · Latest coaching snippet · CTA My assignments

### Data
me/assignments, me/submissions (includes `latest_run.coaching` + `assignment_title`), me/progress

### Acceptance (L1)
Home “Latest coaching” shows strengths when a formative run exists — contract: `GET me/submissions/` → `latest_run: { id, coaching }`.

---

## Screen: `/learn/assignments` — My assignments (COMPLETE + L2 by course)

**Owner:** Student (learn:access) · **IA:** My studies → My assignments

### Story
Browse published assignments grouped by enrolled course; optional course filter.

### Journey
Open list → pick course filter (optional) → open assignment desk.

### Acceptance
1. Sections grouped by `course_title` (or “No course”).
2. Course filter via `?course=` + `GET me/courses/` + `GET me/assignments?course=`.
3. Calm Paper/Chip list — **not** FilteredDataGrid.
4. EmptyState → Learn home / join path.
5. Loading skeleton; ErrorAlert + retry.

### Composition
```
PageContainer → PageHeader (Course Select filter)
 └─ Stack of course sections
     └─ Paper rows (title, due, mode, my_status) → /learn/assignments/:id
```

### Data
GET `me/courses/` · GET `me/assignments/?course=`

---

## Screen: `/learn/progress` — My progress (COMPLETE)

### Story
See my wave and band trajectory across drafts/runs, grouped by assignment.

### Composition
PageContainer → LearnReadingWidth → PageHeader → EmptyState|assignment groups (trajectory of drafts + WaveChart) → link to assignment.

### Data
GET `me/progress/` → `{results:[{assignment_id,title,submission_id,run_id,status,released,advisory_bands,wave_points,created_at}]}`

### States
loading / empty / loaded / error+retry

---

## Screen: `/teach/stems` — Stems console (FIRST-CLASS)

**Owner:** Professor / marker (teach scope) · **IA:** My classes → Stems

### Story
As a teacher, I browse stems in a Carbon FilteredDataGrid with search + filters, author new stems, and manage course roster — then open a stem to set context and work its cohort.

### Journey
Stems tab (grid) → click row → stem master-detail · Author tab → publish → stem detail · Courses tab → roster.

### Acceptance
1. Multitab console: **Stems** | **Author** | **Courses** (tab persisted localStorage).
2. Stems tab uses `FilteredDataGrid` (search, status/mode/course/profile filters, sort, row click).
3. Click stem navigates to `/teach/stems/:id` and sets teach stem context.
4. Author tab: create draft/publish with summative κ gate (fail-closed).
5. Courses tab: create course + roster activate/deactivate.
6. Legacy `/teach/courses` redirects here.

### Composition
```
PageContainer → PageHeader (New stem | Calibration)
 └─ Tabs: Stems | Author | Courses
 └─ Stems: FilteredDataGrid (embedded)
 └─ Author: form Paper (course, pack, mode, stem, instructions)
 └─ Courses: create + FilteredDataGrid + roster Paper
```

### Data
GET `assignments/`, `courses/`, `profiles/` · POST assignments/courses · enrollments CRUD

---

## Screen: `/teach/stems/:assignmentId` — Stem master-detail

### Story
Operate one stem in context: edit/view prompt, filter submissions, open runs, ingest cohort text.

### Journey
Back to Stems · tabs Stem | Submissions | Runs | Ingest · click submission → submission master-detail · click run → workbench.

### Acceptance
1. Sets `teach.stemContext` (sessionStorage) on load.
2. Multitab with URL `?tab=` + localStorage persistence.
3. **Submissions** tab: embedded FilteredDataGrid — search, status/run/released filters, group-by (status|run|student), sort, row click.
4. **Runs** tab: same grid pattern; row → `/teach/runs/:id`.
5. Preview as student Drawer preserved.
6. Legacy `/teach/assignments/:id` redirects here.

### Composition
PageHeader (context chips) → Tabs → Stem Paper | Submissions FilteredDataGrid | Runs FilteredDataGrid | Ingest Paper

### Data
GET `assignments/:id/` hub (assignment + submissions + runs + counts)

---

## Screen: `/teach/stems/:id/submissions/:submissionId` — Submission master-detail

### Story
Inspect one submission under the active stem; analyze; open latest run workbench.

### Acceptance
1. Tabs: Text | Runs (FilteredDataGrid of runs for this submission).
2. Analyze → navigate to run workbench.
3. Back returns to stem Submissions tab.

### Data
Reuse hub GET; POST `submissions/:id/analyze/`

---

## Screen: `/teach/assignments/:id` — Hub + Preview as student

**Superseded** by `/teach/stems/:id` (redirect). Preview-as-student and audit export remain on stem detail / run workbench.

---

## Screen: `/teach/appeals` — Appeals inbox

### Story
Marker/professor resolves student review requests for their courses.

### Composition
PageContainer → PageHeader → Table (student, assignment, reason, status, opened) → Open run / Resolve Drawer (resolution text + Resolve button)

### Data
GET `appeals/?status=open` (teach-scoped) · POST `appeals/:id/resolve/` `{resolution,status}`

### Nav
Teach manifest: Appeals

---

## Screen: `/apps/gradevance/qa` — QA console

### Story
QA/lead sees reliability (κ), canary note, open appeals count, audit sampling link.

### Composition
PageContainer → PageHeader → Grid of Stats → Calibration deep-link → Appeals count → Fairness notes Callout

### Data
GET `qa/summary/` + reuse calibration query params

---

## Screen: `/apps/gradevance/accessibility` — A11y checklist

### Data
GET `accessibility/` — render checklist table; update VPAT routes to /learn /teach

---

## Screen: `/apps/gradevance/lti` — LTI admin

### Data
GET `lti/status/` + `lti/config/` — read-only cards; copy JWKS/tool-config URLs; no secrets displayed.

---

## Shared backend contracts (Phase D)

### Appeal
```
Appeal: id, run FK, student_user FK, reason Text, status open|accepted|rejected|withdrawn,
        resolution Text, resolved_by FK null, created_at, updated_at
```

### Submission lifecycle
- Default new POST without status → draft if analyze false and status=draft; analyze may keep draft.
- PATCH text/status own only; submitted cannot revert to draft.
- Submit for marking: status=submitted; if summative → ReviewItem open.

### Assignment
- `due_at` DateTimeField null
- Me list includes `my_status`, `course_title`, `due_at`

### Enrollment
- PATCH `active`, `role` (manage)

---

## Reuse audit
- [x] PageContainer / PageHeader / LoadingSkeleton / ErrorAlert / EmptyState
- [x] WaveChart / LctCodesTable from gradevance (extract to components/gradevance if needed)
- [x] No new emoji icons — MUI icon names
- [x] compact-ui size=small
- [x] Shell owns breadcrumbs — no in-page crumbs
