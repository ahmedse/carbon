"""Regression tests for Phase A1 — DQ Rules create/edit blockers (F1, F3, F7).

F1/F6: definition-first write path derives flat columns (name/rule_type/
       rule_level/severity/dimension/is_active) so definition-only bodies work.
F3/D4: drift guard rejects a silent drop of existing bindings on PATCH.
F7:    PATCHing the definition bumps the monotonic version.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Module
from dataschema.models import DataTable, DataField
from mdm.models import OrgUnit
from dq.models import DQRule, RuleFieldAssignment


User = get_user_model()
BASE = '/carbon-api/dq'


def _definition(**overrides):
    """Return a valid v1 rule definition (range, field-level, validity)."""
    base = {
        'schema_version': 1,
        'name': 'Amount in range',
        'level': 'field',
        'dimension': 'validity',
        'type': 'range',
        'severity': 'error',
        'active': True,
        'params': {'min': 0, 'max': 100},
    }
    base.update(overrides)
    return base


class _A1Base(TestCase):
    """Shared fixtures: superuser, org/module/table/field."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='a1_admin', password='pass', is_staff=True, is_superuser=True)
        self.org_unit = OrgUnit.objects.create(
            name='A1 Org', code='A1O', org_type='division')
        self.module = Module.objects.create(name='A1 Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(name='a1_table', module=self.module)
        self.field = DataField.objects.create(
            data_table=self.table, name='amount', label='Amount', type='number')
        self.client.force_authenticate(self.admin)


class DefinitionFirstCreateTests(_A1Base):
    """F1/F6 — definition-only body creates a rule with derived flat columns."""

    def test_create_definition_only_field_level(self):
        r = self.client.post(f'{BASE}/rules/', {'definition': _definition()}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['name'], 'Amount in range')
        self.assertEqual(r.data['rule_type'], 'range')
        self.assertEqual(r.data['rule_level'], 'field_validation')
        self.assertEqual(r.data['severity'], 'error')
        self.assertEqual(r.data['dimension'], 'validity')
        self.assertTrue(r.data['is_active'])

    def test_create_definition_only_business_level(self):
        d = _definition(
            name='Row count threshold', level='business', type='threshold',
            severity='warn', params={'operator': 'gte', 'value': 5})
        r = self.client.post(f'{BASE}/rules/', {'definition': d}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['rule_level'], 'business_rule')
        self.assertEqual(r.data['rule_type'], 'threshold')

    def test_create_definition_only_with_empty_bindings_write(self):
        """Standalone authoring: explicit empty field_assignments_write is valid."""
        body = {'definition': _definition(), 'field_assignments_write': []}
        r = self.client.post(f'{BASE}/rules/', body, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['name'], 'Amount in range')

    def test_create_definition_rejects_anomaly_detect(self):
        """anomaly_detect is intentionally not user-creatable (8-type whitelist)."""
        d = _definition(name='Anomaly rule', type='anomaly_detect', params={})
        r = self.client.post(f'{BASE}/rules/', {'definition': d}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class DriftGuardTests(_A1Base):
    """F3/D4 — PATCH with [] must not silently drop existing bindings."""

    def setUp(self):
        super().setUp()
        self.rule = DQRule.objects.create(
            name='Bound Rule', rule_type='not_null', rule_level='field_validation',
            is_active=True, created_by=self.admin,
            definition=_definition(name='Bound Rule', type='not_null', params={}),
        )
        RuleFieldAssignment.objects.create(
            rule=self.rule, data_table=self.table, data_field=self.field)

    def test_patch_empty_assignments_without_flag_rejected(self):
        r = self.client.patch(
            f'{BASE}/rules/{self.rule.id}/', {'field_assignments_write': []}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        details = r.data.get('details', r.data)
        self.assertIn('field_assignments_write', details)
        self.assertIn('Would drop', str(details['field_assignments_write']))
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.field_assignments.count(), 1)

    def test_patch_empty_assignments_with_flag_confirmed(self):
        body = {'field_assignments_write': [], 'replace_assignments': True}
        r = self.client.patch(f'{BASE}/rules/{self.rule.id}/', body, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.field_assignments.count(), 0)


class VersionBumpTests(_A1Base):
    """F7 — PATCHing the definition bumps the monotonic version."""

    def setUp(self):
        super().setUp()
        self.rule = DQRule.objects.create(
            name='Versioned Rule', rule_type='range', rule_level='field_validation',
            is_active=True, created_by=self.admin, definition=_definition())
        self.assertEqual(self.rule.version, 1)

    def test_patch_definition_bumps_version(self):
        new_def = _definition(name='Amount in range v2', params={'min': 1, 'max': 99})
        r = self.client.patch(
            f'{BASE}/rules/{self.rule.id}/', {'definition': new_def}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['version'], 2)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.version, 2)

    def test_patch_same_definition_does_not_bump(self):
        r = self.client.patch(
            f'{BASE}/rules/{self.rule.id}/', {'definition': _definition()}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['version'], 1)


class FlatColumnReconcileTests(_A1Base):
    """D1 — flat-only PATCH columns must not be reverted by DQRule.save().

    DQRule.save() re-derives name/severity/dimension/is_active from
    `definition`, so a flat edit (toggle, rename) would be silently reverted
    unless the serializer reconciles the flat column back into the definition.
    """

    def setUp(self):
        super().setUp()
        self.rule = DQRule.objects.create(
            name='Amount in range', rule_type='range', rule_level='field_validation',
            is_active=True, created_by=self.admin,
            definition=_definition(name='Amount in range', active=True),
        )

    def test_flat_only_is_active_toggle_persists(self):
        r = self.client.patch(
            f'{BASE}/rules/{self.rule.id}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertFalse(r.data['is_active'])
        self.rule.refresh_from_db()
        self.assertFalse(self.rule.is_active)
        self.assertFalse(self.rule.definition.get('active'))

    def test_flat_only_rename_persists(self):
        r = self.client.patch(
            f'{BASE}/rules/{self.rule.id}/', {'name': 'Renamed Rule'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['name'], 'Renamed Rule')
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.name, 'Renamed Rule')
        self.assertEqual(self.rule.definition.get('name'), 'Renamed Rule')

    def test_flat_only_toggle_does_not_bump_version(self):
        r = self.client.patch(
            f'{BASE}/rules/{self.rule.id}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.version, 1)

    def test_definition_with_flat_override_merges_and_bumps(self):
        body = {
            'definition': _definition(name='Stale', active=True),
            'name': 'Flat Name',
            'severity': 'warn',
        }
        r = self.client.patch(f'{BASE}/rules/{self.rule.id}/', body, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['name'], 'Flat Name')
        self.assertEqual(r.data['severity'], 'warn')
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.name, 'Flat Name')
        self.assertEqual(self.rule.definition.get('name'), 'Flat Name')
        self.assertEqual(self.rule.definition.get('severity'), 'warn')
        self.assertEqual(self.rule.version, 2)
