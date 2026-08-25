# accounts/tests/test_language_preferences.py
# I18N-5 — per-user UI language preference (ADR-0018).

import pytest
from django.urls import reverse

from accounts.models import User
from accounts.serializers import MePreferencesSerializer, UserSerializer


@pytest.mark.django_db
def test_me_preferences_get_returns_default_language(api_client, create_user, get_token_for_user):
    user = create_user("alice", password="alicepass")
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("me-preferences")
    response = api_client.get(url)

    assert response.status_code == 200
    assert response.data["language"] == "en"


@pytest.mark.django_db
def test_me_preferences_requires_auth(api_client):
    url = reverse("me-preferences")
    response = api_client.get(url)
    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_me_preferences_patch_updates_language(api_client, create_user, get_token_for_user):
    user = create_user("alice", password="alicepass")
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("me-preferences")
    response = api_client.patch(url, {"language": "ar"}, format="json")
    assert response.status_code == 200
    assert response.data["language"] == "ar"

    user.refresh_from_db()
    assert user.language == "ar"

    # GET reflects the persisted value.
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["language"] == "ar"


@pytest.mark.django_db
def test_me_preferences_patch_invalid_value_400(api_client, create_user, get_token_for_user):
    user = create_user("alice", password="alicepass")
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("me-preferences")
    response = api_client.patch(url, {"language": "fr"}, format="json")
    assert response.status_code == 400

    user.refresh_from_db()
    assert user.language == "en"


@pytest.mark.django_db
def test_me_context_surfaces_language(api_client, create_user, get_token_for_user):
    user = create_user("alice", password="alicepass")
    user.language = "ar"
    user.save()
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("me-context")
    response = api_client.get(url)

    assert response.status_code == 200
    assert response.data["user"]["language"] == "ar"


@pytest.mark.django_db
def test_user_serializer_roundtrip_language(create_user):
    user = create_user("alice", password="alicepass")

    # Write via the serializer.
    serializer = UserSerializer(instance=user, data={"language": "ar"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()

    user.refresh_from_db()
    assert user.language == "ar"

    # Read via the serializer.
    data = UserSerializer(user).data
    assert data["language"] == "ar"


@pytest.mark.django_db
def test_me_preferences_serializer_invalid_value():
    serializer = MePreferencesSerializer(data={"language": "de"})
    assert not serializer.is_valid()
    assert "language" in serializer.errors
