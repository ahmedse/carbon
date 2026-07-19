"""Tests for OrgUnit hierarchy CRUD and tree operations."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import ScopedRole
from mdm.models import OrgUnit


User = get_user_model()


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
        response = self.client.get('/mdm/org-units/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_org_units_unauthenticated(self):
        """Unauthenticated user gets 401."""
        response = self.client.get('/mdm/org-units/')
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
        response = self.client.post('/mdm/org-units/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Finance')
        self.assertTrue(OrgUnit.objects.filter(name='Finance').exists())

    def test_retrieve_org_unit(self):
        """Can retrieve single org unit."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/mdm/org-units/{self.org_root.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.org_root.id)
        self.assertEqual(response.data['name'], 'Company')

    def test_update_org_unit(self):
        """Admin can update org unit."""
        self.client.force_authenticate(self.admin_user)
        payload = {'description': 'Updated company description'}
        response = self.client.patch(f'/mdm/org-units/{self.org_root.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org_root.refresh_from_db()
        self.assertEqual(self.org_root.description, 'Updated company description')

    def test_delete_org_unit_no_children(self):
        """Can soft-delete org unit without children."""
        org = OrgUnit.objects.create(name='Temp', code='TMP', org_type='other')
        self.client.force_authenticate(self.admin_user)
        response = self.client.delete(f'/mdm/org-units/{org.id}/')
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
        response = self.client.get(f'/mdm/org-units/{self.org_root.id}/tree/')
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
        response = self.client.get(f'/mdm/org-units/{self.org_dept.id}/ancestors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return org_root and org_division (ancestors, not including self)
        self.assertEqual(len(response.data), 2)
        # First should be root, second should be division
        self.assertEqual(response.data[0]['id'], self.org_root.id)
        self.assertEqual(response.data[1]['id'], self.org_division.id)

    def test_full_path_in_serializer(self):
        """Serializer includes full_path field."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/mdm/org-units/{self.org_dept.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # full_path should contain all names
        self.assertIn('Backend', response.data['full_path'])
        self.assertIn('Engineering', response.data['full_path'])
        self.assertIn('Company', response.data['full_path'])

    def test_children_count(self):
        """Serializer includes children_count."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/mdm/org-units/{self.org_root.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # org_root has 1 child (org_division)
        self.assertEqual(response.data['children_count'], 1)

    def test_descendants_count(self):
        """Serializer includes descendants_count."""
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/mdm/org-units/{self.org_root.id}/')
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
        response = self.client.patch(f'/mdm/org-units/{self.org_root.id}/', payload)
        # Should be 403 for this invalid operation
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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
        response = self.client.post('/mdm/org-units/', payload)
        # Should be 400 for validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete_sets_is_active_false(self):
        """Soft delete sets is_active=False."""
        org = OrgUnit.objects.create(
            name='ToDelete', code='DEL', org_type='other', is_active=True
        )
        self.client.force_authenticate(self.admin_user)
        response = self.client.delete(f'/mdm/org-units/{org.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        org.refresh_from_db()
        self.assertFalse(org.is_active)
