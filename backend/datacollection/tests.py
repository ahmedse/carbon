from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Tenant, Context
from core.models import Project, Module
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
    ContextAssignment
)

User = get_user_model()

class DataCollectionModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="TestTenant")
        self.project = Project.objects.create(name="TestProject", tenant=self.tenant)
        self.module = Module.objects.create(name="TestModule", project=self.project)
        self.context = Context.objects.create(name="TestContext", project=self.project)
        self.user = User.objects.create_user(
            username="testuser",
            password="password",
            tenant=self.tenant
        )

    def test_reading_item_definition_belongs_to_tenant(self):
        item = ReadingItemDefinition.objects.create(
            name="Item1",
            data_type="number",
            context=self.context,
            module=self.module
        )
        self.assertEqual(item.context.project.tenant, self.tenant)
        self.assertEqual(item.module.project.tenant, self.tenant)

    def test_reading_template_belongs_to_tenant(self):
        template = ReadingTemplate.objects.create(
            name="Template1",
            context=self.context,
            module=self.module
        )
        self.assertEqual(template.context.project.tenant, self.tenant)
        self.assertEqual(template.module.project.tenant, self.tenant)

    def test_entry_creation(self):
        item = ReadingItemDefinition.objects.create(
            name="Item2",
            data_type="number",
            context=self.context,
            module=self.module
        )
        template = ReadingTemplate.objects.create(
            name="Template2",
            context=self.context,
            module=self.module
        )
        template_field = ReadingTemplateField.objects.create(
            template=template,
            field=item,
            order=1
        )
        entry = ReadingEntry.objects.create(
            template=template,
            template_version=template.version,
            context=self.context,
            item=item,
            data={"value": 42},
            period_start="2024-01-01",
            period_end="2024-01-01",
            submitted_by=self.user
        )
        self.assertEqual(entry.context.project.tenant, self.tenant)
        self.assertEqual(entry.submitted_by.tenant, self.tenant)

    # Further tests can be added for EvidenceFile, ContextAssignment, and API access