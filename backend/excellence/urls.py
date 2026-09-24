from django.urls import path

from .api import (
    AppView,
    ExemptionDeleteView,
    ExemptionListCreateView,
    InitiativeCloseView,
    InitiativeListCreateView,
    LadderView,
    OverviewView,
    RunListCreateView,
    StandardView,
    StreamView,
    SubjectView,
)

urlpatterns = [
    path('overview/', OverviewView.as_view(), name='excellence-overview'),
    path('standard/', StandardView.as_view(), name='excellence-standard'),
    path('apps/<str:app_id>/', AppView.as_view(), name='excellence-app'),
    path('ladder/', LadderView.as_view(), name='excellence-ladder'),
    path('subjects/<str:subject_id>/', SubjectView.as_view(), name='excellence-subject'),
    path('stream/', StreamView.as_view(), name='excellence-stream'),
    path('runs/', RunListCreateView.as_view(), name='excellence-runs'),
    path('initiatives/', InitiativeListCreateView.as_view(), name='excellence-initiatives'),
    path('initiatives/<int:initiative_id>/close/', InitiativeCloseView.as_view(), name='excellence-initiative-close'),
    path('exemptions/', ExemptionListCreateView.as_view(), name='excellence-exemptions'),
    path('exemptions/<int:exemption_id>/', ExemptionDeleteView.as_view(), name='excellence-exemption-delete'),
]
