"""URL routing for admin skill promote/reject decisions (PEC-6A).

Mounted at ``{api_prefix}/ai/skills/`` (see ``config/urls.py``):

    POST /{id}/promote/
    POST /{id}/reject/
"""

from django.urls import path

from ai.skills_decision_api import SkillPromoteView, SkillRejectView

urlpatterns = [
    path(
        "<str:pk>/promote/",
        SkillPromoteView.as_view(),
        name="ai-skill-promote",
    ),
    path(
        "<str:pk>/reject/",
        SkillRejectView.as_view(),
        name="ai-skill-reject",
    ),
]
