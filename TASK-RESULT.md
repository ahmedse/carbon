# TASK-RESULT.md — APP-CARBON-1 (RUN 10: Carbon app wired to real data)

## File created
- backend/emissions/management/commands/setup_carbon_app.py

## Command output
```text
  Factor EG_GRID_2024: created (0.4584 kg CO2e/kWh, scope 2)
  Factor EG_WATER_2024: created (0.3440 kg CO2e/m3, scope 3)
  Rule 'Electricity → CO2e': created=26 skipped=0 errors=0
  Rule 'Water → CO2e': created=18 skipped=0 errors=0

Carbon app ready. Calculations in system: 44. Total ≈ 2,669.9 tonnes CO2e (created 44 this run).
```

## 4.1 no-migration
```bash
cd backend && source venv/bin/activate
python manage.py makemigrations --check --dry-run 2>&1 | tail -3
```
Output:
```text
No changes detected
```

## 4.2 calculations by scope
```bash
cd backend && source venv/bin/activate
python manage.py shell -c "from emissions.models import EmissionFactor, CalculationRule, Calculation; print('factors', EmissionFactor.objects.count(), '| rules', CalculationRule.objects.count(), '| calcs', Calculation.objects.count()); by_scope = {}; [by_scope.__setitem__(c.scope, by_scope.get(c.scope, 0) + float(c.co2e_kg)) for c in Calculation.objects.all()]; print('tonnes by scope:', {k: round(v/1000,1) for k,v in sorted(by_scope.items())})" 2>&1 | grep -E "factors|tonnes"
```
Output:
```text
factors 2 | rules 2 | calcs 44
tonnes by scope: {2: 2663.6, 3: 6.3}
```

## 4.3 dashboard
```bash
cd backend && source venv/bin/activate
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ -H "Content-Type: application/json" -d '{"username":"ahmed","password":"AdminPa_132"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access'])")
curl -s "http://localhost:8009/carbon-api/emissions/dashboard/?year=2023" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(d, indent=2)[:800])"
```
Output:
```json
{
  "reporting_period": null,
  "total_co2e_tonnes": 1293.14,
  "scope_breakdown": [
    {
      "scope": 2,
      "scope_name": "Scope 2 - Indirect Energy",
      "co2e_tonnes": 1288.59,
      "percentage": 99.65
    },
    {
      "scope": 3,
      "scope_name": "Scope 3 - Value Chain",
      "co2e_tonnes": 4.55,
      "percentage": 0.35
    }
  ]
}
```

## 4.4 idempotency
```bash
cd backend && source venv/bin/activate
python manage.py setup_carbon_app 2>&1 | tail -3
```
Output:
```text
  Rule 'Water → CO2e': created=0 skipped=18 errors=0

Carbon app ready. Calculations in system: 44. Total ≈ 2,669.9 tonnes CO2e (created 0 this run).
```

## Deviations / Blockers
- None.

## Final status: PASS
