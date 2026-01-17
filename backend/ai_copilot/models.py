"""
AI Copilot Models
Conversation history, insights, and user preferences
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ConversationMessage(models.Model):
    """
    Stores conversation history for context and learning.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_messages')
    project = models.ForeignKey('core.Project', on_delete=models.CASCADE, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)  # tokens, model used, etc.
    token_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['project', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class ProactiveInsight(models.Model):
    """
    AI-generated insights surfaced proactively to users.
    """
    URGENCY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    TYPE_CHOICES = [
        ('missing_data', 'Missing Data'),
        ('outlier', 'Outlier Detected'),
        ('deadline', 'Deadline Approaching'),
        ('opportunity', 'Improvement Opportunity'),
        ('compliance', 'Compliance Issue'),
        ('benchmark', 'Peer Comparison'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_insights')
    project = models.ForeignKey('core.Project', on_delete=models.CASCADE, null=True, blank=True)
    
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    title = models.CharField(max_length=200)
    description = models.TextField()
    action_label = models.CharField(max_length=100, blank=True)
    action_url = models.CharField(max_length=500, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)  # Additional context
    
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-urgency', '-created_at']
        indexes = [
            models.Index(fields=['user', 'acknowledged', '-created_at']),
            models.Index(fields=['project', '-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.urgency}] {self.title}"


class UserAIPreference(models.Model):
    """
    User preferences for AI behavior and notifications.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ai_preferences')
    
    # Notification preferences
    enable_proactive_insights = models.BooleanField(default=True)
    insight_types = models.JSONField(default=list)  # Which types to show
    
    # AI behavior preferences
    response_detail_level = models.CharField(
        max_length=20,
        choices=[('concise', 'Concise'), ('balanced', 'Balanced'), ('detailed', 'Detailed')],
        default='balanced'
    )
    
    # Privacy
    allow_conversation_learning = models.BooleanField(default=True)
    
    # Panel state
    panel_collapsed = models.BooleanField(default=False)
    panel_width = models.IntegerField(default=320)  # pixels
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"AI Preferences for {self.user.username}"
