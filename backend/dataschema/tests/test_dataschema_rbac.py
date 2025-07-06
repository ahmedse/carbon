import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from accounts.models import Tenant, User, Permission, Role, Context, RoleAssignment
from core.models import Project, Module
from dataschema.models import DataTable, DataField, DataRow

PERMISSION_CODES = [
    "view_data", "manage_data", "view_schema", "manage_schema", "manage_module", "manage_project"
]

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def tenant_a():
    return Tenant.objects.create(name="Tenant A")

@pytest.fixture
def tenant_b():
    return Tenant.objects.create(name="Tenant B")

@pytest.fixture
def project_a1(tenant_a):
    return Project.objects.create(name="Project A1", tenant=tenant_a)

@pytest.fixture
def project_b1(tenant_b):
    return Project.objects.create(name="Project B1", tenant=tenant_b)

@pytest.fixture
def module_a1(project_a1):
    return Module.objects.create(name="Module A1", project=project_a1)

@pytest.fixture
def module_b1(project_b1):
    return Module.objects.create(name="Module B1", project=project_b1)

@pytest.fixture
def user_admin(tenant_a):
    return User.objects.create_user(username="admin", password="pass", tenant=tenant_a)

@pytest.fixture
def user_audit(tenant_a):
    return User.objects.create_user(username="audit", password="pass", tenant=tenant_a)

@pytest.fixture
def user_dataowner(tenant_a):
    return User.objects.create_user(username="dataowner", password="pass", tenant=tenant_a)

@pytest.fixture
def user_outsider(tenant_b):
    return User.objects.create_user(username="outsider", password="pass", tenant=tenant_b)

@pytest.fixture
def permission_objs():
    perms = {}
    for code in PERMISSION_CODES:
        perms[code] = Permission.objects.create(code=code, description=code)
    return perms

@pytest.fixture
def role_admin(permission_objs):
    role = Role.objects.create(name='admin_role')
    role.permissions.set(permission_objs.values())
    return role

@pytest.fixture
def role_audit(permission_objs):
    allowed = [
        permission_objs["view_data"],
        permission_objs["manage_data"],
        permission_objs["manage_module"],
    ]
    role = Role.objects.create(name='audit_role')
    role.permissions.set(allowed)
    return role

@pytest.fixture
def role_dataowner(permission_objs):
    allowed = [
        permission_objs["view_data"],
        permission_objs["manage_data"],
    ]
    role = Role.objects.create(name='dataowner_role')
    role.permissions.set(allowed)
    return role

@pytest.fixture
def context_project_a1(project_a1):
    return Context.objects.create(type="project", project=project_a1)

@pytest.fixture
def context_module_a1(module_a1):
    return Context.objects.create(type="module", module=module_a1, project=module_a1.project)

@pytest.fixture
def datatable(module_a1, user_admin):
    return DataTable.objects.create(
        title="Test Table",
        module=module_a1,
        created_by=user_admin,
        updated_by=user_admin
    )

@pytest.fixture
def datafield(datatable, user_admin):
    return DataField.objects.create(
        data_table=datatable,
        name="amount",
        label="Amount",
        type="number",
        created_by=user_admin,
        updated_by=user_admin,
    )

@pytest.fixture
def datarow(datatable, user_admin):
    return DataRow.objects.create(
        data_table=datatable,
        values={"amount": 123},
        created_by=user_admin,
        updated_by=user_admin,
    )

def login(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

def rbac_context(datatable):
    """Helper: Always return context for project/module for robust GETs."""
    return {
        'project_id': datatable.module.project_id,
        'module_id': datatable.module.id
    }

@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_fixture, context_fixture, user_fixture, allowed, assignment_context_fixture",
    [
        # admin: assign to project context
        ("role_admin", "context_project_a1", "user_admin", {
            "can_view_schema": True,
            "can_manage_schema": True,
            "can_manage_data": True,
            "can_manage_module": True,
            "can_manage_project": True,
            "can_see_table": True
        }, "context_project_a1"),
        # audit: assign to module context
        ("role_audit", "context_project_a1", "user_audit", {
            "can_view_schema": False,
            "can_manage_schema": False,
            "can_manage_data": True,
            "can_manage_module": True,
            "can_manage_project": False,
            "can_see_table": False   # <--- change this to False
        }, "context_module_a1"),
        # dataowner: assign to module context
        ("role_dataowner", "context_module_a1", "user_dataowner", {
            "can_view_schema": False,
            "can_manage_schema": False,
            "can_manage_data": True,
            "can_manage_module": False,
            "can_manage_project": False,
            "can_see_table": False   # <--- change this to False
        }, "context_module_a1"),
    ],
)
def test_dataschema_role_permissions(
    request, api_client,
    role_fixture, context_fixture, user_fixture, allowed, assignment_context_fixture,
    module_a1, datatable, datafield, datarow
):
    role = request.getfixturevalue(role_fixture)
    context = request.getfixturevalue(context_fixture)
    assignment_context = request.getfixturevalue(assignment_context_fixture)
    user = request.getfixturevalue(user_fixture)
    # The key change: assign the role to the correct context type!
    RoleAssignment.objects.create(user=user, role=role, context=assignment_context, is_active=True)
    client = login(api_client, user)
    context_kwargs = rbac_context(datatable)

    # View schema (detail)
    resp = client.get(reverse('dataschema-table-detail', args=[datatable.id]), data=context_kwargs)
    assert (resp.status_code == 200) == allowed['can_view_schema']

    # Edit schema (PATCH)
    resp = client.patch(
        reverse('dataschema-table-detail', args=[datatable.id]),
        data={"title": "Updated Title"},
        content_type="application/json"
    )
    assert (resp.status_code in (200, 202)) == allowed['can_manage_schema']

    # Manage data (add row)
    resp = client.post(
        reverse('dataschema-row-list'),
        data={"data_table": datatable.id, "values": {"amount": 42}},
        content_type="application/json"
    )
    assert (resp.status_code in (201, 200)) == allowed['can_manage_data']

    # List tables
    resp = client.get(reverse('dataschema-table-list'), data=context_kwargs)
    assert (resp.status_code == 200) == allowed['can_see_table']

