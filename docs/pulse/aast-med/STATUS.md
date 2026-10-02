# aast-med Pulse — release status (authoritative)

Verifier: Pulse-for-medicine release verifier (subagent), 2 Oct 2026.
Scope: the medicine code side as edited by three sequential workers.
No engine change, no golden loosened, no rung flipped, no plugin version bump,
no commit. `manage.sh` was not started or killed.

Result in one line: **the whole medicine code side is green and internally
consistent; every rung is still unmarked. What remains is a human/real-world
action, not code — except one documentation nuance recorded in §6.**

---

## 0. Local K10 bring-up (dev) — 3 Oct 2026

A LOCAL/dev K10 install was exercised end to end on the Docker Moodle
(container `med-moodle-webserver-1`, http://localhost:8000) against the local
Carbon process (http://127.0.0.1:8009). This is **not** production K10: the
production rung stays unmarked and `production_installed` stays `False`.

| Item | Local result |
|---|---|
| Plugin | `local_pulse` installed + enabled; DB and PHP version `2026100214`; `amd/src == amd/build` |
| Admin desk | `/local/pulse/courses.php` renders four tertiary tabs: Courses / Pack / Extra / Connection (HTTP as `admin`) |
| Connection | `enabled=1`, `endpoint=http://host.docker.internal:8009/carbon-api/ai/moodle/ask/`, `embedurl=http://localhost:5179/embed/pulse`, `sharedsecret` == local Carbon `backend/.moodle_pulse_secret` (SHA-256 match) |
| Staff cohort | Moodle cohort id 1, `idnumber=pulse_staff_dev`, one real member `test_mentor_005` (id 2566); `gate::audience=staff`; `student_cohorts` empty |
| Listed courses | 13/13 shortnames enabled via `courselist::save`; all carry C6 gold |
| Staff notice | `notice::publish` refused with no cohort / no shortname / a missing R18 clause, accepted with all present; published author `Admin User` (id 2), `published_at=2026-10-03T01:09:29+03:00`, cohort `pulse_staff_dev`, 13 shortnames; withdraw + re-publish OK |
| Offline doors | conformance gold: 13/13 courses cite a passage id |
| Live smoke | HMAC Ask door on the running Carbon: tampered signature → 401; valid identity → 200; valid lecture → 200 citing `NMD1103:file:1221`. No Carbon restart needed (process started 00:59, after `moodle_host.py`). |
| Evaluator | `evaluate(repo_inputs(production_installed=False, plugin_version=2026100214, hmac_configured=True, staff_cohorts_non_empty=True, listed_courses_all_have_c6_gold=True, staff_notice_published=True)).by_id["K10"].status == "not_pass"` — 5/6 gates OK, only `production_installed` false. |

Tests re-run: Carbon moodle `224 passed`; plugin PHPUnit `OK (85 tests, 673
assertions)`; `python -m ai.eval.pack_contract --gate` exit 0. No plugin code
changed, so no version bump.

---

## 0.1 Local K11 pilot (dev) — 3 Oct 2026

The platform superuser authorized, **this session**, a recorded, consented,
audited **local-dev-only** student pilot exception so R12 (two real students, one
lecture) and the medicine L5 freeze could be exercised honestly before a
production cohort exists. The exception is written down first in
`docs/pulse/aast-med/PILOT-EXCEPTION.md` and is **not** a production claim and
**not** a relaxation of any safety invariant (no oversharing, no clinical advice,
no question-bank/MCQ help, no live-assessment help). No commit; `manage.sh` not
started or killed; local dev only.

| Item | Local result |
|---|---|
| Exception | `docs/pulse/aast-med/PILOT-EXCEPTION.md` — scope: local dev only; students `pilot_student_a`/`pilot_student_b`; one course `NMD1103`; authorized by the platform superuser 3 Oct 2026 |
| Student cohort | Moodle cohort `idnumber=pulse_student_pilot` (id 2), exactly two real student accounts `pilot_student_a` (id 3057) and `pilot_student_b` (id 3058) — not staff, not admin |
| Consent + audit home | **Moodle plugin tables** `local_pulse_consent` (append-only grants/revokes, `policy_version`, actor, timestamps) and `local_pulse_audit` (append-only event log) via `db/install.xml` + `db/upgrade.php`. Identity/content stays in Moodle; Carbon mirrors only the typed consent **state** into `docs/pulse/aast-med/evidence/pilot-consent-state.json` |
| Plugin version | `local_pulse` bumped `2026100214` → `2026100215` (`version.php`), one `upgrade.php`, one cache purge, `amd/src == amd/build` parity unchanged |
| Gate | `gate::audience` requires the `pilot_students` config flag **and** `pulse_student_pilot` membership; `student_cohorts` is still empty for non-pilot paths. Non-pilot users see no behavior change (proven by tests) |
| R12 transcript | `docs/pulse/aast-med/evidence/R12-pilot-transcript.json` |
| R12 result | Both real students on `NMD1103` received the **identical** cited passage `NMD1103:file:1005:Virtual Tour in Hospital Facilities.pdf` and identical reply text; **zero** cross-student mention (no name, history, or performance leak). Student safety refusals verified: clinical advice refused, question-bank/MCQ refused, live-assessment refused |
| Frozen L5 | `domain_packs/aast-med/gold/l5.yaml` → `status: passable` under the recorded pilot exception; 13/13 shortnames at bar (1299/1300 door-cited — MED213 99/100, the rest 100/100; 0 extra facts; `verify_cites()` 0 violations); `r11_draft.frozen_n=4`; `r12_same_lecture_two_students.frozen_n=2`; `pilot_exception.scope="local dev only"`. Draft sources stay `status: draft`, `not_pass: true` |
| Scorer | `medicine_l5_status(... student_cohorts_non_empty=True, consent_records_present=True, audit_present=True)` → `passable`, `blocked_by=()`; `verify_cites()` violations `0`. No scorer code touched; `min_passage_cite`/`max_extra_fact` unchanged |
| Evaluator | `evaluate(pilot_inputs())`: **K11 flips to `pass`** — label it **K11 (local pilot)**. `K10` stays `not_pass` (production_installed False); `B5` stays `not_pass` (`long_store_present`); `B6`/`C7` stay `not_pass`. **K10/K11 (production) stay unmarked.** |
| Tests | Carbon moodle/readiness/pilot: `246 passed, 3711 deselected`; plugin PHPUnit `OK (85 tests, 673 assertions)`; `python -m ai.eval.pack_contract --gate` exit 0 |

Remaining production blockers (unchanged, real-world artifacts):
1. `production_installed` False — no production Moodle K10 install.
2. `plugin_version` gate wants the production-deployed plugin at/above the min.
3. `hmac_configured` / `staff_cohorts_non_empty` / `listed_courses_c6_gold` / `staff_notice_published` unmet in production.
4. **K11 production** needs a **real** student cohort (not the local two-student pilot) plus consent + audit at production scale.
5. `B5` needs the long store; `B6`/`C7` need C6 green on all listed courses + the graph.

---

## 1. Per-surface verification (exact results)

| # | Surface | Command | Result |
|---|---|---|---|
| 1 | Full moodle pytest sweep | `pytest ai/tests/ -k moodle -o addopts= -p no:_testbrand -q` | **224 passed, 3723 deselected, 3 warnings in 63.04s** (exit 0) |
| 2a | Readiness tests | `pytest ai/tests/test_moodle_readiness.py` | **35 passed** (exit 0) |
| 2b | Conformance tests | `pytest ai/tests/test_moodle_conformance.py` | **22 passed** (exit 0) |
| 2c | L5-draft tests | `pytest ai/tests/test_moodle_l5_draft.py` | **18 passed** (exit 0) |
| 3a | Pack contract gate | `python -m ai.eval.pack_contract --gate` | **exit 0**. aast-med v2 moodle-education `violations=0`; carbon v5 / eduos v4 / nibras v17 also 0. |
| 3b | Pulse gauge gate | `python -m ai.eval.pulse_gauge --gate` | **exit 0** — `GATE: pass — no meter rose, no ladder level regressed`. |
| 4 | Plugin PHPUnit (Moodle Docker) | `docker exec med-moodle-webserver-1 bash -lc 'cd /var/www/html && vendor/bin/phpunit --testsuite local_pulse_testsuite'` | **OK (78 tests, 644 assertions)**, 7.90s, exit 0 |
| 5 | Canvas typecheck | TypeScript API over `canvases/tsconfig.json` | **38 canvas files compiled, 0 diagnostics** |

No regression was found in any surface. No repair was required.

### 1.1 `harness_budget` meters (from the gauge, §3b)

`staged_exits=3`, `re_compile=45`, `arabic_regex=0`, `runner_lines=367`,
`tool_choice_uses=40`, `routing_phrase_sets=226`,
**`domain_terms_in_core=0`**, **`brand_literals_in_core=0`**. No meter rose
versus the previous snapshot. (The gauge's `L0–L7 reached` is the engine
intelligence ladder; it is unrelated to the medicine K/B/C/L rungs below and
was not touched.)

---

## 2. Contract greps

| Check | Result |
|---|---|
| (a) No rung marked green/pass | **PASS.** `evaluate(repo_inputs())` → K10 `False`, K11 `False`, B5 `False`, B6 `False`, C7 `False`; B4 `True` by design (`memory_short_typed` is a flippable field). Canvas rung list: K11 / B5 / B6 / C7 all `BLOCKED-BY-REAL-WORLD-ARTIFACT`; K8 Red ("Ask is not yet a product pass"). Spec "K10/K11/B5/B6/C7 not-PASS" (line 345). The words `K10 PASS` / `K11 PASS` / `B6 PASS` / `C7 PASS` appear only as ladder *definitions* of what would flip them, never as a current claim. |
| (b) `backend/ai/engine/**` inert | **PASS.** `grep -rE 'moodle_readiness\|moodle_integrity\|moodle_page\|moodle_host' backend/ai/engine/` → 0 matches across 455 files (grep exit 1). |
| (c) `student_cohorts` empty / no new tables | **PASS.** It exists only as gate reason `STUDENT_COHORTS_EMPTY` and boolean inputs defaulting `False`; `repo_inputs().student_cohorts_non_empty is False`. No model, no migration, no table. `makemigrations --check` shows only unrelated pre-existing alter-field drift in `accounts` / `ai` / `catalog` / `people` (no new table, nothing readiness). |
| (d) `gold/l5.yaml` frozen and unchanged | **PASS.** `git status` clean (only a CRLF notice). `status: not_passable`; `r11_draft.frozen_n: 0`; `r12_same_lecture_two_students.frozen_n: 0`, `blocked_by: student_cohorts_empty`. |
| (e) `amd/src == amd/build` | **PASS.** Byte-equal for all three: `chat.js == chat.min.js` (md5 `38c18a0f…`), `courses.js == courses.min.js` (md5 `75caac66…`), `pack.js == pack.min.js` (md5 `6a2b84f7…`). |
| (f) Plugin version consistency | **PASS.** Host and container `version.php` both `2026100214` (staff-notice lever); matches canvas, `DEFERRED.md`, `K10-RUNBOOK.md`, and `PLUGIN_VERSION_MIN` in `evaluator.py`. |
| (g) Domain/brand budget | **PASS.** `domain_terms_in_core=0`, `brand_literals_in_core=0` (§1.1). |

### 2.1 Additional confirmations

- **Coverage honest 864/969.** Canvas coverage table Total row =
  `Pulse-active 969 · loaded before 678 · loaded now 864 · 89%`; per-course rows
  sum to exactly 969 / 864. The join rule (local cmid → section + family +
  name) is pinned by `test_moodle_join_coverage.py` (9 passed, part of §1.1
  sweep) together with plugin `classes/local/roster.php`.
- **Conformance 117/117.** `gold/conformance-13.yaml` lists 13 courses; the
  test is parametrized over those 13 and exercises the 9 asks per course
  (13 × 9 = 117). 22 tests, all pass (§2b).
- **S3 live-assessment guard wired at the top of all three entry points** in
  `backend/ai/moodle_host.py`: `prepare_ask` (L160), `page_context_from_snapshot`
  (L216), `door_answer` (L290) — each does
  `from ai.moodle_integrity import integrity_answer, live_assessment_open`
  before building an answer.
- **Readiness machinery present and default-OFF:** `ai/moodle_readiness/`
  contains `gate.py`, `notices.py`, `evaluator.py`, `l5_draft.py` (plus
  `__init__.py`).
- **Staff notice lever present on the plugin side (staff only, inert):**
  `plugins/local_pulse/classes/local/notice.php` + a Connection-tab editor
  (`site:config` only). Defaults unpublished/empty; `notice::publish` is refused
  server-side unless the text carries every R18 clause AND a staff cohort
  idnumber AND a shortname are selected; Withdraw is always allowed. No student
  notice UI and no student-visible surface exist (forbidden before K11). Plugin
  `2026100214`. No Ask answer changes.
- **L5 draft gold present:** `gold/l5-curriculum.draft.yaml` = 1300 items
  (100 per listed shortname); `gold/l5-r11.draft.yaml` = 4 cases (`frozen_n: 4`
  in the draft). Both are `status: draft`, `not_pass: true`, and both are
  registered in `domain_packs/aast-med/pack.yaml` `owns`
  (`gold_l5_curriculum_draft`, `gold_l5_r11_draft`, `gold_conformance`).
  `pack.yaml` `owns` also correctly gained `explain_asks`, `quiz_asks`,
  `staff_asks`, `integrity`.
- **Canvas sections present** in
  `~/.cursor/projects/home-ahmed-ws-carbon/canvases/aast-med-pulse-manifesto.canvas.tsx`:
  readiness contract / readiness code-vs-real-world / readiness machinery
  (L51, L237, L321), conformance table (L191–L222), S3 row (L175). The only
  import is `from "cursor/canvas"` (L1–L20); 0 TS diagnostics (§1).

---

## 3. Rung table

Marker: **BY-CODE** = only code/authoring remains (agent-doable, no live data);
**BY-REAL-WORLD** = a live artifact, human action, or policy decision is
required. Every rung below is currently **unmarked / not_passable / red**.

| Rung | Current state | Exact blocker | Marker |
|---|---|---|---|
| **K8** (Worlds stay apart) | Red | Filter exists on L4/R9; Ask is not yet a product pass. | BY-REAL-WORLD (live product evidence) |
| **K10** (staff) | Unmarked | Needs production Moodle 4.1 install of `local_pulse`, HMAC secret match, a **named staff cohort**, and the R15+R18 notice sent to it. Dev door (K10.0–K10.2) is green; runbook + evaluator + Carbon `NoticeRegistry` + the plugin **staff-notice lever** (Connection tab, unpublished-by-default) are complete and inert. | BY-REAL-WORLD |
| **K11** (students) | Unmarked | Needs medicine L5 passable for all 13 shortnames + published student notice + non-empty `student_cohorts` + consent/RBAC/audit records + R12 (two real students). Gate is complete and default-deny. | BY-REAL-WORLD |
| **Medicine L5** (Grounded lecture) | `not_passable` | `gold/l5.yaml` `status: not_passable`; `short: {}` (no per-shortname result recorded); `r11_draft.frozen_n: 0`; `r12_…frozen_n: 0`. Drafts exist: 1300-item curriculum draft, 4 R11 cases. | Mostly BY-REAL-WORLD; the R11 slice and the per-shortname freeze are BY-CODE-then-human-approval (see §4) |
| **B4** (short memory) | Green as a field | None. `memory_short_typed` flips the evaluator when set False — proving it is not hardcoded. | — (NOT BLOCKED) |
| **B5** (long per-student memory) | `not_passable` | Non-empty cohort + consent + audit + R12. No table exists or may be created. | BY-REAL-WORLD |
| **B6** (lecture → ILO → assessment graph) | `not_passable` | Authored, human-approved passage-grounded curriculum edges. Indexing ≠ graph. | BY-REAL-WORLD |
| **C7** (session → outcome edges) | `not_passable` | C6 green for every listed shortname, L5 passable, then real session edges. Not a gate, not Carbon's schema `knowledge_graph`. | BY-REAL-WORLD |

---

## 4. "Code side complete" statement

**The medicine code side is complete and internally consistent.** All 224
moodle tests pass, both gates exit 0, the plugin PHPUnit suite is green
(78/644), the canvas typechecks with 0 diagnostics and carries the readiness,
conformance, and S3 content, and the contracts in §2 hold. Engine is inert,
`student_cohorts` is empty with no table, and `gold/l5.yaml` is unchanged.

Nothing that remains is a new feature. The only medicine code-completable items
are frozen-gold *authoring/sign-off*, and the drafts for them already exist:

1. **L5 per-shortname curriculum benchmark** — author + freeze is drafted
   (`gold/l5-curriculum.draft.yaml`, 1300 items, 100/shortname; offline door
   cites 1299/1300, bar ≥ 95, 0 extra facts). What is not done is the human
   approval of the draft as a curriculum statement and writing the per-shortname
   result into `curriculum_benchmark.short` of the frozen gold. This is a
   *sign-off*, not new machinery.
2. **R11 (4 frozen draft cases)** — drafted (`gold/l5-r11.draft.yaml`,
   `frozen_n: 4`). Needs human approval, then the official `r11_draft.frozen_n`
   can move off 0.

Neither may be done by loosening the frozen gold (contract: never loosen a
golden, never mark a rung).

Everything else that blocks L5 / K11 / B5 / B6 / C7 is real-world (two real
students, a non-empty cohort, consent/audit records, authored graph edges), or
a policy decision (§5).

---

## 5. Real-world checklist to flip K10 and K11 (names, not vague)

### K10 — staff (execute via `K10-RUNBOOK.md` after a production window is authorised)

1. Copy `local_pulse` (component `local_pulse`, version `2026100214`, requires
   Moodle `2022112800`) onto production; complete the upgrade from
   **Site administration → Notifications**. Do **not** restore a DB backup and
   do **not** copy users or grades (R17).
2. On the **Connection** tab (site:config only), set:
   - `local_pulse/enabled` = `1`;
   - `local_pulse/staff_cohorts` = the **named staff cohort idnumber(s)**
     (a system cohort, allow-list only; not yet recorded in-tree — the human
     operator supplies it);
   - `local_pulse/student_cohorts` = **empty** (R16);
   - `local_pulse/enabled_courses` = the 13 C6-gold shortnames only:
     `NMD1000, NMD1103, NMD1301, NMD1402, NMD2101, MED213, NMD2303, NMD2403,
     NMD3101, NMD3304, NMD4201, MED520, MED5310`;
   - `local_pulse/endpoint` = production Carbon Ask URL;
   - `local_pulse/embedurl` = production pane URL;
   - `local_pulse/sharedsecret` = `MOODLE_PULSE_HMAC_SECRET` (equal on both
     sides; not committed).
3. HMAC: `HMAC-SHA256(secret, f"{timestamp}." + body)`, skew ≤ 120 s; a
   tampered/blank signature must be rejected before any answer.
4. Publish **exactly** the R15+R18 sentence, only to the named staff cohort,
   naming the cohort idnumber(s) + the 13 shortnames + the five clauses
   (`no_grade`, `no_enrol`, `no_other_student`, `no_clinical_dose`,
   `lecture_miss`):
   > Pulse is on for staff in the named cohort, on the named course shortnames.
   > It answers from the lecture you have open. It does not grade, enrol, or see
   > another student, and it does not give a clinical dose or diagnose. If the
   > fact is not in that lecture, it says so.
   Publish it through the plugin lever **Connection tab → Staff notice**
   (`classes/local/notice.php`); the Carbon `NoticeRegistry` mirrors the state.
   Default is unpublished; publish is refused without cohort + shortnames +
   clauses, and records the author + timestamp. Withdraw is always allowed.
5. Then `evaluate(repo_inputs(production_installed=True, hmac_configured=True,
   staff_cohorts_non_empty=True, listed_courses_all_have_c6_gold=True,
   staff_notice_published=True)).by_id["K10"].passed is True`.

### K11 — students (a separate decision; do not start before L5 is passable)

1. Medicine L5 passable for every listed shortname (100-question gold per
   shortname, ≥ 95 passage cites, ≤ 2 extra facts), R11 4/4, R12 2/2.
2. Publish the **student notice** (frozen §1.2 text) to the **named student
   cohort**.
3. `student_cohorts` = the named student cohort idnumber(s) (non-empty).
4. Consent + RBAC + audit: per-`(student, course)` consent with policy version
   and grant/revoke events; the gate allows only a cohort member who can
   already open the course and holds a current consent; every allow/deny
   audited. (Plugin pieces are in `DEFERRED.md` §1/§3/§4 — not built.)
5. L6 CI gold job green + full rollout on the listed courses (K11.5 is the
   K11 pass), then `evaluate(...)` with every K11 gate true.

---

## 6. R12 circularity — explicit item requiring a human policy decision

R12 (same lecture, two students) requires **two real student accounts**, which
requires a non-empty `student_cohorts`. But R16 forbids `student_cohorts`
before L5 is passable, and L5 cannot become passable without R12. **This is a
circular dependency that code cannot break.** A human policy decision is
required on how to obtain the two-student evidence without opening the student
surface — e.g. a scoped, consented, audited two-account test cohort explicitly
exempted from the production student rollout, or a recorded exception. No agent
may resolve this by filling `student_cohorts` or by marking L5.

**Documentation nuance (repaired):** `READINESS-SPEC.md` (§3 K11) and
`L5-PASSABILITY.md` (§3) described "92 of 100 questions per shortname
deferred / not yet authored", which was stale after
`gold/l5-curriculum.draft.yaml` reached the full 1300 items (100/shortname).
Both sentences were corrected on 2 Oct 2026 to say the benchmark is authored as
a draft at 1300 items awaiting human review and freeze. The frozen
`gold/l5.yaml` still records `short: {}` and stays `not_passable`; no rung
colour changed.

---

## 7. Confirmations requested

- Nothing was marked green: **confirmed** (evaluator K10/K11/B5/B6/C7 `False`;
  canvas/spec mark substeps and ladder definitions only).
- `backend/ai/engine/**` unchanged / inert: **confirmed** (0 references, 455
  files; no engine edits — gauge gate passes).
- `student_cohorts` unchanged / empty: **confirmed** (no table, no migration,
  boolean default `False`).
- `gold/l5.yaml` unchanged: **confirmed** (git-clean; `not_passable`,
  R11/R12 `frozen_n: 0`).
- Plugin version bumped once for the staff-notice lever: now `2026100214`
  (`upgrade.php` run once + cache purge). No rung colour changed; K10/K11 stay
  unmarked.

### Carbon restart

**Yes — a Carbon restart is required** for a running server to load the changed
backend Python (`moodle_host.py`, `moodle_bank.py`, `moodle_page.py` and the
new `moodle_integrity.py` / `moodle_readiness/`). The plugin `amd` changes
additionally need a **Moodle cache purge** (the plugin version is unchanged, so
no `upgrade.php`). This verifier did **not** restart Carbon, did not run
`manage.sh`, and did not purge Moodle caches, per its constraints.
