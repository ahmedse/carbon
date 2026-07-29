# dataschema/tests/test_rbac.py

import pytest
from django.urls import reverse

# Role name constants matching the viewset required_role lists
ADMIN = "admin"
AUDIT = "auditors_group"
DATAOWNER = "dataowners_group"

@pytest.fixture
def setup_schema(db):
    from core.models import Module
    from dataschema.models import DataTable, DataField, DataRow

    module = Module.objects.create(name="Test Module")
    table = DataTable.objects.create(title="Test Table", name="test_table", module=module)
    field = DataField.objects.create(data_table=table, name="value", label="Value", type="string")
    row = DataRow.objects.create(data_table=table, values={"value": "hello"})

    return {
        "project": None,
        "module": module,
        "table": table,
        "field": field,
        "row": row,
    }

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        (ADMIN, 200),
        (AUDIT, 403),
        (DATAOWNER, 403),
        (None, 403),
    ]
)
def test_table_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema, group, expected_status
):
    module = setup_schema["module"]
    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group == ADMIN:
        create_scoped_role(user, group)  # global admin role for list access
    elif group:
        create_scoped_role(user, group, module=module)  # module-scoped
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-table-list")
    resp = api_client.get(url)
    assert resp.status_code == expected_status

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        (ADMIN, 200),
        (AUDIT, 403),
        (DATAOWNER, 403),
        (None, 403),
    ]
)
def test_field_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema, group, expected_status
):
    module = setup_schema["module"]
    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group == ADMIN:
        create_scoped_role(user, group)  # global admin role for list access
    elif group:
        create_scoped_role(user, group, module=module)  # module-scoped
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-field-list")
    resp = api_client.get(url)
    assert resp.status_code == expected_status

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status_module,expected_status_other_module",
    [
        (ADMIN, 200, 200),
        (AUDIT, 200, 200),
        (DATAOWNER, 200, 403),
        (None, 403, 403),
    ]
)
def test_row_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema,
    group, expected_status_module, expected_status_other_module
):
    module = setup_schema["module"]

    from core.models import Module as CoreModule
    other_module = CoreModule.objects.create(name="Other Module")

    from dataschema.models import DataTable, DataField, DataRow
    other_table = DataTable.objects.create(title="Other Table", name="other_table", module=other_module)
    DataField.objects.create(data_table=other_table, name="other_value", label="OtherValue", type="string")
    DataRow.objects.create(data_table=other_table, values={"other_value": "foo"})

    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group == DATAOWNER:
        create_scoped_role(user, group, module=module)
    elif group in (ADMIN, AUDIT):
        create_scoped_role(user, group)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-row-list") + f"?module_id={module.id}"
    resp = api_client.get(url)
    assert resp.status_code == expected_status_module

    url = reverse("dataschema-row-list") + f"?module_id={other_module.id}"
    resp = api_client.get(url)
    assert resp.status_code == expected_status_other_module

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        (ADMIN, 200),
        (AUDIT, 403),
        (DATAOWNER, 403),
        (None, 403),
    ]
)
def test_schema_log_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema, group, expected_status
):
    module = setup_schema["module"]
    groups = [group] if group else []
    user = create_user("bob", groups=groups)
    if group == ADMIN:
        create_scoped_role(user, group)  # global admin role for list access
    elif group:
        create_scoped_role(user, group, module=module)  # module-scoped
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-schemalog-list")
    resp = api_client.get(url)
    assert resp.status_code == expected_status