# accounts/tests/test_users.py

import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_admin_can_list_users(api_client, create_user, create_scoped_role, get_token_for_user):
    admin = create_user("admin", password="adminpass", is_superuser=True, is_staff=True)
    create_scoped_role(admin, "admin")
    user = create_user("bob", password="bobpass")
    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("user-list")
    response = api_client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_normal_user_cannot_list_users(api_client, create_user, get_token_for_user):
    user = create_user("alice", password="alicepass")
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("user-list")
    response = api_client.get(url)
    assert response.status_code in [403, 401]

@pytest.mark.django_db
def test_user_detail_admin(api_client, create_user, create_scoped_role, get_token_for_user):
    admin = create_user("admin", password="adminpass")
    create_scoped_role(admin, "admin")
    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    user = create_user("alice", password="alicepass")
    url = reverse("user-detail", args=[user.id])
    response = api_client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_user_cannot_access_other_user_detail(api_client, create_user, get_token_for_user):
    user1 = create_user("alice")
    user2 = create_user("bob")
    token = get_token_for_user(user1)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("user-detail", args=[user2.id])
    response = api_client.get(url)
    assert response.status_code in [403, 404]