# accounts/tests/test_rbac.py

import pytest
from django.urls import reverse

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        ("admin", 200),
        ("audit", 403),
        ("dataowner", 403),  # Only 'admin' should have access according to current permissions
        (None, 403),
    ]
)
def test_group_access_to_role_list(api_client, create_user, create_scoped_role, get_token_for_user, group, expected_status):
    """
    Users with appropriate ScopedRole can access 'role-list'.
    Only users with 'admin' ScopedRole are allowed.
    """
    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group:
        create_scoped_role(user, group)  # Assign the scoped role.
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.get(reverse("role-list"))
    assert resp.status_code == expected_status