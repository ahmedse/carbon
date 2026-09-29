# Data Migration Studio

**Status:** Accepted · ADR-0060 · Track DMS  
**Product name:** Data Migration Studio  
**Django app:** `inbound` (core; installed)  
**Routes:** `/people/import` (typed) · `/catalog/imports` (Data Product, already in nav)  
**Not:** a new Activity Bar studio · `importexport` renamed · My/Team menu items

## What it is

A file-to-system-of-record studio. HR or a steward uploads CSV, maps it, smoke-tests
it, then commits. The last step is one of two kinds:

| Kind | Target | After commit | Adapter owner |
|------|--------|--------------|---------------|
| `data_product` | `Module` + `DataTable` | `DataRow` (and optional Dataset version) | Catalog |
| `typed_object` | Named cartridge | Typed Django row + `GovernanceEvent` | Hosted app (People first) |

These are different stores. The studio chrome is shared. The mapper and the commit
are not.

## Why not the existing scraps

| Scrap | What it actually does |
|-------|------------------------|
| `importexport.ImportJob` | File → `DataTable` in one request. No saved template, no smoke, no SoD. |
| `BulkImportWizard` | Browser PapaParse + fuzzy header map onto `DataField`. |
| `import_gofsco_employees` | Dev command for one August 2026 workbook. No manager, no hire date. |

Keep all three. Do not grow them into the studio.

## Pipe (domain-free)

`inbound` knows: bytes, SHA-256, encoding (utf-8, windows-1256, cp1252), delimiter,
header row, saved **Template** (source column → target field + value crosswalk),
**Batch** (file + template + kind + target id), staged projections (JSON, not
`DataRow`), smoke verdict (insert/update/skip/reject counts + sample), reject CSV,
reconcile totals, prepare vs commit.

`inbound` does not know: leave, employee, GOSI, Module.scope, GOFSCO.

Registration (same direction as `dq.ModelRuleAssignment`):

```
inbound.registry.register(
    kind="typed_object",
    key="people.employee_snapshot",
    label=...,
    fields=[...],           # declared, not _meta
    natural_key=...,
    smoke=callable,         # returns envelope; zero writes
    commit=callable,        # domain service
)
```

Hosted apps import `inbound`. `inbound` never imports `people` / `emissions` / `gradevance`.

## Typed cartridges (Nibras v1)

| Key | Natural key | Commit meaning |
|-----|-------------|----------------|
| `people.employee_snapshot` | `employee_no` | Upsert current employee. Manager is a **second pass** after all rows exist. |
| `people.leave_opening_balance` | employee + year + leave_type + as_of | Sets entitlement / used / carried. That number is the balance. |
| `people.leave_history` | employee + leave_type + start + end | Already-decided history. No manager notify. Must not increment `used_days`. |

Payroll history and YTD are out of v1.

## Data Product adapter (Catalog)

Kind `data_product` calls today's `ImportService` / `BulkImportService`. Mapping
target is `DataField`. Smoke is parse + required fields + type. Optional later:
publish a `DatasetVersion` of the same table (source contract). That publication
is not an HR commit.

PII (civil id, salary) must not be the reason to choose this kind. If Nibras owns
the record, use a typed cartridge.

## Security

| Cap | Meaning |
|-----|---------|
| `inbound:prepare` | Upload, map, smoke, download rejects. No live write. |
| `inbound:commit` | Commit a smoked batch. |
| existing | `people:manage` still required for People cartridges; Catalog ingest caps still required for Data Product targets. |

SoD: preparer ≠ committer on typed People loads (NPS-1 family). `ahmed` may both.
`emp_2378` prepares. `emp_2400` commits.

Chat does not commit (ADR-0046). File parse is **server-side**. Browser preview is
a sample, not the job of record.

## Where it sits (menus)

No new `PLATFORM_STUDIOS` entry. No `/migrate` prefix.

| Who | Activity Bar | Sidebar | Route | Kind locked |
|-----|--------------|---------|-------|-------------|
| `emp_2378` / `emp_2400` | **People** | Configuration → **Import** | `/people/import` | `typed_object` only |
| Catalog steward | **Catalog Studio** | Connect & move → **Imports** (already there) | `/catalog/imports` | `data_product` only |

My / Team / Pulse: no Import item. Command palette: "People · Import" and existing Catalog Imports.

## Instance view

- **Nibras:** People door for cartridges. Catalog Imports only if a measurement table is in play (attendance device later).
- **AASTMT Data Trust:** Catalog Imports is the door. People app may be off.
- **EduOS:** no cartridge until a later track.

## Retention

The original file hangs off the batch (hash + encoding). It is not a Data Product
and not `evidence.Evidence` (that model FKs `DataRow`). After commit, the typed
row (or `DataRow` for kind A) is the live data. Batch + file are audit.

