# File: core/serializers.py
# DRF serializers for Project and Module models.

from rest_framework import serializers
from .models import Project, Module
from .models import Feedback

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'name', 'email', 'message', 'rating', 'submitted_at']
        read_only_fields = ['id', 'submitted_at']
        
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