# aast-med Pulse — Production Evidence Checklist (WS-5 / L-P)

**Purpose.** This is the WS-5 (production evidence) checklist for the frozen
teaching-wave spec's L-P ladder. For each production rung it records (a) the
**exact evidence the frozen spec requires**, (b) the **current honest state**
with a doc citation, (c) a classification — **LOCALLY CLOSABLE** (concrete
local command/artifact closes it) vs **BY-REAL-WORLD** (a live artifact, human
action, or policy decision is required) — and (d) the exact next action.

**Source of truth (frozen):** [`TEACHING-WAVE-SPEC.md`](TEACHING-WAVE-SPEC.md)
— FROZEN v1.0, 3 Oct 2026 — especially **§1.5 L-P** (local vs BY-REAL-WORLD per
rung) and **§3 WS-5** (production benchmark + evidence). Supporting frozen
contracts: [`READINESS-SPEC.md`](READINESS-SPEC.md) (frozen 2 Oct),
[`L5-PASSABILITY.md`](L5-PASSABILITY.md) (frozen 2 Oct),
[`K10-RUNBOOK.md`](K10-RUNBOOK.md), [`DEFERRED.md`](DEFERRED.md). Authoritative
current status: [`STATUS.md`](STATUS.md) (3 Oct 2026).

**Date of this checklist:** 3 Oct 2026.

**This is a checklist, not a pass.** Nothing here is marked green, and no rung
is changed by this document (see §4).

---

## 1. Per-rung table

"Spec evidence" = the exact evidence the frozen spec requires. "Current" cites
the doc that states the honest state. Classification is the **residual**
classification for production; local sub-parts already done are noted further
in the row.

