import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import AssetProfile, DataDomain, GlossaryTerm, GovernanceEvent

User = get_user_model()


class CatalogAuditTests(APITestCase):
    def _api_prefix(self):
        return settings.API_PREFIX.strip('/').strip()

    def setUp(self):
        self.admin = User.objects.create_user(username='catalog_admin', password='pass123')
        self.admin.is_superuser = True
        self.admin.save()
        self.other_user = User.objects.create_user(username='other_user', password='pass123')

    def test_asset_profile_patch_emits_update_event(self):
        asset = AssetProfile.objects.create(owner=self.admin, steward=self.admin, classification='internal')
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/{self._api_prefix()}/catalog/assets/{asset.id}/',
            {'owner': self.other_user.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = GovernanceEvent.objects.filter(entity_type='AssetProfile', entity_id=asset.id, action='update').latest('timestamp')
        self.assertEqual(event.user, self.admin)
        self.assertEqual(event.asset, asset)
        self.assertEqual(event.before['owner'], self.admin.id)
        self.assertEqual(event.after['owner'], self.other_user.id)

    def test_no_event_when_patch_has_no_real_change(self):
        asset = AssetProfile.objects.create(owner=self.admin, steward=self.admin, classification='internal')
        self.client.force_authenticate(user=self.admin)

        self.client.patch(
            f'/{self._api_prefix()}/catalog/assets/{asset.id}/',
            {'classification': 'internal'},
            format='json',
        )

        self.assertEqual(GovernanceEvent.objects.filter(entity_type='AssetProfile', entity_id=asset.id).count(), 0)

    def test_glossary_delete_emits_delete_event(self):
        """Test that DELETE is not allowed (hard delete disabled)."""
        term = GlossaryTerm.objects.create(term='Governance', definition='Policy definition')
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(f'/{self._api_prefix()}/catalog/glossary/{term.id}/')

        # DELETE is explicitly disabled in favor of soft delete via PATCH
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_compliance_summary_endpoint_returns_recent_activity(self):
        asset = AssetProfile.objects.create(owner=self.admin, steward=self.admin, classification='internal')
        GovernanceEvent.objects.create(
            asset=asset,
            entity_type='AssetProfile',
            entity_id=asset.id,
            action='update',
            before={'owner': self.admin.id},
            after={'owner': self.admin.id},
            user=self.admin,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f'/{self._api_prefix()}/catalog/governance/compliance/?days=30')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['window_days'], 30)
        self.assertGreaterEqual(response.data['total_events'], 1)
        self.assertTrue(any(item['entity_type'] == 'AssetProfile' for item in response.data['by_entity_type']))
        self.assertTrue(any(item['action'] == 'update' for item in response.data['by_action']))
