# connections/tests/test_security.py
"""E1-T5 regression tests — DataSource connection-config masking.

Security lockdown guarantees:
1. Stored secrets never appear in API responses (detail + list).
2. The write path (create/update) still accepts the real config.
3. Echoed masked placeholders on PATCH do NOT clobber stored secrets.
4. The Django admin change page never renders stored secret values.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework.test import APIClient

from connections.models import DataSource
from connections.services import MASK_VALUE

User = get_user_model()

SECRET = "SuperSecret-2026-E1"


class DataSourceConfigMaskingTests(TestCase):
    """API-level: GET never leaks stored secrets; create/update still work."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="conn-admin",
            password="pw-admin-2026",
            email="admin@example.com",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.source = DataSource.objects.create(
            name="Prod Database",
            source_type="database",
            connection_config={"host": "db.internal", "password": SECRET},
        )
        self.detail_url = f"/carbon-api/connections/sources/{self.source.id}/"
        self.list_url = "/carbon-api/connections/sources/"

    def test_get_never_leaks_stored_secret(self):
        resp = self.client.get(self.detail_url)
        assert resp.status_code == 200
        config = resp.data["connection_config"]
        assert config["host"] == MASK_VALUE
        assert config["password"] == MASK_VALUE
        assert SECRET not in resp.content.decode()

    def test_list_never_leaks_stored_secret(self):
        resp = self.client.get(self.list_url)
        assert resp.status_code == 200
        config = resp.data[0]["connection_config"]
        assert config["password"] == MASK_VALUE
        assert SECRET not in resp.content.decode()

    def test_create_accepts_full_config_returns_masked(self):
        resp = self.client.post(
            self.list_url,
            {
                "name": "New Source",
                "source_type": "api",
                "connection_config": {"token": SECRET},
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["connection_config"]["token"] == MASK_VALUE
        stored = DataSource.objects.get(name="New Source")
        assert stored.connection_config["token"] == SECRET

    def test_update_with_masked_placeholders_keeps_secret(self):
        resp = self.client.patch(
            self.detail_url,
            {
                "connection_config": {
                    "host": MASK_VALUE,
                    "password": MASK_VALUE,
                    "port": 5432,
                }
            },
            format="json",
        )
        assert resp.status_code == 200
        self.source.refresh_from_db()
        assert self.source.connection_config["password"] == SECRET  # kept
        assert self.source.connection_config["port"] == 5432  # added
        assert resp.data["connection_config"]["password"] == MASK_VALUE


class DataSourceAdminMaskingTests(TestCase):
    """Admin-level: change page never renders stored secret values."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="conn-admin2",
            password="pw-admin-2026",
            email="admin2@example.com",
        )
        self.source = DataSource.objects.create(
            name="Prod Database",
            source_type="database",
            connection_config={"host": "db.internal", "password": SECRET},
        )

    def test_admin_change_page_never_shows_secret(self):
        admin_client = Client()
        admin_client.force_login(self.admin)
        resp = admin_client.get(
            f"/carbon-api/admin/connections/datasource/{self.source.id}/change/"
        )
        assert resp.status_code == 200
        assert SECRET not in resp.content.decode()
