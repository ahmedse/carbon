# Data Migration Studio — Production Rollout Contract

**Status:** Proposed for Master sign-off · 2026-09-29  
**Subject:** `platform.module.inbound` (ADR-0060 Accepted · ADR-0051)  
**Product:** Data Migration Studio · Django app `inbound`  
**Canvases (one reading):** `data-migration-studio` Status · `dms-production-rollout` Status / Coverage / Ladder  
**Scored excellence today:** L4 Proven · coverage 45/54 declared (not a pass-rate). Rank 5 Operated is unmet. L6 is not defined.

This document defines principles, rules, benchmarks, coverage, and the excellence plan for **telling operators to work** on Import. It is not a new product slice. No cartridge, door, or screen is opened by this plan.

---

## Complete system — when we may say it is working fine

Three bars. Do not mix them.

| Bar | Says | Exit | Today |
|-----|------|------|-------|
| **Product** | The pipe and doors exist | DMS-0–DMS-8 + ADR-0060 | **DONE** |
| **Pilot** | Operators may run a capped CSV | P0–P3 signed · People `reject=0` · brief 2378/2400 | **UNSIGNED** |
| **Complete system** | Excellence Operated | L5 ledgered · all nine rank-5 probes `enforcement-verified` | **UNMET · stay L4** |

**Working fine** for this subject means the third bar only: L5 Operated in the ledger.

| Level | Name | Floor | This subject | Working fine? |
|-------|------|-------|--------------|---------------|
| L1 | Specified | configured | Pipe + studio doc + ADR-0060 | No |
| L2 | Instrumented | configured | Caps, doors, collector registered | No |
| L3 | Exercised | executed | pytest inbound + People-door once | No |
| L4 | Proven | executed | Scored 45/54. Nine dimensions Proven | Product proven. Not operated. |
| L5 | Operated | enforcement-verified | Green full `ci.yml` + named runner + nightly | **Yes — this is the bar** |
| L6+ | — | not defined | Not claimed | Not a bar |

Coverage **45/54** = 9 dimensions × levels 1–6, with ranks 1–5 declared (45 cells) and nine L6 cells open. It is a declaration count. It is not L5.

Still open before L5:

| Lane | Probes | Benchmark | Status |
|------|--------|-----------|--------|
| A · CI | SEC-06 · GOV-05 · MNT-05 | `ci.yml` conclusion success on the scored commit. Full pytest. No path / `-k` / `-m` / `--deselect` / `--ignore` inbound | `7bf9d6be` run `36613144123`: phase1-enterprise 27/27 after the :8000 fix. Workflow still **failure** — pilot-governance login **429** because `DJANGO_ENV=ci` used the production `5/minute` login throttle. Production stays 5/minute. Not L5 until a later SHA is green |
| B · Nightly | COR-05 · REL-06 | Named runner that already has the stack. `inbound-nightly.yml`. `ubuntu-latest` rejected. COR needs `headSha` | DEFINED-UNMET · runners 0 · Pulse `pulse-nightly-ess.yml` schedule greens do not count |
| C · In-process | SPC-11 · PRF-06 · USE-06 · OBS-05 | Passed once on `81cbea62`. Not ledger events | PASSED ONCE · does not raise the subject |

Rejected as working-fine: DMS-0–8 done, Pilot signed, jobs/observe/health/DQ Ready, health p95, leave-charts G5 local, PASSED ONCE cells, Pulse night `2026-09-23`.

---

## Honest gate (read first)

| Claim | Allowed when | Forbidden when |
|-------|--------------|----------------|
| **Pilot go-live** — named preparers and committers may load CSV on a named brand/environment | Master signs this contract; SoD roles exist; doors load; smoke ≠ write; reject path works; backup/rollback named | Claiming L5; claiming “working fine”; claiming five-night soak; inventing a runner |
| **Complete system working fine (L5)** | Every rank-1..5 check on every dimension is enforcement-verified, including green full `ci.yml` and a scheduled People-door nightly on a named stack runner | Treating PASSED ONCE in-process as ledger L5; `ubuntu-latest` nightly; health p95 as inbound SLO |
| **Users “just use Import”** | After Pilot gate + operator briefing + first supervised batch | Before SoD training; before first smoke on a real file; Chat as the commit path |

DMS-0 through DMS-8 are **DONE**. Remaining work is evidence, ops naming, and operator enablement — not another Wizard rewrite.

