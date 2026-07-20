# File: core/serializers.py
# DRF serializers for Module models.

from rest_framework import serializers
from .models import Module, Feedback


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'name', 'email', 'message', 'rating', 'submitted_at']
        read_only_fields = ['id', 'submitted_at']


class ModuleSerializer(serializers.ModelSerializer):
    org_unit_name = serializers.CharField(source='org_unit.name', read_only=True, default=None)

    class Meta:
        model = Module
        fields = ['id', 'name', 'description', 'scope', 'org_unit', 'org_unit_name', 'is_locked']