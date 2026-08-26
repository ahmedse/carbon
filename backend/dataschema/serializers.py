from rest_framework import serializers
from .models import DataTable, DataField, DataRow, SchemaChangeLog, TableRelation

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

    def to_representation(self, instance):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request is not None else None
        if user is not None and getattr(user, 'is_authenticated', False):
            from accounts.capabilities import has_capability
            # access_policies is prefetched in views; .all() also works for N+1-safe-enough
            for policy in instance.access_policies.all():
                if not has_capability(user, policy.required_capability):
                    if policy.action == 'deny':
                        return {'id': instance.id, 'name': instance.name, 'access_denied': True}
                    else:  # mask
                        data = super().to_representation(instance)
                        data['is_masked'] = True
                        return data
        return super().to_representation(instance)

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
        # Use prefetched cache — len() avoids COUNT query (P14)
        return sum(1 for r in obj.rows.all() if not r.is_archived)

    class Meta:
        model = DataTable
        fields = [
            'id', 'title', 'description', 'module', 'module_name', 'version',
            'is_archived', 'is_locked', 'created_at', 'created_by', 'updated_at', 'updated_by', 'fields', 'row_count'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version', 'fields', 'row_count'
        ]

class DataTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataTable
        fields = [
            'id', 'title', 'description', 'module', 'version',
            'is_archived', 'is_locked', 'created_at', 'created_by', 'updated_at', 'updated_by'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version'
        ]

class DataRowSerializer(serializers.ModelSerializer):
    dq_flags = serializers.JSONField(read_only=True)

    def validate_values(self, values):
        if not isinstance(values, dict):
            raise serializers.ValidationError("Values must be a JSON object.")
        return values

    def validate(self, data):
        data_table = data.get('data_table') or (self.instance.data_table if self.instance else None)
        if data_table:
            values = data.get('values', {})
            if self.instance and self.partial:
                existing_values = self.instance.values or {}
                if not isinstance(existing_values, dict):
                    existing_values = {}
                values = {**existing_values, **(values or {})}
            elif values is None:
                values = {}

            # Unified Level 1 validation against field metadata (P19)
            from .validators import validate_row
            fields = list(data_table.fields.filter(is_active=True))
            errors = validate_row(values, fields)
            if errors:
                raise serializers.ValidationError(
                    {e['field']: e['message'] for e in errors}
                )

            # ── Level 2: DQ Gate ─────────────────────────────────────
            from dq.gate import check_rows
            gate_result = check_rows(data_table, [values])
            self._gate_result = gate_result  # store for create/update

            if gate_result['summary']['blocked'] > 0:
                blocked_failures = [
                    f for rv in gate_result['row_verdicts']
                    if rv['verdict'] == 'block'
                    for f in rv['failures']
                ]
                raise serializers.ValidationError(
                    {f['field']: f['message'] for f in blocked_failures}
                )

        return data

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._persist_gate_warnings(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._persist_gate_warnings(instance)
        return instance

    def _persist_gate_warnings(self, instance):
        """Append warn/info-level gate failures to instance.dq_flags."""
        gate_result = getattr(self, '_gate_result', None)
        if not gate_result:
            return

        from django.utils import timezone
        new_flags = []
        for rv in gate_result.get('row_verdicts', []):
            for f in rv.get('failures', []):
                if f['severity'] in ('warn', 'info'):
                    new_flags.append({
                        'rule_id': f['rule_id'],
                        'rule_name': f['rule_name'],
                        'severity': f['severity'],
                        'message': f['message'],
                        'at': timezone.now().isoformat(),
                    })

        if new_flags:
            current = list(instance.dq_flags) if instance.dq_flags else []
            current.extend(new_flags)
            instance.dq_flags = current
            instance.save(update_fields=['dq_flags'])

    class Meta:
        model = DataRow
        fields = [
            'id', 'data_table', 'values', 'dq_flags',
            'created_at', 'created_by', 'updated_at', 'updated_by',
            'is_archived', 'version'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version', 'dq_flags'
        ]

class TableRelationSerializer(serializers.ModelSerializer):
    from_table_title = serializers.CharField(source='from_table.title', read_only=True)
    from_field_label = serializers.CharField(source='from_field.label', read_only=True, allow_null=True)
    to_table_title = serializers.CharField(source='to_table.title', read_only=True)
    to_field_label = serializers.CharField(source='to_field.label', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by', read_only=True, allow_null=True)

    class Meta:
        model = TableRelation
        fields = [
            'id', 'from_table', 'from_table_title', 'from_field', 'from_field_label',
            'to_table', 'to_table_title', 'to_field', 'to_field_label',
            'relation_type', 'label', 'description', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']


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