---

## Principles (12)

1. **Two kinds, one receive path.** `typed_object` and `data_product` never share a mapper. `inbound` does not import `people`, `emissions`, or `gradevance`.
2. **Prepare is not commit.** Non-superuser preparer cannot commit their own batch. Caps: `inbound:prepare`, `inbound:commit`.
3. **Server parse is the job of record.** Browser preview is a sample. CSV only in v1. Encoding is chosen on Upload.
4. **Smoke is zero live writes.** Commit is the only live write. Reject counts with `allow_partial=false` block commit.
5. **Chat does not commit** (ADR-0046). No Agent write tool for inbound in this rollout.
6. **Doors stay in the owning app.** People `/people/import` · Catalog `/catalog/imports`. No `/migrate`. No new Activity Bar studio. No Import on My/Team.
7. **UI primitives are mandatory.** `PageContainer`, `PageHeader`, `FilteredDataGrid`, `Wizard`, `SearchSelect`, `FormField`+`TextField`, `CsvDropzone`, `ConfirmDialog`/`SystemDialog`. Row click highlights only; eye opens the record. No raw MUI Table as the list. No raw `<Select>` for targets.
8. **A missing artifact is `unknown`, never a pass.** Nightly absent → COR/REL unknown. Red `ci.yml` → SEC/GOV/MNT fail. Untracked smoke series is allowed; a git-tracked series fails OBS-05.
9. **Unmeasured is not a benchmark.** Health latency is not the pipe. Sample cap ≤20 is the v1 performance claim.
10. **Dev credentials are not production secrets.** Prod uses env (`CARBON_ADMIN_PASSWORD`, `NIBRAS_ADMIN_PASSWORD`, `EMPLOYEE_DEFAULT_PASSWORD`, …). Dev table (`ahmed`/`AdminPa_132`, …) is local only.
11. **Excellence level is the weakest dimension** (ADR-0051). Rank N requires ranks 1..N. Rank 5 requires evidence class `enforcement-verified`.
12. **Pilot go-live and L5 are different gates.** Operators may work under Pilot without claiming Operated. Narrowing SEC/GOV/MNT to inbound-only tests would be a different rule — do not rewrite the probe to buy a green cell.

---

## Rules (operator + platform)

### Roles (Nibras People door)

| Role | Persona (dev known) | Cap | May |
|------|---------------------|-----|-----|
| Preparer | HR Manager `emp_2378` | `inbound:prepare` (+ People access) | Upload, map, smoke, download rejects. Not commit own batch (SoD) |
| Committer | People lead `emp_2400` | `inbound:commit` | Commit a smoked batch prepared by someone else |
| Both | Platform superuser `ahmed` | superuser | Prepare and commit. Exception to SoD |
| Forbidden | ESS `emp_1067` / My / Team | — | Never see Import |

Catalog door: steward with Catalog ingest / `datahub` caps. `people:manage` alone cannot create `data_product` batches (403).

### Flow (must)

1. List → New import → SearchSelect target → Upload CSV → Map → Smoke → (other user) Commit via ConfirmDialog.
2. After commit: list shows Committed; reopen is read-only for that batch’s write path.
3. Remap after reject: fix file or map; smoke again. No automatic retry.
4. Arabic: logged-in language is `User.language` (`accounts/me/context/`). `carbon.lang` is pre-login only.

### Flow (must not)

- Row click opening the studio (eye only).
- Browser PapaParse as commit path.
- Excel / xlsx.
- Payroll / YTD cartridges in this rollout.
- Pulse Chat Confirm for load commit.
- Starting or killing `manage.sh` as part of a gauge or nightly that claims L5.

---

## Benchmarks (named, fail-closed)

### Product suites (already the DMS test plan)

| Id | Suite | Proves |
|----|-------|--------|
| DMS-COR-PIPE | `backend/inbound/tests/test_pipe.py` | Parse, 400/403/409 modes, SoD, template |
| DMS-COR-BOUND | `backend/inbound/tests/test_boundary.py` | No people/emissions/gradevance import |
| DMS-COR-PRODUCT | `backend/inbound/tests/test_data_product_adapter.py` | Smoke 0 DataRow; product commit; people:manage 403 |
| DMS-COR-LEAVE | `backend/people/tests/test_inbound_cartridges.py` | Opening balance / history; history does not increment used_days |
| DMS-COR-CART | `backend/inbound/tests/test_cartridges.py` | Declaration, unbound refuse, retrieve count |
| DMS-OBS-04 | `backend/inbound/tests/test_observe_series.py` | Series matches stored smoke envelope |
| DMS-USE-04 | `journey-dms-people-door.spec.ts` | emp_2378 list; eye opens; row click stays |

