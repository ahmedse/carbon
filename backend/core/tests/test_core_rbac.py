# core/tests/test_core_rbac.py

import pytest
from django.urls import reverse

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        ("admin", 200),      # Only 'admin' ScopedRole can access
        ("dataowner", 403),  # 'dataowner' cannot manage/list projects or modules
        ("audit", 403),
        (None, 403),
    ]
)
def test_group_access_to_project_list(api_client, create_user, create_scoped_role, get_token_for_user, group, expected_status):
    """
    Only users with 'admin' ScopedRole can list projects.
    """
    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group:
        create_scoped_role(user, group)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("project-list")
    response = api_client.get(url)
    assert response.status_code == expected_status

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        ("admin", 200),      # Only 'admin' ScopedRole can access
        ("dataowner", 403),  # 'dataowner' cannot manage/list modules
        ("audit", 403),
        (None, 403),
    ]
)
def test_group_access_to_module_list(api_client, create_user, create_scoped_role, get_token_for_user, group, expected_status):
    """
    Only users with 'admin' ScopedRole can list modules.
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