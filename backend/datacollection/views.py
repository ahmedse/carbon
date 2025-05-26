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
from core.models import Module

# --- Tenant filtering helper ---
def user_tenant(request):
    return getattr(request.user, 'tenant', None)

class ReadingItemDefinitionViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingItemDefinition.objects.none()
    serializer_class = ReadingItemDefinitionSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "manage_item_definitions"

    def get_queryset(self):
        tenant = user_tenant(self.request)
        context = self.get_context_from_request(self.request)
        if context and context.project and context.project.tenant == tenant:
            return ReadingItemDefinition.objects.filter(context=context)
        return ReadingItemDefinition.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        tenant = user_tenant(self.request)
        # Safety: Ensure context belongs to user's tenant
        if context and context.project and context.project.tenant == tenant:
            serializer.save(context=context)
        else:
            raise PermissionError("Invalid context for your tenant.")

class ReadingTemplateViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingTemplate.objects.none()
    serializer_class = ReadingTemplateSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "manage_templates"

    def get_queryset(self):
        tenant = user_tenant(self.request)
        context = self.get_context_from_request(self.request)
        if context and context.project and context.project.tenant == tenant:
            return ReadingTemplate.objects.filter(context=context)
        return ReadingTemplate.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        tenant = user_tenant(self.request)
        if context and context.project and context.project.tenant == tenant:
            serializer.save(context=context)
        else:
            raise PermissionError("Invalid context for your tenant.")

class ReadingTemplateFieldViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingTemplateField.objects.none()
    serializer_class = ReadingTemplateFieldSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "manage_templates"

    def get_queryset(self):
        tenant = user_tenant(self.request)
        context = self.get_context_from_request(self.request)
        if context and context.project and context.project.tenant == tenant:
            return ReadingTemplateField.objects.filter(template__context=context)
        return ReadingTemplateField.objects.none()

class ReadingEntryViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingEntry.objects.none()
    serializer_class = ReadingEntrySerializer
    permission_classes = [HasRBACPermission]
    required_permission = "submit_entry"

    def get_queryset(self):
        tenant = user_tenant(self.request)
        context = self.get_context_from_request(self.request)
        if context and context.project and context.project.tenant == tenant:
            return ReadingEntry.objects.filter(context=context)
        return ReadingEntry.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        tenant = user_tenant(self.request)
        if context and context.project and context.project.tenant == tenant:
            serializer.save(context=context, submitted_by=self.request.user)
        else:
            raise PermissionError("Invalid context for your tenant.")

class EvidenceFileViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = EvidenceFile.objects.none()
    serializer_class = EvidenceFileSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "upload_evidence"

    def get_queryset(self):
        tenant = user_tenant(self.request)
        context = self.get_context_from_request(self.request)
        if context and context.project and context.project.tenant == tenant:
            return EvidenceFile.objects.filter(context=context)
        return EvidenceFile.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        tenant = user_tenant(self.request)
        if context and context.project and context.project.tenant == tenant:
            serializer.save(context=context)
        else:
            raise PermissionError("Invalid context for your tenant.")

class ContextAssignmentViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ContextAssignment.objects.none()
    serializer_class = ContextAssignmentSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "assign_roles"

    def get_queryset(self):
        tenant = user_tenant(self.request)
        context = self.get_context_from_request(self.request)
        if context and context.project and context.project.tenant == tenant:
            return ContextAssignment.objects.filter(context=context)
        return ContextAssignment.objects.none()