### Rank-5 operated probes (L5)

| Probe | Pass condition | Current honest status |
|-------|----------------|----------------------|
| INBOUND-SPC-11 | Code diff same merge as studio doc or ADR-0060 | PASSED ONCE (in process) |
| INBOUND-COR-05 | Scheduled `inbound-nightly.yml` success, `headSha` = this commit | DEFINED-UNMET (file absent; runners 0) |
| INBOUND-SEC-06 | Full `ci.yml` success; named 403 defs in suite | FAILED ONCE until green conclusion |
| INBOUND-REL-06 | One schedule+success of that nightly, any commit | DEFINED-UNMET |
| INBOUND-PRF-06 | Live smoked/committed batch sample length ≤20 | PASSED ONCE |
| INBOUND-USE-06 | i18n:check + Arabic People-door spec, dir rtl | PASSED ONCE |
| INBOUND-MNT-05 | Ratchet step script substrings; green ci job | FAILED ONCE until green conclusion |
| INBOUND-OBS-05 | Untracked series ≤14d matching `InboundBatch.smoke` | PASSED ONCE |
| INBOUND-GOV-05 | Boundary def in full suite; green ci.yml | FAILED ONCE until green conclusion |

### Rejected as inbound benchmarks

`PLAT-PRF-05` health p95 · `PLAT-REL-05` health error rate · `PLAT-SEC-05` 429 rate · `PLAT-OBS-02` migrations folder · Pulse five-night streak · `ubuntu-latest` for People-door nightly.

---

## Coverage (denominator)

Excellence grid for `platform.module.inbound`: **9 dimensions × levels 1..6 = 54** applicable cells (`assurance/standard` module grid). **45/54** means ranks **1–5 are declared** on every dimension; the **nine L6 cells stay open** (Rank 6 is not defined for inbound — do not invent it). Coverage is **declaration**, not pass-rate. Scored product level stays **L4 Proven** until rank-5 ledger events all satisfy with evidence class `enforcement-verified`. In-process PASSED ONCE / FAILED ONCE cells are not ledger Met.

Inherited platform L5 probes (`PLAT-PRF-05` health p95, `PLAT-REL-05`, `PLAT-SEC-05`, `PLAT-OBS-02` migrations) may appear on the subject grid but are **rejected** as inbound benchmarks (see Rejected table above).

| Dimension | L1–L4 | L5 probe | L5 honest status | L6 |
|-----------|-------|----------|------------------|-----|
| specified | Met (scored L4) | INBOUND-SPC-11 | PASSED ONCE · not ledger | open |
| correct | Met | INBOUND-COR-05 | DEFINED-UNMET (nightly absent) | open |
| secure | Met | INBOUND-SEC-06 | FAILED ONCE (ci.yml) | open |
| reliable | Met | INBOUND-REL-06 | DEFINED-UNMET | open |
| performant | Met | INBOUND-PRF-06 | PASSED ONCE · not ledger | open |
| usable | Met | INBOUND-USE-06 | PASSED ONCE · not ledger | open |
| maintainable | Met | INBOUND-MNT-05 | FAILED ONCE (ci.yml) | open |
| observed | Met | INBOUND-OBS-05 | PASSED ONCE · not ledger | open |
| governed | Met | INBOUND-GOV-05 | FAILED ONCE (ci.yml) | open |

**Actualization coverage** (operator lanes — separate from excellence cells):

| Lane | Pilot gate | Evidence |
|------|------------|----------|
| Business process | Prepare → smoke → other-user commit on real CSV | Supervised batch id recorded |
| Product capability | Both doors ship; three People cartridges + product kind | DMS-0–8 DONE |
| Setup | Caps granted; cartridges bound; brand DB | `ensure_*` / role matrix |
| Data readiness | Source CSV encoding known; natural keys present | Smoke reject=0 or allow_partial explicit |
| Access & controls | SoD 403 on same-user commit; Import hidden on My/Team | Named tests + live check |
| Integration | Catalog product uses ImportService; People typed services | Adapter tests |
| Adoption | Briefing complete; first cycle owners named | Checklist below |

