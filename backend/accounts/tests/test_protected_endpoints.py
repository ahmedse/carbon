# accounts/tests/test_protected_endpoints.py

import pytest
from django.urls import reverse

# (endpoint_name, allowed_groups)
PROTECTED_ENDPOINTS = [
    ("tenant-list", ["superuser"]),    # Only Django superuser can access tenants
    ("role-list", ["admin"]),          # Only ScopedRole 'admin'
    ("user-list", ["admin"]),          # Only ScopedRole 'admin'
]

GROUPS = ["admin", "audit", "dataowner", None, "superuser"]

@pytest.mark.django_db
@pytest.mark.parametrize("endpoint,allowed_groups", PROTECTED_ENDPOINTS)
@pytest.mark.parametrize("group", GROUPS)
def test_group_access_to_protected_endpoints(
    api_client, create_user, create_scoped_role, get_token_for_user, endpoint, allowed_groups, group
):
    """
    Test if each group (or superuser) can access protected endpoints.
    """
    if group == "superuser":
        user = create_user("superadmin", is_superuser=True, is_staff=True)
    else:
        groups = [group] if group else []
        user = create_user("testuser", groups=groups)
        if group:
            create_scoped_role(user, group)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse(endpoint)
    resp = api_client.get(url)

    if group in allowed_groups:
        assert resp.status_code == 200
    else:
        assert resp.status_code == 403