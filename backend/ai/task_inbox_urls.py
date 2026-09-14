"""URL routing for the Human Task Inbox API (P3-09).

Mounted at ``{api_prefix}/ai/inbox/`` (see ``config/urls.py``).  Literal
``approve``/``decline``/``stream`` routes are declared before the
``<str:pk>/`` detail route so Django matches them first (same convention as
``ai.registry_urls``):

    {api_prefix}/ai/inbox/tasks/                list pending
    {api_prefix}/ai/inbox/tasks/<id>/           retrieve one
    {api_prefix}/ai/inbox/tasks/<id>/approve/   approve (mints grant)
    {api_prefix}/ai/inbox/tasks/<id>/decline/   decline (no grant)
    {api_prefix}/ai/inbox/stream/               SSE stream
"""

from django.urls import path

from ai.task_inbox_api import TaskInboxStreamView, TaskInboxViewSet

urlpatterns = [
    path(
        "tasks/",
        TaskInboxViewSet.as_view({"get": "list"}),
        name="ai-inbox-list",
    ),
    path(
        "tasks/<str:pk>/approve/",
        TaskInboxViewSet.as_view({"post": "approve"}),
        name="ai-inbox-approve",
    ),
    path(
        "tasks/<str:pk>/decline/",
        TaskInboxViewSet.as_view({"post": "decline"}),
        name="ai-inbox-decline",
    ),
    path(
        "tasks/<str:pk>/",
        TaskInboxViewSet.as_view({"get": "retrieve"}),
        name="ai-inbox-detail",
    ),
    path(
        "stream/",
        TaskInboxStreamView.as_view(),
        name="ai-inbox-stream",
    ),
]
