# File: config/log_urls.py
# URL routing for the centralized log viewer API.

from django.urls import path
from .log_api import LogViewerAPIView

urlpatterns = [
    path('', LogViewerAPIView.as_view(), name='system-logs'),
]
