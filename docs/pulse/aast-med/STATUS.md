# aast-med Pulse — release status (authoritative)

Verifier: Pulse-for-medicine release verifier/consolidator (subagent), 3 Oct 2026.
Scope: the medicine code side as edited by ~7 sequential workers (plugin
staff-notice lever, embed isolation fix, local K10 bring-up, local K11 pilot +
consent tables + gold freeze, legacy `.ppt` extraction, blueprint review).

No engine change, no golden loosened, no rung flipped by this verifier, no
plugin version bump by this verifier, no commit. `manage.sh` was not started or
killed, nothing was deployed. This pass was verify-and-repair only.

**Result in one line:** the medicine code side is complete and internally
consistent for the frozen scope; every **production** rung is still unmarked
(K8 red; production K10/K11/B5/B6/C7 `not_pass`/`not_passable`). One recorded
**LOCAL (dev)** exception exists: the consented, audited two-student K11 pilot
freezes medicine L5 `passable` and flips K11 as **K11 (local pilot)** only.
This page is the single authoritative status; the other `aast-med/*.md` files
are the frozen contracts (2 Oct) or evidence and are superseded here on the
L5/R11/R12 status only.

**Content distillation.** The engine described in
[`CONTENT-ENGINE-SPEC.md`](CONTENT-ENGINE-SPEC.md) is now **wired into the staff
“Index this course” job** — never into an Ask / Chat turn. `ai/content_engine/`
supplies the shared readers (office incl. `.ppt/.pptx/.pptm/.ppsx` + speaker
notes, pdf, text/html for `.txt/.md/.json/.csv/.html`, image), OCR (pytesseract
eng+ara 5.5.0), the chunk index and the knowledge graph; the job runner is
`ai/moodle_content_job.py`, invoked by `MoodleIndexView`. Outcomes:

- **Extra as course content** — `.txt/.md/.json` uploaded to `local_pulse/extra`
  are read through the same registry and written to the `course-extra-13` bank,
  citable as `extra:<name>` (verbatim only). Students stay 403 on manage.
- **OCR** — local scanned PDFs / images OCR during the staff Index job. English
  is citable; Arabic is stored **non-citable** with `status=pending_signoff`
  under `domain_packs/aast-med/bank/ocr-pending/<shortname>.jsonl` until the
  recorded sign-off.
- **Drive** — `acquire.drive_acquire` is reachable from the Index job but
  **default-OFF** (`PULSE_CONTENT_DRIVE_ENABLED` + credentials); never on a Chat
  turn; per-source status recorded.
- **Chunk index + graph** — 6,622 chunk rows and 4,925 nodes / 23,364 edges over
  the 13 listed courses, under `domain_packs/aast-med/index/` and
  `domain_packs/aast-med/graph/`. Every graph edge carries a real `passage_ref`.
  Keyword layer only; semantic stays default-OFF.
- **Doors** — Ask does **not** consume the keyword index yet (deferred to keep
  every golden and every budget meter flat). The index is a staff-visible
  artifact.

