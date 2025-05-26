# File: accounts/tests.py
# Purpose: Basic test cases for the multi-tenant RBAC structure.

from django.test import TestCase
from accounts.models import Tenant, User, Project, Module, Role, Context, RoleAssignment

class RBACModelTests(TestCase):
    def setUp(self):
        # Create tenants
        self.tenant1 = Tenant.objects.create(name="Tenant A")
        self.tenant2 = Tenant.objects.create(name="Tenant B")

        # Users
        self.user1 = User.objects.create_user(username="user1", password="pass", tenant=self.tenant1)
        self.user2 = User.objects.create_user(username="user2", password="pass", tenant=self.tenant2)

        # Projects & modules
        self.project1 = Project.objects.create(name="Project 1", tenant=self.tenant1)
        self.project2 = Project.objects.create(name="Project 2", tenant=self.tenant2)
        self.module1 = Module.objects.create(name="Module 1", project=self.project1)
        self.module2 = Module.objects.create(name="Module 2", project=self.project2)

        # Roles
        self.role_mgr = Role.objects.create(name="manager", permissions=["manage_project", "view_data"])
        self.role_viewer = Role.objects.create(name="viewer", permissions=["view_data"])

        # Contexts
        self.project1_context = Context.objects.create(type="project", project=self.project1)
        self.module1_context = Context.objects.create(type="module", module=self.module1)

        # RoleAssignments
        self.ra1 = RoleAssignment.objects.create(user=self.user1, role=self.role_mgr, context=self.project1_context)
        self.ra2 = RoleAssignment.objects.create(user=self.user1, role=self.role_viewer, context=self.module1_context)

    def test_user_belongs_to_tenant(self):
        self.assertEqual(self.user1.tenant, self.tenant1)
        self.assertEqual(self.user2.tenant, self.tenant2)

    def test_project_belongs_to_tenant(self):
        self.assertEqual(self.project1.tenant, self.tenant1)
        self.assertEqual(self.project2.tenant, self.tenant2)

    def test_module_belongs_to_project(self):
        self.assertEqual(self.module1.project, self.project1)
        self.assertEqual(self.module2.project, self.project2)

    def test_role_assignment(self):
        self.assertEqual(self.ra1.user, self.user1)
        self.assertEqual(self.ra1.role, self.role_mgr)
        self.assertEqual(self.ra1.context, self.project1_context)

    def test_tenant_isolation(self):
        # User1 should not see projects/modules of tenant2
        user1_project_ids = Project.objects.filter(tenant=self.user1.tenant).values_list("id", flat=True)
        self.assertNotIn(self.project2.id, user1_project_ids)

    def test_permissions(self):
        # Check user1's permissions in project1 context
        perms_project1 = [ra.role.permissions for ra in RoleAssignment.objects.filter(user=self.user1, context=self.project1_context)]
        self.assertIn("manage_project", perms_project1[0])
        self.assertIn("view_data", perms_project1[0])

        # Check user1's permissions in module1 context
        perms_module1 = [ra.role.permissions for ra in RoleAssignment.objects.filter(user=self.user1, context=self.module1_context)]
        self.assertIn("view_data", perms_module1[0])

    def test_no_cross_tenant_role_assignments(self):
        # User1 (tenant1) should not have assignments for tenant2's contexts
        context2 = Context.objects.create(type="project", project=self.project2)
        assignment_count = RoleAssignment.objects.filter(user=self.user1, context=context2).count()
        self.assertEqual(assignment_count, 0)