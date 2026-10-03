# K10 Runbook — install Pulse on production and tell the staff cohort

Human-executable. This runbook performs the real-world actions that flip K10.
An agent does **not** execute it: no deploy, no `manage.sh` start/kill, no
production write. Run it only after the parent authorises a production window.

Frozen contract: the readiness spec `READINESS-SPEC.md`. Evidence returns to
the readiness evaluator (`ai/moodle_readiness.evaluator`), which marks K10
`pass` only when every gate is true.

## 0. Preconditions (do not start if any fails)

- [ ] Stage 0–1 green on dev: admin on a listed dev course gets a ticket URL;
      the eight NMD1103 C6 questions pass from the open activity.
- [ ] `python -m ai.eval.pack_contract --gate` = 0 violations.
- [ ] `test_moodle_l5.py` still `not_passable`; `student_cohorts` empty.
- [ ] The exact shortnames to enable are the ones that have **C6 gold**
      (`enabled_courses_gold_covers` in `gold/l5.yaml`). No other course.
- [ ] A named **staff** cohort idnumber exists (system cohort, allow-list only;
      no cohort-sync enrol method attached).
- [ ] `MOODLE_PULSE_HMAC_SECRET` is set on the Carbon process and matches the
      value you will enter. Not committed.

## 1. Install / upgrade the plugin

Plugin source: `plugins/local_pulse` (component `local_pulse`, version
`2026100301` on disk — T2 teach-apply; requires Moodle 4.1 `2022112800`).

1. Copy `local_pulse` into `<moodleroot>/local/pulse` on **production**. Do
   **not** restore a database backup onto production; do **not** copy users or
   grades (R17).
2. Visit **Site administration → Notifications** and complete the upgrade.
3. Confirm the Settings page shows exactly one Pulse name with four tertiary
   tabs: **Courses / Pack / Extra / Connection**.
4. Leave **Enable Pulse = off** for now.

## 2. Connection: Ask URL + pane URL + HMAC (R17)

On **Connection** (site:config only; HMAC fields must not appear on Courses):

| Setting | Value |
|---|---|
| `local_pulse/enabled` | `1` (turn on after the checks below) |
| `local_pulse/staff_cohorts` | the named staff cohort idnumber(s) |
| `local_pulse/student_cohorts` | **leave empty** (R16) |
| `local_pulse/enabled_courses` | the C6-gold shortnames only |
| `local_pulse/endpoint` | production Carbon Ask URL, e.g. `https://<carbon-host>/carbon-api/ai/moodle/ask/` |
| `local_pulse/embedurl` | production pane URL, e.g. `https://<carbon-host>/embed/pulse` |
| `local_pulse/sharedsecret` | equals `MOODLE_PULSE_HMAC_SECRET`; not committed |

HMAC rules (from `ai/moodle_host.py`): signature is
`HMAC-SHA256(secret, f"{timestamp}." + body)`; skew `|now - ts| <= 120 s`;
missing/blank secret or timestamp or signature ⇒ reject. A wrong signature
**must** be rejected before any answer.

## 3. Staff notice publish (R15 + R18)

1. Publish exactly this sentence, and only to the named staff cohort:

   > Pulse is on for staff in the named cohort, on the named course shortnames.
   > It answers from the lecture you have open. It does not grade, enrol, or see
   > another student, and it does not give a clinical dose or diagnose. If the
   > fact is not in that lecture, it says so.

2. The notice must name the cohort idnumber(s) and the exact C6-gold
   shortnames, and carry all five R18 clauses (no grade, no enrol, no other
   student, no clinical dose, lecture miss).
3. Publish the notice through the plugin lever: **Connection tab → Staff
   notice** (`classes/local/notice.php`, `notice::publish`). Publish is refused
   server-side unless the text carries every R18 clause AND a staff cohort
   idnumber AND a shortname are selected; on success it records the author and
   timestamp. The registry defaults unpublished; **Withdraw** is always allowed.
   The Carbon `NoticeRegistry` mirrors the same state, so the evaluator sees the
   published record.
4. Never a college-wide mail. Never a student mail. Never the student notice.

## 4. Per-course smoke (after enable)

For each enabled C6-gold shortname, as a **staff cohort member** (not a site
admin):

1. Open a course page and confirm the Pulse pane opens.
2. Ask a course-identity question → the open course is named from the snapshot.
3. Ask a section-title question → matches the snapshot.
4. Open one activity and ask a C6 fact question → returns the passage id and
   the quote; a quote from another activity returns exactly
   `This is not in this lecture.`
5. Ask an unlisted shortname → `This is not on the course list.` and no
   fullname is leaked.
6. Ask a clinical-advice question → the fixed refusal; no dose; no patient.
7. Ask an MCQ/exam question → the question-bank refusal.
8. HMAC negative: replay a request with a tampered signature → rejected.

Record per course: shortname, cmid, ask, expected, observed, pass/fail.

## 5. Rollback

Trigger on any smoke fail that is not a config typo, or on a PHP fatal.

1. **Fastest:** set `local_pulse/enabled = 0`. The pane closes; Ask returns
   the course-list miss; the pack stays on disk.
2. If the fatal persists with Pulse disabled, remove
   `<moodleroot>/local/pulse` and purge caches
   (**Site administration → Development → Purge caches**).
3. The staff notice cannot be un-sent; send a correction to the same cohort
   stating Pulse is off. Do not silently stop answering.
4. Preserve logs (web server + Carbon) for the post-window review.

## 6. Evidence checklist that flips K10

Attach each item; the evaluator reads the booleans.

- [ ] `production_installed` — plugin present and enabled on production 4.1;
      version `>= 2026100215`.
- [ ] `hmac_configured` — Ask URL + pane URL + secret set; correct signature
      accepted, tampered signature rejected.
- [ ] `staff_cohorts_non_empty` — the named staff cohort idnumber(s).
- [ ] `listed_courses_all_have_c6_gold` — every enabled shortname has C6 gold.
- [ ] `staff_notice_published` — published staff notice record (R15+R18).
- [ ] `student_cohorts` empty; per-course smoke table all pass (R14, R17).
- [ ] `evaluate(repo_inputs(production_installed=True, hmac_configured=True,
      staff_cohorts_non_empty=True, listed_courses_all_have_c6_gold=True,
      staff_notice_published=True)).by_id["K10"].passed is True`.

Only when the last line is true may the canvas mark K10. Until then it stays
unmarked.
