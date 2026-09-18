"""KnowledgeItem routes — mounted at ``/carbon-api/ai/knowledge/``."""

from django.urls import path

from ai.knowledge_api import (
    KnowledgeItemDetailView,
    KnowledgeItemListCreateView,
    KnowledgeItemRevokeView,
)

urlpatterns = [
    path("items/", KnowledgeItemListCreateView.as_view(), name="ai-knowledge-items"),
    path(
        "items/<str:item_id>/",
        KnowledgeItemDetailView.as_view(),
        name="ai-knowledge-item-detail",
    ),
    path(
        "items/<str:item_id>/revoke/",
        KnowledgeItemRevokeView.as_view(),
        name="ai-knowledge-item-revoke",
    ),
]
