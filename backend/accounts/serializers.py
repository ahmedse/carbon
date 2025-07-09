# File: accounts/serializers.py
# DRF serializers for tenants, users, roles, scoped roles, and audit logs.

from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import Tenant, User, ScopedRole, RoleAssignmentAuditLog

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'tenant', 'is_active', 'is_staff']

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']

class ScopedRoleSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    group = serializers.StringRelatedField()
    tenant = serializers.StringRelatedField()
    project = serializers.StringRelatedField()
    module = serializers.StringRelatedField()

    class Meta:
        model = ScopedRole
        fields = [
            'id', 'user', 'group', 'tenant', 'project', 'module', 'is_active', 'created_at'
        ]

class ScopedRoleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScopedRole
        fields = [
            'user', 'group', 'tenant', 'project', 'module', 'is_active'
        ]

class RoleAssignmentAuditLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    group = serializers.StringRelatedField()
    tenant = serializers.StringRelatedField()
    project = serializers.StringRelatedField()
    module = serializers.StringRelatedField()

    class Meta:
        model = RoleAssignmentAuditLog
        fields = [
            'id', 'user', 'group', 'tenant', 'project', 'module', 'action', 'timestamp'
        ]