import pytest
from accounts.models import Tenant, User, Permission, Role, Context, RoleAssignment
from core.models import Project, Module

ADMIN_ROLE = 'admin_role'
AUDIT_ROLE = 'audit_role'
DATAOWNER_ROLE = 'dataowner_role'
PERMISSION_CODES = [
    "view_data",
    "manage_data",
    "view_schema",
    "manage_schema",
    "manage_module",
    "manage_project",
]

@pytest.fixture
def tenant():
    return Tenant.objects.create(name="Tenant A")

@pytest.fixture
def user(tenant):
    return User.objects.create_user(username="alice", password="pass", tenant=tenant)

@pytest.fixture
def permission_objs():
    perms = {}
    for code in [
        "view_data", "manage_data", "view_schema", "manage_schema", "manage_module", "manage_project"
    ]:
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
def project(tenant):
    return Project.objects.create(name="Project 1", tenant=tenant)

@pytest.fixture
def module(project):
    return Module.objects.create(name="Module 1", project=project)

@pytest.fixture
def module2(project):
    return Module.objects.create(name="Module 2", project=project)

@pytest.fixture
def context_project(project):
    return Context.objects.create(type="project", project=project)

@pytest.fixture
def context_module(module):
    return Context.objects.create(type="module", module=module, project=module.project)

@pytest.fixture
def context_module2(module2):
    return Context.objects.create(type="module", module=module2, project=module2.project)

@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_fixture, expected_permissions",
    [
        (
            'role_admin',
            {
                "project": {p: True for p in PERMISSION_CODES},
                "module": {p: True for p in PERMISSION_CODES},
                "module2": {p: True for p in PERMISSION_CODES},
            }
        ),
        (
            'role_audit',
            {
                "project": {p: False for p in PERMISSION_CODES},
                "module": {
                    "view_data": True,
                    "manage_data": True,
                    "view_schema": False,
                    "manage_schema": False,
                    "manage_module": True,
                    "manage_project": False,
                },
                "module2": {
                    "view_data": True,
                    "manage_data": True,
                    "view_schema": False,
                    "manage_schema": False,
                    "manage_module": True,
                    "manage_project": False,
                },
            }
        ),
        (
            'role_dataowner',
            {
                "project": {p: False for p in PERMISSION_CODES},
                "module": {
                    "view_data": True,
                    "manage_data": True,
                    "view_schema": False,
                    "manage_schema": False,
                    "manage_module": False,
                    "manage_project": False,
                },
                "module2": {p: False for p in PERMISSION_CODES},
            }
        ),
    ],
    ids=[
        "Admin: full access (project+modules)",
        "Audit: data+module only (modules only)",
        "Dataowner: data only (one module only)"
    ]
)
def test_rbac_all_roles_permission_matrix(
    user, project, module, module2, context_project, context_module, context_module2,
    role_fixture, request, expected_permissions
):
    from accounts.utils import user_has_permission

    role = request.getfixturevalue(role_fixture)

    if role_fixture == 'role_admin':
        # Assign admin at project and all modules
        RoleAssignment.objects.create(user=user, role=role, context=context_project, is_active=True)
        RoleAssignment.objects.create(user=user, role=role, context=context_module, is_active=True)
        RoleAssignment.objects.create(user=user, role=role, context=context_module2, is_active=True)
    elif role_fixture == 'role_audit':
        # Assign audit at module contexts only
        RoleAssignment.objects.create(user=user, role=role, context=context_module, is_active=True)
        RoleAssignment.objects.create(user=user, role=role, context=context_module2, is_active=True)
    elif role_fixture == 'role_dataowner':
        # Assign dataowner at one module context only
        RoleAssignment.objects.create(user=user, role=role, context=context_module, is_active=True)

    for perm, expected in expected_permissions['project'].items():
        print(f"[PROJECT] {role.name}: perm={perm} expected={expected}")
        assert user_has_permission(user, perm, project_id=project.id) is expected

    for perm, expected in expected_permissions['module'].items():
        print(f"[MODULE1] {role.name}: perm={perm} expected={expected}")
        assert user_has_permission(user, perm, project_id=project.id, module_id=module.id) is expected

    for perm, expected in expected_permissions['module2'].items():
        print(f"[MODULE2] {role.name}: perm={perm} expected={expected}")
        assert user_has_permission(user, perm, project_id=project.id, module_id=module2.id) is expected

    for perm in PERMISSION_CODES:
        print(f"[FAKE_MODULE] {role.name}: perm={perm} expected=False")
        assert user_has_permission(user, perm, project_id=project.id, module_id=999999) is False