### Cite or extend (no duplicate runbook)

| Path | Use |
|------|-----|
| ADR-0060 · `DATA-MIGRATION-STUDIO.md` · `SCREEN-SPEC-DMS.md` | Product + UI + failure modes |
| `docs/ops/MASTERS-COMMS.md` | Master decision trail |
| ADR-0025 · `STORAGE-PATTERN-HOSTED-APPS.md` | People ≠ Data Product |
| `GOFSCO-ONBOARDING-RUNBOOK.md` · `NSR-9-go-live-gate.md` | Adjacent staff go-live pattern — not DMS Studio |
| `DEV-CREDENTIALS.md` · env vars | DEV rehearsal only · prod prefers env |

This file is the DMS production rollout / enablement runbook that was missing.

---

## Backup, rollback, allow_partial

| Topic | Rule | Benchmark / evidence |
|-------|------|----------------------|
| **Backup before first Pilot commit** | Named DB backup (or restore point) owned by Ops; date recorded on P1 | P1.4 exit; no commit without owner |
| **Batch file retention** | Original CSV hangs on the batch (hash + encoding); not a Data Product; not `evidence.Evidence` | Studio doc Retention |
| **Rollback typed (People)** | Bad commit is a **data** problem: correct with a new CSV + cartridge (snapshot upsert / leave rows). No silent un-commit button in v1 | Domain service + GovernanceEvent trail |
| **Rollback product (Catalog)** | Bad `DataRow` load: steward corrects via Catalog / new import; do not use People door | Kind locked by door |
| **`allow_partial`** | Default **false**. Only Master or named committer may set true when reject>0 and residual rejects are accepted in writing | Commit 400 when reject>0 and flag false |
| **Reject CSV loop** | Download rejects → fix source or map → smoke again. No automatic retry | Failure modes table |

### Failure matrix (operator)

| Condition | Result | Operator action |
|-----------|--------|-----------------|
| Unknown `target_key` | 400 · batch not created | Pick a bound cartridge |
| Required field unmapped | 400 · stays draft | Complete map |
| Smoke before map | 409 | Map first |
| Commit before smoke | 409 | Smoke first |
| Non-superuser commits own batch | 403 · stays smoked | Other user commits |
| `people:manage` on `data_product` | 403 | Use Catalog door / steward |
| Rejects remain · `allow_partial` false | 400 · stays smoked | Fix file or get Master OK for partial |

---

## Training checklist (day-1 · 10 items)

1. Find **People → Configuration → Import** (not My/Team, not Chat).
2. Know your role: prepare **or** commit (not one shared login).
3. CSV only; pick encoding; server parse is the job of record.
4. SearchSelect the cartridge; never invent payroll/YTD in this phase.
5. Map every required field; smoke must run before commit.
6. Read smoke counts; download reject CSV if reject>0.
7. Eye opens the batch; row click only highlights.
8. Committer uses ConfirmDialog; preparer does not force SoD.
9. Catalog Imports is a different kind — People owners do not create product batches.
10. Escalate stop conditions (smoke wrote live rows, Chat Confirm, Excel, Import on My).

---

## Excellence ladder (this subject)

| Level | Name | Floor | Inbound today | Rollout meaning |
|-------|------|-------|---------------|-----------------|
| L1 | Specified | configured | Met | Spec + ADR exist |
| L2 | Instrumented | configured | Met | Caps, registry, collector registered |
| L3 | Exercised | executed | Met | pytest + journeys run |
| L4 | Proven | executed | **Scored** | All nine dimensions Proven · 45/54 |
| L5 | Operated | enforcement-verified | **Unmet** | Green full ci.yml + named-runner nightly |
| L6+ | — | not defined for this subject | Not claimed | Do not invent |

**Pilot enablement rung** (not an excellence level): Master sign-off + operator briefing + supervised first batch. May precede L5. Must not be labeled “L5” or “Excellent.”

---

## Waves to tell users to work

