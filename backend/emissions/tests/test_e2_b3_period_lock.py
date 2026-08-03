# emissions/tests/test_e2_b3_period_lock.py
# E2-B3: Period-lock enforcement regression tests.
# Tests: calc blocked on locked/verified/closed periods; lock/unlock
# propagates to DataTable.is_locked; data POST to locked table → 403;
# open/lock/close actions return correct status codes.

from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from django.contrib.auth.models import Group
from decimal import Decimal

from accounts.models import User, ScopedRole
from emissions.models import (
    EmissionFactor, CalculationRule, ReportingPeriod,
)
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from core.models import Module


class PeriodLockCalculationGatingTests(TestCase):
    """Calculation is blocked when the period is locked, verified, or closed."""

    def setUp(self):
        self.admin = User.objects.create_superuser(username='lockadmin', password='pass')
        self.org_unit = OrgUnit.objects.create(name='LockOrg', slug='lock-org')
        self.module = Module.objects.create(name='LockMod', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='lock_table')
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number', required=True,
        )
        self.factor = EmissionFactor.objects.create(
            code='LOCK_GRID', name='Lock Grid', category='electricity', scope=2,
            factor_value=Decimal('0.5'), activity_unit='kWh',
            source='EPA', valid_from='2024-01-01',
        )
        self.rule = CalculationRule.objects.create(
            data_table=self.table, activity_field=self.field,
            emission_factor=self.factor, name='Lock→CO2',
            is_active=True, auto_calculate=True,
        )
        DataRow.objects.create(data_table=self.table, values={'kwh': '100'})
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _set_period_status(self, status):
        """Helper: create a period with given status, bypassing state machine."""
        period = ReportingPeriod.objects.create(
            name=f'Period-{status}',
            start_date='2026-01-01',
            end_date='2026-12-31',
            status=status,
        )
        return period

    # ── Calculation gating ───────────────────────────────────────────

    def test_calc_blocked_on_locked_period(self):
        """POST /calculate/ with a locked period returns 422."""
        period = self._set_period_status('locked')
        resp = self.client.post(reverse('emissions:calculate'), {
            'rule_id': self.rule.id,
            'reporting_period_id': period.id,
        })
        self.assertEqual(resp.status_code, 422)
        self.assertIn('error', resp.json())

    def test_calc_blocked_on_verified_period(self):
        """POST /calculate/ with a verified period returns 422."""
        period = self._set_period_status('verified')
        resp = self.client.post(reverse('emissions:calculate'), {
            'rule_id': self.rule.id,
            'reporting_period_id': period.id,
        })
        self.assertEqual(resp.status_code, 422)
        self.assertIn('error', resp.json())

    def test_calc_blocked_on_closed_period(self):
        """POST /calculate/ with a closed period returns 422 (existing behavior)."""
        period = self._set_period_status('closed')
        resp = self.client.post(reverse('emissions:calculate'), {
            'rule_id': self.rule.id,
            'reporting_period_id': period.id,
        })
        self.assertEqual(resp.status_code, 422)
        self.assertIn('error', resp.json())

    def test_calc_allowed_on_open_period(self):
        """POST /calculate/ with an open period succeeds."""
        period = self._set_period_status('open')
        resp = self.client.post(reverse('emissions:calculate'), {
            'rule_id': self.rule.id,
            'reporting_period_id': period.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('success'))

    def test_batch_calc_blocked_on_locked_period(self):
        """Batch calculate with a locked period returns error detail."""
        period = self._set_period_status('locked')
        resp = self.client.post(reverse('emissions:batch-calculate'), {
            'table_ids': [self.table.id],
            'period_id': period.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('detail', data)
        self.assertIn('locked', data['detail'])


class PeriodTransitionActionsTests(TestCase):
    """open/lock/close actions return correct status codes and propagate locks."""

    def setUp(self):
        self.admin = User.objects.create_superuser(username='transadmin', password='pass')
        admins_group, _ = Group.objects.get_or_create(name='admins_group')
        self.admin.groups.add(admins_group)

        self.org_unit = OrgUnit.objects.create(name='TransOrg', slug='trans-org')
        self.module = Module.objects.create(name='TransMod', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='trans_table')
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number', required=True,
        )
        self.factor = EmissionFactor.objects.create(
            code='TRANS_GRID', name='Trans Grid', category='electricity', scope=2,
            factor_value=Decimal('0.5'), activity_unit='kWh',
            source='EPA', valid_from='2024-01-01',
        )
        self.rule = CalculationRule.objects.create(
            data_table=self.table, activity_field=self.field,
            emission_factor=self.factor, name='Trans→CO2',
            is_active=True, auto_calculate=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    # ── open action ──────────────────────────────────────────────────

    def test_open_from_draft_succeeds(self):
        """open action: draft → open succeeds."""
        period = ReportingPeriod.objects.create(
            name='OpenTest', start_date='2026-01-01', end_date='2026-12-31', status='draft',
        )
        resp = self.client.post(reverse('emissions:reporting-period-open', args=[period.id]))
        self.assertEqual(resp.status_code, 200)
        period.refresh_from_db()
        self.assertEqual(period.status, 'open')

    def test_open_from_locked_unlocks_tables(self):
        """open action from locked → open, tables unlocked."""
        period = ReportingPeriod.objects.create(
            name='UnlockTest', start_date='2026-01-01', end_date='2026-12-31', status='locked',
        )
        # Pre-lock the table
        self.table.is_locked = True
        self.table.save()

        resp = self.client.post(reverse('emissions:reporting-period-open', args=[period.id]))
        self.assertEqual(resp.status_code, 200)
        period.refresh_from_db()
        self.assertEqual(period.status, 'open')
        self.table.refresh_from_db()
        self.assertFalse(self.table.is_locked)

    def test_open_invalid_transition_409(self):
        """open action from 'submitted' → 409."""
        period = ReportingPeriod.objects.create(
            name='BadOpen', start_date='2026-01-01', end_date='2026-12-31', status='submitted',
        )
        resp = self.client.post(reverse('emissions:reporting-period-open', args=[period.id]))
        self.assertEqual(resp.status_code, 409)

    # ── lock action ──────────────────────────────────────────────────

    def test_lock_from_open_locks_tables(self):
        """lock action: open → locked, tables locked."""
        period = ReportingPeriod.objects.create(
            name='LockTest', start_date='2026-01-01', end_date='2026-12-31', status='open',
        )
        self.assertFalse(self.table.is_locked)

        resp = self.client.post(reverse('emissions:reporting-period-lock', args=[period.id]))
        self.assertEqual(resp.status_code, 200)
        period.refresh_from_db()
        self.assertEqual(period.status, 'locked')
        self.table.refresh_from_db()
        self.assertTrue(self.table.is_locked)

    def test_lock_invalid_transition_409(self):
        """lock action from 'draft' → 409."""
        period = ReportingPeriod.objects.create(
            name='BadLock', start_date='2026-01-01', end_date='2026-12-31', status='draft',
        )
        resp = self.client.post(reverse('emissions:reporting-period-lock', args=[period.id]))
        self.assertEqual(resp.status_code, 409)

    # ── close action ─────────────────────────────────────────────────

    def test_close_from_verified_succeeds(self):
        """close action: verified → closed succeeds."""
        period = ReportingPeriod.objects.create(
            name='CloseTest', start_date='2026-01-01', end_date='2026-12-31', status='verified',
        )
        resp = self.client.post(reverse('emissions:reporting-period-close', args=[period.id]))
        self.assertEqual(resp.status_code, 200)
        period.refresh_from_db()
        self.assertEqual(period.status, 'closed')

    def test_close_invalid_transition_409(self):
        """close action from 'open' → 409."""
        period = ReportingPeriod.objects.create(
            name='BadClose', start_date='2026-01-01', end_date='2026-12-31', status='open',
        )
        resp = self.client.post(reverse('emissions:reporting-period-close', args=[period.id]))
        self.assertEqual(resp.status_code, 409)


class DataRowLockedTableWriteGuardTests(TestCase):
    """Data POST/PUT/PATCH/DELETE to locked table → 403."""

    def setUp(self):
        self.user = User.objects.create_user(username='rowwriter', password='pass')
        dataowners_group, _ = Group.objects.get_or_create(name='dataowners_group')
        ScopedRole.objects.create(
            user=self.user, group=dataowners_group, is_active=True,
        )

        self.org_unit = OrgUnit.objects.create(name='RowLockOrg', slug='rowlock-org')
        self.module = Module.objects.create(name='RowLockMod', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(
            module=self.module, name='rowlock_table', is_locked=True,
        )
        self.field = DataField.objects.create(
            data_table=self.table, name='val', label='Value', type='number', required=True,
        )
        DataRow.objects.create(data_table=self.table, values={'val': '42'})
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_row_on_locked_table_403(self):
        """POST /rows/ to a locked table → 403."""
        resp = self.client.post(
            reverse('dataschema-row-list'),
            {'data_table': self.table.id, 'values': {'val': '99'}},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_row_on_locked_table_403(self):
        """PUT /rows/{id}/ on a locked table → 403."""
        row = DataRow.objects.first()
        resp = self.client.put(
            reverse('dataschema-row-detail', args=[row.id]),
            {'data_table': self.table.id, 'values': {'val': '99'}},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_partial_update_row_on_locked_table_403(self):
        """PATCH /rows/{id}/ on a locked table → 403."""
        row = DataRow.objects.first()
        resp = self.client.patch(
            reverse('dataschema-row-detail', args=[row.id]),
            {'values': {'val': '99'}},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_row_on_locked_table_403(self):
        """DELETE /rows/{id}/ on a locked table → 403."""
        row = DataRow.objects.first()
        resp = self.client.delete(
            reverse('dataschema-row-detail', args=[row.id]),
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_row_on_unlocked_table_succeeds(self):
        """POST /rows/ to an unlocked table is not blocked by lock guard."""
        self.table.is_locked = False
        self.table.save()
        resp = self.client.post(
            reverse('dataschema-row-list'),
            {'data_table': self.table.id, 'values': {'val': '99'}},
            format='json',
        )
        # 400 (validation) or 201 (success) — both mean lock guard didn't block
        self.assertIn(resp.status_code, [201, 400])
        self.assertNotEqual(resp.status_code, 403)
