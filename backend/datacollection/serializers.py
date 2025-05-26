from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
    ContextAssignment
)
from accounts.models import Context
from core.models import Module

User = get_user_model()

class ContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = Context
        fields = '__all__'

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'name', 'project']

class TenantScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """
    Restricts related field queryset to the current user's tenant.
    """
    def get_queryset(self):
        request = self.context.get('request', None)
        if not request or not hasattr(request.user, 'tenant'):
            return Module.objects.none()
        # The Module's project must match the user's tenant
        return Module.objects.filter(project__tenant=request.user.tenant)

class TenantScopedContextRelatedField(serializers.PrimaryKeyRelatedField):
    """
    Restricts Context queryset to the current user's tenant.
    """
    def get_queryset(self):
        request = self.context.get('request', None)
        if not request or not hasattr(request.user, 'tenant'):
            return Context.objects.none()
        return Context.objects.filter(project__tenant=request.user.tenant)

class ReadingItemDefinitionSerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = TenantScopedContextRelatedField(
        source='context', write_only=True
    )
    module = ModuleSerializer(read_only=True)
    module_id = TenantScopedPrimaryKeyRelatedField(
        source='module', write_only=True
    )

    class Meta:
        model = ReadingItemDefinition
        fields = '__all__'

class ReadingTemplateFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingTemplateField
        fields = '__all__'

class ReadingTemplateSerializer(serializers.ModelSerializer):
    fields = ReadingTemplateFieldSerializer(many=True, read_only=True, source='readingtemplatefield_set')
    context = ContextSerializer(read_only=True)
    context_id = TenantScopedContextRelatedField(
        source='context', write_only=True
    )
    module = ModuleSerializer(read_only=True)
    module_id = TenantScopedPrimaryKeyRelatedField(
        source='module', write_only=True
    )

    available_items = serializers.SerializerMethodField(read_only=True)

    def get_available_items(self, obj):
        if obj.context and obj.module:
            items = ReadingItemDefinition.objects.filter(context=obj.context, module=obj.module)
            return ReadingItemDefinitionSerializer(items, many=True, context=self.context).data
        return []

    class Meta:
        model = ReadingTemplate
        fields = '__all__' 

class ReadingEntrySerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = TenantScopedContextRelatedField(
        source='context', write_only=True
    )
    item = serializers.PrimaryKeyRelatedField(
        queryset=ReadingItemDefinition.objects.all()
    )

    class Meta:
        model = ReadingEntry
        fields = '__all__'

class EvidenceFileSerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = TenantScopedContextRelatedField(
        source='context', write_only=True
    )

    class Meta:
        model = EvidenceFile
        fields = '__all__'

class ContextAssignmentSerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = TenantScopedContextRelatedField(
        source='context', write_only=True
    )
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = ContextAssignment
        fields = '__all__'