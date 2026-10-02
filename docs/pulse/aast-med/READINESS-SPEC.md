# aast-med Pulse — Readiness Spec (frozen 2 Oct 2026)

Owner: Pulse-for-medicine readiness. Scope: the four frozen ladders on the
aast-med manifesto canvas — staff **K10**, students **K11**, memory **B4/B5**,
graph **B6/C7** — plus the notice, consent, cohort, RBAC, and audit rules a
student surface must satisfy.

This spec does **not** rewrite the frozen ladders. It states, per rung, the
principle, the exact rule, the checkable benchmark that flips it, an
L0–L5-style excellence ladder, and an honest blocker. Nothing here marks K8,
K10, K11, L5, B5, B6, or C7 green.

Frozen contracts this spec obeys, without exception:

- ADR-0046 / RULE_35 — Chat never host-mutates; writes are Plan → Approve →
  Run → RULE_21.
- Pulse 2.1 contract (`backend/**/engine/**` domain-free; no phrase tables,
  no routing `re.compile`, no brand ids).
- Intelligence contract (ADR-0047) and measurement contract (RULE_36).
- `student_cohorts` stays empty. K4/K9, B5, B6, C7 stay red/not_passable.

Code side (default-OFF, inert until constructed in tests):
`backend/ai/moodle_readiness/` — `gate.py`, `notices.py`, `evaluator.py`.

---

## 0. Two things that are both called "L5" — read this first

There are two unrelated rungs named L5. Do not conflate them.

| Name | Where | What it means now |
|---|---|---|
| **intelligence L5** | `ai.eval.intelligence_ladder.score_l5` | ESS autonomy unit contract: bound lookup + bound write spend 0 LLM. Scored from `lookup_zero_llm` / `write_zero_llm`; a live plan `llm_calls > 0` downgrades to `partial`. Unrelated to students. |
| **medicine L5** ("Grounded lecture") | canvas Excellence ladder; frozen in `domain_packs/aast-med/gold/l5.yaml`; checked by `ai/tests/test_moodle_l5.py` | C6 green for every listed shortname; ≥95 of 100 curriculum answers per shortname cite a passage from that lecture; ≤2 add a non-passage fact; **R11 and R12 green**. This is the L5 that blocks K11. |

This spec's K11/B5 use **medicine L5**. Its full passability analysis is in
`L5-PASSABILITY.md`.

---

## 1. Cross-cutting rules — notice, consent, cohort, RBAC, audit

These are exact rules. The code side is `ai/moodle_readiness/`; the wire-up is
a deferred plugin/Carbon change (see `DEFERRED.md`).

### 1.1 Staff notice (K10, R15 + R18)

- **Exact content (frozen, the only sentence that may be sent):**

  > Pulse is on for staff in the named cohort, on the named course shortnames.
  > It answers from the lecture you have open. It does not grade, enrol, or see
  > another student. If the fact is not in that lecture, it says so.

- **Must also carry the R18 "does not" clauses** (stable tokens in code:
  `no_grade`, `no_enrol`, `no_other_student`, `no_clinical_dose`,
  `lecture_miss`): no grade, no enrol, no other student's work, no clinical
  dose, and "not in this lecture" when the passage is missing.
- **Must name** the staff cohort idnumbers and the exact shortnames that have
  C6 gold. Naming a course that has files but no fact gold fails R15.
- **Placement:** sent to exactly the named staff cohort (Moodle system cohort
  idnumbers), never a college-wide mail. A site admin is a test door, not a
  recipient. The publish record (body + recipient cohort id + timestamp) is
  the K10 evidence.
- **Default:** unpublished. `NoticeRegistry()` constructs the staff notice
  `published=False`; publishing requires cohort + shortnames + all five R18
  clauses + a timestamp, or raises `NoticeDraftError`.

### 1.2 Student notice (K11, R16 — a separate decision)

- **Exact content (spec-frozen; NOT publishable until L5 passable and K11
  preconditions hold):**

  > Pulse is available to students in the named student cohort, on the named
  > course shortnames. It answers from the lecture you have open. It does not
  > grade or enrol you. It never shows another student's answers or work. It
  > does not give clinical doses or diagnose patients. If the fact is not in
  > that lecture, it says so. You may withdraw consent at any time;
  > withdrawing stops Pulse for you.

