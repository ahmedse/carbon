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
from core.models import Module, Project

User = get_user_model()

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name', 'tenant']

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'name', 'project']

class ReadingItemDefinitionSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)
    # Do NOT require project_id from frontend

    class Meta:
        model = ReadingItemDefinition
        fields = '__all__'
        extra_kwargs = {
            'project': {'read_only': True}
        }

class ReadingTemplateFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingTemplateField
        fields = '__all__'

class ReadingTemplateSerializer(serializers.ModelSerializer):
    fields = ReadingTemplateFieldSerializer(many=True, read_only=True, source='readingtemplatefield_set')
    project = ProjectSerializer(read_only=True)
    module = ModuleSerializer(read_only=True)
    module_id = serializers.PrimaryKeyRelatedField(
        queryset=Module.objects.all(), source='module', write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = ReadingTemplate
        fields = '__all__'
        extra_kwargs = {
            'project': {'read_only': True}
        }

class ReadingEntrySerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)
    item = serializers.PrimaryKeyRelatedField(
        queryset=ReadingItemDefinition.objects.all()
    )

    class Meta:
        model = ReadingEntry
        fields = '__all__'
        extra_kwargs = {
            'project': {'read_only': True}
        }

class EvidenceFileSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = EvidenceFile
        fields = '__all__'
        extra_kwargs = {
            'project': {'read_only': True}
        }

class ContextAssignmentSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = ContextAssignment
        fields = '__all__'
        extra_kwargs = {
            'project': {'read_only': True}
        }