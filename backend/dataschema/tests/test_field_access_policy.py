# dataschema/tests/test_field_access_policy.py
"""
EPH-4A: Column-Level RBAC (FieldAccessPolicy) tests.
"""
import pytest
from django.urls import reverse


@pytest.fixture
def setup_schema(db):
    from core.models import Module
    from dataschema.models import DataTable, DataField

    module = Module.objects.create(name="Test Module")
    table = DataTable.objects.create(title="Test Table", name="test_table", module=module)
    field = DataField.objects.create(data_table=table, name="value", label="Value", type="string")

    return {
        "module": module,
        "table": table,
        "field": field,
    }


@pytest.mark.django_db
def test_field_with_pii_cap_sees_full_data(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    FieldAccessPolicy.objects.create(
        field=field, required_capability="catalog:view_pii", action="deny"
    )

    user = create_user("owner")
    create_scoped_role(user, "dataowners_group")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("dataschema-field-detail", kwargs={"pk": field.id})
    resp = api_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "label" in data
    assert "access_denied" not in data


@pytest.mark.django_db
def test_field_without_cap_gets_denied(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    FieldAccessPolicy.objects.create(
        field=field, required_capability="catalog:view_pii", action="deny"
    )

    user = create_user("analyst")
    create_scoped_role(user, "analysts_group")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("dataschema-field-detail", kwargs={"pk": field.id})
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.json() == {"id": field.id, "name": field.name, "access_denied": True}


@pytest.mark.django_db
def test_field_without_cap_gets_masked(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    FieldAccessPolicy.objects.create(
        field=field, required_capability="catalog:view_pii", action="mask"
    )

    user = create_user("analyst")
    create_scoped_role(user, "analysts_group")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("dataschema-field-detail", kwargs={"pk": field.id})
    resp = api_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "label" in data
    assert data["is_masked"] is True


@pytest.mark.django_db
def test_superuser_bypasses_policy(
    api_client, create_user, get_token_for_user, setup_schema
):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    FieldAccessPolicy.objects.create(
        field=field, required_capability="catalog:view_pii", action="deny"
    )

    user = create_user("root", is_superuser=True)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("dataschema-field-detail", kwargs={"pk": field.id})
    resp = api_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "label" in data
    assert "access_denied" not in data
    assert "is_masked" not in data


@pytest.mark.django_db
def test_create_policy_admin_201(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    user = create_user("admin")
    create_scoped_role(user, "admin")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("field-policies", kwargs={"field_id": field.id})
    resp = api_client.post(
        url, {"required_capability": "catalog:view_pii", "action": "deny"}, format="json"
    )
    assert resp.status_code == 201
    assert FieldAccessPolicy.objects.count() == 1


@pytest.mark.django_db
def test_create_policy_non_admin_403(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    field = setup_schema["field"]
    user = create_user("analyst")
    create_scoped_role(user, "analysts_group")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("field-policies", kwargs={"field_id": field.id})
    resp = api_client.post(
        url, {"required_capability": "catalog:view_pii", "action": "deny"}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_delete_policy_admin_204(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    policy = FieldAccessPolicy.objects.create(
        field=field, required_capability="catalog:view_pii", action="deny"
    )

    user = create_user("admin")
    create_scoped_role(user, "admin")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("field-policy-detail", kwargs={"field_id": field.id, "pk": policy.id})
    resp = api_client.delete(url)
    assert resp.status_code == 204
    assert FieldAccessPolicy.objects.count() == 0


@pytest.mark.django_db
def test_delete_policy_non_admin_403(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    policy = FieldAccessPolicy.objects.create(
        field=field, required_capability="catalog:view_pii", action="deny"
    )

    user = create_user("analyst")
    create_scoped_role(user, "analysts_group")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("field-policy-detail", kwargs={"field_id": field.id, "pk": policy.id})
    resp = api_client.delete(url)
    assert resp.status_code == 403
    assert FieldAccessPolicy.objects.count() == 1


@pytest.mark.django_db
def test_cascade_delete_field_deletes_policies(setup_schema):
    from dataschema.models import FieldAccessPolicy

    field = setup_schema["field"]
    FieldAccessPolicy.objects.create(
        field=field, required_capability="catalog:view_pii", action="deny"
    )
    assert FieldAccessPolicy.objects.count() == 1

    field.delete()
    assert FieldAccessPolicy.objects.count() == 0
