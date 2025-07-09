# dataschema/tests/test_rbac.py

import pytest
from django.urls import reverse

@pytest.fixture
def setup_schema(db, create_tenant):
    from core.models import Project, Module
    from dataschema.models import DataTable, DataField, DataRow

    tenant = create_tenant()
    project = Project.objects.create(name="Test Project", tenant=tenant)
    module = Module.objects.create(name="Test Module", project=project)
    table = DataTable.objects.create(title="Test Table", name="test_table", module=module)
    field = DataField.objects.create(data_table=table, name="value", label="Value", type="string")
    row = DataRow.objects.create(data_table=table, values={"value": "hello"})

    return {
        "tenant": tenant,
        "project": project,
        "module": module,
        "table": table,
        "field": field,
        "row": row,
    }

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        ("admin", 200),
        ("audit", 403),
        ("dataowner", 403),
        (None, 403),
    ]
)
def test_table_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema, group, expected_status
):
    project = setup_schema["project"]
    tenant = setup_schema["tenant"]
    groups = [group] if group else []
    user = create_user("bob", groups=groups, tenant=tenant)
    if group:
        create_scoped_role(user, group, tenant=tenant, project=project)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-table-list") + f"?project_id={project.id}"
    resp = api_client.get(url)
    assert resp.status_code == expected_status

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        ("admin", 200),
        ("audit", 403),
        ("dataowner", 403),
        (None, 403),
    ]
)
def test_field_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema, group, expected_status
):
    project = setup_schema["project"]
    tenant = setup_schema["tenant"]
    groups = [group] if group else []
    user = create_user("bob", groups=groups, tenant=tenant)
    if group:
        create_scoped_role(user, group, tenant=tenant, project=project)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-field-list") + f"?project_id={project.id}"
    resp = api_client.get(url)
    assert resp.status_code == expected_status

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status_module,expected_status_other_module",
    [
        ("admin", 200, 200),
        ("audit", 200, 200),
        ("dataowner", 200, 403),
        (None, 403, 403),
    ]
)
def test_row_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema,
    group, expected_status_module, expected_status_other_module
):
    project = setup_schema["project"]
    module = setup_schema["module"]
    tenant = setup_schema["tenant"]

    from core.models import Module as CoreModule
    other_module = CoreModule.objects.create(name="Other Module", project=project)

    from dataschema.models import DataTable, DataField, DataRow
    other_table = DataTable.objects.create(title="Other Table", name="other_table", module=other_module)
    DataField.objects.create(data_table=other_table, name="other_value", label="OtherValue", type="string")
    DataRow.objects.create(data_table=other_table, values={"other_value": "foo"})

    groups = [group] if group else []
    user = create_user("bob", groups=groups, tenant=tenant)
    if group == "dataowner":
        create_scoped_role(user, group, tenant=tenant, module=module)
    elif group in ("admin", "audit"):
        create_scoped_role(user, group, tenant=tenant, project=project)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-row-list") + f"?project_id={project.id}&module_id={module.id}"
    resp = api_client.get(url)
    assert resp.status_code == expected_status_module

    url = reverse("dataschema-row-list") + f"?project_id={project.id}&module_id={other_module.id}"
    resp = api_client.get(url)
    assert resp.status_code == expected_status_other_module

@pytest.mark.django_db
@pytest.mark.parametrize(
    "group,expected_status",
    [
        ("admin", 200),
        ("audit", 403),
        ("dataowner", 403),
        (None, 403),
    ]
)
def test_schema_log_list_access(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema, group, expected_status
):
    project = setup_schema["project"]
    tenant = setup_schema["tenant"]
    groups = [group] if group else []
    user = create_user("bob", groups=groups, tenant=tenant)
    if group:
        create_scoped_role(user, group, tenant=tenant, project=project)
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    url = reverse("dataschema-schemalog-list") + f"?project_id={project.id}"
    resp = api_client.get(url)
    assert resp.status_code == expected_status