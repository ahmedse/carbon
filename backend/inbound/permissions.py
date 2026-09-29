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
