"""Shared fixtures for appregistry tests."""
import pytest

from appregistry.models import AppActivation, AppManifest


@pytest.fixture
def superuser(create_user):
    return create_user('super_user', is_superuser=True)


@pytest.fixture
def make_app():
    """Create an AppManifest (+ activation record)."""
    def _make(slug='healthy', name='Healthy Foods', version='1.0.0',
              required_capabilities=None, is_system=False, **kwargs):
        app = AppManifest.objects.create(
            slug=slug,
            name=name,
            version=version,
            required_capabilities=required_capabilities or [],
            is_system=is_system,
            **kwargs,
        )
        AppActivation.objects.get_or_create(app=app)
        return app
    return _make
