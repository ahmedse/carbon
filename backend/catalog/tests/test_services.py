"""Tests for catalog services: ensure_asset_profiles()."""
from django.test import TestCase

from catalog.models import AssetProfile
from catalog.services import ensure_asset_profiles
from core.models import Module
from dataschema.models import DataTable, DataField
from mdm.models import OrgUnit


class EnsureAssetProfilesTests(TestCase):
    def setUp(self):
        self.org_unit = OrgUnit.objects.create(name='CatOrg', slug='cat-org')
        self.module = Module.objects.create(name='CatModule', scope=1, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='cat_table')
        self.field = DataField.objects.create(
            data_table=self.table, name='value', label='Value', type='number'
        )

    def test_creates_profiles_for_new_tables_and_fields(self):
        count = ensure_asset_profiles()
        self.assertEqual(count, 2)  # one table profile + one field profile

    def test_idempotent_second_call_returns_zero(self):
        ensure_asset_profiles()
        count = ensure_asset_profiles()
        self.assertEqual(count, 0)

    def test_returns_zero_when_all_profiles_exist(self):
        AssetProfile.objects.create(data_table=self.table)
        AssetProfile.objects.create(data_field=self.field)
        count = ensure_asset_profiles()
        self.assertEqual(count, 0)
