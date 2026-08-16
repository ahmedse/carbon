"""URL routing for the AI Workspace API."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ai.workspace_api import WorkspaceArtifactViewSet, WorkspaceConversationViewSet

router = DefaultRouter()
router.register(r"conversations", WorkspaceConversationViewSet, basename="ai-workspace-conversation")
router.register(r"artifacts", WorkspaceArtifactViewSet, basename="ai-workspace-artifact")

urlpatterns = [
    path("", include(router.urls)),
]
