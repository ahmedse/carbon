"""Tests for BatchCalculateAPIView and CalculationAudit model/ViewSet."""
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
        self.user = User.objects.create_superuser(username='batch', password='pass')
        self.org_unit = OrgUnit.objects.create(name='BatchOrg', slug='batch-org')
        self.module = Module.objects.create(name='BatchMod', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='batch_table')
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number', required=True
        )
        self.factor = EmissionFactor.objects.create(
            code='BATCH_GRID', name='Batch Grid', category='electricity', scope=2,
            factor_value=Decimal('0.5'), activity_unit='kWh',
            source='EPA', valid_from='2024-01-01'
        )
        self.rule = CalculationRule.objects.create(
            data_table=self.table, activity_field=self.field,
            emission_factor=self.factor, name='Batch→CO2',
            is_active=True, auto_calculate=True
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
        resp = self.client.get(
            reverse('emissions:calculation-audit-list') + '?trigger_type=batch'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_filter_audit_by_period(self):
        resp = self.client.get(
            reverse('emissions:calculation-audit-list') + f'?period_id={self.period.id}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_audit_has_user_name(self):
        resp = self.client.get(reverse('emissions:calculation-audit-list'))
        data = resp.json()
        self.assertEqual(data[0]['triggered_by_name'], 'audit')
