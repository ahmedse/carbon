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

    def validate(self, data):
        data_table = data.get('data_table') or (self.instance.data_table if self.instance else None)
        name = data.get('name') or (self.instance.name if self.instance else None)
        if DataField.objects.filter(data_table=data_table, name=name).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Field name must be unique within the table.")
        if data.get('type') in ['select', 'multiselect']:
            options = data.get('options')
            if not options or not isinstance(options, list) or not all('value' in opt for opt in options):
                raise serializers.ValidationError("Options must be a list of dicts with a 'value' key for select/multiselect fields.")
        return data

class DataTableDetailSerializer(serializers.ModelSerializer):
    fields = DataFieldSerializer(many=True, read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    row_count = serializers.SerializerMethodField()

    def get_row_count(self, obj):
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
    def validate_values(self, values):
        if not isinstance(values, dict):
            raise serializers.ValidationError("Values must be a JSON object.")
        return values

    def validate(self, data):
        data_table = data.get('data_table') or (self.instance.data_table if self.instance else None)
        if data_table:
            required_fields = data_table.fields.filter(required=True).values_list('name', flat=True)
            values = data.get('values', {})
            missing = [f for f in required_fields if f not in values or values[f] in (None, '', [])]
            if missing:
                raise serializers.ValidationError({f: "This field is required." for f in missing})
            for f in data_table.fields.all():
                if f.name in values:
                    val = values[f.name]
                    # Type: number
                    if f.type == 'number' and not isinstance(val, (int, float)):
                        raise serializers.ValidationError({f.name: "Must be a number."})
                    # Type: boolean
                    if f.type == 'boolean' and not isinstance(val, bool):
                        raise serializers.ValidationError({f.name: "Must be true or false."})
                    # Type: select
                    if f.type == 'select':
                        allowed = [opt['value'] for opt in f.options or []]
                        if val not in allowed:
                            raise serializers.ValidationError({f.name: f"Value must be one of {allowed}."})
                    # Type: multiselect
                    if f.type == 'multiselect':
                        allowed = [opt['value'] for opt in f.options or []]
                        if not isinstance(val, list) or not all(v in allowed for v in val):
                            raise serializers.ValidationError({f.name: f"All values must be in {allowed}."})
        return data

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