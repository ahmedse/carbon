# accounts/tests/test_users.py

import pytest
from django.urls import reverse
from mdm.models import OrgUnit
from people.models import Employee


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


@pytest.mark.django_db
def test_user_list_includes_linked_employee_identity(
    api_client, create_user, create_scoped_role, get_token_for_user,
):
    """Admin Users list surfaces linked Employee full_name + org for identity."""
    admin = create_user("admin", password="adminpass", is_superuser=True, is_staff=True)
    create_scoped_role(admin, "admin")
    emp_user = create_user("emp_99001", password="x")
    root = OrgUnit.objects.create(
        name='Deploy Root Users', slug='deploy-root-users-test', org_type='company',
    )
    org = OrgUnit.objects.create(
        name='Ops Desk', slug='ops-desk-users', code='OPS-U',
        org_type='department', parent=root,
    )
    Employee.objects.create(
        org_unit=org,
        employee_no='99001',
        full_name='Ada Lovelace',
        user=emp_user,
        is_active=True,
        basic_salary='0.000',
    )

    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = api_client.get(reverse("user-list"))
    assert response.status_code == 200
    rows = response.json()
    if isinstance(rows, dict):
        rows = rows.get('results', [])
    row = next(r for r in rows if r['username'] == 'emp_99001')
    assert row['employee_full_name'] == 'Ada Lovelace'
    assert row['employee_no'] == '99001'
    assert 'Ops Desk' in (row['employee_org_unit'] or '')
    # Unlinked account → null identity fields
    bare = next(r for r in rows if r['username'] == 'admin')
    assert bare.get('employee_full_name') in (None, '')