| Wave | Name | Who works | Exit |
|------|------|-----------|------|
| P0 | Contract freeze | Master | This doc + canvas signed; do-nots acknowledged |
| P1 | Environment | Ops | Brand DB, HTTPS, env secrets, backups, restore drill named |
| P2 | Access | Ops + HR lead | Caps on preparer/committer; Import visible only where allowed; ESS cannot see door |
| P3 | Dry run | Preparer + Committer | One non-prod or supervised prod smoke+commit of a small real CSV; reject path exercised |
| P4 | Pilot open | Named users only | Users told: work on People Import / Catalog Imports per briefing; support channel named |
| P5 | Excellence L5 | Platform | (A) green full `ci.yml` on scored commit · (B) runner named · nightly file · one schedule success — then rescored gauge (ledger write is Master/CI, not ad-hoc agent `--write`) |

### P1 environment checklist (Ops exit)

| # | Check | Pass evidence | Fail if |
|---|-------|---------------|---------|
| P1.1 | Brand is the intended production brand | `manage.sh brand <id>` recorded; DB name known | Guessing brand from local nibras_dev alone |
| P1.2 | App reachable on production URL over HTTPS | Health `GET /carbon-api/health/` 200 on that host | Using health p95 as an inbound SLO |
| P1.3 | Secrets from env, not committed defaults | `CARBON_ADMIN_PASSWORD`, brand admin, employee default, FERNET/TURNKEY as required by deploy | Shipping `AdminPa_132` as the prod password |
| P1.4 | Backup + restore named | Owner, schedule, last successful restore drill date | “We have snapshots somewhere” |
| P1.5 | Cartridges bound on that brand | People three keys registered; Catalog tables intended for product loads listed | Unbound key receiving a batch |
| P1.6 | Support channel named | Chat/email/ticket for Pilot | Silent failures |

### P2 access checklist

| # | Check | Pass evidence |
|---|-------|---------------|
| P2.1 | Preparer has `inbound:prepare` and People access | Login as preparer → Import visible |
| P2.2 | Committer has `inbound:commit` | Commit step visible on smoked batch they did not prepare |
| P2.3 | Same-user commit 403 for non-superuser | Attempted live or covered by `test_same_user_commit_403` + live smoke |
| P2.4 | `emp_*` ESS without caps cannot open Import | My/Team have no Import item; direct URL 403/redirect |
| P2.5 | Catalog steward cannot be confused with People SoD | Product kind 403 for `people:manage` alone |

### P3 dry-run checklist

| # | Check | Pass evidence |
|---|-------|---------------|
| P3.1 | Small real CSV through Upload → Map → Smoke | Batch id · status smoked · sample ≤20 |
| P3.2 | Reject path | Force one bad row · download reject · remap · smoke again |
| P3.3 | Other-user commit | Committer confirms ConfirmDialog · status committed |
| P3.4 | Reopen read-only | Eye opens committed batch · no silent re-write |
| P3.5 | Record | Batch id + who prepared + who committed in Pilot log |

**Stop conditions:** same-user commit succeeds for non-superuser; smoke writes live rows; Chat offers Confirm for commit; Excel accepted as job of record; Import appears on My/Team.

---

## Operator briefing (copy for users)

**People (typed):** Configuration → Import. Upload CSV. Map. Smoke. A different person commits. Eye opens a batch; clicking the row only highlights it. Download rejects if smoke reports them. Fix file or map; smoke again.

**Catalog (product):** Catalog Studio → Imports. Same chrome; targets are DataTables. People owners cannot create product batches.

**Do not:** ask Chat to commit a load; upload Excel; expect payroll YTD in this phase; share one login for prepare and commit.

---

## Hard do-nots (toolkit)

- No `/migrate` · no new `PLATFORM_STUDIOS` entry · no BulkImportWizard rewrite as the studio.
- No commit of `docs/migration/evidence/inbound-smoke-series.json`.
- No `inbound-nightly.yml` on `ubuntu-latest`.
- No inventing GitHub runners.
- No loosening YAML goldens or granting `people:view` to `emp_1067` to buy CI green for other tracks.
- No claiming L6/L7 or five-night soak for inbound.
- Agent must not `--write` excellence ledger except existing CI ratchet path.

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Master Architect (Nibras) | | | Pilot P0–P4 / Hold |
| Ops | | | Environment P1 ready / Hold |
| HR lead (committer) | | | Briefing accepted / Hold |

Until Master signs Pilot, do not broadcast “production open” to the full user base.

---

## Ops readiness — Jobs · Observability · Health · DQ

Master scoreboard for “what it takes to be ready.” Product DMS-0–8 is done. These four lenses decide Pilot honesty and L5 later.

