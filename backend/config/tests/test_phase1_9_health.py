"""Phase 1.9: Health Dashboard — tests."""
import pytest
from django.test import Client
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
