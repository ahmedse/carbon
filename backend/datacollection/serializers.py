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

User = get_user_model()

class ContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = Context
        fields = '__all__'

class ReadingItemDefinitionSerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True
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
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True
    )

    # Only show items from the same module and context
    available_items = serializers.SerializerMethodField(read_only=True)

    def get_available_items(self, obj):
        if obj.context and obj.module:
            items = ReadingItemDefinition.objects.filter(context=obj.context, module=obj.module)
            return ReadingItemDefinitionSerializer(items, many=True).data
        return []

    class Meta:
        model = ReadingTemplate
        fields = '__all__' 

class ReadingEntrySerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True
    )
    item = serializers.PrimaryKeyRelatedField(
        queryset=ReadingItemDefinition.objects.all()
    )

    class Meta:
        model = ReadingEntry
        fields = '__all__'

class EvidenceFileSerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True
    )

    class Meta:
        model = EvidenceFile
        fields = '__all__'

class ContextAssignmentSerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True
    )
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = ContextAssignment
        fields = '__all__'