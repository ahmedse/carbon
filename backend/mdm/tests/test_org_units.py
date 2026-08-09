"""Tests for OrgUnit hierarchy CRUD and tree operations."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import ScopedRole
from mdm.models import OrgUnit


User = get_user_model()


def _list_data(resp):
    """Unwrap a list response body regardless of pagination shape.

    config.pagination.CarbonPageNumberPagination skips pagination when pytest
    is in sys.modules, so list responses are either {count, page_size, page,
    results} dicts (Django test runs) or plain lists (combined runs with
    pytest-importing modules). PB-15 / BUG-06 taught us to be shape-agnostic.
    """
    data = resp.data
    return data['results'] if isinstance(data, dict) else data


class OrgUnitCRUDTestCase(TestCase):
    """Test CRUD operations on org units."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin', password='admin', is_staff=True, is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='user1', password='user1'
        )
        self.org_root = OrgUnit.objects.create(
            name='Company', slug='company', code='CO',
            org_type='company', is_active=True
        )

    def test_list_org_units_authenticated(self):
        """Authenticated user can list org units."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get('/carbon-api/mdm/org-units/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_org_units_unauthenticated(self):
        """Unauthenticated user gets 401."""
        response = self.client.get('/carbon-api/mdm/org-units/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_org_unit_admin(self):
        """Admin can create org unit."""
        self.client.force_authenticate(self.admin_user)
        payload = {
            'name': 'Finance',
            'code': 'FIN',
            'org_type': 'division',
            'parent': self.org_root.id,
            'description': 'Finance division'
        }
        response = self.client.post('/carbon-api/mdm/org-units/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Finance')
        self.assertTrue(OrgUnit.objects.filter(name='Finance').exists())

    def test_retrieve_org_unit(self):
        """Can retrieve single org unit."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/carbon-api/mdm/org-units/{self.org_root.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.org_root.id)
        self.assertEqual(response.data['name'], 'Company')

    def test_update_org_unit(self):
        """Admin can update org unit."""
        self.client.force_authenticate(self.admin_user)
        payload = {'description': 'Updated company description'}
        response = self.client.patch(f'/carbon-api/mdm/org-units/{self.org_root.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org_root.refresh_from_db()
        self.assertEqual(self.org_root.description, 'Updated company description')

    def test_delete_org_unit_no_children(self):
        """Can soft-delete org unit without children."""
        org = OrgUnit.objects.create(name='Temp', code='TMP', org_type='other')
        self.client.force_authenticate(self.admin_user)
        response = self.client.delete(f'/carbon-api/mdm/org-units/{org.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        org.refresh_from_db()
        self.assertFalse(org.is_active)


class OrgUnitHierarchyTestCase(TestCase):
    """Test hierarchy and tree operations."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin', password='admin', is_staff=True, is_superuser=True
        )
        self.org_root = OrgUnit.objects.create(
            name='Company', slug='company', code='CO', org_type='company'
        )
        self.org_division = OrgUnit.objects.create(
            name='Engineering', slug='company-eng', code='ENG',
            org_type='division', parent=self.org_root
        )
        self.org_dept = OrgUnit.objects.create(
            name='Backend', slug='company-eng-backend', code='BACKEND',
            org_type='department', parent=self.org_division
        )

    def test_tree_endpoint(self):
        """GET /org-units/{id}/tree/ returns subtree."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/carbon-api/mdm/org-units/{self.org_root.id}/tree/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should contain root, division, and dept
        self.assertEqual(len(response.data), 3)
        ids = {item['id'] for item in response.data}
        self.assertIn(self.org_root.id, ids)
        self.assertIn(self.org_division.id, ids)
        self.assertIn(self.org_dept.id, ids)

    def test_ancestors_endpoint(self):
        """GET /org-units/{id}/ancestors/ returns path to root."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/carbon-api/mdm/org-units/{self.org_dept.id}/ancestors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return org_root and org_division (ancestors, not including self)
        self.assertEqual(len(response.data), 2)
        # First should be root, second should be division
        self.assertEqual(response.data[0]['id'], self.org_root.id)
        self.assertEqual(response.data[1]['id'], self.org_division.id)

    def test_full_path_in_serializer(self):
        """Serializer includes full_path field."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/carbon-api/mdm/org-units/{self.org_dept.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # full_path should contain all names
        self.assertIn('Backend', response.data['full_path'])
        self.assertIn('Engineering', response.data['full_path'])
        self.assertIn('Company', response.data['full_path'])

    def test_children_count(self):
        """Serializer includes children_count."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/carbon-api/mdm/org-units/{self.org_root.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # org_root has 1 child (org_division)
        self.assertEqual(response.data['children_count'], 1)

    def test_descendants_count(self):
        """Serializer includes descendants_count."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/carbon-api/mdm/org-units/{self.org_root.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # org_root has 2 descendants (division and dept, not including self)
        self.assertEqual(response.data['descendants_count'], 2)


class OrgUnitValidationTestCase(TestCase):
    """Test validation rules."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin', password='admin', is_staff=True, is_superuser=True
        )
        self.org_root = OrgUnit.objects.create(
            name='Company', slug='company', code='CO', org_type='company'
        )
        self.org_division = OrgUnit.objects.create(
            name='Engineering', slug='company-eng', code='ENG',
            org_type='division', parent=self.org_root
        )

    def test_circular_reference_prevention(self):
        """Cannot set parent to be a descendant (circular ref)."""
        self.client.force_authenticate(self.admin_user)
        # Try to set org_root's parent to org_division (which is a descendant)
        payload = {'parent': self.org_division.id}
        response = self.client.patch(f'/carbon-api/mdm/org-units/{self.org_root.id}/', payload)
        # Should be 400 for validation error (circular reference)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unique_name_within_parent(self):
        """Cannot create two children with same name under same parent."""
        # Create first child
        OrgUnit.objects.create(
            name='Duplicate', parent=self.org_root, code='DUP1', org_type='division'
        )
        self.client.force_authenticate(self.admin_user)
        # Try to create another with same name
        payload = {
            'name': 'Duplicate',
            'code': 'DUP2',
            'org_type': 'division',
            'parent': self.org_root.id
        }
        response = self.client.post('/carbon-api/mdm/org-units/', payload)
        # Should be 400 for validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete_sets_is_active_false(self):
        """Soft delete sets is_active=False."""
        org = OrgUnit.objects.create(
            name='ToDelete', code='DEL', org_type='other', is_active=True
        )
        self.client.force_authenticate(self.admin_user)
        response = self.client.delete(f'/carbon-api/mdm/org-units/{org.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        org.refresh_from_db()
        self.assertFalse(org.is_active)


class OrgUnitRbacScopingTestCase(TestCase):
    """BUG-03 (F-07): /mdm/org-units/ must scope results to the user's
    org subtree (get_visible_org_units), not return all org units."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin-rbac', password='admin', is_staff=True, is_superuser=True
        )
        # Tree: AAST -> CollegeEng -> Transportation (+ Facilities sibling)
        self.aast = OrgUnit.objects.create(
            name='AAST', slug='aast', code='AAST', org_type='company'
        )
        self.college = OrgUnit.objects.create(
            name='College of Engineering', slug='college-eng', code='CE',
            org_type='college', parent=self.aast,
        )
        self.transport = OrgUnit.objects.create(
            name='Transportation', slug='transportation', code='TR',
            org_type='department', parent=self.college,
        )
        self.facilities = OrgUnit.objects.create(
            name='Facilities', slug='facilities', code='FA',
            org_type='department', parent=self.college,
        )
        # Data owner scoped to Transportation (mirrors alamein.transport)
        self.data_owner = User.objects.create_user(
            username='alamein.transport', password='Transport_123'
        )
        group, _ = Group.objects.get_or_create(name='dataowners_group')
        ScopedRole.objects.create(
            user=self.data_owner, group=group, org_unit=self.transport
        )

    def test_data_owner_sees_only_own_subtree(self):
        """Bug repro: data owner gets ALL org units; must get only their subtree."""
        self.client.force_authenticate(self.data_owner)
        response = self.client.get('/carbon-api/mdm/org-units/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {ou['name'] for ou in _list_data(response)}
        self.assertEqual(names, {'Transportation'})

    def test_scoped_user_cannot_retrieve_out_of_scope_org(self):
        """Data owner must NOT be able to retrieve an org outside their subtree."""
        self.client.force_authenticate(self.data_owner)
        response = self.client.get(f'/carbon-api/mdm/org-units/{self.facilities.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_sees_all_org_units(self):
        """Admins/superusers keep full visibility."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get('/carbon-api/mdm/org-units/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {ou['name'] for ou in _list_data(response)}
        self.assertEqual(names, {'AAST', 'College of Engineering', 'Transportation', 'Facilities'})

    def test_user_without_roles_sees_nothing(self):
        """Restrictive default: authenticated user with no org scope sees []."""
        orphan = User.objects.create_user(username='no-scope', password='pass123')
        self.client.force_authenticate(orphan)
        response = self.client.get('/carbon-api/mdm/org-units/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(_list_data(response), [])
    # ── BUG-04 (E16): list-level /mdm/org-units/tree/ ──────────

    def test_list_level_tree_returns_nested_visible_tree(self):
        """BUG-04 repro: GET /mdm/org-units/tree/ must return the full visible
        org tree as a nested structure (was 404 — only /{id}/tree/ existed)."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get('/carbon-api/mdm/org-units/tree/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual([r['name'] for r in response.data], ['AAST'])
        root = response.data[0]
        self.assertEqual(
            [c['name'] for c in root['children']],
            ['College of Engineering'],
        )
        grandchildren = root['children'][0]['children']
        self.assertEqual(
            {g['name'] for g in grandchildren},
            {'Transportation', 'Facilities'},
        )

    def test_list_level_tree_scoped_to_user_subtree(self):
        """List-level tree must respect RBAC visibility (BUG-03 rule): the
        scoped data owner sees only their own unit as the tree root."""
        self.client.force_authenticate(self.data_owner)
        response = self.client.get('/carbon-api/mdm/org-units/tree/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([r['name'] for r in response.data], ['Transportation'])
        # No children below Transportation in this fixture
        self.assertNotIn('children', response.data[0])

    def test_list_level_tree_empty_for_no_role_user(self):
        """Authenticated user with no org scope sees an empty tree."""
        orphan = User.objects.create_user(username='no-scope2', password='pass123')
        self.client.force_authenticate(orphan)
        response = self.client.get('/carbon-api/mdm/org-units/tree/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])