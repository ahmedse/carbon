# backend/mdm/tests/test_reference_sets.py
"""
Tests for ReferenceSet API endpoints with RBAC enforcement.
Tests verify:
1. Unauthenticated users get 401
2. Authenticated users can list reference sets (filtered by org_unit scope)
3. Creating reference set auto-assigns steward
4. Non-steward cannot edit (403)
5. Steward can edit
6. Soft delete (is_active=False)
7. Add value to reference set
"""
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from mdm.models import ReferenceSet, ReferenceValue, OrgUnit
from accounts.models import ScopedRole
from catalog.models import DataDomain
from django.contrib.auth.models import Group

User = get_user_model()


class ReferenceSetViewSetTest(APITestCase):
    """Tests for ReferenceSet API endpoints."""
    
    def setUp(self):
        """Set up test users, org units, domains, and groups."""
        self.client = APIClient()
        
        # Create users
        self.user1 = User.objects.create_user('user1', password='pass123')
        self.user2 = User.objects.create_user('user2', password='pass123')
        self.admin_user = User.objects.create_user('admin', password='pass123')
        self.admin_user.is_staff = True
        self.admin_user.save()
        
        # Create org units
        self.org_unit_1 = OrgUnit.objects.create(
            name='Engineering', code='ENG', org_type='college'
        )
        self.org_unit_2 = OrgUnit.objects.create(
            name='Medicine', code='MED', org_type='college'
        )
        
        # Create data domains
        self.domain_1 = DataDomain.objects.create(
            name='Engineering Domain', id=self.org_unit_1.id
        )
        self.domain_2 = DataDomain.objects.create(
            name='Medicine Domain', id=self.org_unit_2.id
        )
        
        # Create admin group
        self.admins_group = Group.objects.create(name='admins_group')
        
        # Assign org units to users via ScopedRole
        ScopedRole.objects.create(
            user=self.user1, group=self.admins_group, org_unit=self.org_unit_1, is_active=True
        )
        ScopedRole.objects.create(
            user=self.user2, group=self.admins_group, org_unit=self.org_unit_2, is_active=True
        )

    def test_unauthenticated_get_401(self):
        """Test: unauthenticated user gets 401."""
        response = self.client.get('/api/v1/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_list_reference_sets(self):
        """Test: authenticated user can list reference sets in their scope."""
        # Create reference set for org_unit_1
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        # User1 should see it (has access to org_unit_1)
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Status')
        
        # User2 should NOT see it (has access to org_unit_2, not org_unit_1)
        self.client.force_authenticate(user=self.user2)
        response = self.client.get('/api/v1/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_create_sets_steward_to_current_user(self):
        """Test: creating reference set auto-assigns steward to current user."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.post('/api/v1/mdm/reference-sets/', {
            'name': 'Department', 'domain': self.domain_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ref_set = ReferenceSet.objects.get(name='Department')
        self.assertEqual(ref_set.steward, self.user1)

    def test_non_steward_cannot_edit_403(self):
        """Test: non-steward gets 403 Forbidden on update."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user2)
        response = self.client.put(f'/api/v1/mdm/reference-sets/{ref_set.id}/', {
            'name': 'Modified', 'domain': self.domain_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_steward_can_edit(self):
        """Test: steward can edit reference set."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.put(f'/api/v1/mdm/reference-sets/{ref_set.id}/', {
            'name': 'Status Updated', 'domain': self.domain_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ref_set.refresh_from_db()
        self.assertEqual(ref_set.name, 'Status Updated')

    def test_admin_can_edit_any_reference_set(self):
        """Test: admin user can edit any reference set."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.put(f'/api/v1/mdm/reference-sets/{ref_set.id}/', {
            'name': 'Admin Modified', 'domain': self.domain_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_soft_delete_on_destroy(self):
        """Test: deleting reference set sets is_active=False."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(f'/api/v1/mdm/reference-sets/{ref_set.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        ref_set.refresh_from_db()
        self.assertFalse(ref_set.is_active)

    def test_add_value_to_reference_set(self):
        """Test: steward can add value to reference set."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/v1/mdm/reference-sets/{ref_set.id}/add_value/', {
            'code': 'ACTIVE', 'label': 'Active', 'sort_order': 1
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify value was created
        value = ReferenceValue.objects.get(code='ACTIVE')
        self.assertEqual(value.reference_set, ref_set)
        self.assertEqual(value.label, 'Active')

    def test_non_steward_cannot_add_value_403(self):
        """Test: non-steward gets 403 when trying to add value."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f'/api/v1/mdm/reference-sets/{ref_set.id}/add_value/', {
            'code': 'ACTIVE', 'label': 'Active', 'sort_order': 1
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
