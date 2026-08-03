# File: accounts/serializers.py
# DRF serializers for users, roles, scoped roles, and audit logs.

from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import User, ScopedRole, RoleAssignmentAuditLog, GroupMetadata, PlatformAppConfig

class UserSerializer(serializers.ModelSerializer):
    # Write-only: accepted on create/update, never returned in responses.
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_active', 'is_staff', 'password']
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class GroupSerializer(serializers.ModelSerializer):
    permissions_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    role_type = serializers.SerializerMethodField()
    app_id = serializers.SerializerMethodField()
    manifest_key = serializers.SerializerMethodField()
    is_scoped = serializers.SerializerMethodField()
    is_protected = serializers.SerializerMethodField()
    description = serializers.CharField(allow_blank=True, required=False, default='')

    class Meta:
        model = Group
        fields = [
            'id',
            'name',
            'description',
            'permissions_count',
            'users_count',
            'role_type',
            'app_id',
            'manifest_key',
            'is_scoped',
            'is_protected',
        ]
        read_only_fields = ['id', 'permissions_count', 'users_count', 'role_type', 'app_id', 'manifest_key', 'is_scoped', 'is_protected']

    def get_permissions_count(self, obj):
        return obj.permissions.count()

    def get_users_count(self, obj):
        from .models import ScopedRole
        return ScopedRole.objects.filter(group=obj, is_active=True).values('user').distinct().count()

    def get_role_type(self, obj):
        from .constants import VISIBILITY_ROLES, ADMINS_GROUP, ADMIN_GROUP
        name = obj.name.lower()
        platform_roles = {ADMIN_GROUP, ADMINS_GROUP, 'audit', 'steward', 'dataowners_group', 'data_owners_group', 'analysts_group', 'data_analysts_group'}
        if name in platform_roles or name.startswith('admin'):
            return 'platform'
        if '_' in name:
            return 'app'
        return 'platform'

    def get_app_id(self, obj):
        from .constants import ADMINS_GROUP, ADMIN_GROUP
        name = obj.name.lower()
        if '_' not in name:
            return None
        if name in {ADMINS_GROUP, ADMIN_GROUP, 'audit', 'steward'}:
            return None
        return name.split('_', 1)[0]

    def get_manifest_key(self, obj):
        app_id = self.get_app_id(obj)
        if not app_id:
            return None
        suffix = obj.name[len(app_id) + 1:]
        return f'{app_id}:{suffix}'

    def get_is_scoped(self, obj):
        name = obj.name.lower()
        return any(token in name for token in ['data_owner', 'dataowner', 'analyst', 'steward'])

    def get_is_protected(self, obj):
        from .constants import PROTECTED_GROUPS
        return obj.name.lower() in PROTECTED_GROUPS

    def get_description(self, obj):
        try:
            return obj.metadata.description or ''
        except GroupMetadata.DoesNotExist:
            return ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['description'] = self.get_description(instance)
        return data

    def update(self, instance, validated_data):
        description = validated_data.get('description')
        model_validated_data = validated_data.copy()
        model_validated_data.pop('description', None)
        instance = super().update(instance, model_validated_data)
        if description is not None:
            metadata, _ = GroupMetadata.objects.get_or_create(group=instance)
            metadata.description = description
            metadata.save()
        return instance

    def create(self, validated_data):
        description = validated_data.get('description')
        model_validated_data = validated_data.copy()
        model_validated_data.pop('description', None)
        instance = super().create(model_validated_data)
        if description is not None:
            metadata, _ = GroupMetadata.objects.get_or_create(group=instance)
            metadata.description = description
            metadata.save()
        return instance

class ScopedRoleSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    group = serializers.StringRelatedField()
    org_unit = serializers.StringRelatedField()
    module = serializers.StringRelatedField()

    class Meta:
        model = ScopedRole
        fields = [
            'id', 'user', 'group', 'org_unit', 'module', 'is_active', 'created_at'
        ]

class ScopedRoleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScopedRole
        fields = [
            'user', 'group', 'org_unit', 'module', 'is_active'
        ]

class RoleAssignmentAuditLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    group = serializers.StringRelatedField()
    org_unit = serializers.StringRelatedField()
    module = serializers.StringRelatedField()

    class Meta:
        model = RoleAssignmentAuditLog
        fields = [
            'id', 'user', 'group', 'org_unit', 'module', 'action', 'timestamp'
        ]


class PlatformAppConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAppConfig
        fields = ['id', 'app_id', 'is_enabled', 'display_order', 'updated_at']
        read_only_fields = ['id', 'updated_at']