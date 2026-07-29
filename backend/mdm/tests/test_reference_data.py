from django.test import TestCase

from core.models import Module
from dataschema.models import DataField, DataTable
from mdm.models import ReferenceSet, ReferenceValue


class ReferenceDataTests(TestCase):
    def setUp(self):
        self.user = self._create_user()
        from mdm.models import OrgUnit
        self.org_unit = OrgUnit.objects.create(name='Test Org', slug='test-org', code='TEST', org_type='college')
        self.module = Module.objects.create(name='Module 1', description='demo', scope=1, org_unit=self.org_unit)
        self.table = DataTable.objects.create(name='test_table', module=self.module)
        self.field = DataField.objects.create(data_table=self.table, name='scope', label='Scope', type='reference', required=False)

    def _create_user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(username='mdmuser', email='mdm@example.com', password='Password123!')

    def test_reference_set_values_are_available(self):
        reference_set = ReferenceSet.objects.create(name='Emission Scopes', slug='emission-scopes', steward=self.user, domain=None)
        ReferenceValue.objects.create(reference_set=reference_set, code='scope1', label='Scope 1', is_active=True)
        ReferenceValue.objects.create(reference_set=reference_set, code='scope2', label='Scope 2', is_active=True)

        self.field.reference_set = reference_set
        self.field.save()

        values = reference_set.get_active_values()
        self.assertEqual(values.count(), 2)
