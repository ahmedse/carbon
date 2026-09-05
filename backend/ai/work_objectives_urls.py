"""URL routing for the Work Objectives API (Pulse v2 Phase 8)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ai.work_objectives_api import WorkObjectiveViewSet

router = DefaultRouter()
router.register(r"", WorkObjectiveViewSet, basename="ai-work-objective")

urlpatterns = [
    path("", include(router.urls)),
]