### Jobs

| Job / command | Mode | Trigger | Exists | Prod ready? |
|---------------|------|---------|--------|-------------|
| Upload / parse CSV | Sync HTTP | POST file | Yes | Yes for v1 (sample ≤20) |
| Smoke | Sync HTTP | POST `…/smoke/` | Yes | Yes · zero live writes |
| Commit | Sync HTTP | POST `…/commit/` | Yes | Yes · SoD · large-file timeout + People row-by-row partial-write risk |
| ImportJob (product) | Sync inside commit | `data_product` commit | Yes | Not a queue worker |
| `write_inbound_smoke_series` | Management command | Ops / OBS-05 | Yes | Manual · **no cron** · file untracked |
| `inbound-nightly.yml` | Scheduled GH | cron `30 3 * * *` | **Missing** | Blocked · runners 0 · no `ubuntu-latest` · no `manage.sh` |
| Celery / RQ / async parse | Background | — | **No** (out of v1 budget) | Not a Pilot exit · L5 blocked by nightly first, not by Celery |
| Retention / purge batch files | Scheduled | — | **No** | Policy only (file on batch) · name owner before long Pilot |

**Principle:** v1 is a synchronous pipe. Smoke and commit each re-parse the full CSV in-process. An async queue is a later Master track. Document a max row count for Pilot sync commits.

### Observability

| Signal | Exists | Prod gap | Ready when |
|--------|--------|----------|------------|
| Smoke envelope on `InboundBatch.smoke` | Yes | No ops dashboard | Operator reads Smoke step |
| Reject CSV | Yes | — | P3 dry-run |
| `GovernanceEvent` on People commit | Yes | No alert on emit failure | Support can query by `batch_id` |
| `ImportJob` on Catalog commit | Yes | — | Steward opens job |
| Smoke series JSON | Yes · untracked | Must not be committed | Ops runs command ≤14d |
| `inbound_operated` collector | Yes · fail-closed | L5 unmet | Green ci.yml + nightly |
| Inbound Prometheus / alerts | No | No smoke/commit series | Optional · not Pilot blocker |
| Batch-scoped request correlator | Weak | Incident logs may lack `batch_id` | Gap for support |

### Health

| Check | Proves | Inbound claim? |
|-------|--------|----------------|
| `GET /carbon-api/health/` | DB · Redis · disk · backup hint | **Platform up only** — not the pipe |
| `PLAT-PRF-05` health p95 | Latency on health URL | **Rejected** as inbound SLO |
| Preparer opens `/people/import` | Route + cap + chrome | **Yes** — door readiness |
| Smoke returns envelope | Cartridge + parse live | **Yes** — pipe readiness |
| Live batch `sample` length ≤20 | PRF-06 | **Yes** when stack up |

Do not put health p95 on the inbound excellence ladder.

### DQ

| Layer | Exists | Honest meaning |
|-------|--------|----------------|
| Required-field map gate | Yes | 400 until mapped |
| People cartridge smoke | Yes · **hand-rolled** | Org/ref/salary/employee → `reject_rows`. **ADR-0060 said `dq.typed_gate`; code does not call it** (drift — claim load gate, not typed_gate, until fixed or ADR amended) |
| Leave cartridge smoke | Yes | Employee + leave_type + entitled; history does not bump `used_days` |
| Catalog smoke | Yes | `dataschema.validate_row` (not typed_gate) |
| Reject CSV + `allow_partial` | Yes | Default false · Master OK if partial |
| Product commit skips `reject_rows` | Yes | `reject_idx` in adapter |
| People commit skips `reject_rows` | **Weak** | Skips incomplete rows; does **not** index smoke `reject_rows`. Pilot rule: **reject=0** before commit (or written allow_partial) |
| Post-commit DQ / re-profile job | **No** | Smoke is the **load gate**, not the enterprise DQ suite |

**Principle:** Claiming “full DQ platform via Import” or “typed_gate on smoke” is false today. Claiming “smoke blocks dirty commits when reject=0 / allow_partial false” is true.

### Observability extras (audit 9914c6f1)

- Prepare/smoke emit **no** GovernanceEvent — audit who smoked via `prepared_by` / batch status, not GE.
- Catalog product commit emits **ImportJob**, not GE.
- Only coarse HTTP metrics (`app=inbound`); no smoke/commit outcome counters or alerts.
