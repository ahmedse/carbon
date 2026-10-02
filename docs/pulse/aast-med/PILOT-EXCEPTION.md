# Local consented student pilot — recorded exception

Status: **ACTIVE — local dev only**. Authorized 3 Oct 2026, by the platform
superuser (`ahmed`), in a live session, for the aast-med Pulse readiness work.

This document records a deliberate, audited **exception** to the default-deny
rule in `READINESS-SPEC.md`. The frozen spec says `student_cohorts` stays empty
until medicine L5 is passable, and L5 cannot pass without R12 (two real
students on one lecture). That is a circular dependency (§6 of `STATUS.md`).
This exception breaks the loop **locally**, with consent and audit, and nothing
more. It is a first-class artifact, not a hack: the same gate, cohort, consent,
and audit machinery the spec describes is exercised end to end.

---

## 1. Exact scope

| Item | Value |
|---|---|
| Environment | Local dev only — Docker Moodle `med-moodle-webserver-1` at `http://localhost:8000` + local Carbon at `http://127.0.0.1:8009`. |
| Brand / pack | `aast-med` (`world: aast-mbbs`). |
| Students | Exactly **two** real local Moodle accounts: `pilot_student_a`, `pilot_student_b` (student archetype, not staff, not admin). |
| Cohort | One system cohort, idnumber `pulse_student_pilot`, members = those two accounts only. |
| Course / lecture | One listed course, `NMD1103` (Clinical Skills 1, course id 5). Enrolment only; **no course content is edited**. |
| Consent | Explicit per-`(student, course_shortname)` opt-in, `policy_version` = 1, recorded with grant time and actor. |
| Audit | Append-only allow/deny + grant/revoke rows (`local_pulse_audit`). |
| Feature flag | `local_pulse/pilot_students` (default `0`). Students receive a Pulse audience only when the flag is on **and** they are in `student_cohorts`. |

The two accounts are enrolled in the 13 listed shortnames so the RBAC
"can already open the course" precondition holds, but the pilot surface is
scoped to `NMD1103` by consent: every other course still denies.

## 2. Who authorized it

- **Authorizer:** `ahmed` — the platform superuser for every brand (see
  `.cursor/rules/universal-superuser.mdc`).
- **When:** 3 Oct 2026, this session.
- **Act:** an explicit, recorded authorization to run a local, consented,
  audited student pilot that the frozen rules otherwise forbid before L5.
- The authorization is recorded here and referenced from `gold/l5.yaml` and
  the STATUS evidence block. No production system is touched.

## 3. Invariants this exception does NOT relax

The exception opens a *local, consented, audited* two-student surface. It does
**not** relax any safety or honesty rule:

1. **No oversharing.** Two students on the same lecture receive the identical
   cited passage; neither reply mentions the other student, prior history, or
   performance (R12). No cross-student data ever leaves Moodle.
2. **No clinical advice.** Dose, diagnosis, and treatment questions are refused
   for students exactly as for staff.
3. **No live-assessment help.** When an assessment is open, the S3 guard
   refuses (integrity answer) before any content is produced.
4. **No exam/MCQ help.** Quiz/answer questions are refused.
5. **No writes.** Chat never host-mutates (ADR-0046). The pilot only reads.
6. **No production.** `production_installed` stays `False`; K10 stays
   not-pass; no rollout, no deploy.
7. **No scope creep.** The pilot does not create a per-student memory store
   (B5 stays not-pass), a graph (B6), or a second datastore.
8. **No engine change.** `backend/ai/engine/**` is untouched.

## 4. Withdrawal and audit rules

- Consent is an append-only event log. A later `consent_revoke` row overrides
  an earlier grant; `active()` reads the latest row.
- The **very next** student turn after a revoke denies (`no_consent`); there is
  no penalty and no further per-student use.
- Every student allow and deny is audited with the typed reason, subject,
  course, and timestamp. Content is never logged beyond ids.
- Grant and revoke are both audited.
- Withdrawing the notice, the flag, or the cohort membership stops Pulse for
  the students immediately.
- To stand the pilot down: revoke consent for both students, set
  `local_pulse/pilot_students=0`, empty `local_pulse/student_cohorts`. The
  accounts and audit rows remain as the honest record.

## 5. Sunset

This exception has **no production meaning**. It sunsets when the real
artifacts exist:

- **Production K11 still requires:** medicine L5 passable + a **production**
  Moodle install + a real (non-pilot) student cohort + a published student
  notice + consent/RBAC/audit — not this local pilot.
- The freeze of `gold/l5.yaml` to `passable` is explicitly qualified: it rests
  on this recorded local consented pilot exception, **not** on a production
  cohort. `K11 (production)` remains unmarked until the production conditions
  above hold.
- K10 (production staff) remains not-pass: `production_installed` is `False`.

## 6. What this exception turns on, concretely

1. Cohort `pulse_student_pilot` with the two accounts (real Moodle cohort).
2. `local_pulse_consent` + `local_pulse_audit` tables (plugin `2026100215`),
   the single source of truth for consent + audit; identity stays in Moodle.
3. A Carbon mirror of **only** the typed consent state (grant/revoke +
   `policy_version` + timestamp), never student content, consumed by
   `ai.moodle_readiness.pilot`.
4. R12 run as the two real accounts on `NMD1103`: identical cited passage,
   zero cross-student mention.
5. The safety refusals re-asserted for students.

See also: `READINESS-SPEC.md` §1.3/§1.6, `L5-PASSABILITY.md` §2.3,
`STATUS.md` §6.
