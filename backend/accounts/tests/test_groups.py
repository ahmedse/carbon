# accounts/tests/test_groups.py

import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_admin_can_list_groups(api_client, create_user, create_scoped_role, get_token_for_user):
    """
    User with 'admin' ScopedRole should be able to list groups (roles).
    """
    user = create_user("adminuser", groups=["admin"])
    create_scoped_role(user, "admin")
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.get(reverse("role-list"))
    assert resp.status_code == 200

@pytest.mark.django_db
@pytest.mark.parametrize("group", [
    "audit",
    "dataowner",
    None
])
def test_non_admin_cannot_list_groups(api_client, create_user, create_scoped_role, get_token_for_user, group):
    """
    Users without 'admin' ScopedRole should NOT be able to list groups.
    """
    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group:
        create_scoped_role(user, group)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.get(reverse("role-list"))
    assert resp.status_code == 403