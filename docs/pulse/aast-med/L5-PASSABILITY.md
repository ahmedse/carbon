# Medicine L5 — passability analysis (frozen 2 Oct 2026)

This is the "Grounded lecture" L5 that blocks K11 and R16, **not**
`ai.eval.intelligence_ladder.score_l5` (the ESS autonomy rung). The frozen
status lives in `domain_packs/aast-med/gold/l5.yaml`; the contract test is
`backend/ai/tests/test_moodle_l5.py`.

## 1. What the scorer requires today

`test_moodle_l5.py` asserts, and `gold/l5.yaml` encodes:

| Field | Required | Current |
|---|---|---|
| `status` | `passable` to open | `not_passable` |
| `curriculum_benchmark.sample_size` | `100` per shortname | `100` |
| `curriculum_benchmark.min_passage_cite` | `>= 95` of 100 | `95` |
| `curriculum_benchmark.max_extra_fact` | `<= 2` of 100 | `2` |
| `curriculum_benchmark.per` | `shortname` | `shortname` |
| `curriculum_benchmark.notice_courses` | `13` | `13` |
| `curriculum_benchmark.at_bar` | shortnames at the bar | `13` |
| `curriculum_benchmark.handout_frozen_n` | 8 NMD1103 handout cases | `8` |
| `curriculum_benchmark.short` | per-shortname result map | `{}` (empty) |
| `enabled_courses_gold_covers` | the listed shortnames | 13 names |
| `r11_draft.required_n` / `frozen_n` | `4` / `>= 4` | `4` / **`0`** |
| `r12_same_lecture_two_students.required_n` / `frozen_n` | `2` / `>= 2` | `2` / **`0`** |
| `r12_same_lecture_two_students.blocked_by` | must clear | `student_cohorts_empty` |

`_status` is all-or-nothing: any false gate keeps L5 `not_passable`. R11 and
R12 are the two false gates (both `frozen_n == 0`). `short: {}` means the
per-shortname 100-question curriculum benchmark is **not yet recorded as
passing** for any shortname.

## 2. Exactly what must exist for L5 to pass

### 2.1 Curriculum benchmark (per shortname, code + authored content)

For **each** shortname in `enabled_courses_gold_covers` (13):

- a frozen 100-question set whose answers are checkable against the pack
  bank, produced from the course's own stored passages;
- `>= 95` of 100 answers cite a passage id **from that lecture**;
- `<= 2` of 100 add a curriculum fact that is not in the passage;
- the per-shortname result is written into `curriculum_benchmark.short`.

Authoring the questions and citing passages is **code/content work** (the
deterministic doors already cite; `gold/conformance-13.yaml` proves body-only
topics per course). Freezing them as gold and proving counts is code work.
**Approving** the gold as a curriculum statement is a human decision.

### 2.2 R11 — draft labelling (4 frozen cases)

Four frozen cases showing a teaching/study draft is labelled draft and does
**not** claim a Moodle write (ADR-0046). This is **code work**: draft-only
proposals already exist; the four cases must be authored and frozen.

### 2.3 R12 — same lecture, two students (2 frozen cases)

Two frozen cases where **two real student accounts** open the same lecture and:

- receive the **same** cited passages;
- neither reply mentions past performance or the other student.

This needs a **real student cohort** (two student accounts) because it tests
oversharing between real identities. **`student_cohorts` is empty**, and R16
forbids filling it before L5. So R12 is the circular blocker: it needs a
cohort, and the cohort is forbidden until L5 passes.

## 3. Code vs real-world

| Part | Classification | Notes |
|---|---|---|
| Per-shortname 100-question benchmark + passage-cite counting | **CODE** (finishable) | Deterministic doors already cite; author + freeze gold + assert counts. Human approval of the frozen gold is a sign-off, not new machinery. |
| R11 draft cases (4) | **CODE** (finishable) | Draft-only proposals exist; freeze four cases. |
| R12 two-student cases (2) | **REAL-WORLD ARTIFACT** | Requires two real student accounts on the same lecture. |
| Non-empty `student_cohorts` | **REAL-WORLD ARTIFACT** | A deliberate config decision; R16 forbids it before L5. |
| Consent / RBAC / audit records | **REAL-WORLD ARTIFACT** (code built) | Gate exists default-OFF; needs real records. |

The per-shortname benchmark was a **CODE** gap: `sample_size: 100`,
`handout_frozen_n: 8`. It is now authored in full at
`gold/l5-curriculum.draft.yaml` — 1300 items, 100 per shortname across all 13
listed courses, each citing a real passage with a verbatim span (the door cites
1299/1300, bar ≥95, 0 extra facts). The remaining step is **human review and
freeze** of that draft into `gold/l5.yaml`, which is a sign-off, not new
machinery. The frozen `gold/l5.yaml` stays `not_passable` with `short: {}`
until that sign-off; do not self-approve it.

## 4. What must NOT happen

- Do not fake the scorer or edit `gold/l5.yaml` `status` to `passable`.
- Do not loosen `min_passage_cite` / `max_extra_fact`.
- Do not fill `student_cohorts` to make R12 possible.
- Do not mark L5 green anywhere; it stays `not_passable` with the blocker.
- Do not count the intelligence-ladder L5 (ESS autonomy) toward this L5.

## 5. One verified step from flipping

The code-side machinery is complete and proven default-OFF
(`ai/moodle_readiness`). The remaining rung that needs a **real-world
artifact** — R12 with two real students — is one deliberate, audited config +
consent action away once the CODE items (per-shortname 100-question gold, R11)
are authored and approved. That action is exactly: publish the student notice,
set `student_cohorts`, record consent, and run the two same-lecture cases.
