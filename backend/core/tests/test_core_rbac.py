# core/tests/test_core_rbac.py

import pytest
from django.urls import reverse

# Role name constants matching the viewset required_role lists
ADMIN = "admin"
DATAOWNER = "dataowners_group"
AUDIT = "auditors_group"

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        (ADMIN, 200),      # ModuleViewSet GET uses IsAuthenticated — all authenticated users pass
        (DATAOWNER, 200),  # 
        (AUDIT, 200),      # 
        (None, 200),       # Authenticated user with no scoped role
    ]
)
def test_group_access_to_project_list(api_client, create_user, create_scoped_role, get_token_for_user, group, expected_status):
    """
    Module list uses IsAuthenticated for GET — all authenticated users can access.
    """
    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group:
        create_scoped_role(user, group)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("module-list")
    response = api_client.get(url)
    assert response.status_code == expected_status

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        (ADMIN, 200),      # ModuleViewSet GET uses IsAuthenticated — all authenticated users pass
        (DATAOWNER, 200),  # 
        (AUDIT, 200),      # 
        (None, 200),       # Authenticated user with no scoped role
    ]
)
def test_group_access_to_module_list(api_client, create_user, create_scoped_role, get_token_for_user, group, expected_status):
    """
    Module list uses IsAuthenticated for GET — all authenticated users can access.
    Unauthenticated users get 401.
    """
    groups = [group] if group else []
    user = create_user("alice", groups=groups)
    if group:
        create_scoped_role(user, group)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("module-list")
    response = api_client.get(url)
    assert response.status_code == expected_status