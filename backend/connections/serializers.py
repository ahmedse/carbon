# connections/serializers.py
from rest_framework import serializers
from .models import DataSource, ConsumingConnection


class DataSourceSerializer(serializers.ModelSerializer):
    owner_name = serializers.StringRelatedField(source='owner', read_only=True)
    domain_name = serializers.StringRelatedField(source='domain', read_only=True)

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
