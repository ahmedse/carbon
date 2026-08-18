# appregistry/urls.py
# Mounted at <api_prefix>/apps/ (see config/urls.py) — all paths are relative.
from django.urls import path

from .views import ActivateAppView, AppManifestViewSet, DeactivateAppView

urlpatterns = [
    path('', AppManifestViewSet.as_view({'get': 'list'}),
         name='appregistry-list'),
    path('<slug:slug>/', AppManifestViewSet.as_view({'get': 'retrieve'}),
         name='appregistry-detail'),
    path('<slug:slug>/activate/', ActivateAppView.as_view(),
         name='appregistry-activate'),
    path('<slug:slug>/deactivate/', DeactivateAppView.as_view(),
         name='appregistry-deactivate'),
]
