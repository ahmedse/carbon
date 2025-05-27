from rest_framework import viewsets
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
    ContextAssignment
)
from .serializers import (
    ReadingItemDefinitionSerializer,
    ReadingTemplateSerializer,
    ReadingTemplateFieldSerializer,
    ReadingEntrySerializer,
    EvidenceFileSerializer,
    ContextAssignmentSerializer
)
from accounts.permissions import HasRBACPermission
from accounts.context_mixin import ContextExtractorMixin

def user_tenant(request):
    return getattr(request.user, 'tenant', None)

def audit_print(prefix, **kwargs):
    print(f"[AUDIT] {prefix}")
    for k, v in kwargs.items():
        print(f"    {k}: {v}")

class TenantProjectBaseViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    """
    Base viewset: always filters by project_id (from context_id) and tenant.
    Child classes set:
      - queryset
      - serializer_class
      - required_permission
    """
    permission_classes = [HasRBACPermission]
    queryset = None  # Set in child

    def get_project_id(self):
        # Uses the mixin's method, which checks for context_id in both data and query params
        return self.get_project_id_from_request(self.request)

    def get_queryset(self):
        tenant = user_tenant(self.request)
        project_id = self.get_project_id()

        print("[AUDIT] get_queryset user:", self.request.user)
        print("[AUDIT] get_queryset project_id:", project_id)
        print("[AUDIT] get_queryset tenant:", tenant)
        print("[AUDIT] get_queryset query_params:", dict(self.request.query_params))
        print("[AUDIT] get_queryset data:", dict(getattr(self.request, "data", {})))

        audit_print(
            "get_queryset",
            user=str(self.request.user),
            project_id=project_id,
            tenant=str(tenant)
        )
        if not project_id or not tenant:
            return self.queryset.none()
        return self.queryset.model.objects.filter(
            project_id=project_id,
            project__tenant=tenant
        )

    def perform_create(self, serializer):
        project_id = self.get_project_id()
        tenant = user_tenant(self.request)
        from core.models import Project
        audit_print(
            "perform_create",
            user=str(self.request.user),
            project_id=project_id,
            tenant=str(tenant),
            data=self.request.data
        )
        try:
            project = Project.objects.get(
                id=project_id,
                tenant=tenant
            )
        except Project.DoesNotExist:
            audit_print("PermissionError", reason="Project not found or does not belong to tenant")
            raise PermissionError("Project not found or does not belong to your tenant.")
        # Final check: user.tenant must match project.tenant
        if tenant != project.tenant:
            audit_print("PermissionError", reason="User tenant does not match project tenant")
            raise PermissionError("You do not have access to this project.")
        serializer.save(project=project)
        audit_print("Saved object", object=serializer.instance)

class ReadingItemDefinitionViewSet(TenantProjectBaseViewSet):
    queryset = ReadingItemDefinition.objects.all()
    serializer_class = ReadingItemDefinitionSerializer
    required_permission = "manage_item_definitions"

class ReadingTemplateViewSet(TenantProjectBaseViewSet):
    queryset = ReadingTemplate.objects.all()
    serializer_class = ReadingTemplateSerializer
    required_permission = "manage_templates"

class ReadingTemplateFieldViewSet(TenantProjectBaseViewSet):
    queryset = ReadingTemplateField.objects.all()
    serializer_class = ReadingTemplateFieldSerializer
    required_permission = "manage_templates"

class ReadingEntryViewSet(TenantProjectBaseViewSet):
    queryset = ReadingEntry.objects.all()
    serializer_class = ReadingEntrySerializer
    required_permission = "manage_data"

    def perform_create(self, serializer):
        project_id = self.get_project_id()
        tenant = user_tenant(self.request)
        from core.models import Project
        audit_print(
            "ReadingEntry perform_create",
            user=str(self.request.user),
            project_id=project_id,
            tenant=str(tenant),
            data=self.request.data
        )
        try:
            project = Project.objects.get(
                id=project_id,
                tenant=tenant
            )
        except Project.DoesNotExist:
            audit_print("PermissionError", reason="Project not found or does not belong to tenant")
            raise PermissionError("Project not found or does not belong to your tenant.")
        if tenant != project.tenant:
            audit_print("PermissionError", reason="User tenant does not match project tenant")
            raise PermissionError("You do not have access to this project.")
        # Add audit log to entry
        audit_trail = [{
            "action": "created",
            "user": str(self.request.user),
            "data": dict(self.request.data),
        }]
        serializer.save(project=project, submitted_by=self.request.user, audit_log=audit_trail)
        audit_print("Saved ReadingEntry", object=serializer.instance)

class EvidenceFileViewSet(TenantProjectBaseViewSet):
    queryset = EvidenceFile.objects.all()
    serializer_class = EvidenceFileSerializer
    required_permission = "manage_data"

    def perform_create(self, serializer):
        project_id = self.get_project_id()
        tenant = user_tenant(self.request)
        from core.models import Project
        audit_print(
            "EvidenceFile perform_create",
            user=str(self.request.user),
            project_id=project_id,
            tenant=str(tenant),
            data=self.request.data
        )
        try:
            project = Project.objects.get(
                id=project_id,
                tenant=tenant
            )
        except Project.DoesNotExist:
            audit_print("PermissionError", reason="Project not found or does not belong to tenant")
            raise PermissionError("Project not found or does not belong to your tenant.")
        if tenant != project.tenant:
            audit_print("PermissionError", reason="User tenant does not match project tenant")
            raise PermissionError("You do not have access to this project.")
        serializer.save(project=project)
        audit_print("Saved EvidenceFile", object=serializer.instance)

class ContextAssignmentViewSet(TenantProjectBaseViewSet):
    queryset = ContextAssignment.objects.all()
    serializer_class = ContextAssignmentSerializer
    required_permission = "assign_roles"