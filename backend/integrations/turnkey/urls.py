# integrations/turnkey/urls.py
# Mounted in config/urls.py at {api_prefix}/integrations/turnkey/ → in dev and
# prod this resolves to /carbon-api/integrations/turnkey/ (RULE_4).
from django.urls import path

from .views import (
    DriftAlertCallbackView, PredictionCallbackView, PredictionFeedbackView,
    TurnKeyConfigListCreateView, TurnKeyLinkDriftAlertsView,
    TurnKeyLinkListCreateView, TurnKeyLinkPredictionsView,
    TurnKeyLinkPromoteView,
)

urlpatterns = [
    # Management API (§6.6)
    path('configs/', TurnKeyConfigListCreateView.as_view(), name='turnkey-configs'),
    path('links/', TurnKeyLinkListCreateView.as_view(), name='turnkey-links'),
    path('links/<uuid:link_id>/promote/',
         TurnKeyLinkPromoteView.as_view(), name='turnkey-link-promote'),
    path('links/<uuid:link_id>/predictions/',
         TurnKeyLinkPredictionsView.as_view(), name='turnkey-link-predictions'),
    path('links/<uuid:link_id>/predictions/<uuid:prediction_id>/feedback/',
         PredictionFeedbackView.as_view(), name='turnkey-prediction-feedback'),
    path('links/<uuid:link_id>/drift-alerts/',
         TurnKeyLinkDriftAlertsView.as_view(), name='turnkey-link-drift-alerts'),
    # Inbound callbacks (§6.5) — HMAC-SHA256 signed
    path('callback/predictions/',
         PredictionCallbackView.as_view(), name='turnkey-callback-predictions'),
    path('callback/drift-alerts/',
         DriftAlertCallbackView.as_view(), name='turnkey-callback-drift-alerts'),
]
