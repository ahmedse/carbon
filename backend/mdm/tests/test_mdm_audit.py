from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import DataDomain
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from catalog.models import GovernanceEvent

User = get_user_model()


class MdmAuditTests(APITestCase):
    def _api_prefix(self):
        return settings.API_PREFIX.strip('/').strip()

    def setUp(self):
        self.admin = User.objects.create_user(username='mdm_admin', password='pass123')
        self.admin.is_superuser = True
        self.admin.save()
        self.domain = DataDomain.objects.create(name='Master Data', slug='master-data')

    def test_reference_set_update_emits_event(self):
        ref_set = ReferenceSet.objects.create(name='Status', slug='status', domain=self.domain, steward=self.admin)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/{self._api_prefix()}/mdm/reference-sets/{ref_set.id}/',
            {'description': 'Updated description'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = GovernanceEvent.objects.filter(entity_type='ReferenceSet', entity_id=ref_set.id, action='update').latest('timestamp')
        self.assertEqual(event.user, self.admin)
        self.assertEqual(event.before['description'], '')
        self.assertEqual(event.after['description'], 'Updated description')

    def test_reference_value_deactivation_emits_event(self):
        ref_set = ReferenceSet.objects.create(name='Status', slug='status', domain=self.domain, steward=self.admin)
        value = ReferenceValue.objects.create(reference_set=ref_set, code='ACTIVE', label='Active')
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/{self._api_prefix()}/mdm/reference-values/{value.id}/',
            {'is_active': False},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = GovernanceEvent.objects.filter(entity_type='ReferenceValue', entity_id=value.id, action='update').latest('timestamp')
        self.assertEqual(event.after['is_active'], False)

    def test_org_unit_parent_change_emits_event(self):
        parent = OrgUnit.objects.create(name='Parent', slug='parent')
        child = OrgUnit.objects.create(name='Child', slug='child', parent=parent)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/{self._api_prefix()}/mdm/org-units/{child.id}/',
            {'parent': None},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = GovernanceEvent.objects.filter(entity_type='OrgUnit', entity_id=child.id, action='update').latest('timestamp')
        self.assertEqual(event.before['parent'], parent.id)
        self.assertEqual(event.after['parent'], None)
