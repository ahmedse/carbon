# accounts/tests/test_auth.py
"""
Authentication scenarios for accounts app.
Covers JWT token obtain/refresh, login, and invalid login.
"""

import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_user_can_obtain_jwt_token(api_client, create_user):
    """
    Any registered user should be able to obtain a JWT token with valid credentials.
    """
    user = create_user("alice", password="alicepass")
    url = reverse("token_obtain_pair")
    response = api_client.post(url, {"username": "alice", "password": "alicepass"})
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data

@pytest.mark.django_db
def test_invalid_credentials_cannot_obtain_token(api_client):
    """
    Invalid credentials should not return a JWT token.
    """
    url = reverse("token_obtain_pair")
    response = api_client.post(url, {"username": "wrong", "password": "wrong"})
    assert response.status_code == 401

@pytest.mark.django_db
def test_token_refresh(api_client, create_user, get_token_for_user):
    """
    User can refresh a valid refresh token to get a new access token.
    """
    user = create_user("bob", password="bobpass")
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    url = reverse("token_refresh")
    response = api_client.post(url, {"refresh": str(refresh)})
    assert response.status_code == 200
    assert "access" in response.data