## Out of scope (v1)

Excel/xlsx (CSV only). Direct DB/API pull. Pulse Agent commit. Payroll load.
Generic ORM field map. Dataset Hub as the employee store.

## Test plan

Suites that exist. A row is not a plan until the named test fails when the rule breaks.

| Id | Suite | Proves |
|----|--------|--------|
| DMS-COR-PIPE | `backend/inbound/tests/test_pipe.py` | Parse, unknown target 400, unmapped required blocks smoke, commit-before-smoke 409, same-user commit 403, two-person commit, template round-trip |
| DMS-REL-03 | `backend/inbound/tests/test_pipe.py` | After an unmapped required field returns 400, a corrected map still smokes. There is no automatic retry. |
| DMS-PRF-03 | `backend/inbound/tests/test_pipe.py` | 25 data rows keep `row_count` 25 and a sample of 20 |
| DMS-COR-BOUND | `backend/inbound/tests/test_boundary.py` | `inbound` does not import `people`, `emissions`, or `gradevance` |
| DMS-COR-PRODUCT | `backend/inbound/tests/test_data_product_adapter.py` | Smoke writes 0 `DataRow`; commit writes projected rows and an `ImportJob`; `people:manage` cannot create a product batch |
| DMS-COR-LEAVE | `backend/people/tests/test_inbound_cartridges.py` | Opening balance and history cartridges; history does not increment `used_days` |
| DMS-COR-CART | `backend/inbound/tests/test_cartridges.py` | Studio declaration. Unbound key cannot receive a batch. A bound handler cannot be deleted. A studio label survives the next `register()`. Retrieve lists the batches for that key. The list stays a count. |
| DMS-OBS-04 | `backend/inbound/tests/test_observe_series.py` | Writer reads the smoke envelope already stored on the batch and writes a temp series. Counts are not typed into the file. |
| DMS-USE-04 | `carbon-frontend/e2e/journeys/journey-dms-people-door.spec.ts` | emp_2378 on `/people/import`. Row click stays on the list. Eye opens batch 6, Leave history, Committed. |

## Capabilities and roles

| Cap | Who gets it | What it allows |
|-----|-------------|----------------|
| `inbound:prepare` | `people:manage`, `catalog:manage_products`, `datahub:ingest` | Create, upload, map, smoke. No live write. |
| `inbound:commit` | `people_lead` via `inbound:commit`, `datahub:manage` | Commit a smoked batch prepared by someone else. |
| `people:manage` | People data owners | `typed_object` only. Product targets return 403. |
| `catalog:manage_products` / `datahub:ingest` | Catalog steward | `data_product` prepare. |
| `datahub:manage` | `datahub_lead` | Product commit. |

`ahmed` is the platform superuser and may prepare and commit. Chat has no inbound commit tool (ADR-0046).

## Failure modes

| Condition | Result | Batch after |
|-----------|--------|-------------|
| Unknown `target_key` | 400 | not created |
| Required field unmapped | 400 | stays draft |
| Smoke before map | 409 | unchanged |
| Commit before smoke | 409 | unchanged |
| Non-superuser preparer commits their own batch | 403 | stays smoked |
| `people:manage` on `data_product` | 403 | not created |
| Rejects remain and `allow_partial` is false | 400 | stays smoked |

There is no automatic retry. The preparer fixes the file or the map and smokes again. A committed batch does not accept a new file.

## Budget

v1 budget, as implemented: one CSV per batch, parsed on the server (`utf-8`, `windows-1256`, `cp1252`). The smoke envelope keeps a sample of 20 rows. The browser does not parse the file. Excel, a row cap, and an async queue are not in this budget. Do not treat a missing number as a measured latency.

## Cartridge definition

The studio owns the declaration (`InboundCartridge`: key, labels, fields, enabled, owner app). People, and later any other hosted app, registers `smoke` and `commit` for that key from `AppConfig.ready()`. A declaration with no handler is visible here and refused as a batch target. Disabling a bound cartridge hides it from the door. Deleting a bound cartridge is refused. Data product targets stay Catalog tables, not rows in this list. The screen is Platform Admin → Cartridges (`/admin/migration/cartridges`), not a People page and not `/migrate`.

## Module boundary

`inbound` is core. It may import `dataschema` and `importexport`. It must not import `people`, `emissions`, or `gradevance`. Hosted apps import `inbound` and `register()` from `AppConfig.ready()`. `test_boundary.py` fails if a non-test module under `backend/inbound` imports `people`.

## Signal threshold

The commit signal is the smoke envelope. `reject > 0` refuses commit until `allow_partial` is set. `status != smoked` refuses commit. Those two thresholds are the v1 signal. A latency SLO is not declared because none is measured.

