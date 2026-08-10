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
            name='Engineering', code='ENG', org_type='college', slug='engineering'
        )
        self.org_unit_2 = OrgUnit.objects.create(
            name='Medicine', code='MED', org_type='college', slug='medicine'
        )
        
        # Create data domains
        self.domain_1 = DataDomain.objects.create(
            name='Engineering Domain', slug='engineering-domain', id=self.org_unit_1.id
        )
        self.domain_2 = DataDomain.objects.create(
            name='Medicine Domain', slug='medicine-domain', id=self.org_unit_2.id
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
        response = self.client.get('/carbon-api/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_list_reference_sets(self):
        """Test: authenticated users see all active reference sets (shared governance data)."""
        # Create reference set for org_unit_1
        ref_set = ReferenceSet.objects.create(
            name='Status Test Unique', slug='status-test-unique', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        # User1 should see it
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/carbon-api/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ref_set_names = [item['name'] for item in data]
        self.assertIn('Status Test Unique', ref_set_names)
        
        # User2 should ALSO see it (reference sets are shared governance resources)
        self.client.force_authenticate(user=self.user2)
        response = self.client.get('/carbon-api/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ref_set_names = [item['name'] for item in data]
        self.assertIn('Status Test Unique', ref_set_names)

    def test_create_sets_steward_to_current_user(self):
        """Test: creating reference set auto-assigns steward to current user."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.post('/carbon-api/mdm/reference-sets/', {
            'name': 'Department', 'domain': self.domain_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ref_set = ReferenceSet.objects.get(name='Department')
        self.assertEqual(ref_set.steward, self.user1)

    def test_non_steward_cannot_edit_403(self):
        """Test: non-steward gets 403 Forbidden on update."""
        # Place ref set in domain_2 so user2 (scoped to org_unit_2) can see it
        ref_set = ReferenceSet.objects.create(
            name='StatusNonSteward', slug='status-nonsteward', steward=self.user1, domain=self.domain_2, is_active=True
        )
        
        self.client.force_authenticate(user=self.user2)
        response = self.client.put(f'/carbon-api/mdm/reference-sets/{ref_set.id}/', {
            'name': 'Modified', 'domain': self.domain_2.id
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_steward_can_edit(self):
        """Test: steward can edit reference set."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.put(f'/carbon-api/mdm/reference-sets/{ref_set.id}/', {
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
        response = self.client.put(f'/carbon-api/mdm/reference-sets/{ref_set.id}/', {
            'name': 'Admin Modified', 'domain': self.domain_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_soft_delete_on_destroy(self):
        """Test: deleting reference set sets is_active=False."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(f'/carbon-api/mdm/reference-sets/{ref_set.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        ref_set.refresh_from_db()
        self.assertFalse(ref_set.is_active)

    def test_add_value_to_reference_set(self):
        """Test: steward can add value to reference set."""
        ref_set = ReferenceSet.objects.create(
            name='Status', slug='status', steward=self.user1, domain=self.domain_1, is_active=True
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/carbon-api/mdm/reference-sets/{ref_set.id}/add_value/', {
            'code': 'ACTIVE', 'label': 'Active', 'sort_order': 1
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify value was created
        value = ReferenceValue.objects.get(code='ACTIVE')
        self.assertEqual(value.reference_set, ref_set)
        self.assertEqual(value.label, 'Active')

    def test_non_steward_cannot_add_value_403(self):
        """Test: non-steward gets 403 when trying to add value."""
        # Place ref set in domain_2 so user2 can see it
        ref_set = ReferenceSet.objects.create(
            name='StatusNonStewardAdd', slug='status-nonsteward-add', steward=self.user1, domain=self.domain_2, is_active=True
        )
        
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f'/carbon-api/mdm/reference-sets/{ref_set.id}/add_value/', {
            'code': 'ACTIVE', 'label': 'Active', 'sort_order': 1
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Regression: steward reassignment (audit finding: steward field was read-only) ---

    def test_steward_can_reassign_stewardship(self):
        """Steward may transfer ownership of a reference set to another user."""
        ref_set = ReferenceSet.objects.create(
            name='StewardTransfer', slug='steward-transfer', steward=self.user1, domain=self.domain_1, is_active=True
        )
        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(
            f'/carbon-api/mdm/reference-sets/{ref_set.id}/',
            {'steward': self.user2.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ref_set.refresh_from_db()
        self.assertEqual(ref_set.steward, self.user2)

    def test_non_steward_cannot_reassign_stewardship(self):
        """Non-steward cannot change steward (403)."""
        ref_set = ReferenceSet.objects.create(
            name='StewardBlock', slug='steward-block', steward=self.user1, domain=self.domain_1, is_active=True
        )
        self.client.force_authenticate(user=self.user2)
        response = self.client.patch(
            f'/carbon-api/mdm/reference-sets/{ref_set.id}/',
            {'steward': self.user2.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Regression: N+1 value_count uses view annotation ---

    def test_value_count_uses_annotation(self):
        """List response value_count reflects active values (annotation path)."""
        ref_set = ReferenceSet.objects.create(
            name='CountedSet', slug='counted-set', steward=self.user1, domain=self.domain_1, is_active=True
        )
        ReferenceValue.objects.create(reference_set=ref_set, code='A', label='A', is_active=True)
        ReferenceValue.objects.create(reference_set=ref_set, code='B', label='B', is_active=True)
        ReferenceValue.objects.create(reference_set=ref_set, code='C', label='C', is_active=False)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/carbon-api/mdm/reference-sets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        row = next(item for item in data if item['id'] == ref_set.id)
        self.assertEqual(row['value_count'], 2)

    # --- Regression: stewards can CRUD values via generic endpoints ---

    def test_steward_can_create_value_via_generic_endpoint(self):
        """Steward can create a value on the generic reference-values endpoint."""
        ref_set = ReferenceSet.objects.create(
            name='GenericCreate', slug='generic-create', steward=self.user1, domain=self.domain_1, is_active=True
        )
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(
            '/carbon-api/mdm/reference-values/',
            {'reference_set': ref_set.id, 'code': 'X1', 'label': 'X One'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_steward_cannot_create_value_via_generic_endpoint(self):
        """Non-steward is denied on the generic reference-values endpoint."""
        ref_set = ReferenceSet.objects.create(
            name='GenericDeny', slug='generic-deny', steward=self.user1, domain=self.domain_1, is_active=True
        )
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(
            '/carbon-api/mdm/reference-values/',
            {'reference_set': ref_set.id, 'code': 'X2', 'label': 'X Two'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_steward_can_update_and_delete_value_via_generic_endpoint(self):
        """Steward can update and soft-delete values through the generic endpoint."""
        ref_set = ReferenceSet.objects.create(
            name='GenericUpdate', slug='generic-update', steward=self.user1, domain=self.domain_1, is_active=True
        )
        value = ReferenceValue.objects.create(reference_set=ref_set, code='Y', label='Y')
        self.client.force_authenticate(user=self.user1)

        response = self.client.patch(
            f'/carbon-api/mdm/reference-values/{value.id}/',
            {'label': 'Y Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        value.refresh_from_db()
        self.assertEqual(value.label, 'Y Updated')

        response = self.client.delete(f'/carbon-api/mdm/reference-values/{value.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        value.refresh_from_db()
        self.assertFalse(value.is_active)

    def test_deleted_value_hidden_from_active_list(self):
        """Regression: soft-deleted values must not appear in the active list.

        The Values tab fetches with active=1; a deleted (is_active=False) value
        must disappear immediately, matching the reference-set contract where
        archived sets are hidden from all endpoints.
        """
        ref_set = ReferenceSet.objects.create(
            name='HiddenDeleted', slug='hidden-deleted', steward=self.user1, domain=self.domain_1, is_active=True
        )
        value = ReferenceValue.objects.create(reference_set=ref_set, code='K', label='Keep me')
        self.client.force_authenticate(user=self.user1)

        # Before delete: value is visible in the active list.
        response = self.client.get(
            '/carbon-api/mdm/reference-values/', {'reference_set': ref_set.id, 'active': '1'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Defensive: DRF pagination may wrap list responses in {'count', 'results'}.
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        self.assertIn(value.id, {item['id'] for item in data})

        # Soft-delete the value.
        response = self.client.delete(f'/carbon-api/mdm/reference-values/{value.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # After delete: value is hidden from the active list.
        response = self.client.get(
            '/carbon-api/mdm/reference-values/', {'reference_set': ref_set.id, 'active': '1'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        self.assertNotIn(value.id, {item['id'] for item in data})
        value.refresh_from_db()
        self.assertFalse(value.is_active)