@pytest.mark.django_db
def test_rbac_dataowner_additional_cases(user, role_dataowner, context_module, context_module2, project, module, module2):
    from accounts.utils import user_has_permission
    RoleAssignment.objects.create(user=user, role=role_dataowner, context=context_module, is_active=True)
    for perm in PERMISSION_CODES:
        if perm in {"view_data", "manage_data"}:
            print(f"[DATAOWNER MODULE1] perm={perm} expected=True")
            assert user_has_permission(user, perm, project_id=project.id, module_id=module.id)
            print(f"[DATAOWNER MODULE2] perm={perm} expected=False")
            assert not user_has_permission(user, perm, project_id=project.id, module_id=module2.id)
        else:
            print(f"[DATAOWNER MODULE1] perm={perm} expected=False")
            assert not user_has_permission(user, perm, project_id=project.id, module_id=module.id)
            print(f"[DATAOWNER MODULE2] perm={perm} expected=False")
            assert not user_has_permission(user, perm, project_id=project.id, module_id=module2.id)
        print(f"[DATAOWNER PROJECT] perm={perm} expected=False")
        assert not user_has_permission(user, perm, project_id=project.id)
        print(f"[DATAOWNER FAKE_MODULE] perm={perm} expected=False")
        assert not user_has_permission(user, perm, project_id=project.id, module_id=999999)

@pytest.mark.django_db
def test_rbac_no_assignment_no_permission(user, project, module):
    from accounts.utils import user_has_permission
    for perm in PERMISSION_CODES:
        print(f"[NO ASSIGN] perm={perm} expected=False")
        assert not user_has_permission(user, perm, project_id=project.id)
        assert not user_has_permission(user, perm, project_id=project.id, module_id=module.id)

@pytest.mark.django_db
def test_rbac_superuser_all_permissions(user, project, module):
    from accounts.utils import user_has_permission
    user.is_superuser = True
    user.save()
    for perm in PERMISSION_CODES:
        print(f"[SUPERUSER] perm={perm} expected=True")
        assert user_has_permission(user, perm, project_id=project.id)
        assert user_has_permission(user, perm, project_id=project.id, module_id=module.id)
        assert user_has_permission(user, perm, project_id=project.id, module_id=1234567)

@pytest.mark.django_db
def test_rbac_inactive_assignments(user, role_admin, context_project, project, module):
    from accounts.utils import user_has_permission
    RoleAssignment.objects.create(user=user, role=role_admin, context=context_project, is_active=False)
    for perm in PERMISSION_CODES:
        print(f"[INACTIVE ASSIGN] perm={perm} expected=False")
        assert not user_has_permission(user, perm, project_id=project.id)
        assert not user_has_permission(user, perm, project_id=project.id, module_id=module.id)

@pytest.mark.django_db
def test_rbac_multiple_assignments(user, role_admin, role_dataowner, context_project, context_module, project, module):
    from accounts.utils import user_has_permission
    RoleAssignment.objects.create(user=user, role=role_admin, context=context_project, is_active=True)
    RoleAssignment.objects.create(user=user, role=role_dataowner, context=context_module, is_active=True)
    for perm in PERMISSION_CODES:
        print(f"[MULTI-ASSIGN] perm={perm} expected=True")
        assert user_has_permission(user, perm, project_id=project.id)
        assert user_has_permission(user, perm, project_id=project.id, module_id=module.id)