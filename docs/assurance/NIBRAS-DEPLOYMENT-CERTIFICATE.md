# Nibras deployment certificate

**Date:** 23 September 2026  
**Brand:** `nibras` / DB `nibras_dev`  
**Evidence commit label:** `nibras-demo-2026-09-23`  
**Ledger:** `docs/assurance/evidence/nibras-demo-2026-09-23.jsonl`

This is **not** a claim that Nibras is 100% production-assured, PAM-connected, or a Kuwait legal opinion. It is an evidence-backed statement of what the host People / My / Team processes do on this instance, under ADR-0029, ADR-0045, ADR-0046, and the Nibras assurance pack.

## Verdict

**Ready for an internal live demo and limited internal deployment of the named journeys below.**

**Not ready** to treat WPS as a bank/PAM filing, to close a full-roster statutory month without watching fail-closed ledger gaps, or to say Pulse Chat can change HR records.

| Gate | Result |
|---|---|
| Nibras assurance pack (17 blocking rules) | Binding probes pass on this tree. Re-run `python -m assurance probe --pack nibras` to stamp a ledger. |
| Platform `PL-CI-01` / `PL-VERIFY-01` | **Binding passed** — CI workflow runs pytest; `verify.sh` default includes people. GitHub `main` is not protected (404, empty rulesets). |
| Platform `PL-SSE-01` | **Configured** — staff route `/admin/assurance` and `GET /assurance/stream/`. It reads a ledger. It does not run pytest. |
| PAM / bank WPS acknowledgement | **Not wired** — local submit keeps `reconciled=False` |
| Nationality / Kuwaitization on live GOFSCO rows | Blank nationality now **refuses** Kuwaiti-scoped EOSI/leave. Do not invent codes. |

## What was closed on this pass

1. **One basic authority (ADR-0029 / NR-EOSI-01).** EOSI and leave-accrual refuse `Employee.basic_salary`. They use `CompensationService.verified_basic_amount`. Missing ledger → HTTP 409. Payroll already did this.
2. **WPS honesty (NR-WPS-02).** Submit stamps `LOCAL-WPS-*` and leaves `reconciled=False`. A local flag is not a PAM receipt.
3. **Payroll commit retry (NR-PAY-03).** `select_for_update`; a second commit on an already-committed run returns `idempotent: true`.
4. **Staff-facing copy.** My leave remaining / pending reserved; payslip source; People SoD and WPS banners; EOSI says ledger, not profile.
5. **Chat (ADR-0046 / NR-AI-01 / G2).** Chat must not stage host writes. Pulse change stays Agent + RULE_21, or My / Team / People.
6. **One active payroll period (NR-PAY-04).** Create and compute refuse a second draft/computed/validated/committed run for the same org and dates. Failed runs may be superseded. Historical duplicates were not deleted.
7. **Nationality fail-closed (NR-NAT-01).** Kuwaiti-only leave propagation requires a nationality FK. EOSI/leave-accrual refuse HTTP 409 when a `*kuwaiti*` rule exists and nationality is blank. Seed code `KWT` selects the Kuwaiti rule.
8. **Employee 360 (NR-360-01).** Opening a profile loads that employee and `?employee=` lists. The full directory loads only for edit pickers.
9. **Pack widened.** GOSI bands from the rule (NR-GOSI-01). Hire onboard leaves opening basic unverified (NR-ONB-01). Payroll prefers persisted loan installments (NR-LOAN-01).
10. **Local gate (PL-VERIFY-01).** `verify.sh` default pytest set is `ai dq accounts people`.

## Live two-actor payroll (observed)

Org **QA Payroll Leaf**. Period **2026-09-01 … 2026-09-30**. Run **#29**.

| Step | Actor | Result |
|---|---|---|
| Compute | `emp_2400` Abdullah AlHajri | `computed`, 1 employee, 3 lines |
| Validate | `emp_2400` | `validated`, net/lineage/reconcilation passed |
| Commit | `emp_2400` (same actor) | **refused** `sod_same_actor` |
| Commit | `admin` (distinct) | `committed` |
| Commit again | `admin` | `idempotent: true` |

Payslip lines for employee `9091701`: gross 850.500, GOSI 140.333, net 803.722.

## Demo accounts (tomorrow)

Password for all `emp_*`: `mozafNibrasPa_132`.

| App | Person | Login | Show |
|---|---|---|---|
| **My** | Bilagot Panta Suerte | `emp_1067` | Coiled Tubing; manager Mohammad Bolto Ali; pending leave reserved; payslip honesty |
| **Team** | Mohammad Bolto Ali | `emp_1712` | Directory 1 of 1 = 1067; inbox includes leave `CRS-2026-0087` |
| **People** | Abdullah Mubarak Rashed AlHajri | `emp_2400` | Payroll run #29 committed; SoD banner; WPS is not a PAM receipt; EOSI on 1067 uses ledger |
| Brand admin (second payroll actor only) | — | `admin` / `AdmNibras_132` | Commit only. Not the HR staff story. |

Do **not** use Chat to submit leave or payroll.

## Residuals (say these out loud)

- WPS file download / `LOCAL-WPS-*` is Carbon output. **No PAM or bank receipt.**
- Historical runs may show **Prepared by —**. Commit still fail-closes if preparer is missing.
- Live nationality is often empty. Those rows now **refuse** Kuwaiti-scoped EOSI/leave instead of guessing.
- Employee 360 and People lists no longer download the full roster to label a row. The directory asks the server for one page at a time and keeps search and filters on that request. The grid footer moves to the next page. Pickers search 20 matches.
- Two active runs for the same org/month are refused in create/compute, and the database has the same unique rule for a clean database. nibras_dev still has duplicate committed runs (Maintenance Department 2027-01, runs 22–28; QA Payroll Leaf 2026-09, runs 17 and 29). Those rows were not deleted, so that database does not have the constraint yet.
- Payroll **Prepared by** shows the username when compute recorded one, and a dash when it did not. The dash is not a name. Old runs were not given a preparer. Commit stays closed when the stamp is missing.
- GitHub `ahmedse/carbon` `main` was read on 23 Sep 2026. Branch protection returned 404. Rulesets were empty. A merge is not blocked by GitHub.
- The assurance board is a staff page. It is not a PAM receipt and it does not run the test suite.
- GOSI/EOSI **formula rates** are data. This certificate does not attest PIFSS or KLL amounts.

## How to regenerate evidence

```bash
.venv/bin/python -m assurance probe --pack nibras --commit <sha> --ledger docs/assurance/evidence/nibras-demo-2026-09-23.jsonl
.venv/bin/python -m assurance report --pack nibras --commit <sha> --ledger docs/assurance/evidence/nibras-demo-2026-09-23.jsonl
```

A row is `passed` only when a probe or host test wrote `passed` for that rule on the named commit.
