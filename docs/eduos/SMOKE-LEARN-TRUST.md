# Smoke — Learn + Instrument Trust

**Purpose:** Quick product verification after Instrument Trust / Learn changes.  
**Automated:** `pytest gradevance/tests/test_learn_trust_smoke.py` (no live passwords).  
**Manual:** browser on **EduOS** brand (`./manage.sh brand eduos`) — ports backend `8009`, frontend `5179`. If login lands on Nibras, switch brand first.

**Playwright (full professor journey):** from `carbon-frontend` with services up:

```bash
CI=1 npx playwright test journeys/journey-eduos-professor-lifecycle.spec.ts --config=e2e/playwright.config.ts
```

Covers KB pin → course/stem → calibration → publish → analyze → run workbench (shell breadcrumbs, rich LCT, SystemDialog ExpertEdit) → audit → marking → proposals → Learn.

---

## Automated (CI / local)

```bash
cd backend
DJANGO_BRAND=eduos ../.venv/bin/python -m pytest \
  gradevance/tests/test_learn_trust_smoke.py \
  -o addopts= -p no:_testbrand -q
```

Expect: Learn me/* coaching + course filter; Calibration NAA `expert_trusted`; medicine summative blocked as `seeded_draft`.

---

## Manual browser checklist

### Learn (student)

1. Open `/learn` — join form + due soon + **latest coaching** (strengths / actions) after a coach run.
2. `/learn/assignments` — grouped by course; course filter works.
3. Open an assignment — draft, coach, **no JSON dump** for band expectations; withheld = Alert only.
4. Open appeal → **Withdraw** when status is open.
5. `/learn/progress` — drafts grouped by assignment with wave trajectory.

### Teach / Engine (professor / QA)

6. `/teach/...` Calibration — NAA profile: SG/SD κ chips; gold chip **expert** / gate may pass.
7. Switch to medicine CBL profile — gold chip **seeded_draft (not expert)**; info alert; summative blocked.
8. GradeVance QA console — GOLD-EVAL panel links `docs/eduos/qa-evidence/GOLD-EVAL-LATEST.json`.

### Must not claim

- Learn coaching ≠ tutor marks match experts (advisory watermark).
- Medicine/article κ ≠ expert agreement while `seeded_draft`.

---

## Seed (optional, local demo)

```bash
DJANGO_BRAND=eduos python manage.py seed_gradevance_demo
```

Uses demo course entry code `DEMO-LCT` and student `gv_student` (password from seed command / `CARBON_ADMIN_PASSWORD`).
