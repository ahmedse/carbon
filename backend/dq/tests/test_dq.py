from django.test import TestCase

from core.models import Module
from dataschema.models import DataField, DataRow, DataTable
from dq.services import profile_table, run_dq


class DQTests(TestCase):
    def setUp(self):
        self.user = self._create_user()
        # project removed
        self.module = Module.objects.create(project=self.project, name='Module 1', description='demo', created_by=self.user)
        self.table = DataTable.objects.create(title='Test Table', name='test_table', module=self.module, created_by=self.user)
        self.field = DataField.objects.create(data_table=self.table, name='score', label='Score', type='number', required=True, created_by=self.user)
        DataRow.objects.create(data_table=self.table, values={'score': 1}, created_by=self.user)
        DataRow.objects.create(data_table=self.table, values={'score': None}, created_by=self.user)

    def _create_user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(username='dquser', email='dq@example.com', password='Password123!')

    def test_profile_table_and_run_dq(self):
        profile = profile_table(self.table.id)
        self.assertEqual(profile['row_count'], 2)
        self.assertIn('fields', profile)

        result = run_dq(self.table.id)
        self.assertGreaterEqual(len(result['results']), 1)