| Rung | Spec-required evidence (exact) | Current honest state (doc citation) | Classification | Exact next action / artifact |
|---|---|---|---|---|
| **K10** — staff, production | Production **Moodle 4.1** install; HMAC secret set + verifies (wrong-sig rejected, skew > 120 s rejected); a **named staff cohort**; `student_cohorts` empty; `enabled_courses` only C6-gold shortnames; R15+R18 staff notice sent to **exactly** that cohort; then `evaluate(repo_inputs(production_installed=True, hmac_configured=True, staff_cohorts_non_empty=True, listed_courses_all_have_c6_gold=True, staff_notice_published=True)).by_id["K10"].passed is True` + R14/R17 per-course smoke table. Cite: TEACHING-WAVE-SPEC §1.5 (K10 row) and §3 WS-5; READINESS-SPEC §2; K10-RUNBOOK §6. | **`not_pass`.** `repo_inputs()` → K10 `not_pass`, all 6 gates false, `passed_ids == ("B4",)` (STATUS.md §0.2). Local dev inputs → K10 `not_pass`, **5/6** gates OK, only `production_installed` false (STATUS.md §0.2). Runbook + evaluator + plugin notice lever + HMAC logic + admin desk **complete and inert** (STATUS.md §3). Local Docker is Moodle **5.2.3**, not the production **4.1** target (STATUS.md §0 note). | **BY-REAL-WORLD** (residual). Local sub-parts are already done: evaluator, `K10-RUNBOOK.md`, plugin notice lever, HMAC logic, admin desk (TEACHING-WAVE-SPEC §1.5 K10 row). | In an authorized production window, have a human execute `K10-RUNBOOK.md` on production Moodle 4.1: install/enable the plugin, set `MOODLE_PULSE_HMAC_SECRET` + Ask/pane URLs, set the named staff cohort, keep `student_cohorts` empty, publish the R15+R18 notice through Connection → Staff notice, run the per-course smoke, then run the evaluator line. Artifact = production install + the published-notice record (body + cohort id + timestamp) + smoke table. |
| **K11** — students, production | Real **(non-pilot) student cohort**; **student notice** published (separate decision, R16); consent + RBAC + audit at **production scale**; **R12 with two real students** on one lecture; `student_cohorts` non-empty; `evaluate(...)` with every K11 gate true → `K11 = pass`. Cite: TEACHING-WAVE-SPEC §1.5 (K11 row) and §3 WS-5; READINESS-SPEC §3. | **Production `not_pass`.** `repo_inputs()` K11 `not_pass` — `student_notice_published`, `student_cohorts_non_empty`, `consent_gate_present`, `rbac_path_present`, `audit_path_present` all false (STATUS.md §3). Only a recorded **LOCAL (dev)** pilot passes: `pilot_inputs()` → K11 `pass`, labelled **`K11 (local pilot)`** (STATUS.md §0.2, §3), cohort `pulse_student_pilot` behind `pilot_students=1` (PILOT-EXCEPTION; STATUS.md §2(h), §6). Gate machinery `ai/moodle_readiness/` exists, default-OFF/default-deny (STATUS.md §2; READINESS-SPEC §3). | **BY-REAL-WORLD** (residual). Local sub-parts done: gate machinery (default-deny), consent/audit tables, R11 draft cases, L5 curriculum counts (TEACHING-WAVE-SPEC §1.5 K11 row; STATUS.md §3). | Provide a production install + a real, named student cohort + published student notice + production-scale consent/RBAC/audit records + R12 with two real students; then run `evaluate(...)` with every K11 gate true. Requires the recorded **human policy decision** on how to get two-student evidence without opening the production student surface (STATUS.md §6). No agent may fill production `student_cohorts`. |
| **Medicine L5** — production | C6 green for every listed shortname; per-shortname **100-question gold** (`sample_size 100`, `min_passage_cite ≥ 95`, `max_extra_fact ≤ 2`), result written to `curriculum_benchmark.short`; **R11 4/4**; **R12 2/2 with two real students**; `gold/l5.yaml` `status: passable` by **human review + freeze** of the curriculum gold. Cite: TEACHING-WAVE-SPEC §1.5 (Medicine L5 row) and §3 WS-5; READINESS-SPEC §3; L5-PASSABILITY §2/§3. | **Under the recorded local pilot only: `passable`.** STATUS.md §3, §6: `passable` (local pilot) — 13/13 shortnames at bar, door-cited 1299/1300, R11 4/4, R12 2/2; production `not_passable`. The curriculum draft is authored in full (1300 items, 100/shortname) and R11/R12 drafts are `status: draft`, `not_pass: true` (STATUS.md §2(g), §3; L5-PASSABILITY §3). Frozen 2 Oct contracts still say `not_passable`, R11/R12 `frozen_n == 0`, `short: {}` (L5-PASSABILITY §1; READINESS-SPEC §3) — see **conflict C1** in §5. | **BY-REAL-WORLD** for the freeze + production cohort. Local sub-part done: the 100-question gold per shortname (draft, 1300 items) and R11 4/4 (TEACHING-WAVE-SPEC §1.5; STATUS.md §3). | Human review + **freeze/sign-off** of `gold/l5-curriculum.draft.yaml` (1300 items) and `gold/l5-r11.draft.yaml` into `gold/l5.yaml` (a sign-off, not machinery — L5-PASSABILITY §3); then a production cohort for the R12 2/2 freezes (two real students on one lecture). |
| **B5** — long per-student memory | Non-empty cohort + consent + audit + **R12**; a **per-student store behind the gate**; no cross-student mixing; **no new table**; B5 true only after K11. Cite: TEACHING-WAVE-SPEC §1.5 (B5 row); READINESS-SPEC §5. | **`not_pass` / `not_passable`.** Long store **absent**; needs non-empty cohort + consent + audit + R12; "No table exists or may be created" (STATUS.md §3). `repo_inputs()` → B5 `not_pass` (STATUS.md §0.2). B4 short memory is green **as a field** (B4.5 current) (STATUS.md §3; READINESS-SPEC §4). | **BY-REAL-WORLD.** Local sub-part done: typed short memory **B4** (green; TEACHING-WAVE-SPEC §1.5 B5 row; STATUS.md §3). | Satisfy the K11 preconditions (cohort + consent + audit + R12 with two real students) first, then a per-student store behind the gate that never mixes students and audits every read — **without creating a table** (STATUS.md §3). |
| **B6** — lecture→ILO→assessment graph | Authored, **human/teacher-approved**, passage-grounded lecture→ILO→assessment edges, each tracing to a real `passage_ref`; C6 green for every listed shortname; queryable so each edge returns its passage id; index is **not** the graph. Cite: TEACHING-WAVE-SPEC §1.4 G2 and §1.5 (B6/C7 row); READINESS-SPEC §6. | **`not_pass` / `not_passable`.** Needs authored, human-approved passage-grounded edges; "Indexing ≠ graph; no Neo4j" (STATUS.md §3). `repo_inputs()` → B6 `not_pass` (STATUS.md §0.2). The built graph (4,925 nodes / 23,364 edges, real `passage_ref` each) is additive and **not** a teaching dependency and **not** the B6 ILO/assessment layer (STATUS.md §0; TEACHING-WAVE-SPEC §1.4). | **BY-REAL-WORLD.** Local sub-part done: passage-id provenance checks (TEACHING-WAVE-SPEC §1.5 B6/C7 row). | Human/teacher-author and approve passage-grounded lecture→ILO→assessment edges (C6 green first); each edge must return its `passage_ref`. No store is created. |
| **C7** — session→outcome edges | **C6 green** for every listed shortname **and L5 passable** first; authored session→outcome edges, each grounded to a **real session**; audit + consent; retrieval gold. Cite: TEACHING-WAVE-SPEC §1.4 G2 and §1.5 (B6/C7 row); READINESS-SPEC §6. | **`not_pass` / `not_passable`.** "C6 green for every listed shortname, L5 passable, then real session edges; not a gate; not Carbon's `knowledge_graph`" (STATUS.md §3). `repo_inputs()` → C7 `not_pass` (STATUS.md §0.2). L5 is `passable` only under the local pilot (STATUS.md §3, §6). | **BY-REAL-WORLD.** Local sub-part done: passage-id provenance checks (TEACHING-WAVE-SPEC §1.5 B6/C7 row). | After C6 is green for every listed shortname **and** L5 is passable (production), author session→outcome edges each grounded to a real session, with audit + consent. |

