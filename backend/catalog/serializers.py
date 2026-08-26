# catalog/serializers.py
from rest_framework import serializers
from .models import DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent, GovernancePolicy, LineageEdge, FreshnessPolicy


class DataDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataDomain
        fields = ['id', 'name', 'slug', 'description', 'parent', 'owner', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class GlossaryTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlossaryTerm
        fields = ['id', 'term', 'slug', 'definition', 'domain', 'synonyms', 'steward', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'color']
        read_only_fields = ['id', 'slug']


class AssetProfileSerializer(serializers.ModelSerializer):
    asset_type = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all(), required=False)

    class Meta:
        model = AssetProfile
        fields = [
            'id', 'asset_type', 'title', 'data_table', 'data_field',
            'description', 'domain', 'owner', 'steward', 'classification',
            'semantic_type', 'glossary_term', 'tags',
            'quality_status', 'quality_score', 'updated_at', 'updated_by',
        ]
        read_only_fields = [
            'id', 'asset_type', 'title', 'data_table', 'data_field',
            'quality_status', 'quality_score', 'updated_at', 'updated_by',
        ]

    def get_asset_type(self, obj):
        return 'field' if obj.data_field_id else 'table'

    def get_title(self, obj):
        if obj.data_field_id:
            return f"{obj.data_field.label} ({obj.data_field.data_table.title})"
        return obj.data_table.title if obj.data_table_id else ''


class GovernanceEventSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = GovernanceEvent
        fields = ['id', 'asset', 'entity_type', 'entity_id', 'action', 'before', 'after', 'user', 'username', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class GovernancePolicySerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = GovernancePolicy
        fields = [
            'id', 'policy_type', 'name', 'description', 'enabled', 
            'config', 'created_at', 'updated_at', 'updated_by', 'updated_by_username'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'updated_by', 'updated_by_username']


class LineageEdgeSerializer(serializers.ModelSerializer):
    source_table_name = serializers.CharField(source='source_table.title', read_only=True)
    target_table_name = serializers.CharField(source='target_table.title', read_only=True)
    source_field_name = serializers.CharField(source='source_field.label', read_only=True, allow_null=True)
    target_field_name = serializers.CharField(source='target_field.label', read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = LineageEdge
        fields = [
            'id', 'source_table', 'target_table', 'source_field', 'target_field',
            'source_table_name', 'target_table_name', 'source_field_name', 'target_field_name',
            'edge_type', 'transform_description', 'created_by', 'created_by_username', 'created_at'
        ]
        read_only_fields = ['id', 'source_table_name', 'target_table_name', 'source_field_name', 
                            'target_field_name', 'created_by', 'created_by_username', 'created_at']


class FreshnessPolicySerializer(serializers.ModelSerializer):
    table_title = serializers.CharField(source='table.title', read_only=True)
    last_data_updated_at = serializers.DateTimeField(
        source='table.last_data_updated_at', read_only=True, allow_null=True)

    class Meta:
        model = FreshnessPolicy
        fields = [
            'id', 'table', 'table_title', 'max_age_hours', 'alert_level',
            'enabled', 'last_checked_at', 'last_alerted_at', 'last_data_updated_at',
        ]
        read_only_fields = [
            'id', 'table', 'table_title', 'last_checked_at', 'last_alerted_at',
            'last_data_updated_at',
        ]
