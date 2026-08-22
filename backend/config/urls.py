# File: backend/config/urls.py
# Main URL configuration for the 'backend' Django project.

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import ThrottledTokenObtainPairView
from accounts.password_reset_signals import NotifyingPasswordResetView
from .health_views import health_check, metrics_view
from ai import workspace_api as ai_workspace_views

# API prefix, e.g. '/api/v1/' or '/carbon/api/'
api_prefix = getattr(settings, "API_PREFIX", "/api/v1/").strip("/")

# Single predicate for the dev-only URL surface (swagger UI). Production
# never imports drf_yasg, so the API-docs dependency can be dropped from
# prod images entirely.
IS_DEVELOPMENT = getattr(settings, "IS_DEVELOPMENT", False)


urlpatterns = [
    path('admin/', admin.site.urls),
    path(f'{api_prefix}/health/', health_check),
    path(f'{api_prefix}/health/metrics/', metrics_view),

    # JWT Auth endpoints under API prefix
    path(f'{api_prefix}/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path(f'{api_prefix}/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Phase 1.1/1.6: Password Reset (with in-app notification)
    path(
        f'{api_prefix}/password-reset/',
        NotifyingPasswordResetView.as_view(
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            html_email_template_name='accounts/password_reset_email.html',
            extra_email_context={
                'platform_name': getattr(settings, 'PLATFORM_TITLE', 'Data Trust Platform'),
                'platform_short': getattr(settings, 'PLATFORM_SHORT', 'Data Trust'),
            },
        ),
        name='password_reset',
    ),
    path(
        f'{api_prefix}/password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(),
        name='password_reset_done',
    ),
    path(
        f'{api_prefix}/password-reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        f'{api_prefix}/password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),

    # Phase 1.1: Email test endpoint (admin diagnostic)
    path(f'{api_prefix}/email/test/', include('accounts.email_urls')),

    # Phase 1: Centralized log viewer (admin only)
    path(f'{api_prefix}/system/logs/', include('config.log_urls')),

    # App endpoints under API prefix
    path(f'{api_prefix}/accounts/', include('accounts.urls')),
    path(f'{api_prefix}/core/', include('core.urls')),
    path(f'{api_prefix}/dataschema/', include('dataschema.urls')),
    path(f'{api_prefix}/carbon/', include(('emissions.urls', 'carbon'), namespace='carbon')),
    path(f'{api_prefix}/catalog/', include('catalog.urls')),
    path(f'{api_prefix}/mdm/', include('mdm.urls')),
    path(f'{api_prefix}/connections/', include('connections.urls')),
    path(f'{api_prefix}/importexport/', include('importexport.urls')),
    path(f'{api_prefix}/dq/', include('dq.urls')),
    path(f'{api_prefix}/apps/', include('appregistry.urls')),
    path(f'{api_prefix}/integrations/turnkey/', include('integrations.turnkey.urls')),
    path(f'{api_prefix}/healthy/', include('healthy.urls')),
    path(f'{api_prefix}/ai/workspace/', include('ai.workspace_urls')),
    path(f'{api_prefix}/ai/plans/', include('ai.plans_urls')),
    path(f'{api_prefix}/ai/catalog/', include('ai.catalog_urls')),
    path(f'{api_prefix}/ai/runs/', include('ai.durable_urls')),
    path(f'{api_prefix}/ai/usage/', include('ai.usage_urls')),
    path(f'{api_prefix}/ai/profile/', ai_workspace_views.UserProfileView.as_view(), name='ai-user-profile'),
    path(f'{api_prefix}/ai/memory/', include('ai.memory_urls')),
    path(f'{api_prefix}/ai/pulse/', include('ai.ops_urls')),
    path(f'{api_prefix}/', include('evidence.urls')),
]

# ── Development-only surface ─────────────────────────────────────────────
# Swagger UI is dev tooling: gate it on the same predicate as the debug
# toolbars (settings.IS_DEVELOPMENT), not DEBUG — so DEBUG=True in a
# production env cannot accidentally publish API docs.
if IS_DEVELOPMENT:
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    from rest_framework.permissions import AllowAny

    schema_view = get_schema_view(
        openapi.Info(
            title=f"{getattr(settings, 'PLATFORM_TITLE', 'Data Trust Platform')} Core API",
            default_version='v1',
            description=(
                "**Data Trust Core Platform APIs**\n\n"
                "Provides catalog, master data management (MDM), and data quality (DQ) services.\n\n"
                "### Key Modules\n"
                "- **Catalog** (`/catalog/`): Asset profiling, governance events, glossary terms, data domains\n"
                "- **MDM** (`/mdm/`): Reference sets (temporal + lifecycle), org-unit hierarchy, field binding\n"
                "- **DQ** (`/dq/`): Data profiling, rule execution, quality metrics, execution history\n\n"
                "### Authentication\n"
                "All endpoints require JWT. Obtain a token via `POST /carbon-api/token/`.\n\n"
                "### Soft-Delete Policy\n"
                "Hard DELETE is rejected with HTTP 405 on catalog and DQ resources. "
                "Use `PATCH {\"is_active\": false}` or the dedicated `archive-bulk` actions instead."
            ),
            contact=openapi.Contact(email="carbon@aast.edu"),
            license=openapi.License(name="Proprietary"),
        ),
        public=True,
        permission_classes=(AllowAny,),
    )
    urlpatterns += [
        path(f'{api_prefix}/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    ]

# Debug tooling URLs (dev only). Gated on the same IS_DEVELOPMENT predicate
# as their INSTALLED_APPS/MIDDLEWARE entries so the two cannot diverge.
if settings.IS_DEVELOPMENT:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
        path('silk/', include('silk.urls', namespace='silk')),
    ]

# ── Media serving (dev only) ─────────────────────────────────────────────
# Generated artifacts (AI study exports under MEDIA_ROOT/ai_exports, CSV
# exports, evidence uploads) are served by nginx in production. In development
# there is no proxy, so serve them from Django so chat download links resolve.
if settings.IS_DEVELOPMENT:
    from django.conf.urls.static import static
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )