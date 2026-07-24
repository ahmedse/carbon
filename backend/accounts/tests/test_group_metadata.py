# accounts/tests/test_group_metadata.py

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from accounts.models import ScopedRole


@pytest.mark.django_db
def test_group_description_can_be_created_and_updated(api_client, create_user, get_token_for_user):
    user = create_user("groupadmin")
    admin_group = Group.objects.get_or_create(name="admin")[0]
    ScopedRole.objects.create(user=user, group=admin_group, org_unit=None, module=None, is_active=True)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    create_response = api_client.post(reverse("group-list"), {
        "name": "custom_role",
        "description": "Custom role description"
    }, format="json")
    assert create_response.status_code == 201
    assert create_response.json().get("description") == "Custom role description"

    group_id = create_response.json()["id"]
    update_response = api_client.patch(reverse("group-detail", kwargs={"pk": group_id}), {
        "description": "Updated description"
    }, format="json")
    assert update_response.status_code == 200
    assert update_response.json().get("description") == "Updated description"


@pytest.mark.django_db
def test_group_list_returns_empty_description_for_missing_metadata(api_client, create_user, get_token_for_user):
    user = create_user("groupadmin")
    admin_group = Group.objects.get_or_create(name="admin")[0]
    ScopedRole.objects.create(user=user, group=admin_group, org_unit=None, module=None, is_active=True)

    # Create a group without metadata explicitly
    group = Group.objects.create(name="bare_role")

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("group-list"))
    assert response.status_code == 200
    data = response.json()
    assert any(item.get("name") == "bare_role" and item.get("description") == "" for item in data)


@pytest.mark.django_db
def test_group_members_endpoint_returns_global_assignments(api_client, create_user, get_token_for_user):
    admin_user = create_user("groupadmin")
    target_user = create_user("alice")
    admin_group = Group.objects.get_or_create(name="admin")[0]
    data_owner_group = Group.objects.get_or_create(name="carbon_data_owners_group")[0]
    ScopedRole.objects.create(user=admin_user, group=admin_group, org_unit=None, module=None, is_active=True)
    ScopedRole.objects.create(user=target_user, group=data_owner_group, org_unit=None, module=None, is_active=True)

    token = get_token_for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("group-members", kwargs={"pk": data_owner_group.pk}))
    assert response.status_code == 200
    roles = response.json()
    assert any(member["username"] == "alice" for member in roles)


@pytest.mark.django_db
def test_group_scoped_assignments_endpoint_returns_scoped_roles(api_client, create_user, get_token_for_user):
    admin_user = create_user("groupadmin")
    target_user = create_user("bob")
    admin_group = Group.objects.get_or_create(name="admin")[0]
    data_owner_group = Group.objects.get_or_create(name="carbon_data_owners_group")[0]
    org_unit = None
    ScopedRole.objects.create(user=admin_user, group=admin_group, org_unit=None, module=None, is_active=True)
    ScopedRole.objects.create(user=target_user, group=data_owner_group, org_unit=org_unit, module=None, is_active=True)

    token = get_token_for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("group-scoped-assignments", kwargs={"pk": data_owner_group.pk}))
    assert response.status_code == 200
    assignments = response.json()
    assert any(assign["user"] == "bob" for assign in assignments)
