# File: accounts/serializers.py

from rest_framework import serializers
from .models import Tenant, Role, Context, RoleAssignment, User
from core.models import Project, Module

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'

class ProjectSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField()
    class Meta:
        model = Project
        fields = ['id', 'name', 'tenant']

class ModuleSerializer(serializers.ModelSerializer):
    project = serializers.StringRelatedField()
    class Meta:
        model = Module
        fields = ['id', 'name', 'project']

class UserSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField()
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'tenant']

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class ContextSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)
    module = ModuleSerializer(read_only=True)

    class Meta:
        model = Context
        fields = ['id', 'type', 'project', 'module']

class RoleAssignmentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    context = ContextSerializer(read_only=True)

    class Meta:
        model = RoleAssignment
        fields = ['id', 'user', 'role', 'context']