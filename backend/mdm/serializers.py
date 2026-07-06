# mdm/serializers.py
from rest_framework import serializers
from .models import ReferenceSet, ReferenceValue, OrgUnit


class ReferenceValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceValue
        fields = ['id', 'reference_set', 'code', 'label', 'description',
                  'is_active', 'sort_order', 'valid_from', 'valid_to', 'metadata']


class ReferenceSetSerializer(serializers.ModelSerializer):
    value_count = serializers.SerializerMethodField()

    class Meta:
        model = ReferenceSet
        fields = ['id', 'name', 'slug', 'description', 'domain', 'steward',
                  'is_active', 'version', 'value_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'value_count', 'created_at', 'updated_at']

    def get_value_count(self, obj):
        return obj.values.count()


class OrgUnitSerializer(serializers.ModelSerializer):
    full_path = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = OrgUnit
        fields = [
            'id', 'name', 'slug', 'code', 'org_type', 'parent',
            'description', 'is_active', 'full_path', 'children_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'full_path', 'children_count', 'created_at', 'updated_at']

    def get_full_path(self, obj):
        return obj.full_path()

    def get_children_count(self, obj):
        return obj.children.count()
