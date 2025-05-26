# File: accounts/utils.py

def user_has_permission(user, permission, context):
    """
    Determines whether the user has the specified permission in the provided context.
    Checks the most specific context first, then walks up the hierarchy:
    module -> project.
    """
    qs = user.role_assignments.filter(role__permissions__contains=[permission])

    # Check exact context (module or project)
    if qs.filter(context=context).exists():
        return True

    # If context is a module, check project-level assignment
    if context.type == 'module' and context.project:
        if qs.filter(context__type='project', context__project=context.project).exists():
            return True

    # No match found
    return False