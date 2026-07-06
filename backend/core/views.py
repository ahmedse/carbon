from .models import Module, Feedback
from .serializers import ModuleSerializer, FeedbackSerializer
from accounts.permissions import HasScopedRole
from accounts.rbac_utils import get_allowed_module_ids, user_has_global_role
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny, IsAdminUser


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
        user = self.request.user
        if user.is_superuser or user_has_global_role(user, ["admin", "admins_group"]):
            return Module.objects.all()
        allowed = get_allowed_module_ids(
            user, ["admin", "admins_group", "dataowners_group", "auditors_group"]
        )
        return Module.objects.filter(id__in=allowed)

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