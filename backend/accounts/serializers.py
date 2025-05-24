# File: accounts/serializers.py
# Purpose: DRF serializers for the RBAC models.

from rest_framework import serializers
from .models import Role, Context, RoleAssignment

class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer for the Role model.
    """
    class Meta:
        model = Role
        fields = '__all__'

class ContextSerializer(serializers.ModelSerializer):
    """
    Serializer for the Context model.
    """
    class Meta:
        model = Context
        fields = '__all__'

class RoleAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for the RoleAssignment model.
    """
    class Meta:
        model = RoleAssignment
        fields = '__all__'