- **Must satisfy R16:** "student_cohorts stays empty until L5 is green for
  every shortname in the notice." A student idnumber saved to open a pilot
  faster is a fail.
- **Placement:** published to the student cohort only; shown in the pane
  before first use (the consent gate); recorded with timestamp + policy
  version. It is never mailed college-wide and never bundled with the staff
  notice.
- **Default:** unpublished, independent of the staff notice.

### 1.3 Consent — exact rules

1. Consent is **per `(subject, course_shortname)`** and carries a
   `policy_version`. Absent consent ⇒ deny. Default is absent.
2. Consent must be an **explicit positive opt-in**. Enrolment, cohort
   membership, or opening the pane is **never** consent.
3. Consent cannot be bundled with cohort membership or with accepting any
   other term.
4. The record stores `subject_id`, `course_shortname`, `policy_version`,
   `granted`, `granted_at`. A record whose `policy_version` differs from the
   surface's current version is **stale** and denies.
5. **Withdrawal** sets `granted=False`; the very next turn denies; there is no
   penalty and no further per-student learning use. Grant and revoke are both
   audited.
6. `consult_student_surface` check order (first failure is the audit reason):
   `course_not_listed` → `student_cohorts_empty` → `not_in_student_cohort` →
   `l5_not_passable` → `student_notice_unpublished` → `course_not_openable` →
   `no_consent` → `consent_revoked` → `consent_course_mismatch` →
   `consent_policy_stale` → `allow`.

### 1.4 Cohort definition — exact rules

1. A cohort is a **Moodle system cohort idnumber** listed in the plugin
   setting `local_pulse/staff_cohorts` or `local_pulse/student_cohorts`
   (comma-separated). It is an **allow-list only**.
2. Cohorts **never enrol** anyone. No cohort-sync enrol method is attached.
3. `student_cohorts` empty ⇒ **faculty-only**. Every student account is
   blocked, including a test account only when it is not a site admin (R3).
4. Membership is taken from the **signed snapshot**, never from an unsynced
   Carbon table. Carbon has **no** `student_cohorts` table; the empty state is
   configuration, not a DB. `student_cohorts` stays empty.
5. The gate's `Cohort` is `staff_ids` / `student_ids` frozensets; an empty
   `student_ids` reports `students_empty=True` and denies.

### 1.5 RBAC — exact rules

1. Capabilities: `local/pulse:use` (read) and `local/pulse:manage` (write).
   Students must **not** have `manage`; a student calling manage throws.
2. The gate allows only when `can_open_course=True`: the user can **already
   open** the course under Moodle enrolment / group / visibility. Pulse never
   grants access it does not already have.
3. A hidden or forbidden course contributes **zero** facts. Hidden sections
   are omitted (not "locked"). An unlisted course is `course_not_listed`.
4. No `people:view`. No cross-student data. Another student's work never
   leaves Moodle.

### 1.6 Audit — exact rules

1. Every student-surface **allow and deny** is logged with the typed reason,
   subject, course, cohort id, consent policy version, and timestamp. Content
   is not logged beyond ids.
2. **Grant and revoke** consent events are logged.
3. Audit is **append-only**. No per-student learning data is written before
   cohort + consent.
4. Audit must never change the curriculum answer: two students on the same
   lecture get the same cited passages and no history mention (R12).

---

## 2. R-Staff · K10 (staff on production)

**Principle.** A staff user, on the real production Moodle, in the named staff
cohort, on a listed course, opens Pulse and gets a correct cited answer; the
Pulse admin desk works.

**Exact rule.** Plugin installed **and enabled** on the production Moodle 4.1
site; Connection Ask URL + pane URL + HMAC secret set and HMAC verifies;
`staff_cohorts` non-empty (a named cohort); `enabled_courses` lists only
shortnames that have C6 gold; the admin desk (Courses / Pack / Extra /
Connection) works under `local/pulse:manage`; the R15+R18 staff notice is sent
to exactly that cohort; students remain off.

**Benchmark (the evidence that flips it).**

- On production, an admin test door on a listed shortname gets a ticket URL
  (R14); a **staff cohort member** gets a cited answer for a C6 question and
  the exact sentence `This is not in this lecture.` for an out-of-lecture
  question.
- A request with a **wrong HMAC signature is rejected**; the correct
  signature is accepted; clock skew > 120 s is rejected.
