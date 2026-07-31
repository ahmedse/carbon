from .models import Module, Feedback
from .serializers import ModuleSerializer, FeedbackSerializer
from .feedback import AppFeedback
from accounts.permissions import HasScopedRole
from accounts.rbac_utils import get_visible_module_ids
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    required_role = ("admin", "admins_group")

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [HasScopedRole()]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Module.objects.none()
        user = self.request.user
        visible = get_visible_module_ids(user)
        if visible is None:
            return Module.objects.all()
        return Module.objects.filter(id__in=visible)

    def destroy(self, request, *args, **kwargs):
        """
        Delete validation: prevent deletion if module is locked or has tables.
        Superuser may override table dependency with ?force=true.
        """
        instance = self.get_object()

        # Governance policy enforcement
        from catalog.policy_engine import check_policy
        allowed, blocked_by = check_policy('module_delete', org_unit_id=instance.org_unit_id, module=instance)
        if not allowed:
            raise AppFeedback(
                code="policy_blocked",
                title="Action blocked by governance policy",
                detail=f"Delete is blocked by: {', '.join(blocked_by)}",
                reasons=[f"Active policy '{name}' prevents this action." for name in blocked_by],
                remediation=["Contact a platform administrator to review or disable the policy."],
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Locked guard
        if getattr(instance, "is_locked", False) and not request.user.is_superuser:
            raise AppFeedback(
                code="module_locked",
                title="Data product is locked",
                detail=f"'{instance.name}' is locked to prevent accidental changes.",
                reasons=["This data product has been locked by an administrator."],
                remediation=[
                    "Ask an administrator to unlock it before deleting.",
                    "Unlocking is available in the data product settings.",
                ],
                context={"module_id": instance.id, "is_locked": True},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Dependency guard
        table_count = instance.data_tables.count()
        if table_count > 0:
            force = request.query_params.get("force", "").lower() == "true"
            if not (force and request.user.is_superuser):
                raise AppFeedback(
                    code="module_has_tables",
                    title="Cannot delete data product",
                    detail=f"'{instance.name}' still contains {table_count} table(s).",
                    reasons=[
                        f"This data product has {table_count} table(s) attached to it.",
                        "Deleting it would remove all of those tables and their data.",
                    ],
                    remediation=[
                        "Move or delete the tables inside this data product first.",
                        "Then retry deleting the data product.",
                    ],
                    context={"module_id": instance.id, "table_count": table_count},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        return super().destroy(request, *args, **kwargs)

class FeedbackViewSet(mixins.CreateModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    """
    API for submitting and listing feedback.
    Only staff can list; anyone can submit.
    """
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer

    def get_permissions(self):
        # Only allow listing for staff, allow create for anyone (or customize as needed)
        from rest_framework.permissions import IsAdminUser, AllowAny
        if self.action == 'list':
            return [IsAdminUser()]
        return [AllowAny()]