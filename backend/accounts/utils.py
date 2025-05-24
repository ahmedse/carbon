# File: accounts/utils.py
# Purpose: Utility functions for RBAC permission checks.

def user_has_permission(user, permission, context):
    """
    Determines whether the user has the specified permission in the provided context.
    Checks the most specific context first, then walks up the hierarchy:
    module -> cycle -> project -> global.

    Args:
        user: The user object.
        permission: The permission string to check (e.g., "add_data").
        context: The context object representing the scope.

    Returns:
        bool: True if the user has the permission, otherwise False.
    """
    qs = user.role_assignments.filter(role__permissions__contains=[permission])

    # Check exact context
    if qs.filter(context=context).exists():
        return True

    # Check parent contexts if available
    if context.type == 'module':
        # Check cycle-level
        if qs.filter(context__type='cycle', context__cycle=context.cycle).exists():
            return True
        # Check project-level
        if qs.filter(context__type='project', context__project=context.project).exists():
            return True
    if context.type in ['module', 'cycle']:
        # Check global-level
        if qs.filter(context__type='global').exists():
            return True
    return False