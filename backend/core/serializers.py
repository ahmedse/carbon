# File: core/serializers.py
# DRF serializers for Project and Module models.

from rest_framework import serializers
from .models import Project, Module

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