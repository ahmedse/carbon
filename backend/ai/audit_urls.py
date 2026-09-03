"""Phase H1-B — AI audit trail routes (mounted at ``/carbon-api/ai/audit/``)."""

from django.urls import path

from ai.audit_api import AuditListView

urlpatterns = [
    path("", AuditListView.as_view(), name="ai-audit-list"),
]
