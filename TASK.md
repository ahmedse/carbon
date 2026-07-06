# TASK.md — Active Task (Executor Control File)

**Master (planner):** GitHub Copilot
**Executor:** Sonnet (worker)
**Date:** 2026-07-06
**Task ID:** APP-CARBON-1 — **RUN 10: Carbon (Emissions) app wires itself onto the trusted data**
**Goal:** The **Carbon app** (the `emissions` Django app) consumes the platform's real Facilities data tables and produces CO₂e, so the emissions dashboards show real numbers. This is APP logic, not platform/core logic — everything lives in the `emissions` app.
**Report to:** `TASK-RESULT.md` (create/overwrite for this run).

> ⚠️ **You may be a smaller/cheaper model. Read this WHOLE file first. Do steps IN ORDER. Copy code VERBATIM. Run §4 checks and paste real output into TASK-RESULT.md.**

---

## 0. 🚫 STRICT GUARD RAILS

### Architecture principle (do not violate)
- **Carbon = a hosted APP** on the platform. Its logic (emission factors, calculation rules, CO₂e) lives ONLY in the `emissions` app.
- The `emissions` app MAY import platform core (`dataschema`, `core`, `mdm`, `catalog`). The core apps must NEVER import `emissions` — do not add any such import.

### Files you MAY create/edit — EXACTLY these 1:
1. `backend/emissions/management/commands/setup_carbon_app.py` (**create new**)

### You MUST NOT:
- ❌ Edit any model, migration, view, serializer, url, or settings file (NO schema change, NO migration).
- ❌ Edit any file in `catalog/`, `mdm/`, `dq/`, `dataschema/`, `core/`, `accounts/`, or the frontend.
- ❌ Reintroduce `project` / `projectId` / `project_id`.
- ✅ If you think you need to change a model or any file other than the one new command, STOP and write a BLOCKED note.

---

## 1. Context — the trusted data this app consumes (already seeded, do NOT recreate)

Real AASTMT Abu Qir data already exists in the platform's `dataschema` tables (owned by the "Facilities & Utilities" org unit):

| DataTable `name` | Activity field (`name`) | Date field (`name`) | Unit |
|---|---|---|---|
| `monthly_electricity` | `total_kwh` | `month` | kWh |
| `monthly_water` | `total_m3` | `month` | m³ |
| `monthly_chilled_water` | `total_tr` | `month` | TR |

The emissions engine models (already exist — do NOT change them):
- `EmissionFactor(name, code, category, scope, factor_value, factor_unit, activity_unit, source, valid_from, is_active)`
- `CalculationRule(data_table, activity_field, date_field, emission_factor, name, rule_type='direct', is_active, auto_calculate)`
- `CalculationRule.calculate_for_table(reporting_period=None, user=None, recalculate=False)` → `(created, skipped, errors)`.

This run: seed the app's **emission factors**, create **calculation rules** binding the tables' activity fields to those factors, and **run the calculations**. The dashboards already read `Calculation` rows — no view/frontend change needed.

---

## 2. STEP 1 — Create the Carbon app setup command

**Create new file:** `backend/emissions/management/commands/setup_carbon_app.py`
**Content (verbatim, entire file):**
```python
# emissions/management/commands/setup_carbon_app.py
# Carbon (emissions) APP self-setup: seeds emission factors, binds calculation
# rules to the platform's trusted data tables, and computes CO2e.
# The emissions app MAY import platform core; core never imports this app.
# Idempotent + additive. NO model/schema changes.
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from dataschema.models import DataTable, DataField
from emissions.models import EmissionFactor, CalculationRule


# Emission factors this app uses (Egypt context). Values are documented, editable later.
FACTORS = [
    # code, name, category, scope, factor_value, activity_unit, source
    ("EG_GRID_2024", "Egypt National Grid (Electricity)", "electricity", 2, "0.4584", "kWh",
     "Egypt national grid average (IFI/IEA-based)"),
    ("EG_WATER_2024", "Water Supply + Treatment (Egypt)", "water", 3, "0.3440", "m3",
     "Water supply + treatment (DEFRA-based proxy)"),
]

# Which table's activity field maps to which factor.
# (table_name, activity_field_name, date_field_name, factor_code, rule_name)
RULE_BINDINGS = [
    ("monthly_electricity", "total_kwh", "month", "EG_GRID_2024", "Electricity → CO2e"),
    ("monthly_water",       "total_m3",  "month", "EG_WATER_2024", "Water → CO2e"),
    # NOTE: monthly_chilled_water (TR) is intentionally NOT wired yet — the CO2e
    # methodology for district chilled water (TR) needs to be decided separately.
]


class Command(BaseCommand):
    help = "Carbon app setup: seed emission factors, bind calculation rules to trusted tables, compute CO2e."

    def add_arguments(self, parser):
        parser.add_argument('--recalculate', action='store_true',
                            help='Delete existing calculations for these rules and recompute.')

    def handle(self, *args, **options):
        # 1. Emission factors
        for code, name, category, scope, value, unit, source in FACTORS:
            ef, created = EmissionFactor.objects.get_or_create(
                code=code,
                defaults={
                    'name': name, 'category': category, 'scope': scope,
                    'factor_value': Decimal(value), 'factor_unit': 'kg CO2e',
                    'activity_unit': unit, 'source': source,
                    'valid_from': date(2023, 1, 1), 'is_active': True,
                },
            )
            self.stdout.write(f"  Factor {code}: {'created' if created else 'exists'} "
                              f"({value} kg CO2e/{unit}, scope {scope})")

        # 2. Calculation rules bound to the trusted data tables
        total_created = 0
        for table_name, activity_name, date_name, factor_code, rule_name in RULE_BINDINGS:
            table = DataTable.objects.filter(name=table_name, is_archived=False).first()
            if not table:
                self.stdout.write(self.style.WARNING(f"  SKIP: table '{table_name}' not found"))
                continue
            activity_field = DataField.objects.filter(data_table=table, name=activity_name).first()
            date_field = DataField.objects.filter(data_table=table, name=date_name).first()
            factor = EmissionFactor.objects.filter(code=factor_code).first()
            if not (activity_field and factor):
                self.stdout.write(self.style.WARNING(
                    f"  SKIP: missing field/factor for '{table_name}'"))
                continue

            rule, _ = CalculationRule.objects.get_or_create(
                data_table=table, activity_field=activity_field, emission_factor=factor,
                defaults={
                    'name': rule_name, 'date_field': date_field,
                    'rule_type': 'direct', 'is_active': True, 'auto_calculate': True,
                },
            )
            if rule.date_field_id != (date_field.id if date_field else None):
                rule.date_field = date_field
                rule.save(update_fields=['date_field'])

            created, skipped, errors = rule.calculate_for_table(
                recalculate=options['recalculate']
            )
            total_created += created
            self.stdout.write(f"  Rule '{rule_name}': created={created} skipped={skipped} errors={errors}")

        # 3. Summary
        from emissions.models import Calculation
        total = Calculation.objects.count()
        tonnes = sum(float(c.co2e_kg) for c in Calculation.objects.all()) / 1000.0
        self.stdout.write(self.style.SUCCESS(
            f"\nCarbon app ready. Calculations in system: {total}. "
            f"Total ≈ {tonnes:,.1f} tonnes CO2e (created {total_created} this run)."
        ))
```
**Deliverable:** file exists at that path.

