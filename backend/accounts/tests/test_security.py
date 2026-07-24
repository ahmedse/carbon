# accounts/tests/test_security.py
"""
Security tests: check for leaking data, token misuse, and proper RBAC isolation.
"""

import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_user_cannot_access_token_of_another_user(api_client, create_user, get_token_for_user):
    """
    User A's token cannot be used to access User B's detail.
    """
    user1 = create_user("alice")
    user2 = create_user("bob")
    token = get_token_for_user(user1)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("user-detail", args=[user2.id])
    resp = api_client.get(url)
    assert resp.status_code in [403, 404]

@pytest.mark.django_db
def test_jwt_cannot_be_reused_after_logout(api_client, create_user, get_token_for_user):
    """
    (If you implement token blacklist): After logout/blacklist, token should be invalid.
    """
    user = create_user("alice")
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Suppose you have a logout/blacklist endpoint
    # api_client.post(reverse("token_blacklist"), {"refresh": refresh_token_here})
    # Now try to use the old token:
    # resp = api_client.get(reverse("user-detail", args=[user.id]))
    # assert resp.status_code == 401
    pass  # Implement if JWT blacklist is enabled.

@pytest.mark.django_db
def test_user_cannot_access_detail_of_another_user(api_client, create_user, get_token_for_user):
    user1 = create_user("alice")
    user2 = create_user("bob")
    token = get_token_for_user(user1)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("user-detail", args=[user2.id])
    response = api_client.get(url)
    assert response.status_code in [403, 404]