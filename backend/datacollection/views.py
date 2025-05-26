# backend/datacollection/views.py

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

class ReadingItemDefinitionViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingItemDefinition.objects.all()  # Added queryset
    serializer_class = ReadingItemDefinitionSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "manage_item_definitions"

    def get_queryset(self):
        context = self.get_context_from_request(self.request)
        if context:
            return ReadingItemDefinition.objects.filter(context=context)
        return ReadingItemDefinition.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        serializer.save(context=context)

class ReadingTemplateViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingTemplate.objects.all()  # Added queryset
    serializer_class = ReadingTemplateSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "manage_templates"

    def get_queryset(self):
        context = self.get_context_from_request(self.request)
        if context:
            return ReadingTemplate.objects.filter(context=context)
        return ReadingTemplate.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        serializer.save(context=context)

class ReadingTemplateFieldViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingTemplateField.objects.all()  # Added queryset
    serializer_class = ReadingTemplateFieldSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "manage_templates"

    def get_queryset(self):
        context = self.get_context_from_request(self.request)
        if context:
            return ReadingTemplateField.objects.filter(template__context=context)
        return ReadingTemplateField.objects.none()

class ReadingEntryViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ReadingEntry.objects.all()  # Added queryset
    serializer_class = ReadingEntrySerializer
    permission_classes = [HasRBACPermission]
    required_permission = "submit_entry"

    def get_queryset(self):
        context = self.get_context_from_request(self.request)
        if context:
            return ReadingEntry.objects.filter(context=context)
        return ReadingEntry.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        serializer.save(context=context, submitted_by=self.request.user)

class EvidenceFileViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = EvidenceFile.objects.all()  # Added queryset
    serializer_class = EvidenceFileSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "upload_evidence"

    def get_queryset(self):
        context = self.get_context_from_request(self.request)
        if context:
            return EvidenceFile.objects.filter(context=context)
        return EvidenceFile.objects.none()

    def perform_create(self, serializer):
        context = self.get_context_from_request(self.request)
        serializer.save(context=context)

class ContextAssignmentViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = ContextAssignment.objects.all()  # Added queryset
    serializer_class = ContextAssignmentSerializer
    permission_classes = [HasRBACPermission]
    required_permission = "assign_roles"

    def get_queryset(self):
        context = self.get_context_from_request(self.request)
        if context:
            return ContextAssignment.objects.filter(context=context)
        return ContextAssignment.objects.none()