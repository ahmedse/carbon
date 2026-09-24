from django.urls import path

from .api import (
    ExemptionDeleteView,
    ExemptionListCreateView,
    LadderView,
    RunListCreateView,
    StreamView,
    SubjectView,
)

urlpatterns = [
    path('ladder/', LadderView.as_view(), name='excellence-ladder'),
    path('subjects/<str:subject_id>/', SubjectView.as_view(), name='excellence-subject'),
    path('stream/', StreamView.as_view(), name='excellence-stream'),
    path('runs/', RunListCreateView.as_view(), name='excellence-runs'),
    path('exemptions/', ExemptionListCreateView.as_view(), name='excellence-exemptions'),
    path('exemptions/<int:exemption_id>/', ExemptionDeleteView.as_view(), name='excellence-exemption-delete'),
]
