# File: accounts/utils.py

from .models import RoleAssignment

def get_user_permission_matrix(user, project_id):
    """
    Returns a list of all roles and permissions for the user
    in the project and all its modules.
    """
    assignments = (
        user.role_assignments
        .filter(is_active=True, context__project_id=project_id)
        .select_related('role', 'context')
    )
    matrix = []
    for ra in assignments:
        matrix.append({
            "role": ra.role.name,
            "permissions": [p.code for p in ra.role.permissions.all()],
            "context_type": ra.context.type,
            "context_id": ra.context.id,
            "module_id": ra.context.module_id,
            "project_id": ra.context.project_id,
        })
    return matrix

def audit_user_permissions(user, project_id):
    """
    Prints a detailed audit of all the user's active roles and permissions for the given project.
    """
    matrix = get_user_permission_matrix(user, project_id)
    # print for debugging/auditing if needed

def user_has_permission(user, permission_code, project_id, module_id=None):
    if user.is_superuser:
        return True

    # Check project-level roles
    project_assignment = RoleAssignment.objects.filter(
        user=user,
        is_active=True,
        context__type='project',
        context__project_id=project_id,
        role__permissions__code=permission_code,
    ).exists()

    if project_assignment:
        return True

    # Check module-level roles
    if module_id:
        module_assignment = RoleAssignment.objects.filter(
            user=user,
            is_active=True,
            context__type='module',
            context__module_id=module_id,
            role__permissions__code=permission_code,
        ).exists()
        if module_assignment:
            return True

    return False