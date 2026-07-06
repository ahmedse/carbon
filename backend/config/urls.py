# File: backend/config/urls.py
# Main URL configuration for the 'backend' Django project.

from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from accounts.views import ThrottledTokenObtainPairView

# API prefix, e.g. '/api/v1/' or '/carbon/api/'
api_prefix = getattr(settings, "API_PREFIX", "/api/v1/").strip("/")

schema_view = get_schema_view(
    openapi.Info(
        title="Carbon API",
        default_version='v1',
        description="Carbon platform API",
    ),
    public=True,
    permission_classes=(AllowAny,),
)

def health_check(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    # path('admin/', admin.site.urls),
    path(f'{api_prefix}/admin/', admin.site.urls),
    # Health check (not under API prefix for load balancer/infra)
    path(f'{api_prefix}/health/', health_check),
    # path('health/', health_check),

    # JWT Auth endpoints under API prefix
    path(f'{api_prefix}/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path(f'{api_prefix}/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # App endpoints under API prefix
    path(f'{api_prefix}/accounts/', include('accounts.urls')),
    path(f'{api_prefix}/core/', include('core.urls')),
    path(f'{api_prefix}/dataschema/', include('dataschema.urls')),
    path(f'{api_prefix}/ai/', include('ai_copilot.urls')),
    path(f'{api_prefix}/emissions/', include('emissions.urls')),
    path(f'{api_prefix}/catalog/', include('catalog.urls')),
    path(f'{api_prefix}/mdm/', include('mdm.urls')),
    path(f'{api_prefix}/dq/', include('dq.urls')),
    path(f'{api_prefix}/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]