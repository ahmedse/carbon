# accounts/tests/test_rbac.py

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import ScopedRole


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


@pytest.mark.django_db
def test_me_context_returns_perspectives_for_scoped_roles(api_client, create_user, create_scoped_role, get_token_for_user):
    user = create_user("rbacuser")
    admin_group = Group.objects.get_or_create(name="admin")[0]
    data_owner_group = Group.objects.get_or_create(name="carbon_data_owners_group")[0]
    ScopedRole.objects.create(user=user, group=admin_group, org_unit=None, module=None, is_active=True)
    ScopedRole.objects.create(user=user, group=data_owner_group, org_unit=None, module=None, is_active=True)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("me-context"))

    assert response.status_code == 200
    data = response.json()
    assert "admin" in data["perspectives"]
    assert "data-owner" in data["perspectives"]
    # Unlinked account → employee is null (shell identity contract)
    assert data.get("employee") is None


@pytest.mark.django_db
def test_me_context_includes_linked_employee_summary(api_client, create_user, get_token_for_user):
    """Shell bootstrap: linked ESS users get employee.full_name for display."""
    from mdm.models import OrgUnit
    from people.models import Employee, Position

    emp_user = create_user("emp_shell_id")
    root = OrgUnit.objects.create(
        name='Shell Root', slug='shell-id-root', org_type='company',
    )
    org = OrgUnit.objects.create(
        name='Coiled Tubing', slug='shell-id-ct', code='CT-SHELL',
        org_type='department', parent=root,
    )
    position = Position.objects.create(
        code='FT-SHELL', title='Field Technician', org_unit=org,
    )
    Employee.objects.create(
        org_unit=org,
        employee_no='SHELL-1067',
        full_name='Bilagot Panta Suerte',
        user=emp_user,
        is_active=True,
        basic_salary='0.000',
        position=position,
    )

    token = get_token_for_user(emp_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = api_client.get(reverse("me-context"))

    assert response.status_code == 200
    data = response.json()
    emp = data.get("employee")
    assert emp is not None
    assert emp["full_name"] == "Bilagot Panta Suerte"
    assert emp["employee_no"] == "SHELL-1067"
    assert emp["job_title"] == "Field Technician"
    assert emp["org_unit_name"] == "Coiled Tubing"
    assert emp["id"] is not None


@pytest.mark.django_db
def test_role_registry_returns_manifest_roles(api_client, create_user, get_token_for_user):
    user = create_user("registryuser")
    group = Group.objects.get_or_create(name="admin")[0]
    ScopedRole.objects.create(user=user, group=group, org_unit=None, module=None, is_active=True)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("role-registry"))

    assert response.status_code == 200
    data = response.json()
    assert "apps" in data
    carbon_app = next((app for app in data["apps"] if app["id"] == "carbon"), None)
    assert carbon_app is not None
    assert carbon_app["roles"]


@pytest.mark.django_db
def test_admin_can_create_and_list_groups(api_client, create_user, get_token_for_user):
    user = create_user("groupadmin")
    admin_group = Group.objects.get_or_create(name="admin")[0]
    ScopedRole.objects.create(user=user, group=admin_group, org_unit=None, module=None, is_active=True)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    create_response = api_client.post(reverse("group-list"), {"name": "custom_role"}, format="json")
    assert create_response.status_code == 201

    list_response = api_client.get(reverse("group-list"))
    assert list_response.status_code == 200
    names = [item["name"] for item in list_response.json()]
    assert "custom_role" in names


@pytest.mark.django_db
def test_protected_groups_cannot_be_deleted(api_client, create_user, get_token_for_user):
    user = create_user("protectadmin")
    admin_group = Group.objects.get_or_create(name="admin")[0]
    ScopedRole.objects.create(user=user, group=admin_group, org_unit=None, module=None, is_active=True)

    protected_group = Group.objects.get_or_create(name="carbon_data_owners_group")[0]

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.delete(reverse("group-detail", kwargs={"pk": protected_group.pk}))

    assert response.status_code == 400
    assert "Cannot delete protected group" in response.json()["error"]