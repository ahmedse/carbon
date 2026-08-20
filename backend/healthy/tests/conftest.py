"""Shared fixtures for the healthy app test suite."""
import pytest

HEALTHY_API = '/carbon-api/healthy/'


@pytest.fixture
def superuser(create_user):
    return create_user('healthy_admin', is_superuser=True)


@pytest.fixture
def viewer(create_user, create_scoped_role):
    """Authenticated user with only ``healthy:view`` (via viewers_group)."""
    user = create_user('healthy_viewer')
    create_scoped_role(user, 'viewers_group')
    return user


@pytest.fixture
def auth(api_client, get_token_for_user):
    """Return an APIClient authenticated as the given user."""
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory
