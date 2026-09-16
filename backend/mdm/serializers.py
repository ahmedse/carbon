# mdm/serializers.py
from django.utils import timezone
from rest_framework import serializers

from .governed import resolve_reference_value
from .models import ReferenceSet, ReferenceValue, OrgUnit


class GovernedValueField(serializers.Field):
    """ADR-0027 governed lookup: FK to ``mdm.ReferenceValue``.

    Read shape: ``{id, code, label, set}`` or ``null``.
    Write shape: integer PK **or** string code within ``set_name``
    (resolved to a ``ReferenceValue`` instance). Blank/null → null when
    ``allow_null=True``. Never creates ReferenceValues (RULE_16).
    """

    def __init__(self, set_name, **kwargs):
        self.set_name = set_name
        kwargs.setdefault('allow_null', True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value is None:
            return None
        if isinstance(value, int):
            try:
                value = ReferenceValue.objects.select_related('reference_set').get(pk=value)
            except ReferenceValue.DoesNotExist:
                return None
        set_name = self.set_name
        if getattr(value, 'reference_set_id', None):
            # Prefer the related set name when already loaded / available.
            try:
                set_name = value.reference_set.name
            except Exception:
                set_name = self.set_name
        return {
            'id': value.pk,
            'code': value.code,
            'label': value.label,
            'set': set_name,
        }

    def to_internal_value(self, data):
        if data is None or data == '':
            if not self.allow_null:
                raise serializers.ValidationError('This field may not be null.')
            return None

        # Nested write: {"id": 12} or {"code": "EGY"}
        if isinstance(data, dict):
            if data.get('id') is not None:
                data = data['id']
            elif data.get('code') is not None:
                data = data['code']
            else:
                raise serializers.ValidationError(
                    'Expected reference id, code, or {id|code} object.'
                )

        try:
            return resolve_reference_value(
                self.set_name,
                data,
                as_of=timezone.localdate(),
                require_current=True,
            )
        except ReferenceSet.DoesNotExist:
            raise serializers.ValidationError(
                f"Reference set {self.set_name!r} is not configured"
            )
        except ReferenceValue.DoesNotExist:
            raise serializers.ValidationError(
                f"{data!r} is not a current value of reference set {self.set_name!r}"
            )
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'Expected reference id (int) or code (string).'
            )


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
    
    values = ReferenceValueSerializer(many=True, read_only=True)
    steward_name = serializers.SerializerMethodField()
    domain_name = serializers.CharField(
        source='domain.name', read_only=True, allow_null=True
    )
    value_count = serializers.SerializerMethodField()

    class Meta:
        model = ReferenceSet
        fields = [
            'id', 'name', 'slug', 'description', 'domain', 'domain_name',
            'steward', 'steward_name', 'is_active', 'version', 'lifecycle_state',
            'value_count', 'values',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'value_count', 'lifecycle_state', 'created_at', 'updated_at'
        ]

    def get_steward_name(self, obj):
        """Return steward's username or full name."""
        if not obj.steward:
            return None
        full_name = obj.steward.get_full_name()
        if full_name and full_name.strip():
            return full_name
        return obj.steward.username
    
    def get_value_count(self, obj):
        """Return count of active values.

        Uses the values_count annotation from the view queryset when present
        (avoids N+1 queries on list views), otherwise falls back to a direct query.
        """
        annotated = getattr(obj, 'values_count', None)
        if annotated is not None:
            return annotated
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

    def to_internal_value(self, data):
        """Normalize JSON null for optional fields (frontend `|| null` idiom).

        The OrgUnit model contract is `blank=True` (empty string), NOT
        null=True. The MDM edit dialog sends null for empty code/description
        fields (e.g. when an admin changes only the parent) and null/'' for an
        unset org_type (UI 'None' option) — previously these all surfaced as
        DRF 400 "This field may not be null." / "not a valid choice".

        Only JSON dict payloads are normalized: multipart/form-data arrives as
        a QueryDict (values would be lists after dict()) and DRF must handle
        it natively.
        """
        if isinstance(data, dict):
            data = {k: v for k, v in data.items()}
            for field in ('code', 'description'):
                if field in data and data[field] is None:
                    data[field] = ''
            if 'org_type' in data and data['org_type'] in (None, ''):
                data['org_type'] = 'other'  # model default for 'unspecified'
        return super().to_internal_value(data)

    class Meta:
        model = OrgUnit
        fields = [
            'id', 'name', 'slug', 'code', 'org_type', 'description',
            'manager_employee_id',
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
        """Count direct children from prefetched cache (P14 — no DB hit)."""
        return sum(1 for c in obj.children.all() if c.is_active)

    def get_descendants_count(self, obj):
        """Count all active descendants using prefetched children cache (BFS)."""
        count = 0
        frontier = [c for c in obj.children.all() if c.is_active]
        visited = {c.id for c in frontier}
        while frontier:
            child = frontier.pop(0)
            count += 1
            for grandchild in child.children.all():
                if grandchild.id not in visited and grandchild.is_active:
                    visited.add(grandchild.id)
                    frontier.append(grandchild)
        return count

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
        """Validate against circular references and ADR-0028 single root."""
        # Check if parent is being set and would create a circular ref
        new_parent = data.get('parent')
        if self.instance and new_parent:
            # Check if new_parent is a descendant of this unit
            descendant_ids = self.instance.get_descendant_ids(include_self=True)
            if new_parent.id in descendant_ids:
                raise serializers.ValidationError(
                    "Cannot set parent to be a descendant of this unit (circular reference)"
                )

        # Resolve effective parent / is_active for create + partial update
        if self.instance:
            parent = data['parent'] if 'parent' in data else self.instance.parent
            is_active = data['is_active'] if 'is_active' in data else self.instance.is_active
            exclude_pk = self.instance.pk
        else:
            parent = data.get('parent')
            is_active = data.get('is_active', True)
            exclude_pk = None
        if parent is None and is_active:
            qs = OrgUnit.objects.filter(parent__isnull=True, is_active=True)
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            other = qs.first()
            if other is not None:
                raise serializers.ValidationError({
                    'parent': (
                        f"Only one active root OrgUnit is allowed per deployment "
                        f"(ADR-0028). Active root already exists: "
                        f"id={other.id} slug={other.slug!r}."
                    )
                })
        return data
