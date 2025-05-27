# File: accounts/utils.py

def get_user_permission_matrix(user, project_id):
    """
    Returns a list of all roles and permissions for the user
    in the project and all its modules.
    """
    # Get all active role assignments for this user where the context (project or module) is part of this project
    assignments = (
        user.role_assignments
        .filter(is_active=True, context__project_id=project_id)
        .select_related('role', 'context')
    )
    matrix = []
    for ra in assignments:
        matrix.append({
            "role": ra.role.name,
            "permissions": ra.role.permissions,
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
    print(f"\n[AUDIT] ===== User '{user}' roles/permissions for project {project_id} =====")
    if not matrix:
        print("[AUDIT] No roles found for this project.")
    for entry in matrix:
        print(f"[AUDIT] Role: {entry['role']} | Context: {entry['context_type']} (context_id={entry['context_id']}, module_id={entry['module_id']})")
        print(f"        Permissions: {entry['permissions']}")
    print("[AUDIT] =============================================================\n")

def user_has_permission(user, permission, project_id):
    """
    Returns True if user has the permission on the given project, at project or any module context.
    Logs which role/context grants the permission for auditing.
    """
    audit_user_permissions(user, project_id)
    for entry in get_user_permission_matrix(user, project_id):
        if permission in entry["permissions"]:
            print(f"[AUDIT] Permission '{permission}' GRANTED to user '{user}' via role '{entry['role']}' in context {entry['context_type']} (context_id={entry['context_id']}, module_id={entry['module_id']})\n")
            return True
    print(f"[AUDIT] Permission '{permission}' DENIED to user '{user}' on project {project_id}\n")
    return False