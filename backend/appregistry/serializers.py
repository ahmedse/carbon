"""
appregistry/serializers.py — thin DRF serializers for the App Registry.

Validation at the serializer boundary; activation business rules live in
appregistry/services.py.
"""
from rest_framework import serializers

from .models import AppActivation, AppManifest


class AppManifestSerializer(serializers.ModelSerializer):
    """Full manifest + effective activation state.

    ``is_active`` reflects the runtime activation record when one exists
    (AppActivation), otherwise the manifest's declared default.
    """
    activation = serializers.SerializerMethodField()

    class Meta:
        model = AppManifest
        fields = [
            'id', 'name', 'slug', 'version', 'description', 'icon',
            'entry_route', 'required_modules', 'required_capabilities',
            'consumed_datasets', 'is_system', 'is_active',
            'activation', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'is_system', 'activation', 'created_at', 'updated_at',
        ]

    def get_activation(self, obj):
        activation = getattr(obj, 'activation', None)
        return {
            'is_active': activation.is_active if activation else obj.is_active,
            'activated_at': activation.activated_at if activation else None,
            'deactivated_at': activation.deactivated_at if activation else None,
        }


class AppActivationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppActivation
        fields = ['app', 'is_active', 'activated_at', 'deactivated_at']
        read_only_fields = ['app', 'activated_at', 'deactivated_at']
