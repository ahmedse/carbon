# TASK.md — APP-CARBON-G5: Emissions Tests → 60% Coverage
# Phase I, Group 5 | Depends on G4 (tests G4 audit model)
# Worker: backend-worker | Model: DeepSeek (medium cost)

## Summary
Expand test coverage from ~15% (7 passing tests) to 60%+ across the emissions domain. Create 4 new test files, fix 1 existing broken test file. All new code from G1-G4 must be covered, plus core services.

## Files to Read First (BEFORE writing anything)
1. `.ai-toolkit/project.config.md`
2. `.ai-toolkit/shared/base-rules.md`
3. `.ai-toolkit/roles/backend-worker.md`
4. `.ai-toolkit/shared/data-layer.md`
5. `backend/emissions/models.py` — full read (all models you'll fixture)
6. `backend/emissions/services.py` — full read (all services to test)
7. `backend/emissions/views.py` — focus on new G1-G4 views
8. `backend/emissions/serializers.py` — all serializers
9. `backend/emissions/tests/test_calculation_validation.py` — pattern reference
10. `backend/emissions/tests/test_owner_endpoints.py` — pattern reference
11. `backend/emissions/tests/test_report_config.py` — the broken file to fix

## Registry Check
Run `./.ai-toolkit/scripts/scan.sh`. Confirm no existing test files beyond the 3 in `emissions/tests/`.

## Files to Create
| File | Content |
|------|---------|
| `backend/emissions/tests/test_targets.py` | SBTiTarget model, serializer, ViewSet CRUD, TargetService.get_progress |
| `backend/emissions/tests/test_verification.py` | VerificationRecord, ReportingPeriod actions (submit/verify/reject), VerificationRecordViewSet |
| `backend/emissions/tests/test_services.py` | DashboardService, YearlyComparisonService, ReportService, OwnerService |
| `backend/emissions/tests/test_batch_audit.py` | BatchCalculateAPIView, CalculationAudit model/ViewSet |

## Files to Fix
| File | Issue |
|------|-------|
| `backend/emissions/tests/test_report_config.py` | All 10 tests fail with `null value in column "data_row_id" violates not-null constraint` — setUp creates Calculation objects without data_row_id |

## DO NOT TOUCH
- Any frontend file
- `catalog/`, `mdm/`, `dq/`, `dataschema/`, `accounts/`, `core/`
- `backend/emissions/services.py` — test it, don't change it
- `backend/emissions/tests/test_calculation_validation.py` — don't modify
- `backend/emissions/tests/test_owner_endpoints.py` — don't modify

## Test File 1 — test_targets.py (~150 lines)
```python
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from decimal import Decimal

from accounts.models import User
from emissions.models import SBTiTarget, Calculation, EmissionFactor, ReportingPeriod
from mdm.models import OrgUnit
from core.models import Module
from dataschema.models import DataTable, DataField, DataRow


class SBTiTargetModelTests(TestCase):
    def test_str_method(self):
        target = SBTiTarget(
            name='Test Target', base_year=2023, target_year=2030,
            target_type='absolute', scope='1+2', reduction_pct=Decimal('50.00')
        )
        s = str(target)
        self.assertIn('Test Target', s)
        self.assertIn('2023', s)
        self.assertIn('50', s)

    def test_default_status_is_draft(self):
        org = OrgUnit.objects.create(name='Test Org', slug='test-org')
        target = SBTiTarget.objects.create(
            org_unit=org, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30.00')
        )
        self.assertEqual(target.status, 'draft')

    def test_ordering_by_base_year_desc(self):
        org = OrgUnit.objects.create(name='Test Org', slug='test-org-2')
        SBTiTarget.objects.create(org_unit=org, name='Old', base_year=2020, target_year=2030, target_type='absolute', scope='1', reduction_pct=Decimal('30'))
        SBTiTarget.objects.create(org_unit=org, name='New', base_year=2024, target_year=2030, target_type='absolute', scope='1', reduction_pct=Decimal('30'))
        targets = list(SBTiTarget.objects.all())
        self.assertGreaterEqual(targets[0].base_year, targets[1].base_year)


class SBTiTargetAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='targetuser', password='pass')
        self.org_unit = OrgUnit.objects.create(name='Facilities', slug='facilities')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_target(self):
        resp = self.client.post(reverse('emissions:targets-list'), {
            'org_unit': self.org_unit.id, 'name': '2030 Goal',
            'base_year': 2023, 'target_year': 2030,
            'target_type': 'absolute', 'scope': '1+2',
            'reduction_pct': '50.00', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['name'], '2030 Goal')
        self.assertEqual(data['org_unit_name'], 'Facilities')

    def test_list_targets(self):
        SBTiTarget.objects.create(
            org_unit=self.org_unit, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30')
        )
        resp = self.client.get(reverse('emissions:targets-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_update_target(self):
        target = SBTiTarget.objects.create(
            org_unit=self.org_unit, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30')
        )
        resp = self.client.patch(
            reverse('emissions:targets-detail', args=[target.id]),
            {'status': 'committed'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'committed')

    def test_delete_target(self):
        target = SBTiTarget.objects.create(
            org_unit=self.org_unit, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30')
        )
        resp = self.client.delete(reverse('emissions:targets-detail', args=[target.id]))
        self.assertEqual(resp.status_code, 204)
```

## Test File 2 — test_verification.py (~140 lines)
```python
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from django.contrib.auth.models import Group

from accounts.models import User, ScopedRole
from emissions.models import ReportingPeriod, VerificationRecord


class VerificationWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='verifier', password='pass')
        self.admin = User.objects.create_user(username='adminuser', password='pass', is_staff=True)
        admins_group, _ = Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.admin, group=admins_group, is_active=True)
        self.period = ReportingPeriod.objects.create(
            name='Q1 2026', start_date='2026-01-01', end_date='2026-03-31', status='draft'
        )
        self.client = APIClient()

    def test_submit_draft_period(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 200)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'submitted')
        self.assertIsNotNone(self.period.submitted_at)

    def test_submit_non_draft_fails(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 400)

    def test_verify_creates_record(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 201)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'verified')
        self.assertTrue(VerificationRecord.objects.filter(reporting_period=self.period).exists())

    def test_verify_non_submitted_fails(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 400)

    def test_verify_by_non_admin_blocked(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 403)

    def test_reject_with_notes(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('emissions:reporting-period-reject', args=[self.period.id]),
            {'notes': 'Missing Scope 3 data'}, format='json'
        )
        self.assertEqual(resp.status_code, 201)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'rejected')
        record = VerificationRecord.objects.get(reporting_period=self.period)
        self.assertIn('Missing Scope 3', record.notes)

    def test_verifications_filter_by_period(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        resp = self.client.get(f"{reverse('emissions:verification-list')}?period_id={self.period.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_verifier_name_in_response(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        resp = self.client.get(reverse('emissions:verification-list'))
        data = resp.json()
        self.assertEqual(data[0]['verifier_name'], 'adminuser')
```

## Test File 3 — test_services.py (~180 lines)
Test the core service methods. Use Django TestCase with database fixtures — no mocking needed.

```python
from django.test import TestCase
from decimal import Decimal

from accounts.models import User
from emissions.models import (
    EmissionFactor, CalculationRule, Calculation, ReportingPeriod, GWP
)
from emissions.services import (
    DashboardService, YearlyComparisonService, ReportService,
    CalculationEngineService, OwnerService, TargetService,
)
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from core.models import Module


class CalculationEngineServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='engine', password='pass')
        self.org_unit = OrgUnit.objects.create(name='Eng', slug='eng')
        self.module = Module.objects.create(name='Electricity', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='electricity')
        self.field = DataField.objects.create(data_table=self.table, name='kwh', label='kWh', type='number', required=True)
        self.factor = EmissionFactor.objects.create(
            code='GRID', name='Grid', category='electricity', scope=2,
            factor_value=Decimal('0.5'), activity_unit='kWh', source='EPA', valid_from='2024-01-01'
        )
        self.rule = CalculationRule.objects.create(
            data_table=self.table, activity_field=self.field,
            emission_factor=self.factor, name='Elec→CO2', is_active=True, auto_calculate=True
        )
        self.period = ReportingPeriod.objects.create(
            name='FY26', start_date='2026-01-01', end_date='2026-12-31', status='open'
        )

    def test_validate_returns_errors_for_missing_rule_id(self):
        rule, period, errors = CalculationEngineService.validate_calculation_request(None)
        self.assertIn('rule_id', errors)

    def test_validate_returns_rule_not_found(self):
        rule, period, errors = CalculationEngineService.validate_calculation_request(9999)
        self.assertIn('rule_id', errors)

    def test_validate_rejects_inactive_rule(self):
        self.rule.is_active = False
        self.rule.save()
        rule, period, errors = CalculationEngineService.validate_calculation_request(self.rule.id)
        self.assertIn('rule_id', errors)

    def test_validate_rejects_closed_period(self):
        self.period.status = 'closed'
        self.period.save()
        rule, period, errors = CalculationEngineService.validate_calculation_request(self.rule.id, period_id=self.period.id)
        self.assertIn('reporting_period_id', errors)

    def test_validate_reports_incomplete_rows(self):
        DataRow.objects.create(data_table=self.table, values={})
        DataRow.objects.create(data_table=self.table, values={'kwh': '100'})
        rule, period, errors = CalculationEngineService.validate_calculation_request(self.rule.id, period_id=self.period.id)
        self.assertIn('incomplete_rows', errors)
        self.assertEqual(len(errors['incomplete_rows']), 1)


class TargetServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='targets', password='pass')
        self.org_unit = OrgUnit.objects.create(name='TargetOrg', slug='target-org')
        from emissions.models import SBTiTarget
        self.target = SBTiTarget.objects.create(
            org_unit=self.org_unit, name='2030 Goal', base_year=2023,
            target_year=2030, target_type='absolute', scope='1+2',
            reduction_pct=Decimal('50.00')
        )

    def test_get_progress_returns_structure(self):
        result = TargetService.get_progress(self.target.id, 2025)
        self.assertEqual(result['target_id'], self.target.id)
        self.assertEqual(result['name'], '2030 Goal')
        self.assertIn('actual_tco2e', result)
        self.assertIn('status', result)


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dash', password='pass')

    def test_get_dashboard_returns_structure(self):
        result = DashboardService.get_dashboard(self.user)
        self.assertIn('total_emissions', result)
        self.assertIn('scope_breakdown', result)
        self.assertIn('top_sources', result)

    def test_get_dashboard_with_period(self):
        period = ReportingPeriod.objects.create(
            name='FY26', start_date='2026-01-01', end_date='2026-12-31'
        )
        result = DashboardService.get_dashboard(self.user, period_id=period.id)
        self.assertIn('total_emissions', result)


class OwnerServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='pass')

    def test_get_org_units_returns_list_for_non_staff(self):
        result = OwnerService.get_org_units(self.user)
        self.assertIsInstance(result, list)

    def test_get_org_units_returns_none_for_superuser(self):
        self.user.is_superuser = True
        self.user.save()
        result = OwnerService.get_org_units(self.user)
        self.assertIsNone(result)
```

## Test File 4 — test_batch_audit.py (~130 lines)
```python
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from decimal import Decimal

from accounts.models import User
from emissions.models import (
    EmissionFactor, CalculationRule, ReportingPeriod, CalculationAudit
)
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from core.models import Module


class BatchCalculateAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='batch', password='pass')
        self.org_unit = OrgUnit.objects.create(name='BatchOrg', slug='batch-org')
        self.module = Module.objects.create(name='BatchMod', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='batch_table')
        self.field = DataField.objects.create(data_table=self.table, name='kwh', label='kWh', type='number', required=True)
        self.factor = EmissionFactor.objects.create(
            code='BATCH_GRID', name='Batch Grid', category='electricity', scope=2,
            factor_value=Decimal('0.5'), activity_unit='kWh', source='EPA', valid_from='2024-01-01'
        )
        self.rule = CalculationRule.objects.create(
            data_table=self.table, activity_field=self.field,
            emission_factor=self.factor, name='Batch→CO2', is_active=True, auto_calculate=True
        )
        self.period = ReportingPeriod.objects.create(
            name='Batch FY26', start_date='2026-01-01', end_date='2026-12-31', status='open'
        )
        DataRow.objects.create(data_table=self.table, values={'kwh': '100'})
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_batch_calculate_returns_200(self):
        resp = self.client.post(reverse('emissions:batch-calculate'), {
            'table_ids': [self.table.id],
            'period_id': self.period.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('total_created', data)
        self.assertIn('per_table', data)

    def test_batch_calculate_missing_table_ids(self):
        resp = self.client.post(reverse('emissions:batch-calculate'), {
            'period_id': self.period.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_batch_calculate_missing_period_id(self):
        resp = self.client.post(reverse('emissions:batch-calculate'), {
            'table_ids': [self.table.id],
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_batch_calculate_creates_audit(self):
        self.client.post(reverse('emissions:batch-calculate'), {
            'table_ids': [self.table.id], 'period_id': self.period.id,
        }, format='json')
        self.assertTrue(CalculationAudit.objects.filter(trigger_type='batch').exists())
        audit = CalculationAudit.objects.first()
        self.assertEqual(audit.trigger_type, 'batch')


class CalculationAuditAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='audit', password='pass')
        self.period = ReportingPeriod.objects.create(
            name='Audit FY26', start_date='2026-01-01', end_date='2026-12-31'
        )
        self.audit = CalculationAudit.objects.create(
            trigger_type='batch', triggered_by=self.user,
            reporting_period=self.period, table_ids=[1, 2],
            created_count=5, skipped_count=10, error_count=0,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_audits(self):
        resp = self.client.get(reverse('emissions:calculation-audit-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_filter_audit_by_type(self):
        resp = self.client.get(reverse('emissions:calculation-audit-list') + '?trigger_type=batch')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_filter_audit_by_period(self):
        resp = self.client.get(reverse('emissions:calculation-audit-list') + f'?period_id={self.period.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_audit_has_user_name(self):
        resp = self.client.get(reverse('emissions:calculation-audit-list'))
        data = resp.json()
        self.assertEqual(data[0]['triggered_by_name'], 'audit')
```

## Fix: test_report_config.py
The `setUp` method creates `Calculation` objects directly without `data_row_id`. Since `data_row_id` is NOT NULL, these fail. Fix: create proper `DataRow` fixtures.

In `setUp`, add BEFORE the Calculation creations:
```python
        # Create DataTable + DataRow so Calculations have valid data_row_id
        self.report_table = DataTable.objects.create(
            module=self.module1, name='report_test_table'
        )
        self.report_field = DataField.objects.create(
            data_table=self.report_table, name='kwh', label='kWh', type='number', required=True
        )
        self.report_row = DataRow.objects.create(
            data_table=self.report_table, values={'kwh': '100'}
        )
```

Then update every `Calculation.objects.create(...)` call to include `data_row=self.report_row`.

Expected: all 10 tests pass after fix.

## Verification Gate

```bash
# 1. Run all tests
cd backend && source ../.venv/bin/activate && python -m pytest emissions/tests/ -v

# Expected:
# test_calculation_validation.py — 3 passed
# test_owner_endpoints.py — 4 passed
# test_report_config.py — 10 passed (after fix)
# test_targets.py — 7 passed
# test_verification.py — 8 passed
# test_services.py — 10 passed
# test_batch_audit.py — 7 passed
# TOTAL: 49 passed, 0 failed

# 2. Coverage check
python -m pytest emissions/tests/ --cov=emissions --cov-report=term-missing 2>&1 | tail -20
# Target: at least 60% coverage for emissions/ package

# 3. AI Toolkit gate
./.ai-toolkit/scripts/verify.sh backend
# Must: GATE PASSED

# 4. No regressions
python manage.py check
python manage.py makemigrations --check
# Must: 0 errors, "No changes detected"
```

## Handoff
Write `plans/carbon-phase/phase-03-targets/TASK-RESULTS-G5.md` with:
- Test output (pass/fail counts per file)
- Coverage percentage
- Any antipatterns introduced
