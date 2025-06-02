# File: dataschema/serializers.py

from rest_framework import serializers
from .models import DataTable, DataField, DataRow, SchemaChangeLog

class DataFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataField
        fields = [
            'id', 'data_table', 'name', 'label', 'type', 'order',
            'description', 'required', 'options', 'validation',
            'is_active', 'is_archived', 'version',
            'reference_table',
            'created_at', 'created_by', 'updated_at', 'updated_by'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version'
        ]

class DataTableDetailSerializer(serializers.ModelSerializer):
    fields = DataFieldSerializer(many=True, read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    row_count = serializers.SerializerMethodField()

    def get_row_count(self, obj):
        # Use correct related_name ('rows')
        return obj.rows.filter(is_archived=False).count()

    class Meta:
        model = DataTable
        fields = [
            'id', 'title', 'description', 'module', 'module_name', 'version',
            'is_archived', 'created_at', 'created_by', 'updated_at', 'updated_by', 'fields', 'row_count'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version', 'fields', 'row_count'
        ]

class DataTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataTable
        fields = [
            'id', 'title', 'description', 'module', 'version',
            'is_archived', 'created_at', 'created_by', 'updated_at', 'updated_by'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version'
        ]

class DataRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataRow
        fields = [
            'id', 'data_table', 'values',
            'created_at', 'created_by', 'updated_at', 'updated_by',
            'is_archived', 'version'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version'
        ]

class SchemaChangeLogSerializer(serializers.ModelSerializer):
    data_table_title = serializers.CharField(source='data_table.title', read_only=True)
    data_field_label = serializers.CharField(source='data_field.label', read_only=True)

    class Meta:
        model = SchemaChangeLog
        fields = [
            'id', 'action', 'data_table', 'data_table_title', 'data_field',
            'data_field_label', 'before', 'after', 'user', 'timestamp', 'notes'
        ]
        read_only_fields = [
            'id', 'timestamp'
        ]