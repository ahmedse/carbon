"""URL routing for the Process Registry API (P3-05a).

Mounted at ``{api_prefix}/ai/registry/`` (see ``config/urls.py``) — every route
carries the literal ``processes/`` segment, so the full paths are:

    {api_prefix}/ai/registry/processes/                    list / create
    {api_prefix}/ai/registry/processes/<id>/               retrieve / edit
    {api_prefix}/ai/registry/processes/<id>/submit/        draft → review
    {api_prefix}/ai/registry/processes/<id>/publish/       review → active
    {api_prefix}/ai/registry/processes/<id>/deprecate/     active → deprecated
    {api_prefix}/ai/registry/processes/<id>/diff/          diff draft/review vs active
    {api_prefix}/ai/registry/processes/<id>/autonomy/      GET / PATCH the dial
    {api_prefix}/ai/registry/processes/<id>/kill/          set the kill switch

Explicit ``as_view`` mappings instead of a router (same convention as
``ai.catalog_urls`` / ``ai.plans_urls``). Literal routes are declared before the
``<str:pk>/`` detail route so Django matches ``/diff/`` etc. first.
"""

from django.urls import path

from ai.registry_api import RegistryViewSet

urlpatterns = [
    path(
        "processes/",
        RegistryViewSet.as_view({"get": "list", "post": "create"}),
        name="ai-registry-list",
    ),
    path(
        "processes/<str:pk>/submit/",
        RegistryViewSet.as_view({"post": "submit"}),
        name="ai-registry-submit",
    ),
    path(
        "processes/<str:pk>/publish/",
        RegistryViewSet.as_view({"post": "publish"}),
        name="ai-registry-publish",
    ),
    path(
        "processes/<str:pk>/deprecate/",
        RegistryViewSet.as_view({"post": "deprecate"}),
        name="ai-registry-deprecate",
    ),
    path(
        "processes/<str:pk>/diff/",
        RegistryViewSet.as_view({"get": "diff"}),
        name="ai-registry-diff",
    ),
    path(
        "processes/<str:pk>/autonomy/",
        RegistryViewSet.as_view({"get": "autonomy", "patch": "set_autonomy"}),
        name="ai-registry-autonomy",
    ),
    path(
        "processes/<str:pk>/kill/",
        RegistryViewSet.as_view({"post": "kill"}),
        name="ai-registry-kill",
    ),
    path(
        "processes/<str:pk>/",
        RegistryViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="ai-registry-detail",
    ),
]