---

## 3. STEP 2 — Run the command + restart
```bash
cd backend && source venv/bin/activate
python manage.py check          # must be 0 issues, NO migration prompt
python manage.py setup_carbon_app --recalculate
cd /home/ahmed/aast/carbon && ./manage.sh restart
```

---

## 4. Acceptance checks (run; paste into TASK-RESULT.md)

### 4.1 No schema change
```bash
cd backend && source venv/bin/activate
python manage.py makemigrations --check --dry-run 2>&1 | tail -3
```
**Condition:** "No changes detected".

### 4.2 Calculations produced
```bash
python manage.py shell -c "
from emissions.models import EmissionFactor, CalculationRule, Calculation
print('factors', EmissionFactor.objects.count(), '| rules', CalculationRule.objects.count(), '| calcs', Calculation.objects.count())
by_scope = {}
for c in Calculation.objects.all():
    by_scope[c.scope] = by_scope.get(c.scope, 0) + float(c.co2e_kg)
print('tonnes by scope:', {k: round(v/1000,1) for k,v in sorted(by_scope.items())})
" 2>&1 | grep -E "factors|tonnes"
```
**Condition:** factors ≥ 2, rules ≥ 2, calcs > 0; scope 2 (electricity) and scope 3 (water) both show non-zero tonnes.

### 4.3 Dashboard returns real numbers (HTTP)
```bash
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ -H "Content-Type: application/json" -d '{"username":"ahmed","password":"AdminPa_132"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access'])")
curl -s "http://localhost:8009/carbon-api/emissions/dashboard/?year=2023" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(d, indent=2)[:600])"
```
**Condition:** dashboard responds 200 with non-zero total CO₂e for 2023.

### 4.4 Idempotency
```bash
python manage.py setup_carbon_app 2>&1 | tail -3   # WITHOUT --recalculate
```
**Condition:** re-run without `--recalculate` reports `skipped` > 0 and does NOT duplicate calculations (calc count unchanged from 4.2).

### PASS BAR
- [ ] 4.1 no migration needed.
- [ ] 4.2 factors ≥ 2, rules ≥ 2, calcs > 0; scope 2 + scope 3 non-zero.
- [ ] 4.3 dashboard 200 with non-zero total.
- [ ] 4.4 re-run is idempotent (no duplicates).
- [ ] Only the 1 new command file was added; no model/migration/core/frontend change.

---

## 5. Report to `TASK-RESULT.md`
```markdown
# TASK-RESULT.md — APP-CARBON-1 (RUN 10: Carbon app wired to real data)

## File created
- backend/emissions/management/commands/setup_carbon_app.py

## Command output
<paste setup_carbon_app --recalculate output>

## 4.1 no-migration
<paste>
## 4.2 calculations by scope
<paste>
## 4.3 dashboard
<paste>
## 4.4 idempotency
<paste>

## Deviations / Blockers
- none / <describe>

## Final status: PASS / PARTIAL / BLOCKED
```

---

## 6. Hard stops
- If `makemigrations --check` says a migration is needed → you edited a model; STOP and report.
- If you need to touch any file other than the one new command → STOP and report.
- When all PASS BAR items pass, write Final status = PASS and STOP.