`ai/moodle_content_registry.py` (locked by
`ai/tests/test_moodle_content_registry.py`) remains the read-only capability
reporter. It adds no Chat-time OCR, network, vector store, or turn-path graph,
and marks no rung. engine/** and gold/** are untouched.

---

## 0. Verification sweep (exact results)

| # | Command | Exact result | Exit |
|---|---|---|---|
| 1 | `DJANGO_SETTINGS_MODULE=config.settings python -m pytest ai/tests/ -k moodle -o addopts= -p no:_testbrand -q` | **277 passed, 3752 deselected, 3 warnings in 80.97s** (run on an isolated `TEST_DB_NAME` to avoid a concurrent worker's test DB) | 0 |
| 2a | `python -m ai.eval.pack_contract --gate` | `aast-med v2 moodle-education instance=ok violations=0`; `carbon v5 data_trust` 0; `eduos v4 education` 0; `nibras v17 hrms` 0 | 0 |
| 2b | `python -m ai.eval.pulse_gauge --gate` | `GATE: pass — no meter rose, no ladder level regressed` | 0 |
| 3 | `docker exec med-moodle-webserver-1 bash -lc 'cd /var/www/html && vendor/bin/phpunit --testsuite local_pulse_testsuite'` | **OK (88 tests, 686 assertions)**, 8.975s | 0 |
| 4 | Canvas typecheck (`tsc -p canvases/tsconfig.json`, TypeScript 5.9.2) | **0 diagnostics** over all `*.canvas.tsx` | 0 |
| 5 | `python -c 'from ai.moodle_extraction_gap import report, totals; ...'` (read-only reporter) | active **934**, loaded **860**, unread **74**; `legacy_ppt=0`, `scanned_pdf=1`, remote 69 (external_web 40 · youtube 17 · google 12), media 4 | 0 |
| 6 | Teaching-wave **FINAL SWEEP** — `pytest ai/tests/ -k 'moodle or conformance or l5'` · `test_moodle_retrieval.py` + `test_moodle_retrieval_r2.py` · `ai.eval.pack_contract --gate` · `ai.eval.pulse_gauge --gate` (isolated `TEST_DB_NAME=pulse_final_sweep`) | **532 passed / 3763 deselected** (moodle · conformance · l5); retrieval **144 passed**; `pack_contract` exit 0 (4/4 packs `instance=ok violations=0`); `pulse_gauge` exit 0 (**no meter rose**). R1 / R2 / R3 / T1 / T2 / G1 audited; index determinism locked (byte-identical rebuild; safe degradation to the exact miss); no pre-existing golden moved; BY-REAL-WORLD rungs unchanged (K10 / K11 / L5-prod / B5 / B6 / C7 / T3 / R3-vector / G2). **No rung marked green.** | 0 |

Notes:

- The PHPUnit suite globs `public/local/pulse/tests/*_test.php`, which includes
  `embed_url_test.php` — so the **embed-URL isolation guard was run in-suite**
  (the earlier caveat about it never having been run does not apply; phpunit is
  installed in the container).
- The Docker Moodle container is **Moodle 5.2.3+ / PHP 8.3.33 / pgsql 17.11**,
  not Moodle 4.1. The plugin declares `requires 2022112800` (4.1). The local dev
  install therefore exercises the plugin on a newer Moodle than the production
  runbook's 4.1 target; production install on 4.1 is still real-world work.
- **Content-engine wiring pass (3 Oct 2026):** the new pytest files
  `ai/tests/test_moodle_content_ingest.py` and `ai/tests/test_moodle_content_job.py`
  are included in the 277 above. PHPUnit was **not** re-run — no
  `med-moodle-webserver-1` container is running in this environment — so the new
  `local_pulse/tests/extra_test.php` case is `php -l` syntax-clean but unexecuted
  here; the plugin version is bumped to `2026100301` (T2 teach-apply: new
  Extra-tab Apply + `MoodleTeachApplyView`); still PENDING live upgrade + PHPUnit
  (no container).
- The **live-Moodle coverage view is 873/969 (90%)**, unread 96; the
  **offline committed-bank join view is 860/934**, unread 74. `legacy_ppt = 0`
  (the 9 legacy `.ppt` decks were read). The 1 scanned Arabic PDF (MED5310)
  stays unread.

### 0.1 `harness_budget` meters (from gate 2b)

`staged_exits=3 (=)`, `re_compile=45 (−14 vs 2026-09-25)`, `arabic_regex=0 (=)`,
`runner_lines=367 (=)`, `tool_choice_uses=40 (+7)`,
`routing_phrase_sets=226 (−34)`, **`domain_terms_in_core=0 (=)`**,
**`brand_literals_in_core=0 (=)`**. **No meter rose.**

### 0.2 Evaluator runs

- `evaluate(repo_inputs())` — default honest repository state:
  `student_cohorts_non_empty=False`, `l5_status=passable`, `r11_frozen_n=4`,
  `r12_frozen_n=2`, `sample_size=100`. Result: **K10 `not_pass`** (all 6 gates
  false), **K11 `not_pass`** (5 gates false), **B4 `pass`**, **B5 `not_pass`**,
  **B6 `not_pass`**, **C7 `not_pass`**. `passed_ids == ("B4",)`.
- Local dev K10 inputs (`plugin_version=2026100215`, `production_installed=False`,
  HMAC + staff cohort + C6 gold + staff notice True): **K10 `not_pass`**, gates
  OK = `plugin_version, hmac_configured, staff_cohorts_non_empty,
  listed_courses_c6_gold, staff_notice_published`; only `production_installed`
  false (**5/6**).
- `evaluate(pilot_inputs())`: **K11 `pass`** (label it **K11 (local pilot)**),
  **K10 `not_pass`**, **B5/B6/C7 `not_pass`**; `passed_ids == ("K11","B4")`.

---

## 1. Drift found and reconciled

| # | Drift | Ground truth | Repair |
|---|---|---|---|
| a | Plugin version: `version.php` (host **and** container) and `evaluator.py PLUGIN_VERSION_MIN` are **`2026100215`**, but `STATUS.md` (6 refs), `DEFERRED.md` (4 refs), `K10-RUNBOOK.md` (2 refs), and the canvas (6 refs) said `2026100214`. The canvas also contradicted itself (one rung row already said `2026100215`). | version.php + container DB `local_pulse/version = 2026100215` | Set all docs + canvas to `2026100215`. |
| b | STATUS §0 evaluator line used `plugin_version=2026100214` and reported "5/6 OK". With `PLUGIN_VERSION_MIN=2026100215`, that input now fails `plugin_version` (4/6). | `evaluator.py:31` | Corrected to `plugin_version=2026100215` → 5/6, only `production_installed` false. |
| c | Test counts: STATUS §1 said `224 passed` (§0.1 said `246 passed, 3711 deselected`); PHPUnit said `78/644` (§0.1 `85/673`). | Sweep #1 and #3 above. | STATUS now carries `248 / 3727` and `88 / 686`. |
| d | Coverage: `BLUEPRINT-REVIEW.md` header said `864/969`. | Live view is `873/969`; offline is `860/934`. | Header set to `873/969`; this page carries both views. |
| e | `gold/l5.yaml`: STATUS §2(d)/§3 said `status: not_passable`, `r11/r12 frozen_n: 0`, `short: {}`. | `status: passable` under the recorded pilot; `r11_draft.frozen_n: 4`, `r12…frozen_n: 2`, `short` populated 13/13. | STATUS reconciled to the frozen gold; see §3/§6. |
| f | Canvas K11 production row said "**92 questions deferred**". | `gold/l5-curriculum.draft.yaml` is authored in full: **1300 items, 100/shortname**. | Canvas text corrected to "curriculum draft authored at 1300 items (100/shortname)". |
| g | `DEFERRED.md` said "items #3–#8 remain deferred". | The 3 Oct LOCAL pilot executed #3 (consent + audit) and the typed-mirror side of #7. | `DEFERRED.md` update block + per-item notes rewritten truthfully. |
| h | Canvas "Deferred changes" text said "the other 7 stay deferred". | Same as (g). | Canvas text now matches `DEFERRED.md`. |
| i | `READINESS-SPEC.md` (frozen 2 Oct) §3 and `L5-PASSABILITY.md` (frozen 2 Oct) §1/§3/§4 still state `L5 not_passable`, `R11/R12 frozen_n == 0`, and "do not fill student_cohorts". | These are the **frozen 2 Oct contracts and predate the 3 Oct pilot**. They were **not edited** (frozen contracts; editing them would look like loosening). | Recorded here precisely: the recorded pilot exception supersedes those lines for the L5/R11/R12 status **only**; they remain the frozen pre-pilot analysis. `STATUS.md` is authoritative. |

| j | **Plugin version on disk rose to `2026100216`** (content-engine Index wiring: `files_for_index` + build/drive payload + a new PHPUnit case), but `upgrade.php --non-interactive` was **not** run because no `med-moodle-webserver-1` container is up, so the **applied / DB version remains `2026100215`**. | `version.php` on disk = `2026100216`; DB `local_pulse/version` = `2026100215` (unchanged) | Live docs + canvas refs set to `2026100216`; applied stays `2026100215`. **Action:** apply on the next stack bring-up (`upgrade.php --non-interactive`) and re-run the `local_pulse` PHPUnit suite. |
| k | **Plugin version on disk rose again to `2026100301`** (T2 teach-apply: new Extra-tab Apply + `MoodleTeachApplyView`), but `upgrade.php` still has **not** run (no `med-moodle-webserver-1` container), so the **applied / DB version remains `2026100215`**. | `version.php` on disk = `2026100301`; DB `local_pulse/version` = `2026100215` (unchanged) | Live docs + canvas refs set to `2026100301`; applied stays `2026100215`. **PENDING:** live upgrade (`upgrade.php --non-interactive`) + `local_pulse` PHPUnit (no container). |

No mismatch was papered over; the one that reflects a real question (i) is
recorded, not edited.

---

## 2. Contract checks

| Check | Result |
|---|---|
| (a) Plugin version consistent (`version.php` · canvas · STATUS · DEFERRED · K10-RUNBOOK · `PLUGIN_VERSION_MIN`) | **PASS on disk; DB upgrade PENDING.** Host `version.php` `2026100301` (disk; no container running); `PLUGIN_VERSION_MIN=2026100215`; canvas/STATUS/DEFERRED/K10-RUNBOOK now `2026100301`. **Applied/DB version stays `2026100215` until `upgrade.php` runs** (no `med-moodle-webserver-1`). |
| (b) Coverage identical across canvas + STATUS + reporter | **PASS.** Canvas Total row `969 · 678 · 873 · 90%`; STATUS same; reporter offline `934 · 860 · 74`. Live unread 96 / offline unread 74. |
| (c) No rung marked green | **PASS.** `repo_inputs` → only B4 `pass`; K10/K11/B5/B6/C7 `not_pass`. Canvas: K8 **Red**; K10/K11 rows say **LOCAL (dev) … · production Red**; B5/B6/C7 `not_passable`; B4 "green as a field". Local K10/K11 are explicitly labelled **LOCAL**. |
| (d) `engine/**` inert | **PASS.** `grep -rE 'moodle_readiness\|moodle_integrity\|moodle_page\|moodle_host' ai/engine/` → **0** matches (**478** files). |
| (e) Harness budget | **PASS.** `domain_terms_in_core=0`, `brand_literals_in_core=0`; `pulse_gauge --gate` exit 0. |
| (f) `amd/src == amd/build` | **PASS (byte-equal).** `chat.js==chat.min.js` md5 `38c18a0f…`; `courses.js==courses.min.js` md5 `75caac66…`; `pack.js==pack.min.js` md5 `6a2b84f7…`. |
| (g) `gold/l5.yaml` frozen + pilot reference; drafts still draft | **PASS.** `status: passable`; `pilot_exception` block names the authority/cohort/two students/course; `r12…evidence` → `evidence/R12-pilot-transcript.json`. `gold/l5-curriculum.draft.yaml` and `gold/l5-r11.draft.yaml` are `status: draft`, `not_pass: true`. `gold/l5-r12.pilot.yaml` is `status: pilot`. |
| (h) `student_cohorts` empty; tables; `people:view` | **PASS with recorded nuance.** Evaluator/repo `student_cohorts_non_empty=False`; **no Carbon/medicine table** exists. The local Docker's recorded pilot config sets `student_cohorts=pulse_student_pilot`, gated by `pilot_students=1` (the PILOT-EXCEPTION); non-pilot paths default-deny. Moodle plugin tables are exactly **`local_pulse_consent` + `local_pulse_audit`** (no others). No `people:view` on any medicine surface; no grant made. |

Also verified: S3 live-assessment guard `ai/moodle_integrity.py` wired at the
top of `prepare_ask`, `page_context_from_snapshot`, `door_answer` in
`ai/moodle_host.py`; readiness machinery `ai/moodle_readiness/{gate,notices,
evaluator,l5_draft,pilot}.py` present, **default-OFF** (no migrations, no
`models.py`, not imported by the ask turn — `test_turn_path_never_names_readiness`
passes in the sweep).

---

## 3. Consolidated rung table

Marker: **BY-CODE** = only code/authoring remains; **BY-REAL-WORLD** = a live
artifact, human action, or policy decision is required. Every row is currently
unmarked in production.

| Rung | LOCAL (dev, plugin `2026100215` applied; disk `2026100301`, upgrade pending) | PRODUCTION | Marker | Exact production blocker |
|---|---|---|---|---|
| **K8** Worlds stay apart | Red | Unmarked / Red | BY-REAL-WORLD | Filter exists (L4/R9); Ask is not yet a product pass. Live product evidence required. |
| **K10** Staff | **DONE locally** — 5/6 gates (plugin version, HMAC, `staff_cohorts=pulse_staff_dev`, all 13 listed courses carry C6 gold, staff notice published with author + timestamp). Only `production_installed` false → K10 `not_pass`. | **Unmarked / Red** | BY-REAL-WORLD | Production Moodle 4.1 install + HMAC + named staff cohort + R15+R18 notice to it. Runbook + evaluator + plugin lever complete and inert. |
| **K11** Students | **LOCAL PILOT PASS** — K11 (local pilot) only: cohort `pulse_student_pilot`, two consented real accounts, student notice published, audit live, R12 2/2, L5 frozen `passable` under the exception. | **Unmarked** — `repo_inputs` K11 `not_pass` (`student_notice_published`, `student_cohorts_non_empty`, `consent_gate_present`, `rbac_path_present`, `audit_path_present` all false). | BY-REAL-WORLD | Production install + real (non-pilot) student cohort + student notice + consent/RBAC/audit at production scale + R12 with two real students. |
| **Medicine L5** Grounded lecture | `passable` (local pilot) — 13/13 shortnames at bar, door-cited 1299/1300 (MED213 99/100), 0 extra facts, R11 4/4, R12 2/2. | `not_passable` (production) | BY-REAL-WORLD | Real student cohort/install; the freeze rests on the recorded local exception, not a production cohort. |
| **B4** Short memory | Green as a field | same | — (NOT BLOCKED) | None. `memory_short_typed`; setting it `False` flips the evaluator, proving it is a flippable input, not hardcoded. |
| **B5** Long per-student memory | `not_passable` | `not_passable` | BY-REAL-WORLD | Long store absent; needs non-empty cohort + consent + audit + R12. No table exists or may be created. |
| **B6** Lecture→ILO→assessment graph | `not_passable` | `not_passable` | BY-REAL-WORLD | Authored, human-approved passage-grounded edges. Indexing ≠ graph. No Neo4j. |
| **C7** Session→outcome edges | `not_passable` | `not_passable` | BY-REAL-WORLD | C6 green for every listed shortname, L5 passable, then real session edges. Not a gate; not Carbon's `knowledge_graph`. |

Tutor sub-rungs T1/T2/T3/T5 and enterprise rungs B0–B3 are green; they are not
the K/B/C medicine rungs above. No production medicine rung is green.

---

## 4. "Code side complete" statement

**The medicine release code side is complete and internally consistent for the
frozen scope.** 248 moodle tests pass; both gates exit 0 with no meter rise; the
plugin PHPUnit suite is green (88/686, including the embed-URL guard); the canvas
typechecks with 0 diagnostics; the engine is inert (0 references, budget 0); the
`amd/src == amd/build` parity holds; `student_cohorts` defaults empty with no
Carbon table; and `gold/l5.yaml` is unchanged by this verifier.

Nothing that blocks production is a new feature for an agent to silently build.
The **remaining BLOCKED-BY-CODE backlog items** are the ones named in
`BLUEPRINT-REVIEW.md` §3 (exact items B1–B6) — backlog, **not** release
blockers, and **not** built in this pass:

- **B1 · Extraction upgrades.** PowerPoint speaker-note/comment extraction; OCR
  machinery for a PDF with no text layer; LibreOffice-headless `.ppt`→`.pptx`
  (LibreOffice is **not** installed here; the 9 legacy decks were recovered with
  the committed direct OLE2/CFB reader). Plus vision descriptions **only** as
  non-citable retrieval labels. *OCR text sign-off and any vision text are
  BY-REAL-WORLD.*
- **B2 · Keyword/BM25 hybrid (no vector store).** Blocked by code: the B3-style
  retrieval gold (a title-door miss a unique passage answers) must be authored
  first. No `re.compile`, no phrase table in the engine; unique-passage rule stands.
- **B3 · Faithfulness / entailment second pass.** Blocked by code but **not
  needed now**: every medicine door is deterministic (verbatim spans only).
- **B4 · Intent taxonomy + risk tags + learner signals in typed state.** Code
  work; must land in `Decision`/`ConversationState`, never a phrase table.

(`B5` and `B6` are BY-REAL-WORLD and cannot be completed by code.)

---

## 5. Real-world checklist to flip K10 / K11 (production)

### K10 — staff (execute `K10-RUNBOOK.md` after a production window is authorised)

1. Copy `local_pulse` (component `local_pulse`, **version `2026100301`**,
   requires Moodle 4.1 `2022112800`) onto production; finish the upgrade from
   **Site administration → Notifications**. Do **not** restore a DB backup; do
   **not** copy users or grades (R17).
2. On **Connection** (site:config only): `enabled=1`; `staff_cohorts` = the
   named staff cohort idnumber(s); `student_cohorts` = **empty** (R16);
   `enabled_courses` = the 13 C6-gold shortnames only (`NMD1000, NMD1103,
   NMD1301, NMD1402, NMD2101, MED213, NMD2303, NMD2403, NMD3101, NMD3304,
   NMD4201, MED520, MED5310`); `endpoint` = production Carbon Ask URL;
   `embedurl` = production pane URL; `sharedsecret` = `MOODLE_PULSE_HMAC_SECRET`.
3. HMAC: `HMAC-SHA256(secret, f"{timestamp}." + body)`, skew ≤ 120 s; a
   tampered/blank signature is rejected before any answer.
4. Publish **exactly** the R15+R18 sentence, only to the named staff cohort,
   through Connection → Staff notice (`classes/local/notice.php`); refused
   without cohort + shortnames + all five clauses; records author + timestamp;
   Withdraw always allowed; default unpublished.
5. Then `evaluate(repo_inputs(production_installed=True, hmac_configured=True,
   staff_cohorts_non_empty=True, listed_courses_all_have_c6_gold=True,
   staff_notice_published=True)).by_id["K10"].passed is True`, plus the
   per-course staff smoke table (R14/R17).

### K11 — students (a separate decision; do not start before L5 is passable)

1. Medicine L5 passable for every listed shortname in **production**: 100-question
   gold per shortname, ≥ 95 passage cites, ≤ 2 extra facts; R11 4/4; R12 2/2 with
   **two real students**.
2. Publish the **student notice** (frozen §1.2 text) to the named student cohort.
3. `student_cohorts` = the named student cohort idnumber(s) (non-empty).
4. Consent + RBAC + audit at production scale: per-`(student, course_shortname)`
   consent with policy version and grant/revoke events; gate allows only a cohort
   member who can already open the course and holds a current consent; every
   allow/deny audited. (Plugin consent/audit exists locally from the pilot; the
   Carbon-side host audit sink is still unbuilt — `DEFERRED.md` #7.)
5. L6 CI gold job green + full rollout on the listed courses (K11.5 is the pass),
   then `evaluate(...)` with every K11 gate true.

---

## 6. R12 circularity / policy note

R12 (same lecture, two students) requires **two real student accounts**, which
requires a non-empty `student_cohorts`. But R16 keeps `student_cohorts` empty
until L5 is passable, and L5 cannot pass without R12. **This circular dependency
cannot be broken by code.**

**Recorded local resolution.** On 3 Oct 2026 the platform superuser (`ahmed`)
authorised a recorded, consented, audited **local-dev-only** pilot
(`PILOT-EXCEPTION.md`): cohort `pulse_student_pilot` with two real local
accounts (`pilot_student_a` 3057, `pilot_student_b` 3058) on `NMD1103`, consent
+ audit in `local_pulse_consent`/`local_pulse_audit`, gated by
`pilot_students`. R12 returned the **identical** cited passage
(`NMD1103:file:1005:Virtual Tour in Hospital Facilities.pdf`) and identical reply
for both, with **zero** cross-student mention; clinical, MCQ, and live-assessment
refusals re-asserted. This is why `gold/l5.yaml` is `passable` and K11 is
`pass` **as K11 (local pilot)**.

**Still a human policy decision in production.** The pilot does **not** resolve
the production loop. Production K11 needs a production install plus a real
(non-pilot) student cohort and a recorded policy decision on how to obtain
two-student evidence without opening the production student surface — e.g. a
scoped, consented, audited test cohort explicitly exempted from the rollout, or
a recorded exception. **No agent may resolve this by filling production
`student_cohorts` or by marking a production rung.**

---

## 7. Confirmations requested

- **Nothing marked green.** `repo_inputs` passes only `B4`; K10/K11/B5/B6/C7 are
  `not_pass`. Canvas: K8 Red; K10/K11 rows "LOCAL (dev) · production Red";
  B5/B6/C7 `not_passable`; B4 "green as a field". The only pass beyond B4 is K11
  **labelled K11 (local pilot)**.
- **`engine/**` untouched / inert.** 0 references across 478 files; gauge exit 0;
  `domain_terms_in_core=0`; `brand_literals_in_core=0`.
- **Golds untouched.** This verifier edited no file under `domain_packs/`.
  `gold/l5.yaml` was already `passable` from the pilot (read-only here);
  `l5-curriculum.draft.yaml` / `l5-r11.draft.yaml` remain `status: draft`,
  `not_pass: true`.
- **`student_cohorts`.** Evaluator/repo state empty (`False`); **no new table**
  anywhere in Carbon. The only plugin tables are `local_pulse_consent` +
  `local_pulse_audit`. On the local Docker the recorded pilot sets
  `student_cohorts=pulse_student_pilot` behind `pilot_students=1`; non-pilot
  paths deny. **No `people:view`.**
- **`amd/src == amd/build`** byte-equal for chat/courses/pack.
- **No commit**, no deploy, `manage.sh` not started/killed.

### Restart / rebuild needed?

**Yes for a running Carbon:** the backend Python (`moodle_host.py`,
`moodle_bank.py`, `moodle_page.py`, `moodle_integrity.py`, `moodle_readiness/`)
must be reloaded for a live Ask server to pick it up. The plugin PHP is already
loaded in the Docker Moodle (DB + PHP version `2026100215`, one `upgrade.php`
run); further `amd` changes would need a Moodle **cache purge**. The canvas is
not runnable code (typecheck only). This verifier performed **no** restart, start,
or kill.
