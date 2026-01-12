"""
AI Copilot URL Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, InsightViewSet, PreferenceViewSet

# Create router
router = DefaultRouter()
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'insights', InsightViewSet, basename='insights')
router.register(r'preferences', PreferenceViewSet, basename='preferences')

urlpatterns = [
    path('', include(router.urls)),
]
