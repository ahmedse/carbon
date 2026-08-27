# File: backend/config/urls.py
# Main URL configuration for the 'backend' Django project.

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import ThrottledTokenObtainPairView
from accounts.password_reset_signals import NotifyingPasswordResetView
from .health_views import health_check, metrics_view, prometheus_metrics_view
from ai import workspace_api as ai_workspace_views
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from accounts.permissions import AdminOrSuperuserOnly

# API prefix, e.g. '/api/v1/' or '/carbon/api/'
api_prefix = getattr(settings, "API_PREFIX", "/api/v1/").strip("/")

# Single predicate for the dev-only URL surface (debug toolbar, silk).
# drf-spectacular is import-safe in ALL environments (ADR 0003), so the
# OpenAPI schema/docs endpoints below are NOT dev-gated — they run in
# production too, protected by AdminOrSuperuserOnly.
IS_DEVELOPMENT = getattr(settings, "IS_DEVELOPMENT", False)


urlpatterns = [
    path('admin/', admin.site.urls),
    path(f'{api_prefix}/health/', health_check),
    path(f'{api_prefix}/health/metrics/', metrics_view),
    # EPH-6A: full Prometheus registry export (generate_latest)
    path(f'{api_prefix}/health/prometheus/', prometheus_metrics_view),

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

# ── OpenAPI schema + docs (ADR 0003 — drf-spectacular) ──────────────────
# NOT dev-gated: drf-spectacular is import-safe in every environment, so the
# schema endpoints run in production too — protected by AdminOrSuperuserOnly.
urlpatterns += [
    path(f'{api_prefix}/schema/', SpectacularAPIView.as_view(permission_classes=[AdminOrSuperuserOnly]), name='schema'),
    path(f'{api_prefix}/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='schema-swagger-ui'),
    path(f'{api_prefix}/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='schema-redoc'),
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