- `staff_cohorts` non-empty, `student_cohorts` empty; `enabled_courses` all
  carry C6 gold.
- The staff notice is published with cohort idnumbers + listed shortnames +
  the five R18 clauses.
- **Produced by:** a human operator executing `K10-RUNBOOK.md`.
- **Verified by:** the runbook evidence checklist **and**
  `evaluate(repo_inputs(production_installed=True, hmac_configured=True,
  staff_cohorts_non_empty=True, listed_courses_all_have_c6_gold=True,
  staff_notice_published=True))` returning `K10 = pass`. The evaluator is the
  reader; it never hardcodes the result.

**Excellence ladder.**

| Level | Requires |
|---|---|
| K10.0 Door on dev | R14: admin on a listed dev course gets a ticket URL. *(green)* |
| K10.1 One course cited on dev | C6 gold on NMD1103; miss is the exact sentence. *(green)* |
| K10.2 Admin desk | Courses / Pack / Extra / Connection, coverage formula, Index legend. *(green)* |
| K10.3 Production staged, closed | Plugin copied onto production 4.1 read-only; HMAC matches; disabled; no users/grades copied; no notice. |
| K10.4 One staff cohort, one production course | `staff_cohorts` non-empty; one shortname with C6 gold; students empty; pane cites for that cohort. *(Stage 2)* |
| K10.5 Notice to those staff | R15+R18 sentence sent to exactly that cohort, naming cohort + C6-gold shortnames; R14/R17 hold. **This is K10 PASS.** |

**BLOCKED BY REAL-WORLD ARTIFACT.** The code side (runbook, evaluator, notice
registry) is complete; the rung needs a production install and a human notice
to the cohort. No agent may claim K10.

---

## 3. R-Student · K11 (students)

**Principle.** Students may use Pulse on every listed course — and only with a
cohort, consent, RBAC, audit, notice, and a passable L5.

**Exact rule.** Medicine L5 passable for every listed shortname; a
student-visible notice published (separate decision, R16); `student_cohorts`
non-empty; consent + RBAC + audit path present and enforcing; the gate allows
only a cohort member who can already open the course and holds a matching,
current consent.

**Benchmark (the evidence that flips it).**

- `gold/l5.yaml` `status` flips to `passable` and `short` is populated per
  shortname: `sample_size: 100`, `min_passage_cite: 95`, `max_extra_fact: 2`.
- `r11_draft.frozen_n >= required_n == 4`.
- `r12_same_lecture_two_students.frozen_n >= required_n == 2`, produced with
  **two real student accounts on the same lecture**; both get the same cited
  passages and neither reply mentions past performance.
- A published student notice; `student_cohorts` non-empty; consent records per
  student per course; the gate returns `allow` only then.
- **Produced by:** real students + approved authored gold + the notice.
- **Verified by:** `test_moodle_l5.py` green **and**
  `evaluate(...)` with every K11 gate true returning `K11 = pass`.

**Excellence ladder.**

| Level | Requires |
|---|---|
| K11.0 Gate machinery | `ai/moodle_readiness` present, default-OFF, default-deny. *(green, code)* |
| K11.1 Medicine L5 | L5 passable for every listed shortname (100-question gold, ≥95 cites, ≤2 extra facts). |
| K11.2 R11 | 4/4 frozen draft cases: a draft is labelled draft and claims no Moodle write. |
| K11.3 R12 | 2/2 frozen same-lecture-two-students cases with two real students. |
| K11.4 Cohort + consent + RBAC + audit live | Student notice published; `student_cohorts` non-empty; gate enforces; every allow/deny audited. |
| K11.5 L6 CI + rollout | L6 gold job green; full student cohort on listed courses. **This is K11 PASS.** |

**BLOCKED BY REAL-WORLD ARTIFACT.** `student_cohorts` is empty, L5 is
not_passable (R11/R12 `frozen_n == 0`), and the per-shortname 100-item
benchmark is authored only as a draft (`gold/l5-curriculum.draft.yaml`,
1300 items) awaiting human review and freeze. The code side is complete and
inert.

---

## 4. R-Memory · B4 (short memory)

**Principle.** Short memory is typed conversation state — not a prose scan of
history and not a second store.

