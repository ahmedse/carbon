"""URL routing for the AI Workspace API."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ai.workspace_api import WorkspaceConversationViewSet

router = DefaultRouter()
router.register(r"conversations", WorkspaceConversationViewSet, basename="ai-workspace-conversation")

urlpatterns = [
    path("", include(router.urls)),
]
