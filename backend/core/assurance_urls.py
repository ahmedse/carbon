from django.urls import path

from core.assurance_api import AssuranceReportView, AssuranceStreamView

urlpatterns = [
    path('report/', AssuranceReportView.as_view(), name='assurance-report'),
    path('stream/', AssuranceStreamView.as_view(), name='assurance-stream'),
]
