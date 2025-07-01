# File: backend/config/urls.py
# Purpose: Main URL configuration for the 'backend' Django project.
#
# This file defines the list of URL patterns that route HTTP requests
# to the appropriate Django views or applications.

from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponseRedirect
from django.conf import settings

# urlpatterns: List of URL patterns that route to views or included URL configs.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),     # Routes API requests to the accounts app
    path('api/core/', include('core.urls')),    # Routes API requests to the core app
    path('api/dataschema/', include('dataschema.urls')),
    # Catch-all: redirect anything else to /admin/
    # re_path(r'^.*$', lambda request: HttpResponseRedirect('/admin/')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]