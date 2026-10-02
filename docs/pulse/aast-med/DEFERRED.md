# Deferred changes — owned by another worker

I did **not** edit these surfaces (another worker owns them concurrently):
`/home/ahmed/ws/med/plugins/local_pulse/**`, `backend/ai/moodle_page.py`,
`backend/ai/moodle_host.py`, and the aast-med canvas. This ledger lists every
change the spec implies but that I did not make, so the parent can sequence it.

Nothing here is required for the code-side machinery I shipped
(`backend/ai/moodle_readiness/`, all default-OFF).

> **Update 3 Oct 2026 — status.** Item **#1** was executed for the **staff
> notice only** (plugin `2026100214`): a `notice::publish` lever on the
> Connection tab, unpublished-by-default, refused unless the text carries every
> R18 clause and a staff cohort + shortname are selected. Non-staff parts of #1
> (the **student** notice UI and any student-visible surface) remain deferred —
> forbidden before K11. Item **#2** (version bump) was completed by that work.
> Items **#3–#8** remain deferred.

## 1. Plugin — notice registry storage + Connection fields

- **File(s):** `plugins/local_pulse/settings.php`,
  `plugins/local_pulse/lang/en/local_pulse.php`,
  `plugins/local_pulse/courses.php` (Connection tab),
  new `plugins/local_pulse/classes/notice.php`.
- **Intended change:** add a staff/student notice record with
  `published`/`unpublished` state, cohort idnumbers, shortnames, the five R18
  clauses, and a publish timestamp; render an unpublished-by-default notice
  block on Connection (site:config only; never on Courses).
- **Why deferred:** the plugin is co-owned by the concurrent worker. The
  Carbon-side `NoticeRegistry` already models the state and defaults
  unpublished, so no Carbon change is needed to proceed later.

## 2. Plugin — version bump

- **File:** `plugins/local_pulse/version.php`.
- **Intended change:** bump `$plugin->version` when the plugin changes and keep
  it `>= 2026100214`.
- **Status:** done — bumped `2026100213` → `2026100214` with the staff-notice
  lever.
- **Dependency:** `PLUGIN_VERSION_MIN` in
  `backend/ai/moodle_readiness/evaluator.py` mirrors this value; it was
  re-synced to `2026100214` alongside the bump. Keep them equal whenever the
  version rises.

## 3. Plugin — consent capture + audit hook

- **File(s):** new `plugins/local_pulse/classes/consent.php`,
  `plugins/local_pulse/classes/hook_callbacks.php`,
  `plugins/local_pulse/lang/en/local_pulse.php`.
- **Intended change:** explicit per-`(student, course)` opt-in with a policy
  version, grant/revoke events, and an append-only audit call; show the
  student notice before first use; withdraw stops Pulse for that student.
- **Why deferred:** co-owned, and it must not be built before K11
  preconditions (L5 passable, cohort, consent rules in
  `READINESS-SPEC.md` §1.3/§1.6).

## 4. Plugin — future student surface consults the gate

- **File(s):** new `plugins/local_pulse/ajax/student_ask.php` (and a
  `db/access.php` capability check), or an extension of the existing
  `ajax/ask.php` behind a feature flag.
- **Intended change:** before any student turn, call Carbon's
  `consult_student_surface(...)`; on deny, return the typed reason and do not
  send a page snapshot. Default must be closed while `student_cohorts` is
  empty.
- **Why deferred:** co-owned, and opening a student surface is exactly what
  K11/R16 forbid before L5. The Carbon gate exists and is proven default-deny
  in tests.

## 5. Plugin — lang strings for the notices

- **File:** `plugins/local_pulse/lang/en/local_pulse.php`.
- **Intended change:** add the exact staff and student notice strings
  (`READINESS-SPEC.md` §1.1/§1.2) plus consent labels.
- **Why deferred:** co-owned (the concurrent worker is editing lang).

## 6. Carbon — route student turns through the gate (do not touch now)

- **File(s):** `backend/ai/moodle_host.py`, `backend/ai/moodle_page.py`.
- **Intended change:** when a student surface is eventually opened, an
  explicit, feature-flagged call to `consult_student_surface` before building a
  chat; deny → typed refusal, no snapshot.
- **Why deferred:** these two files are read-only for me, and wiring the gate
  into the live turn path now would change behaviour and violate the
  default-OFF requirement. Today neither file names `moodle_readiness`
  (asserted by `test_turn_path_never_names_readiness`).

## 7. Carbon — audit sink (no tables created)

- **File(s):** a future `ai/moodle_readiness/audit.py` + a host sink decided by
  the parent.
- **Intended change:** append-only allow/deny + consent grant/revoke records
  with typed reason, subject, course, cohort, policy version, timestamp.
- **Why deferred:** creating a per-student store before cohort + consent is the
  oversharing failure the contract forbids. No table was created.

## 8. Canvas — reference the evaluator (no status change)

- **File:** `aast-med-pulse-manifesto.canvas.tsx` (Cursor canvas, co-owned).
- **Intended change:** link `READINESS-SPEC.md` / `L5-PASSABILITY.md` /
  `K10-RUNBOOK.md` and, if desired, read `evaluate(repo_inputs()).as_dict()`
  instead of describing rungs by hand. **No rung colour changes:** K8/K10/K11/
  L5 stay unmarked; B5/B6/B6-C7 stay not_passable.
- **Why deferred:** the canvas is co-owned and must not be edited by me.
