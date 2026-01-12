"""
DRF Serializers for AI Copilot
"""

from rest_framework import serializers
from .models import ConversationMessage, ProactiveInsight, UserAIPreference


class ConversationMessageSerializer(serializers.ModelSerializer):
    """Serializer for conversation messages."""
    
    class Meta:
        model = ConversationMessage
        fields = [
            'id', 'user', 'project', 'role', 'content', 
            'metadata', 'token_count', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'token_count', 'created_at']


class ProactiveInsightSerializer(serializers.ModelSerializer):
    """Serializer for proactive insights."""
    
    class Meta:
        model = ProactiveInsight
        fields = [
            'id', 'user', 'project', 'insight_type', 'urgency',
            'title', 'description', 'actions', 'acknowledged',
            'acknowledged_at', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'acknowledged_at']


class UserAIPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for user AI preferences."""
    
    class Meta:
        model = UserAIPreference
        fields = [
            'id', 'user', 'enable_notifications', 'notification_frequency',
            'response_detail', 'preferred_models', 'custom_prompts',
            'copilot_panel_open', 'panel_width', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class ChatRequestSerializer(serializers.Serializer):
    """Serializer for chat API requests."""
    
    message = serializers.CharField(max_length=5000, required=True)
    project_id = serializers.IntegerField(required=False, allow_null=True)
    context = serializers.DictField(required=False, allow_null=True)
    stream = serializers.BooleanField(default=False, required=False)


class ChatResponseSerializer(serializers.Serializer):
    """Serializer for chat API responses."""
    
    response = serializers.CharField()
    conversation_id = serializers.IntegerField()
    tokens_used = serializers.IntegerField()
    cost_estimate = serializers.FloatField()
    sources = serializers.ListField(child=serializers.DictField(), required=False)
