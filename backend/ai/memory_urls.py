"""AI memory + learnt-facts routes (mounted at ``/carbon-api/ai/memory/``)."""

from django.urls import path

from ai.memory_api import (
    MemoryEpisodesView,
    MemoryFactDeleteView,
    MemoryFactRestoreView,
    MemoryFactsView,
    MemoryFactUpdateView,
    MemoryOrgFactsView,
    MemoryRelationshipView,
)

urlpatterns = [
    path("facts/", MemoryFactsView.as_view(), name="ai-memory-facts"),
    path("episodes/", MemoryEpisodesView.as_view(), name="ai-memory-episodes"),
    path(
        "relationship/",
        MemoryRelationshipView.as_view(),
        name="ai-memory-relationship",
    ),
    path(
        "facts/<str:pk>/",
        MemoryFactDeleteView.as_view(),
        name="ai-memory-fact-delete",
    ),
    path(
        "facts/<str:pk>/update/",
        MemoryFactUpdateView.as_view(),
        name="ai-memory-fact-update",
    ),
    path(
        "facts/<str:pk>/restore/",
        MemoryFactRestoreView.as_view(),
        name="ai-memory-fact-restore",
    ),
    path("org/", MemoryOrgFactsView.as_view(), name="ai-memory-org"),
]
