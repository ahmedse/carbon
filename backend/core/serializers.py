# File: core/serializers.py
# DRF serializers for Module models.

from rest_framework import serializers
from .models import Module, Feedback, Notification


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'name', 'email', 'message', 'rating', 'submitted_at']
        read_only_fields = ['id', 'submitted_at']


class ModuleSerializer(serializers.ModelSerializer):
    org_unit_name = serializers.CharField(source='org_unit.name', read_only=True, default=None)
    table_count = serializers.SerializerMethodField()
    carbon_scope = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            'id', 'name', 'description', 'scope', 'domain_attributes', 'carbon_scope',
            'org_unit', 'org_unit_name',
            'is_locked', 'table_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'carbon_scope']

    def get_table_count(self, obj):
        if hasattr(obj, 'data_tables'):
            return obj.data_tables.count()
        return 0

    def get_carbon_scope(self, obj):
        return obj.carbon_scope()


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        ref_name = 'CoreNotification'
        fields = ['id', 'user', 'verb', 'message', 'link', 'read_at', 'created_at']
        read_only_fields = ['id', 'user', 'read_at', 'created_at']