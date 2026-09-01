"""AI operations progress read API routes (mounted at ``/carbon-api/ai/operations/``)."""

from django.urls import path

from ai.ops_progress import OperationsStreamView

urlpatterns = [
    path("stream/", OperationsStreamView.as_view(), name="ai-ops-progress-stream"),
]
