# File: core/tests.py

from django.test import TestCase
from accounts.models import Tenant
from .models import Project, Cycle, Module

class CoreModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="TestTenant")
        self.project = Project.objects.create(name="TestProject", tenant=self.tenant)
        self.cycle = Cycle.objects.create(name="Cycle1", project=self.project)
        self.module = Module.objects.create(name="Module1", project=self.project)

    def test_project_str(self):
        self.assertEqual(str(self.project), "TestProject")

    def test_cycle_str(self):
        self.assertEqual(str(self.cycle), "Cycle1 (TestProject)")

    def test_module_str(self):
        self.assertEqual(str(self.module), "Module1 (TestProject)")

    def test_project_tenant(self):
        self.assertEqual(self.project.tenant, self.tenant)

    def test_cycle_project(self):
        self.assertEqual(self.cycle.project, self.project)

    def test_module_project(self):
        self.assertEqual(self.module.project, self.project)