**Exact rule.** A topic/follow-up resolves against typed `ConversationState`
(`open_question.kind`, `resolved_topic`, `active_plans`), never by scanning
history for markers or matching an apply/yes word list.

**Benchmark.** The typed-state fields exist and a follow-up resolves against
them; no second store table; no module-level phrase allowlist; an affirmation
goes through `dialogue/affirmation.py` only. Today the door answer is unchanged
by history.

**Excellence ladder.**

| Level | Requires |
|---|---|
| B4.0 | Typed `ConversationState` exists. |
| B4.1 | Follow-up resolves against state, not a history scan. |
| B4.2 | No phrase allowlist in a turn path. |
| B4.3 | No second store. |
| B4.4 | Multi-turn bank covers the typed path. |
| B4.5 | Mutating history cannot change the door answer. *(current)* |

**NOT BLOCKED — already true (green as a field).** B4 is the input
`memory_short_typed`; flipping it to `False` flips the evaluator to not-PASS,
proving it is not hardcoded.

---

## 5. R-Memory · B5 (long per-student memory)

**Principle.** Long per-student progress / adaptive learning, without
oversharing.

**Exact rule.** A per-student store behind the K11 cohort+consent+audit gate;
must never mix another student's log; the curriculum answer stays identical
for two students on the same lecture (R12).

**Benchmark.** `student_cohorts` non-empty; consent + audit present; a
per-student store exists and is gated; `r12_frozen_n >= 2`; two students on the
same lecture get the same cited passages with no history mention. B5 is true
only after K11.

**Excellence ladder.**

| Level | Requires |
|---|---|
| B5.0 | Typed short memory (B4). |
| B5.1 | Cohort + consent + audit gate (K11 preconditions). |
| B5.2 | Per-student store behind the gate. |
| B5.3 | R12 green (two real students). |
| B5.4 | No cross-student mixing; every read audited. |
| B5.5 | Adaptation changes only practice order, never the cited curriculum answer; withdrawal stops use. |

**BLOCKED BY REAL-WORLD ARTIFACT.** Needs a non-empty cohort, consent,
audit, and R12. **Do not create tables.** No student memory table exists.

---

## 6. R-Graph · B6 / C7

**Principle.** A passage-grounded lecture → ILO → assessment graph (B6), then
session → outcome edges (C7). Indexing is not a graph.

**Exact rule.**
- **B6:** edges from each lecture to its ILOs to assessments, each edge
  grounded in a cited passage id; C6 green for every listed shortname.
- **C7:** session/outcome edges built **only after C6 is green and L5 is
  passable**; not a gate; not Carbon's schema `knowledge_graph`.

**Benchmark.** B6: every edge traces to a passage id and the graph is
queryable. C7: each edge traces to a real session; C6 green and L5 passable
hold first. No Neo4j and no second Postgres unless a separate decision says
so.

**Excellence ladder.**

| Level | Requires |
|---|---|
| B6.0 | C6 green for every listed shortname. |
| B6.1 | Lecture → ILO edges authored, passage-grounded. |
| B6.2 | ILO → assessment edges authored, passage-grounded. |
| B6.3 | Queryable, each edge returns its passage id. |
| B6.4 | No Neo4j / second Postgres; indexing is not a graph. |
| B6.5 | Retrieval gold over graph edges. **B6 PASS.** |
| C7.0 | C6 green. |
| C7.1 | L5 passable. |
| C7.2 | Session → outcome edges authored. |
| C7.3 | Every edge grounded to a real session. |
| C7.4 | Audit + consent. |
| C7.5 | Retrieval gold. **C7 PASS.** |

**BLOCKED BY REAL-WORLD ARTIFACT.** Needs authored, approved curriculum edges
and (for C7) a passable L5. No graph code is authorized before C6 and L5; no
store is created now.

---

## 7. Evaluator contract (single source of truth)

`evaluate(ReadinessInputs) -> ReadinessReport` computes K10, K11, B4, B5, B6,
C7 as `pass` only when **every** gate for that rung is true. `repo_inputs()`
fills the inputs from `domain_packs/aast-med/gold/l5.yaml` and the default
(unpublished) notice registry; it never invents a cohort. Tests prove:
default deny; default unpublished; K10/K11/B5/B6/C7 not-PASS on empty and on
real inputs; every K11 artifact individually flips the rung; B4 is a flippable
input; the turn path never imports the package.