## Rank 5 contract (defined, not operated)

Inbound is L4 Proven (coverage 45/54, in memory, 2026-09-29, before `inbound_operated` events). Rank 5 is Operated. Nothing below is met. Collector `inbound_operated` is registered and fail-closed. A missing artifact stays unknown.

### Principles

1. Level N requires every check at ranks 1..N satisfied. The subject level is the minimum dimension (ADR-0051).
2. Rank 5 counts only with evidence class `enforcement-verified`. A file read is `executed` and does not meet the floor (`assurance/standard/standard.yaml`).
3. Two destination kinds, never one mapper (ADR-0060). `inbound` does not import `people`, `emissions`, or `gradevance`.
4. Prepare is not commit. A non-superuser preparer cannot commit their own batch.
5. A number that was not measured is not a benchmark. Health latency is not the pipe.
6. A missing artifact is `unknown`, never a pass. Browser locale is not the app language. Logged-in language is `User.language` (`accounts/me/context/`); `localStorage` key `carbon.lang` applies before login.
7. CI rank 5 is a green `ci.yml` run of full `python -m pytest` (no `--ignore` of inbound) on the scored commit, and each named node is a `def` in that suite. The collector does not re-run pytest. Reading the workflow file is not the pass. A workflow conclusion of `failure` is a fail even when the `Run tests` step was skipped. Unknown is only when `gh` returns no run.
8. The People-door nightly is a scheduled GitHub run for this commit. The collector does not run Playwright. `ubuntu-latest` is rejected because `CI=1` does not boot the stack, and no runner is named. Batch id 6 is the 2026-09-29 dev journey, not a rank-5 constant.
9. The ratchet step name is `Excellence ledger tests + changed-subject ratchet (ADR-0051)`. Pass requires the four substrings in that step's script (the two `excellence.gauge` lines, `github.event.pull_request.base.sha`, and `HEAD~1`). The shorthand `python -m excellence.gauge --gate --changed` as one contiguous string is a false fail. `--only` stays `repo,observe`.
10. Spec base is env `GITHUB_BASE_SHA`, else `HEAD~1`, compared with `git diff base...HEAD`. Git failure is unknown. A dirty working tree is outside that diff. `inbound_rtl` is a test seam. The collector does not write the series file.
11. `--no-db` cannot satisfy `INBOUND-OBS-05`. The series match needs `InboundBatch.smoke`. A gauge that skips Django setup records unknown, even when the JSON file exists. A git-tracked series file fails the probe.

### Rejected benchmarks

These probes apply to modules today and must not be treated as an inbound pass:

| Probe | Why it is not the inbound benchmark |
|-------|-------------------------------------|
| `PLAT-PRF-05` `GET /api/health/` p95 ≤ 500 ms, 8 samples | Wrong path (live prefix is `/carbon-api/`). No latency SLO is declared. A green window is a false L5. |
| `PLAT-REL-05` error rate ≤ 0.01 on that path | 404 is not an error in this probe. It does not run smoke, commit, or the failure modes above. |
| `PLAT-SEC-05` 429 rate ≤ 0.05 on that path | Does not exercise `inbound:prepare`, `inbound:commit`, or the 403 paths. |
| `PLAT-OBS-02` migrations package exists | `executed` evidence. Rank 5 rejects it. The observed signal is the smoke envelope, not the migrations folder. |

### Cells

