from django.apps import AppConfig


class AICopilotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_copilot'
    verbose_name = 'AI Copilot'
    
    def ready(self):
        """Initialize AI services when Django starts."""
        # Import signals if any
        pass
