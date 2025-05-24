# File: backend/backend/urls.py
# Purpose: Main URL configuration for the 'backend' Django project.
#
# This file defines the list of URL patterns that route HTTP requests
# to the appropriate Django views or applications.

from django.contrib import admin
from django.urls import path, include

# urlpatterns: List of URL patterns that route to views or included URL configs.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),     # Routes API requests to the accounts app
    path('api/core/', include('core.urls')),    # Routes API requests to the core app
    path('api/datacollection/', include('datacollection.urls')),
]