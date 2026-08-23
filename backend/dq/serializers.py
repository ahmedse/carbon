# dq/serializers.py
from rest_framework import serializers
from .models import TableProfile, FieldProfile, DQRule, DQResult, DQProfileConfig
from .models import FreshnessCheck, SchemaSnapshot, SchemaChange, RuleTag, RuleFieldAssignment
from .models import DQJob, DQSuggestion, DQAnomaly
from dataschema.models import DataField
from .rule_schema import rule_field_type_compatible


class DQJobSerializer(serializers.ModelSerializer):
    """Serializer for Phase 3 DQ jobs.

    Write: job_type (validated by the view), rule/data_table/payload.
    Read: full lifecycle view — status, result, progress, error, pulse_task_id.
    """
    rule_name = serializers.CharField(source='rule.name', read_only=True, allow_null=True)
    table_name = serializers.CharField(source='data_table.name', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )

    class Meta:
        model = DQJob
        fields = [
            'id', 'job_type', 'status', 'rule', 'rule_name',
            'data_table', 'table_name', 'payload', 'result',
            'pulse_task_id', 'progress', 'error',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'result', 'pulse_task_id', 'progress', 'error',
            'created_by', 'created_at', 'updated_at',
        ]


class TableProfileSerializer(serializers.ModelSerializer):
    """Serializer for table data quality profiles."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    
    class Meta:
        model = TableProfile
        fields = [
            'id', 'data_table', 'table_name', 'row_count',
            'completeness_pct', 'null_counts', 'distinct_counts',
            'min_values', 'max_values', 'mean_values', 'profiled_at'
        ]
        read_only_fields = fields


DQProfileConfigSerializer = type('DQProfileConfigSerializer', (serializers.ModelSerializer,), {
    'Meta': type('Meta', (), {
        'model': DQProfileConfig,
        'fields': ['id', 'freshness_threshold_hours', 'volume_anomaly_pct'],
    })
})


class FieldProfileSerializer(serializers.ModelSerializer):
    """Serializer for field data quality profiles."""
    field_name = serializers.CharField(source='data_field.name', read_only=True)
    
    class Meta:
        model = FieldProfile
        fields = [
            'id', 'data_field', 'field_name', 'row_count', 'null_count', 
            'distinct_count', 'completeness_pct', 'uniqueness_pct', 
            'min_value', 'max_value', 'mean_value', 'top_values', 'profiled_at'
        ]
        read_only_fields = ['id', 'profiled_at']


class RuleTagSerializer(serializers.ModelSerializer):
    """Simple serializer for rule categorization tags."""
    class Meta:
        model = RuleTag
        fields = ['id', 'name', 'color', 'description']


class RuleFieldAssignmentSerializer(serializers.ModelSerializer):
    """Field assignments for a DQ rule.

    Used read-only when embedded in rule responses, and writable for the
    dedicated create/delete endpoint (POST/DELETE /dq/rule-assignments/).
    `rule` is required on create; omitting it used to drop the field and
    cause a rule_id NOT NULL IntegrityError on POST.
    """
    field_name = serializers.CharField(source='data_field.name', read_only=True, allow_null=True)
    table_name = serializers.CharField(source='data_table.name', read_only=True)

    class Meta:
        model = RuleFieldAssignment
        fields = ['id', 'rule', 'data_field', 'field_name', 'data_table', 'table_name']
        read_only_fields = ['id']

    def validate(self, data):
        # Cross-check: a field-level binding must target a field of the same
        # table, and a field cannot be bound twice to the same rule.
        from dataschema.models import DataTable
        from .models import DQRule

        data_table = data.get('data_table')
        data_field = data.get('data_field')
        rule = data.get('rule')
        if rule and not DQRule.objects.filter(pk=rule.pk).exists():
            raise serializers.ValidationError(
                {'rule': 'Referenced DQ rule does not exist'}
            )
        if data_table and not DataTable.objects.filter(pk=data_table.pk).exists():
            raise serializers.ValidationError(
                {'data_table': 'Referenced data table does not exist'}
            )
        if data_field and data_table and data_field.data_table_id != data_table.id:
            raise serializers.ValidationError(
                {'data_field': 'data_field must belong to the given data_table'}
            )
        if rule and data_field:
            if RuleFieldAssignment.objects.filter(
                rule=rule, data_field=data_field
            ).exists():
                raise serializers.ValidationError(
                    {'data_field': 'This rule is already bound to this field'}
                )
        return data


class DQRuleSerializer(serializers.ModelSerializer):
    """Serializer for data quality rules with M2M field assignments + tags.

    Write: provide `tag_ids` (list of int) and `field_assignments` (list of
    {data_field, data_table}). Read: returns nested `tags` and `field_assignments`.
    """
    name = serializers.CharField(required=False)
    rule_type = serializers.CharField(required=False)
    tags = RuleTagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False,
        help_text='List of RuleTag IDs to assign'
    )
    field_assignments = RuleFieldAssignmentSerializer(many=True, read_only=True)
    field_assignments_write = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False,
        help_text='List of {data_table (required), data_field (optional, int|null)} dicts'
    )
    replace_assignments = serializers.BooleanField(
        write_only=True, required=False, default=False,
        help_text='Confirm dropping existing bindings when field_assignments_write is empty'
    )
    results_count = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )

    class Meta:
        model = DQRule
        fields = [
            'id', 'rule_level', 'rule_type', 'name', 'description',
            'params', 'severity', 'is_active', 'tags', 'tag_ids',
            'field_assignments', 'field_assignments_write', 'replace_assignments',
            'results_count', 'is_locked',
            'dimension', 'definition', 'version', 'archived',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'results_count', 'is_locked', 'version',
                           'created_by', 'created_at', 'updated_at']

    def get_results_count(self, obj):
        return obj.results.count()

    def get_is_locked(self, obj):
        """Rule is locked if it has been executed at least once (has DQResults)."""
        return obj.results.exists()

    ALLOWED_RULE_TYPES = ['not_null', 'unique', 'allowed_values', 'range', 'regex',
                          'reference_integrity', 'threshold', 'nl_check']
    THRESHOLD_OPERATORS = {'gte', 'gt', 'lte', 'lt', 'eq', 'neq'}

    def validate_rule_type(self, value):
        if value not in self.ALLOWED_RULE_TYPES:
            raise serializers.ValidationError(
                f"rule_type must be one of {self.ALLOWED_RULE_TYPES}")
        return value

    def validate(self, data):
        definition = data.get('definition')
        if definition:
            from .rule_schema import validate_definition
            derrors = validate_definition(definition)
            if derrors:
                raise serializers.ValidationError({'definition': derrors})
            # D1 — definition is the source of truth: derive flat columns from it.
            data.setdefault('name', definition.get('name'))
            rt = definition.get('type')
            if rt not in self.ALLOWED_RULE_TYPES:
                raise serializers.ValidationError(
                    {'definition': f"type must be one of {self.ALLOWED_RULE_TYPES}"})
            data.setdefault('rule_type', rt)
            level = definition.get('level')
            if level in ('field', 'field_validation'):
                data.setdefault('rule_level', 'field_validation')
            elif level in ('business', 'business_rule'):
                data.setdefault('rule_level', 'business_rule')
            data.setdefault('severity', definition.get('severity', 'error'))
            data.setdefault('dimension', definition.get('dimension', 'validity'))
            if 'active' in definition:
                data.setdefault('is_active', bool(definition['active']))
        else:
            # No definition — flat fields are the source of truth (create only;
            # partial updates keep the instance's existing name/rule_type).
            if self.instance is None:
                if not data.get('name'):
                    raise serializers.ValidationError({'name': 'This field is required.'})
                if not data.get('rule_type'):
                    raise serializers.ValidationError({'rule_type': 'This field is required.'})
            # Keep the flat threshold validation (the definition path is already
            # covered by validate_definition's per-type params check).
            rule_type = data.get('rule_type')
            if rule_type == 'threshold':
                params = data.get('params', {})
                if not isinstance(params, dict):
                    raise serializers.ValidationError({"params": "params must be a JSON object"})
                operator = params.get('operator', 'gte')
                if operator not in self.THRESHOLD_OPERATORS:
                    raise serializers.ValidationError({
                        "params": f"operator must be one of {sorted(self.THRESHOLD_OPERATORS)}, got '{operator}'"
                    })
                if 'value' not in params:
                    raise serializers.ValidationError({"params": "value is required for threshold rules"})
                try:
                    float(params['value'])
                except (TypeError, ValueError):
                    raise serializers.ValidationError({
                        "params": f"value must be numeric, got '{params['value']}'"
                    })
        return data

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        field_assignments_data = validated_data.pop('field_assignments_write', [])
        validated_data.pop('replace_assignments', None)
        self._validate_field_applicability(
            validated_data.get('rule_type'), field_assignments_data,
        )
        rule = super().create(validated_data)
        if tag_ids:
            rule.tags.set(tag_ids)
        for assn in field_assignments_data:
            RuleFieldAssignment.objects.create(
                rule=rule,
                data_table_id=assn['data_table'],
                data_field_id=assn.get('data_field'),
            )
        return rule

    @staticmethod
    def _validate_field_applicability(rule_type, assignments):
        """Reject bindings whose field type is incompatible with the rule type.

        Business rules (data_field omitted) skip the check. Field-validation
        rules must bind to a field type the rule engine can meaningfully
        evaluate (see rule_schema.RULE_FIELD_TYPE_COMPAT).
        """
        errors = []
        for assn in assignments:
            field_id = assn.get('data_field')
            if not field_id:
                continue  # table-level business rule — no field to check
            try:
                field = DataField.objects.get(pk=field_id)
            except DataField.DoesNotExist:
                errors.append(f'data_field {field_id} does not exist')
                continue
            if not rule_field_type_compatible(rule_type, field.type):
                errors.append(
                    f"Rule type '{rule_type}' cannot apply to field "
                    f"'{field.name}' (type '{field.type}')"
                )
        if errors:
            raise serializers.ValidationError({'field_assignments_write': errors})

    @staticmethod
    def _reconcile_flat_into_definition(definition, validated_data):
        """Write explicit flat columns back into the definition dict.

        DQRule.save() re-derives name/severity/dimension/is_active from
        `definition`, so a flat-only PATCH (e.g. `{is_active: false}`) or a flat
        column that disagrees with the JSON (e.g. renaming via the top-level
        `name` field while `definition.name` is stale) would be silently reverted
        on save. Reconcile them here so definition stays the single source of
        truth and flat edits stick.
        """
        if 'name' in validated_data:
            definition['name'] = validated_data['name']
        if 'severity' in validated_data:
            definition['severity'] = validated_data['severity']
        if 'dimension' in validated_data:
            definition['dimension'] = validated_data['dimension']
        if 'description' in validated_data:
            definition['description'] = validated_data['description']
        if 'is_active' in validated_data:
            definition['active'] = bool(validated_data['is_active'])
        return definition

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        field_assignments_data = validated_data.pop('field_assignments_write', None)
        replace_assignments = validated_data.pop('replace_assignments', False)

        # F3 / D4 — drift guard: reject a silent drop of existing bindings.
        if field_assignments_data is not None:
            existing_count = instance.field_assignments.count()
            if not field_assignments_data and existing_count and not replace_assignments:
                raise serializers.ValidationError({
                    'field_assignments_write': (
                        f'Would drop {existing_count} existing binding(s). '
                        'Pass replace_assignments=true to confirm, or omit field_assignments_write.'
                    )
                })
            # Applicability guard: each field binding must match the rule type.
            self._validate_field_applicability(
                validated_data.get('rule_type', instance.rule_type),
                field_assignments_data,
            )

        # D1 — definition is the single source of truth, but honor explicit flat
        # columns so DQRule.save() does not revert them (rename / activate bug).
        flat_keys = ('name', 'severity', 'dimension', 'description', 'is_active')
        if any(k in validated_data for k in flat_keys):
            from .rule_schema import validate_definition
            definition = validated_data.get('definition')
            if definition is not None:
                # Definition supplied: merge flat columns into it and let the
                # normal version-bump logic below treat it as a definition edit.
                definition = self._reconcile_flat_into_definition(dict(definition), validated_data)
                derrors = validate_definition(definition)
                if derrors:
                    raise serializers.ValidationError({'definition': derrors})
                validated_data['definition'] = definition
            elif instance.definition:
                # Flat-only update on a definition-backed rule: update the stored
                # definition in place so save() re-syncs consistently, without
                # tripping the "definition changed → version bump" check.
                definition = self._reconcile_flat_into_definition(dict(instance.definition), validated_data)
                derrors = validate_definition(definition)
                if derrors:
                    raise serializers.ValidationError({'definition': derrors})
                instance.definition = definition

        # F7 — bump the monotonic version when the definition actually changes.
        if 'definition' in validated_data and instance.definition != validated_data['definition']:
            instance.version += 1

        rule = super().update(instance, validated_data)
        if tag_ids is not None:
            rule.tags.set(tag_ids)
        if field_assignments_data is not None:
            # Replace all existing assignments
            instance.field_assignments.all().delete()
            for assn in field_assignments_data:
                RuleFieldAssignment.objects.create(
                    rule=instance,
                    data_table_id=assn['data_table'],
                    data_field_id=assn.get('data_field'),
                )
        return rule


class DQResultSerializer(serializers.ModelSerializer):
    """Serializer for data quality rule execution results.

    Phase 4: `status` is one of passed|failed|skipped_unavailable. When
    status == 'skipped_unavailable', `passed` is null (the rule could not be
    evaluated — Pulse unavailable, fail-visible).
    """
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_type = serializers.CharField(source='rule.rule_type', read_only=True)

    class Meta:
        model = DQResult
        fields = [
            'id', 'rule', 'rule_name', 'rule_type', 'run_at', 'status', 'passed',
            'checked_count', 'failed_count', 'sample_failures', 'score'
        ]
        read_only_fields = ['id', 'run_at']


class DQSuggestionSerializer(serializers.ModelSerializer):
    """Phase 4: persisted Pulse rule suggestions awaiting review.

    payload holds the complete v1 rule definition — on accept it becomes a
    DQRule unchanged. Nothing auto-creates rules; a human reviews first.
    """
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )

    class Meta:
        model = DQSuggestion
        fields = [
            'id', 'data_table', 'table_name', 'payload', 'rationale',
            'confidence', 'status', 'reject_reason', 'job',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'data_table', 'table_name', 'payload', 'rationale',
            'confidence', 'status', 'reject_reason', 'job',
            'created_by', 'created_at', 'updated_at',
        ]


class DQAnomalySerializer(serializers.ModelSerializer):
    """Phase 4: anomalies returned by Pulse anomaly.detect (stats-first).

    expected_range = {'low': ..., 'high': ...}; score is the deviation
    magnitude (e.g. z-score); explanation is LLM-written only.
    """
    table_name = serializers.CharField(source='data_table.name', read_only=True)

    class Meta:
        model = DQAnomaly
        fields = [
            'id', 'data_table', 'table_name', 'metric', 'group_key',
            'expected_range', 'observed', 'score', 'explanation',
            'severity', 'job', 'detected_at',
        ]
        read_only_fields = ['id', 'detected_at']


class DQSuggestResponseSerializer(serializers.Serializer):
    """Serializer for DQ suggest API response."""
    table_id = serializers.IntegerField()
    status = serializers.CharField()
    suggestions = serializers.ListField(child=serializers.DictField())
    error = serializers.DictField(required=False)


# ── Phase 1.8: Freshness & Schema Monitoring serializers ──────────────

class FreshnessCheckSerializer(serializers.ModelSerializer):
    """Serializer for per-table freshness checks."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)

    class Meta:
        model = FreshnessCheck
        fields = [
            'id', 'data_table', 'table_name', 'expected_max_age_hours',
            'last_data_timestamp', 'is_fresh', 'checked_at',
        ]
        read_only_fields = ['id', 'checked_at']


class SchemaSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for table schema snapshots."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    column_count = serializers.SerializerMethodField()

    class Meta:
        model = SchemaSnapshot
        fields = [
            'id', 'data_table', 'table_name', 'column_schema',
            'row_count', 'snapshot_at', 'column_count',
        ]
        read_only_fields = ['id', 'snapshot_at']

    def get_column_count(self, obj):
        if isinstance(obj.column_schema, dict):
            return len(obj.column_schema)
        return 0


class SchemaChangeSerializer(serializers.ModelSerializer):
    """Serializer for detected schema changes between snapshots."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)

    class Meta:
        model = SchemaChange
        fields = [
            'id', 'data_table', 'table_name', 'snapshot_from', 'snapshot_to',
            'change_type', 'field_name', 'old_definition', 'new_definition',
            'detected_at',
        ]
        read_only_fields = ['id', 'detected_at']
