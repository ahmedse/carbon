from rest_framework.permissions import BasePermission

from accounts.capabilities import has_capability


def _admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from accounts.models import ScopedRole
    return ScopedRole.objects.filter(
        user=user,
        group__name__in=['admin', 'admins_group'],
        org_unit__isnull=True, module__isnull=True,
    ).live().exists()


def can_prepare(user) -> bool:
    if _admin(user):
        return True
    return has_capability(user, 'inbound:prepare')


def can_commit(user) -> bool:
    if _admin(user):
        return True
    return has_capability(user, 'inbound:commit')


def can_see(user) -> bool:
    return can_prepare(user) or can_commit(user)


def can_see_all(user) -> bool:
    """Full import visibility: superuser, staff, global admin, or commit-capable.

    The two-person rule requires a committer to see a batch prepared by someone
    else, so commit is a full-visibility role. A prepare-only user is scoped to
    the batches they own (``prepared_by`` / ``committed_by``).
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_staff', False):
        return True
    return can_commit(user)


def can_manage_template(user, template) -> bool:
    """A template is editable by its owner; shared/official (ownerless) rows and
    other users' rows only by staff/admin. Never by a peer preparer."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_staff', False) or _admin(user):
        return True
    return template is not None and template.owner_id is not None and template.owner_id == user.id


def can_define(user) -> bool:
    if _admin(user):
        return True
    return has_capability(user, 'inbound:define')


def can_use_typed(user) -> bool:
    if _admin(user):
        return True
    return has_capability(user, 'people:manage')


def can_use_product(user) -> bool:
    if _admin(user):
        return True
    return (
        has_capability(user, 'datahub:ingest')
        or has_capability(user, 'catalog:manage_products')
    )


def can_use_kind(user, kind: str) -> bool:
    if kind == 'typed_object':
        return can_use_typed(user)
    if kind == 'data_product':
        return can_use_product(user)
    return False


class InboundAccess(BasePermission):
    """List/retrieve: prepare or commit. Mutating prepare actions: prepare. commit: commit."""

    PREPARE_ACTIONS = {'create', 'file', 'mapping', 'smoke'}

    def has_permission(self, request, view):
        action = getattr(view, 'action', None)
        if action == 'commit':
            return can_commit(request.user)
        if action in self.PREPARE_ACTIONS:
            return can_prepare(request.user)
        return can_see(request.user)
