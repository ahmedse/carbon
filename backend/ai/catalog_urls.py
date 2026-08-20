"""URL routing for the Unified Agent Catalog API (Phase W3-D).

Mounted at ``{api_prefix}/ai/catalog/`` (see ``config/urls.py``) — paths
below are relative to ``/carbon-api/ai/catalog/``:

    GET/POST /                        list agent roles / register an agent (staff)
    GET/POST /agents/                 literal W3-D spec alias for the root
    GET      /topology/               declared handoff graph (ADR-001)
    GET      /skills/                 skill catalog + admission status
    GET      /index/                  federated index (DB agents + plugins)
    GET/PATCH/DELETE /{id}/           one agent
    GET/PATCH/DELETE /agents/{id}/    literal W3-D spec alias for the detail

Note: explicit ``as_view`` mappings instead of a router because the include
mount already carries the ``catalog`` prefix — a router would double it
(same convention as ``ai.plans_urls``).

Order matters: literal ``agents/`` / ``topology/`` / ``skills/`` / ``index/``
paths are registered BEFORE ``<str:pk>/`` so ``pk`` can never capture them.
"""

from django.urls import path

from ai.catalog_api import CatalogViewSet

urlpatterns = [
    path(
        "",
        CatalogViewSet.as_view({"get": "list", "post": "create"}),
        name="ai-catalog-list",
    ),
    path(
        "agents/",
        CatalogViewSet.as_view({"get": "list", "post": "create"}),
        name="ai-catalog-agents",
    ),
    path(
        "topology/",
        CatalogViewSet.as_view({"get": "topology"}),
        name="ai-catalog-topology",
    ),
    path(
        "skills/",
        CatalogViewSet.as_view({"get": "skills"}),
        name="ai-catalog-skills",
    ),
    path(
        "index/",
        CatalogViewSet.as_view({"get": "federated_index"}),
        name="ai-catalog-index",
    ),
    path(
        "agents/<str:pk>/",
        CatalogViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="ai-catalog-agent-detail",
    ),
    path(
        "<str:pk>/",
        CatalogViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="ai-catalog-detail",
    ),
]
