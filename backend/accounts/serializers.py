# File: accounts/serializers.py
# DRF serializers for users, roles, scoped roles, and audit logs.

from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import User, ScopedRole, RoleAssignmentAuditLog

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
    class Meta:
        model = Group
        fields = ['id', 'name']

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