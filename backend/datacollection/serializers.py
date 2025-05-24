from rest_framework import serializers
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
)
from accounts.models import Context

class ContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = Context
        fields = '__all__'

class ReadingItemDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingItemDefinition
        fields = '__all__'

class ReadingTemplateFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingTemplateField
        fields = '__all__'

class ReadingTemplateSerializer(serializers.ModelSerializer):
    fields = ReadingItemDefinitionSerializer(many=True, read_only=True)
    context = ContextSerializer(read_only=True)
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True, required=False
    )

    class Meta:
        model = ReadingTemplate
        fields = '__all__'

class ReadingEntrySerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True, required=False
    )

    class Meta:
        model = ReadingEntry
        fields = '__all__'

class EvidenceFileSerializer(serializers.ModelSerializer):
    context = ContextSerializer(read_only=True)
    context_id = serializers.PrimaryKeyRelatedField(
        queryset=Context.objects.all(), source='context', write_only=True, required=False
    )

    class Meta:
        model = EvidenceFile
        fields = '__all__'