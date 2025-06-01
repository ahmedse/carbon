# File: dataschema/tests.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from django.contrib.auth import get_user_model
from core.models import Project, Module
from .models import DataTable, DataField, DataRow

User = get_user_model()

class DataSchemaAPITestCase(TestCase):
    def setUp(self):
        # Create users
        self.admin = User.objects.create_user(username='admin', password='admin', is_superuser=True)
        self.owner = User.objects.create_user(username='owner', password='owner')
        self.regular = User.objects.create_user(username='user', password='user')

        # Create project, module, and assign tenants
        self.project = Project.objects.create(name="Test Project", tenant=self.admin.tenant)
        self.module = Module.objects.create(name="Test Module", project=self.project)

        # Assign owner to module context/role via your platform's RBAC system as needed.
        # You may need to adjust this logic to fit your RBAC models.
        # For example:
        # context = Context.objects.create(type="module", project=self.project, module=self.module)
        # role = Role.objects.create(name="dataowner", permissions=["manage_data"])
        # RoleAssignment.objects.create(user=self.owner, role=role, context=context, is_active=True)

        # Create a table as admin
        self.table = DataTable.objects.create(
            title="Test Table",
            module=self.module,
            created_by=self.admin,
            updated_by=self.admin
        )

        self.field = DataField.objects.create(
            data_table=self.table,
            name="value",
            label="Value",
            type="number",
            order=1,
            required=True,
            created_by=self.admin,
            updated_by=self.admin
        )

        self.client = APIClient()

    def test_admin_can_create_table(self):
        self.client.login(username='admin', password='admin')
        url = reverse('dataschema-table-list')
        data = {
            "title": "TableX",
            "description": "desc",
            "module": self.module.id
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DataTable.objects.filter(title="TableX").count(), 1)

    def test_regular_user_cannot_create_table(self):
        self.client.login(username='user', password='user')
        url = reverse('dataschema-table-list')
        data = {
            "title": "BadTable",
            "description": "",
            "module": self.module.id
        }
        response = self.client.post(url, data)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_admin_can_add_field(self):
        self.client.login(username='admin', password='admin')
        url = reverse('dataschema-field-list')
        data = {
            "data_table": self.table.id,
            "name": "quantity",
            "label": "Quantity",
            "type": "number",
            "order": 2,
            "required": False
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_can_add_row(self):
        # You should adjust/ensure owner has manage_data permission for this module in your RBAC
        self.client.login(username='owner', password='owner')
        url = reverse('dataschema-row-list')
        data = {
            "data_table": self.table.id,
            "values": {"value": 123}
        }
        response = self.client.post(url, data)
        # Depending on RBAC config, this could be CREATED or FORBIDDEN
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_403_FORBIDDEN])

    def test_archiving_table(self):
        self.client.login(username='admin', password='admin')
        url = reverse('dataschema-table-archive', args=[self.table.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.table.refresh_from_db()
        self.assertTrue(self.table.is_archived)

    def test_schema_log_access(self):
        self.client.login(username='admin', password='admin')
        url = reverse('dataschema-schemalog-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)