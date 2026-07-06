from django.test import TestCase

from core.models import Module
from dataschema.models import DataField, DataTable
from mdm.models import ReferenceSet, ReferenceValue


class ReferenceDataTests(TestCase):
    def setUp(self):
        self.user = self._create_user()
        # project removed
        self.module = Module.objects.create(project=self.project, name='Module 1', description='demo', created_by=self.user)
        self.table = DataTable.objects.create(title='Test Table', name='test_table', module=self.module, created_by=self.user)
        self.field = DataField.objects.create(data_table=self.table, name='scope', label='Scope', type='reference', created_by=self.user)

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