**Note on K4/K9 (not in the L-P ladder, but named in the frozen spec).**
TEACHING-WAVE-SPEC §0 principle 10: "**K4/K9 stay red**; production
K10/K11/B5/B6/C7 stay unmarked". READINESS-SPEC §1: "`student_cohorts` stays
empty. **K4/K9, B5, B6, C7 stay red/not_passable.**" No medicine production
rung is green.

**Note on the local machinery (LOCALLY CLOSABLE, already done).** The following
local artifacts exist so the residual blocker on each row is real-world, not
code: `ai/moodle_readiness/` (gate, notices, evaluator, l5_draft, pilot) —
default-OFF and not imported by the ask turn (STATUS.md §2); `K10-RUNBOOK.md`;
the plugin staff-notice lever + HMAC logic + admin desk (STATUS.md §3);
`gold/l5-curriculum.draft.yaml` (1300 items) and `gold/l5-r11.draft.yaml` (4/4)
(STATUS.md §3); the typed consent-state mirror (DEFERRED.md #7 update). Local
gate commands that verify the code side today: `python -m ai.eval.pack_contract
--gate`, `python -m ai.eval.pulse_gauge --gate`, and the moodle pytest
selection (STATUS.md §0).

---

## 2. What the user (superuser `ahmed`) must personally authorize or provide

These are the **BY-REAL-WORLD** items only — the ones no agent can produce.

1. **Production window + production Moodle 4.1 install.** Authorize an operator
   to run [`K10-RUNBOOK.md`](K10-RUNBOOK.md) on production Moodle 4.1 (the
   local Docker is 5.2.3, not 4.1 — STATUS.md §0). (K10)
2. **HMAC secret + URLs.** Set `MOODLE_PULSE_HMAC_SECRET` on the production
   Carbon process and enter the matching Ask URL / pane URL / secret in the
   plugin Connection tab (not committed — K10-RUNBOOK §2). (K10)
3. **A named staff cohort** (Moodle system cohort idnumber(s)) and publishing
   the exact **R15+R18 staff notice** to exactly that cohort through
   Connection → Staff notice; `student_cohorts` stays empty (R16). (K10)
4. **A production student cohort decision** + publishing the frozen **student
   notice** + consent/RBAC/audit at production scale. (K11)
5. **Two real students on one lecture (R12)** for production, plus the
   recorded **policy decision** on how to obtain two-student evidence without
   opening the production student surface (STATUS.md §6). (K11 / L5 / B5)
6. **Human review + freeze/sign-off** of the L5 curriculum gold
   (`gold/l5-curriculum.draft.yaml`, 1300 items) and the R11 draft
   (`gold/l5-r11.draft.yaml`) into `gold/l5.yaml` — a human curriculum
   statement, not machinery (L5-PASSABILITY §2.1/§3). (L5)
7. **Authored, human/teacher-approved passage-grounded lecture→ILO→assessment
   edges** (B6), and, once C6 is green and L5 passable in production, **real
   session→outcome edges** (C7). (B6 / C7)
8. **Arabic OCR quote sign-off** — the scanned `MED5310` PDF's Arabic text stays
   `status=pending_signoff` / non-citable until a recorded human sign-off of
   the **exact quote** (TEACHING-WAVE-SPEC §1.3 C2; STATUS.md §0). *(Outside the
   K/B/C rungs but a named real-world sign-off in the frozen spec.)*
9. **The local pilot exception is already authorized and is LOCAL only.** The
   `ahmed`-authorized, consented, audited local-dev pilot
   ([`PILOT-EXCEPTION.md`](PILOT-EXCEPTION.md)) is what lets `gold/l5.yaml` be
   `passable` and K11 read `pass` **as K11 (local pilot)** — it does **not**
   resolve production (STATUS.md §6). No separate action needed, but it must not
   be mistaken for production authorization.

---

## 3. Explicit no-green statement

**Nothing in this document marks any rung green, and this document changes no
rung.** Per the frozen spec (TEACHING-WAVE-SPEC §0 principle 10, §1.5) and the
authoritative status (STATUS.md §0.2, §2(c), §3, §7):

- `repo_inputs()` passes **only** `B4`; **K10, K11, B5, B6, C7 are all
  `not_pass`/`not_passable`** in production.
- **K10 `not_pass`**; **K11 `not_pass`** in production (the only pass beyond B4
  is K11 **labelled `K11 (local pilot)`**); **Medicine L5 `not_passable`** in
  production (`passable` **only** under the recorded local pilot exception);
  **B5/B6/C7 `not_passable`**; **K4/K9 red** (STATUS.md §0.2, §3; READINESS-SPEC
  §1).
- **No rung is marked from a stub, a unit bank, one PASS, or a `--noreload`
  process** (TEACHING-WAVE-SPEC §0 principle 10, §4).
- **`student_cohorts` stays empty** in evaluator/repo state; no Carbon table is
  created; no `people:view` is granted (STATUS.md §2(h), §7).

This checklist records required evidence and classification only.

---

## 4. Doc conflicts found (recorded, not resolved)

The task asked to **note** conflicts rather than pick a side. All are recorded
here; none is papered over.

- **C1 — L5 status: frozen 2 Oct contracts vs 3 Oct status.** `L5-PASSABILITY.md`
  §1/§3/§4 and `READINESS-SPEC.md` §3 (both **frozen 2 Oct**) state L5
  `not_passable`, R11/R12 `frozen_n == 0`, `short: {}`, and "do not fill
  `student_cohorts`". `STATUS.md` §3/§6 (**3 Oct**, authoritative) states L5
  `passable` (local pilot), R11 4/4, R12 2/2. `STATUS.md` §1(i) explicitly
  records this drift: the frozen contracts were **not edited** (doing so would
  look like loosening); the recorded pilot exception supersedes them for the
  L5/R11/R12 status **only**, and `STATUS.md` is authoritative. Both are left
  standing; they disagree.

- **C2 — K10-RUNBOOK preconditions vs the 3 Oct pilot state.** `K10-RUNBOOK.md`
  §0 (frozen 2 Oct) requires "`test_moodle_l5.py` still `not_passable`;
  `student_cohorts` empty". Under the 3 Oct local pilot, `gold/l5.yaml` is
  `passable` and the local Docker sets `student_cohorts=pulse_student_pilot`
  behind `pilot_students=1` (STATUS.md §2(g)/(h), §6). So the runbook's
  precondition as written no longer matches the 3 Oct **local** state — while
  the **production** K10 requirement (`student_cohorts` empty, R16) still
  holds. Recorded, not edited.

- **C3 — Plugin version: runbook/disk vs applied DB.** `K10-RUNBOOK.md` §1 uses
  version `2026100301` and §6 accepts `>= 2026100215`; `STATUS.md` §1(j)/§1(k)
  records `version.php` on disk = `2026100301` (T2 teach-apply) but applied/DB
  `local_pulse/version` = `2026100215` (no container up, `upgrade.php` pending).
  Drift, not a contradiction: the runbook/disk value is ahead of the applied
  value; the upgrade is pending.

- **C4 — Moodle version: production target vs local evidence.** The runbook and
  spec target production **Moodle 4.1**; the local Docker is Moodle **5.2.3 /
  PHP 8.3.33 / pgsql 17.11** (STATUS.md §0 note). Local evidence therefore
  exercises the plugin on a **newer** Moodle than the production target; 4.1
  install remains real-world work.

- **C5 — R11 "4/4" is a draft count, not a frozen one.** TEACHING-WAVE-SPEC
  §1.5 and §3 WS-2 list "R11 4/4" among the locally closable items, while
  `STATUS.md` §2(g) states `gold/l5-r11.draft.yaml` is `status: draft`,
  `not_pass: true` and `gold/l5-curriculum.draft.yaml` is likewise `draft`.
  Reconciled reading: the 4/4 **cases are authored** as drafts; the **freeze**
  is still pending. Noted so "4/4" is not read as frozen evidence.

---

## 5. Scope / safety confirmation

- Only this file (`PRODUCTION-EVIDENCE.md`) was created. No other file was
  edited. `STATUS.md`, `READINESS-SPEC.md`, the canvas, any code, plugin, gold,
  or `domain_packs` were **not** modified.
- No implementation, no commit, no deploy; `manage.sh` was **not** started or
  killed.
