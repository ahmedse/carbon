# File: accounts/serializers.py
# DRF serializers for users, roles, scoped roles, and audit logs.

from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import (
    User, ScopedRole, RoleAssignmentAuditLog, GroupMetadata, PlatformAppConfig, DutyProfile,
)

class UserSerializer(serializers.ModelSerializer):
    # Write-only: accepted on create/update, never returned in responses.
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, style={'input_type': 'password'}
    )
    # Read-only identity from linked Employee (people.Employee.user → related_name
    # employee_profile). Lets platform admins see who emp_* accounts are without
    # browsing People. Null when no employee is linked.
    employee_full_name = serializers.SerializerMethodField(read_only=True)
    employee_org_unit = serializers.SerializerMethodField(read_only=True)
    employee_no = serializers.SerializerMethodField(read_only=True)
    employee_position = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'is_active', 'is_staff', 'language', 'password',
            'employee_full_name', 'employee_org_unit', 'employee_no', 'employee_position',
        ]
        read_only_fields = [
            'id', 'employee_full_name', 'employee_org_unit', 'employee_no', 'employee_position',
        ]

    def _employee(self, obj):
        return getattr(obj, 'employee_profile', None)

    def get_employee_full_name(self, obj):
        emp = self._employee(obj)
        return emp.full_name if emp else None

    def get_employee_org_unit(self, obj):
        emp = self._employee(obj)
        if not emp or not getattr(emp, 'org_unit_id', None):
            return None
        ou = emp.org_unit
        # OrgUnit.full_path is a method — must call it (returning the bound
        # method blows up JSON encoding with TypeError).
        path_fn = getattr(ou, 'full_path', None)
        if callable(path_fn):
            return path_fn()
        return ou.name

    def get_employee_no(self, obj):
        emp = self._employee(obj)
        return emp.employee_no if emp else None

    def get_employee_position(self, obj):
        emp = self._employee(obj)
        position = getattr(emp, 'position', None) if emp else None
        if position is None:
            return None
        if position.code:
            return f'{position.title} ({position.code})'
        return position.title

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

class MePreferencesSerializer(serializers.ModelSerializer):
    """I18N-5: read/write the current user's UI preferences (language only
    for now). Used by `GET/PATCH /accounts/me/preferences/`."""

    class Meta:
        model = User
        fields = ['language']

    def validate_language(self, value):
        if value not in User.Language.values:
            raise serializers.ValidationError(
                f"Unsupported language '{value}'. Choose 'en' or 'ar'."
            )
        return value


class GroupSerializer(serializers.ModelSerializer):
    permissions_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    role_type = serializers.SerializerMethodField()
    app_id = serializers.SerializerMethodField()
    manifest_key = serializers.SerializerMethodField()
    duty = serializers.SerializerMethodField()
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
            'duty',
            'is_scoped',
            'is_protected',
        ]
        read_only_fields = [
            'id', 'permissions_count', 'users_count', 'role_type', 'app_id',
            'manifest_key', 'duty', 'is_scoped', 'is_protected',
        ]

    def get_permissions_count(self, obj):
        return obj.permissions.count()

    def get_users_count(self, obj):
        from .models import ScopedRole
        return ScopedRole.objects.filter(group=obj).live().values('user').distinct().count()

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

    def get_duty(self, obj):
        from accounts.birthright import group_to_duty
        return group_to_duty(obj.name)

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
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    employee_name = serializers.SerializerMethodField()
    group = serializers.StringRelatedField()
    group_id = serializers.IntegerField(source='group.id', read_only=True)
    duty = serializers.SerializerMethodField()
    org_unit = serializers.StringRelatedField()
    org_unit_id = serializers.IntegerField(read_only=True)
    module = serializers.StringRelatedField()

    class Meta:
        model = ScopedRole
        fields = [
            'id', 'user', 'user_id', 'employee_name', 'group', 'group_id', 'duty',
            'org_unit', 'org_unit_id', 'module',
            'provenance', 'valid_from', 'valid_to', 'is_active', 'created_at',
        ]

    def get_duty(self, obj):
        from accounts.birthright import group_to_duty
        return group_to_duty(obj.group.name)

    def get_employee_name(self, obj):
        emp = getattr(obj.user, 'employee_profile', None)
        return (emp.full_name or '') if emp else ''


class ScopedRoleCreateSerializer(serializers.ModelSerializer):
    """Admin grants are exceptions. ``duty`` is the domain id (``people:lead``)."""

    duty = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ScopedRole
        fields = [
            'user', 'group', 'duty', 'org_unit', 'module',
            'provenance', 'valid_from', 'valid_to', 'is_active',
        ]
        extra_kwargs = {
            'group': {'required': False},
            'provenance': {'required': False},
        }

    def validate(self, attrs):
        duty = (attrs.pop('duty', '') or '').strip()
        if duty:
            from accounts.birthright import resolve_group_name
            group, _created = Group.objects.get_or_create(name=resolve_group_name(duty))
            attrs['group'] = group
        if not attrs.get('group') and not getattr(self.instance, 'group_id', None):
            raise serializers.ValidationError({'duty': 'Choose a duty.'})
        attrs['provenance'] = ScopedRole.PROVENANCE_EXCEPTION
        attrs['module'] = None
        return attrs


class DutyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DutyProfile
        fields = ['id', 'position_code', 'duty', 'scope']

    def validate_duty(self, value):
        from accounts.birthright import DUTY_GROUP
        if value not in DUTY_GROUP:
            raise serializers.ValidationError(
                f"Unknown duty '{value}'. Use a domain duty such as people:lead."
            )
        return value

    def validate_position_code(self, value):
        code = (value or '').strip()
        if not code:
            raise serializers.ValidationError('Position code is required.')
        return code

class RoleAssignmentAuditLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    actor = serializers.StringRelatedField()
    group = serializers.StringRelatedField()
    org_unit = serializers.StringRelatedField()
    module = serializers.StringRelatedField()

    class Meta:
        model = RoleAssignmentAuditLog
        fields = [
            'id', 'user', 'actor', 'group', 'org_unit', 'module',
            'action', 'timestamp', 'extra',
        ]


class PlatformAppConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAppConfig
        fields = ['id', 'app_id', 'is_enabled', 'display_order', 'updated_at']
        read_only_fields = ['id', 'updated_at']


# ── Phase 1.2-1.4: Platform Configuration Serializers ─────────────────────────

from .models import EmailConfig, BackupConfig, LogConfig, APIConfig


class EmailConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailConfig
        fields = [
            'id', 'backend', 'host', 'port', 'username', 'password',
            'use_tls', 'use_ssl', 'from_email', 'from_name', 'enabled', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False, 'allow_blank': True},
        }


class BackupConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupConfig
        fields = [
            'id', 'frequency', 'retention_days', 's3_bucket', 's3_path',
            'enabled', 'last_backup_at', 'last_backup_size_bytes', 'updated_at',
        ]
        read_only_fields = ['id', 'last_backup_at', 'last_backup_size_bytes', 'updated_at']


class LogConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogConfig
        fields = [
            'id', 'default_level', 'retention_days', 'json_format', 'db_log_level', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']


class APIConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIConfig
        fields = ['id', 'page_size', 'max_page_size', 'enable_pagination', 'updated_at']
        read_only_fields = ['id', 'updated_at']


# ── Phase 1.6: Notification Serializer ──────────────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import UserAlert
        model = UserAlert
        ref_name = 'UserAlertNotification'
        fields = ['id', 'title', 'body', 'category', 'is_read', 'link', 'created_at']
        read_only_fields = ['id', 'title', 'body', 'category', 'link', 'created_at']