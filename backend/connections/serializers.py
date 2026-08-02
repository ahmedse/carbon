# connections/serializers.py
from rest_framework import serializers
from .models import DataSource, ConsumingConnection
from .services import MASK_VALUE, mask_config


class MaskedConfigField(serializers.JSONField):
    """Connection-config field: full value accepted on write, masked (***) on
    read. Stored secrets therefore never appear in any API response."""

    def to_representation(self, value):
        return mask_config(value)


class DataSourceSerializer(serializers.ModelSerializer):
    owner_name = serializers.StringRelatedField(source='owner', read_only=True)
    domain_name = serializers.StringRelatedField(source='domain', read_only=True)
    connection_config = MaskedConfigField(required=False)

    class Meta:
        model = DataSource
        fields = [
            'id', 'name', 'slug', 'source_type', 'description',
            'connection_config', 'status', 'domain', 'domain_name',
            'owner', 'owner_name', 'last_tested_at', 'last_test_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Auto-set owner to current user if not provided
        if 'owner' not in validated_data or not validated_data['owner']:
            validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Clients read back masked values, so a PATCH may echo them back.
        # Treat MASK_VALUE entries as "keep the stored secret" instead of
        # overwriting the stored config with literal '***'.
        config = validated_data.get('connection_config')
        if config is not None:
            existing = instance.connection_config
            if isinstance(existing, dict) and isinstance(config, dict):
                merged = dict(existing)
                for key, value in config.items():
                    if value == MASK_VALUE:
                        continue  # masked placeholder -> keep stored secret
                    merged[key] = value
                validated_data['connection_config'] = merged
        return super().update(instance, validated_data)


class ConsumingConnectionSerializer(serializers.ModelSerializer):
    owner_name = serializers.StringRelatedField(source='owner', read_only=True)
    # Never expose the hash/salt or plaintext key in the API response
    api_key_hash = serializers.SerializerMethodField()

    class Meta:
        model = ConsumingConnection
        fields = [
            'id', 'name', 'slug', 'system_type', 'description',
            'api_key_hash', 'scopes', 'is_active',
            'owner', 'owner_name', 'last_used_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'slug', 'api_key_hash', 'last_used_at', 'created_at', 'updated_at'
        ]

    def get_api_key_hash(self, obj):
        """Return a masked indication if a key is set."""
        if obj.api_key_hash:
            return "***SET***"
        return None

    def create(self, validated_data):
        if 'owner' not in validated_data or not validated_data['owner']:
            validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)
