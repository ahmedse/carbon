# core/tests/test_error_codes.py
"""EPH-5A — structured error codes + API version header tests.

Covers the ERROR_CODES taxonomy, CarbonAPIError behavior, inference of
error_code on real API responses (404/401), and the API-Version header.
"""
import pytest

from core.error_codes import CarbonAPIError


def test_known_code_returns_taxonomy_message():
    """CarbonAPIError resolves a known taxonomy code to its message."""
    assert CarbonAPIError('ERR_AUTH_003').detail == 'Insufficient permissions'


def test_unknown_code_falls_back_to_default_message():
    """Unknown taxonomy codes fall back to a generic 'Error' message."""
    assert CarbonAPIError('ERR_UNKNOWN_X').detail == 'Error'


@pytest.mark.django_db
def test_404_response_carries_taxonomy_error_code(api_client, create_user, get_token_for_user):
    """404 responses expose error_code ERR_SCH_001 (inferred from status)."""
    user = create_user('err404_user')
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    response = api_client.get('/carbon-api/catalog/assets/999999/')
    assert response.status_code == 404
    assert response.data['error_code'] == 'ERR_SCH_001'


@pytest.mark.django_db
def test_401_response_carries_taxonomy_error_code(api_client):
    """401 responses expose error_code ERR_AUTH_001 (inferred from status)."""
    response = api_client.get('/carbon-api/catalog/assets/')
    assert response.status_code == 401
    assert response.data['error_code'] == 'ERR_AUTH_001'


@pytest.mark.django_db
def test_every_response_carries_api_version_header(api_client):
    """All responses carry the API-Version: 1 header (middleware)."""
    response = api_client.get('/carbon-api/health/')
    assert response.status_code == 200
    assert response['API-Version'] == '1'
