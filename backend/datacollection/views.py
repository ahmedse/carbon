from django.shortcuts import render

from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from accounts.permissions import HasRBACPermission  # Import RBAC permission
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
)
from .serializers import (
    ReadingItemDefinitionSerializer,
    ReadingTemplateSerializer,
    ReadingTemplateFieldSerializer,
    ReadingEntrySerializer,
    EvidenceFileSerializer,
)

class ReadingItemDefinitionViewSet(viewsets.ModelViewSet):
    queryset = ReadingItemDefinition.objects.all()
    serializer_class = ReadingItemDefinitionSerializer
    # permission_classes = [HasRBACPermission]
    # required_permission = "manage_item_definitions"
    permission_classes = [AllowAny]  # Temporarily allow any user

    def get_context(self, request):
        # For global admin actions, context can be None or global
        return None

class ReadingTemplateViewSet(viewsets.ModelViewSet):
    queryset = ReadingTemplate.objects.all()
    serializer_class = ReadingTemplateSerializer
    # permission_classes = [HasRBACPermission]
    # required_permission = "manage_templates"
    from rest_framework.permissions import AllowAny

    def get_context(self, request):
        return None

class ReadingTemplateFieldViewSet(viewsets.ModelViewSet):
    queryset = ReadingTemplateField.objects.all()
    serializer_class = ReadingTemplateFieldSerializer
    # permission_classes = [HasRBACPermission]
    # required_permission = "manage_templates"
    from rest_framework.permissions import AllowAny

    def get_context(self, request):
        return None

class ReadingEntryViewSet(viewsets.ModelViewSet):
    queryset = ReadingEntry.objects.all()
    serializer_class = ReadingEntrySerializer
    # permission_classes = [HasRBACPermission]
    # required_permission = "submit_entry"
    from rest_framework.permissions import AllowAny

    def get_context(self, request):
        # Example: context could be derived from the entry's template or project
        # You may need to adjust this logic based on your Context model
        entry_id = self.kwargs.get('pk')
        if entry_id:
            entry = ReadingEntry.objects.filter(pk=entry_id).first()
            if entry:
                return entry.template  # Or entry.context if you add FK
        return None

class EvidenceFileViewSet(viewsets.ModelViewSet):
    queryset = EvidenceFile.objects.all()
    serializer_class = EvidenceFileSerializer
    # permission_classes = [HasRBACPermission]
    # required_permission = "upload_evidence"
    from rest_framework.permissions import AllowAny

    def get_context(self, request):
        return None