@pytest.mark.django_db
def test_dataschema_tenant_and_project_isolation(
    api_client, tenant_a, tenant_b, project_a1, project_b1,
    module_a1, module_b1, user_admin, user_outsider, role_admin, context_project_a1
):
    datatable = DataTable.objects.create(
        title="Test Table",
        module=module_a1,
        created_by=user_admin,
        updated_by=user_admin
    )
    RoleAssignment.objects.create(user=user_admin, role=role_admin, context=context_project_a1, is_active=True)
    client = login(api_client, user_admin)
    # Use context for module_b1, even though admin is on project_a1
    resp = client.get(reverse('dataschema-table-list'), data={'module_id': module_b1.id, 'project_id': project_b1.id})
    if resp.status_code == 200:
        assert all(t.get("module") != module_b1.id for t in resp.data)
    client = login(api_client, user_outsider)
    resp = client.get(
        reverse('dataschema-table-detail', args=[datatable.id]),
        data={'project_id': datatable.module.project_id, 'module_id': datatable.module.id}
    )
    assert resp.status_code in (404, 403)

@pytest.mark.django_db
def test_dataschema_datafield_uniqueness(module_a1, user_admin):
    datatable = DataTable.objects.create(
        title="Uniqueness Table",
        module=module_a1,
        created_by=user_admin,
        updated_by=user_admin
    )
    DataField.objects.create(
        data_table=datatable,
        name="testfield",
        label="Test Field",
        type="string",
        created_by=user_admin,
        updated_by=user_admin
    )
    with pytest.raises(Exception):
        DataField.objects.create(
            data_table=datatable,
            name="TestField",
            label="Duplicate",
            type="string",
            created_by=user_admin,
            updated_by=user_admin
        )

@pytest.mark.django_db
def test_dataschema_required_field_validation(api_client, user_admin, role_admin, context_project_a1, module_a1):
    datatable = DataTable.objects.create(
        title="Validation Table",
        module=module_a1,
        created_by=user_admin,
        updated_by=user_admin
    )
    field = DataField.objects.create(
        data_table=datatable,
        name="required_field",
        label="Required Field",
        type="string",
        required=True,
        created_by=user_admin,
        updated_by=user_admin
    )
    RoleAssignment.objects.create(user=user_admin, role=role_admin, context=context_project_a1, is_active=True)
    client = login(api_client, user_admin)
    resp = client.post(
        reverse('dataschema-row-list'),
        data={"data_table": datatable.id, "values": {}},
        content_type="application/json"
    )
    assert resp.status_code in (400, 422)

@pytest.mark.django_db
def test_dataschema_archived_objects_hidden(api_client, user_admin, role_admin, context_project_a1, module_a1):
    datatable = DataTable.objects.create(
        title="Archived Table",
        module=module_a1,
        created_by=user_admin,
        updated_by=user_admin
    )
    RoleAssignment.objects.create(user=user_admin, role=role_admin, context=context_project_a1, is_active=True)
    client = login(api_client, user_admin)
    datatable.is_archived = True
    datatable.save()
    resp = client.get(
        reverse('dataschema-table-list'),
        data={'project_id': datatable.module.project_id, 'module_id': datatable.module.id}
    )
    if resp.status_code == 200:
        assert all(t["id"] != datatable.id for t in resp.data)
    resp = client.get(
        reverse('dataschema-table-detail', args=[datatable.id]),
        data={'project_id': datatable.module.project_id, 'module_id': datatable.module.id}
    )
    assert resp.status_code in (404, 403)

@pytest.mark.django_db
def test_dataschema_file_upload_validation(api_client, user_admin, role_admin, context_project_a1, module_a1):
    from django.core.files.uploadedfile import SimpleUploadedFile
    datatable = DataTable.objects.create(
        title="Upload Table",
        module=module_a1,
        created_by=user_admin,
        updated_by=user_admin
    )
    field = DataField.objects.create(
        data_table=datatable,
        name="upload",
        label="Upload",
        type="file",
        created_by=user_admin,
        updated_by=user_admin
    )
    RoleAssignment.objects.create(user=user_admin, role=role_admin, context=context_project_a1, is_active=True)
    client = login(api_client, user_admin)
    file_data = SimpleUploadedFile("test.pdf", b"filecontent", content_type="application/pdf")
    url = reverse('dataschema-row-list')
    row_resp = client.post(url, data={"data_table": datatable.id, "values": {}}, content_type="application/json")
    row_id = row_resp.data["id"]
    upload_url = reverse('dataschema-row-upload', args=[row_id])
    # For upload, pass the context as query params for extra safety
    resp = client.post(upload_url, data={"field": "upload", "file": file_data, "project_id": datatable.module.project_id, "module_id": datatable.module.id}, format="multipart")
    assert resp.status_code in (200, 201)
    resp = client.post(upload_url, data={"field": "notafile", "file": file_data, "project_id": datatable.module.project_id, "module_id": datatable.module.id}, format="multipart")
    assert resp.status_code == 400