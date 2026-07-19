# mdm/serializers.py
from rest_framework import serializers
from .models import ReferenceSet, ReferenceValue, OrgUnit


class ReferenceValueSerializer(serializers.ModelSerializer):
    """Serializer for ReferenceValue with validation."""
    
    class Meta:
        model = ReferenceValue
        fields = [
            'id', 'reference_set', 'code', 'label', 'description',
            'is_active', 'sort_order', 'valid_from', 'valid_to', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_code(self, value):
        """Ensure code is alphanumeric with underscores only."""
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError(
                "Code must be alphanumeric with underscores only"
            )
        return value

    def validate(self, data):
        """Validate valid_from <= valid_to if both are provided."""
        valid_from = data.get('valid_from')
        valid_to = data.get('valid_to')
        
        if valid_from and valid_to and valid_from > valid_to:
            raise serializers.ValidationError(
                "valid_from must be before valid_to"
            )
        return data


class ReferenceSetSerializer(serializers.ModelSerializer):
    """Serializer for ReferenceSet with nested values and steward details."""
    
    values = ReferenceValueSerializer(
        many=True, source='values', read_only=True
    )
    steward_name = serializers.CharField(
        source='steward.get_full_name', read_only=True
    )
    domain_name = serializers.CharField(
        source='domain.name', read_only=True
    )
    value_count = serializers.SerializerMethodField()

    class Meta:
        model = ReferenceSet
        fields = [
            'id', 'name', 'slug', 'description', 'domain', 'domain_name',
            'steward', 'steward_name', 'is_active', 'version',
            'value_count', 'values',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'value_count', 'steward', 'created_at', 'updated_at'
        ]

    def get_value_count(self, obj):
        """Return count of active values."""
        return obj.values.filter(is_active=True).count()

    def validate_name(self, value):
        """Ensure name is unique."""
        qs = ReferenceSet.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(
                "Reference set with this name already exists"
            )
        return value


class OrgUnitSerializer(serializers.ModelSerializer):
    """Serializer for OrgUnit with tree structure support."""
    
    full_path = serializers.SerializerMethodField(read_only=True)
    parent_name = serializers.CharField(
        source='parent.name', read_only=True, allow_null=True
    )
    children_count = serializers.SerializerMethodField(read_only=True)
    descendants_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OrgUnit
        fields = [
            'id', 'name', 'slug', 'code', 'org_type', 'description',
            'parent', 'parent_name', 'is_active',
            'full_path', 'children_count', 'descendants_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'slug', 'full_path', 'children_count', 'descendants_count',
            'created_at', 'updated_at'
        ]

    def get_full_path(self, obj):
        """Return full path from root to this unit."""
        return obj.full_path()

    def get_children_count(self, obj):
        """Count direct children."""
        return obj.children.filter(is_active=True).count()

    def get_descendants_count(self, obj):
        """Count all descendants (not including self)."""
        return len(obj.get_descendant_ids(include_self=False))

    def validate_name(self, value):
        """Ensure name is unique within parent scope."""
        parent = self.initial_data.get('parent')
        qs = OrgUnit.objects.filter(name=value, parent_id=parent)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(
                "An org unit with this name already exists in this parent"
            )
        return value

    def validate(self, data):
        """Validate against circular references."""
        # Check if parent is being set and would create a circular ref
        new_parent = data.get('parent')
        if self.instance and new_parent:
            # Check if new_parent is a descendant of this unit
            descendant_ids = self.instance.get_descendant_ids(include_self=True)
            if new_parent.id in descendant_ids:
                raise serializers.ValidationError(
                    "Cannot set parent to be a descendant of this unit (circular reference)"
                )
        return data