| Dimension | Rule | Benchmark | Status |
|-----------|------|-----------|--------|
| specified | A change under `backend/inbound/**` or `carbon-frontend/src/components/inbound/**` is in the same merge as this file or ADR-0060 | Probe `INBOUND-SPC-11`. Base is env `GITHUB_BASE_SHA`, else `HEAD~1`. Diff is `base...HEAD`. Git failure → unknown. No code diff → pass. Code diff without those docs → fail. | DEFINED-UNMET |
| correct | The People-door journey is green on a scheduled inbound nightly for this commit | Probe `INBOUND-COR-05`. Workflow `.github/workflows/inbound-nightly.yml` (file absent). Cron `30 3 * * *`. The workflow `run` must contain `CI=1 npx playwright test e2e/journeys/journey-dms-people-door.spec.ts --config e2e/playwright.config.ts` and must not contain `manage.sh`. File absent → unknown. Wrong cron or command → fail. Pass: `gh run list` event `schedule`, conclusion `success`, `headSha` equals this commit. The collector does not run Playwright. `ubuntu-latest` is rejected. Batch id 6 is not a constant. | DEFINED-UNMET |
| secure | The named 403 tests are in the full pytest suite, and the `ci.yml` run for this commit succeeded | Probe `INBOUND-SEC-06`. Nodes `test_same_user_commit_403` and `test_people_owner_cannot_create_data_product` exist as `def` in the suite. Step `Run tests` contains `python -m pytest` and does not `--ignore` inbound. The collector does not re-run pytest. No GitHub run → unknown. A red run → fail. | DEFINED-UNMET |
| reliable | One scheduled GitHub run of the inbound nightly succeeded | Probe `INBOUND-REL-06`. Same workflow as `INBOUND-COR-05`. Event `schedule`, conclusion `success`, `runs: 1`. This probe does not require `headSha` (that is `INBOUND-COR-05`). No run → unknown. A schedule run that failed, with no success, → fail. Pulse's five-night streak is not this subject. | DEFINED-UNMET |
| performant | A live read of a smoked or committed batch keeps the sample cap | Probe `INBOUND-PRF-06`. Origin `CARBON_API_URL` or `http://127.0.0.1:8009`. Login `emp_2378` with `NIBRAS_HR_PASSWORD` or `EMPLOYEE_DEFAULT_PASSWORD` (the value is not in the ladder). List `GET /carbon-api/inbound/batches/?kind=typed_object`, highest id whose status is smoked or committed, then GET that id. Pass: `sample` is a list of length ≤ 20, `row_count` is an int, `target_key` is non-empty. No batch or server down → unknown. No `p95_ms`. | DEFINED-UNMET |
| usable | i18n parity, RTL on the People door, and the eye's accessible name | Probe `INBOUND-USE-06`. Spec `carbon-frontend/e2e/journeys/journey-dms-people-door-ar.spec.ts`. It does not click the row or the eye. Login `emp_2378`, `PATCH accounts/me/preferences/` `{language: ar}`, reload `/people/import`, poll until `dir` is `rtl` (server language wins over `carbon.lang`). Eye `فتح الدفعة`, primary `استيراد جديد`, search `بحث الدفعات`. Then `PATCH` `{language: en}` and reload until `Search batches` and `Open batch` are visible. The collector runs `npm run i18n:check` and that spec only when the gauge `--run` names the file, with `CI=1`, and it does not start the stack. `inbound_rtl` stays the unit-test seam. | DEFINED-UNMET |
| maintainable | The changed-subject ratchet fails the job if this subject's level drops | Probe `INBOUND-MNT-05`. Step name `Excellence ledger tests + changed-subject ratchet (ADR-0051)`. The script must contain `github.event.pull_request.base.sha`, `HEAD~1`, `python -m excellence.gauge --collect --only repo,observe --write --gate --changed`, and `python -m excellence.gauge --collect --only repo,observe --no-db --gate --changed`. `--only` is `repo,observe`. The contiguous shorthand `python -m excellence.gauge --gate --changed` is not the match. No GitHub run → unknown. A red run → fail. Citing the step is not the pass. | DEFINED-UNMET |
| observed | A series written by `write_smoke_series` is younger than 14 days and matches the stored envelopes | Probe `INBOUND-OBS-05`. Command `python manage.py write_inbound_smoke_series`. It selects status `smoked` or `committed`, `smoke` is a non-empty dict, order `-id`, limit 10. No such batch → the file is not created. Path `docs/migration/evidence/inbound-smoke-series.json` is not committed. A git-tracked file fails the probe. Schema `1`. Each row's counts equal `InboundBatch.smoke` for `batch_id`. Age ≤ 14 days. File absent → unknown. `--no-db` → unknown, because the match needs the database. A file that does not match a batch → fail. The collector reads. It does not call the command. | DEFINED-UNMET |
| governed | The boundary test is in the full pytest suite, and the `ci.yml` run for this commit succeeded | Probe `INBOUND-GOV-05`. Node `test_inbound_never_imports_people` exists as a `def`. Same CI rule as `INBOUND-SEC-06`, including `rerun_pytest: reject`. No GitHub run → unknown. A red run → fail. | DEFINED-UNMET |

These probes use collector `inbound_operated`, which is registered and fail-closed. A missing workflow run, series file, or live batch is `unknown`, never a pass. A pass from `repo`, `observe`, or `runtime` on `/api/health/` does not meet them. Rank 6 is not defined and is not claimed. The nightly workflow file stays absent until a runner that already has the stack is named.

Commit `0a66aa44` run `36320936245` concluded `failure`. The failed steps are backend `Install dependencies`, frontend `Run unit tests`, and lint `Fail-open lint (P1-13)`. The excellence ratchet step was skipped. CI Python is `3.11` and `backend/requirements.txt` pins `numpy==2.5.3`. Those failures are outside `backend/inbound`. The inbound probes still fail, because the workflow conclusion is the benchmark. Narrowing the probe to inbound tests alone would be a different rule.
