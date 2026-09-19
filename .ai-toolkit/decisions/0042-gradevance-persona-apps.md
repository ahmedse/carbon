# ADR 0042 — GradeVance persona apps: Learn · Teach · Engine (three surfaces, one engine)

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** Master Architect (EduOS seat) with owner
- **Area:** frontend manifests + backend `gradevance` API namespaces (EduOS only, RULE_31)
- **Refines:** ADR-0038 §6 ("roles, not five apps") — still not five apps.
- **Mirrors:** ADR-0030 §8 ("three peer surfaces over one engine": `my` / `team` / `people`).

## Context
GradeVance shipped Phases A–C as one frontend app whose sidebar is a professor console
with a "Student desk" item. Audit (docs/eduos/GRADEVANCE-PERSONA-APPS.md §2) found:
the student page is a demo tool (pack picker, gold examples, `createAssignment` that
403s for a real student); a submit-only user has no landing route; and the shared
`/submissions/` GET returns every student's reflective text to anyone with
`gradevance:submit`. Enterprise precedent (Inspera candidate vs `/admin`, PeopleSoft
Student Center vs Faculty Center, Workday multi-persona dashboards) splits learner and
staff surfaces; Gradescope's global-role model and Canvas's fake Test Student are the
flaws to avoid.

## Decision
1. **Three persona surfaces over one engine.** New frontend manifest apps
   `learn` (`/learn`, "about me" — student) and `teach` (`/teach`, "about my courses"
   — professor + TA/marker). Existing `gradevance` (`/apps/gradevance`) becomes the
   engine room ("about everyone": pack library, calibration, proposals governance, QA,
   LTI admin). Enabled on `eduos` only.
2. **One backend app.** `backend/gradevance` remains the sole system of record and
   pipeline. Add a self-scoped namespace `gradevance/me/*` (as `people/me/*`) and a
   course-scope mixin on manage/mark views. No per-persona backend apps.
3. **Role lives on the enrollment, not the user.** New `Enrollment(course, user,
   role ∈ student|ta|instructor, source ∈ manual|code|nrps)`. Capabilities gate the app
   tile (`learn:access` ⇐ `gradevance:submit`; `teach:access` ⇐ `gradevance:manage|mark`);
   enrollment role gates the data. NRPS sync writes enrollments.
4. **Student surface renders only released fields** for summative runs; formative
   coaching always visible. No authoring affordances in `learn`; practice = published
   practice assignments.
5. **Preview-as-student in `teach`** renders the real `learn` components on a real
   submission — never a fake test user.
6. **Marker and QA are capability facets**, not apps (marker ⊂ `teach`, QA ⊂ `gradevance`).
7. **Density split:** `teach` = compact-ui; `learn` = ADR-0035 mobile-first profile.
8. **P0 independent of this ADR:** scope `/submissions/` GET and
   `/submissions/<id>/analyze/` to own rows unless mark/manage.

## Alternatives Considered
- One app + stricter menu filtering — rejected: persona stays implicit; does not fix
  landing, density, deep links, or self-scoped API.
- One app + persona switcher as architecture — rejected as primary (kept as preview).
- Five apps — rejected (ADR-0038 §6).
- Backend app per persona — rejected (ADR-0030 lesson; one audit trail, one pipeline).

## Consequences
- **Positive:** privacy by construction (self-scope), student UX designed for learners,
  professor journey under one prefix, multi-persona users supported, real student
  preview, shell/registry patterns reused verbatim from Nibras.
- **Negative / trade-off:** page moves + redirects from `/apps/gradevance/*`; new
  `Enrollment` migration; docs to amend (DESIGN §3/§11, LIFECYCLE, JOURNEY, RULE_33,
  seats.md). Naming (`learn`/`teach`) to be locked by owner.

## Related
- Audit + plan: `docs/eduos/GRADEVANCE-PERSONA-APPS.md`
- Canvas: *GradeVance Persona Apps*
- ADR-0030 §8, ADR-0035, ADR-0038, RULE_31, RULE_33
