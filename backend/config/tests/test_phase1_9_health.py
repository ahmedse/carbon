"""Phase 1.9: Health Dashboard — tests."""
import pytest
from django.test import Client, override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


class TestHealthEndpoint:
    """1.9a: Enhanced health check endpoint."""

    def test_health_returns_200(self, client):
        resp = client.get('/carbon-api/health/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] in ('ok', 'degraded')
        assert 'checks' in data
        assert data['checks']['database'] == 'ok'

    def test_health_has_disk_info(self, client):
        resp = client.get('/carbon-api/health/')
        data = resp.json()
        assert 'disk_free_pct' in data
        assert 'last_backup_at' in data

    def test_health_has_timestamp(self, client):
        resp = client.get('/carbon-api/health/')
        assert 'timestamp' in resp.json()

    def test_health_release_is_read_only_identity(self, client):
        resp = client.get('/carbon-api/health/')
        release = resp.json()["release"]
        assert isinstance(release["pack"], str) and release["pack"]
        assert isinstance(release["loaded_packs"], list)
        assert isinstance(release["catalogs"], list)
        assert isinstance(release["extra_packs"], list)
        assert "process_started_at" in release
        assert "pulse_enabled" in release


class TestReleaseExtraPacks:
    """``extra_packs`` is a brand policy statement, not a ``domain_packs`` listing.

    The local dev checkout contains ``aast-med``, ``carbon``, ``eduos`` and
    ``nibras`` under ``domain_packs/``. Reporting all siblings for a nibras
    cell would hide a broken isolation invariant: a nibras deployment must load
    no other platform pack.
    """

    @override_settings(DJANGO_BRAND="nibras")
    def test_nibras_extra_packs_excludes_sibling_platform_packs(self):
        from config.health_views import release_payload

        release = release_payload()
        assert release["process_brand"] == "nibras"
        assert release["pack"] == "nibras"
        assert release["extra_packs"] == []
        forbidden = {"aast-med", "carbon", "eduos", "medos", "tectona"}
        assert not (set(release["extra_packs"]) & forbidden)

    @override_settings(DJANGO_BRAND="aastmt")
    def test_authorized_and_mounted_extra_pack_is_reported(self):
        from ai.platform_bind import extra_packs_for_brand
        from config.health_views import release_payload

        # aastmt is the one brand with a real second pack on its cell.
        assert extra_packs_for_brand("aastmt") == ("aast-med",)
        release = release_payload()
        assert release["process_brand"] == "aastmt"
        assert release["pack"] == "carbon"
        assert release["extra_packs"] == ["aast-med"]

    @override_settings(DJANGO_BRAND="nibras")
    def test_authorized_but_unmounted_extra_pack_is_not_reported(self, monkeypatch):
        """A policy entry whose pack is absent from disk must not be reported."""
        import ai.platform_bind as platform_bind
        from config.health_views import release_payload

        monkeypatch.setattr(
            platform_bind,
            "extra_packs_for_brand",
            lambda brand=None: ("ghost-pack",),
        )
        release = release_payload()
        assert release["extra_packs"] == []


class TestMetricsEndpoint:
    """1.9c: Prometheus metrics endpoint."""

    def test_metrics_returns_200(self, client):
        resp = client.get('/carbon-api/health/metrics/')
        assert resp.status_code == 200
        assert resp['Content-Type'].startswith('text/plain')

    def test_metrics_has_db_metric(self, client):
        resp = client.get('/carbon-api/health/metrics/')
        body = resp.content.decode()
        assert 'carbon_database_up' in body
        assert 'carbon_disk_free_pct' in body
