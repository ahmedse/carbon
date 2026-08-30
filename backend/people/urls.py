# File: people/urls.py
# People & Payroll API routes (NIR-1C). The ``/carbon-api/people/`` prefix is
# applied by ``config/urls.py``; these paths are relative to that prefix.

from django.urls import path

from .views import (
    ComplianceRuleDetailView,
    ComplianceRuleListCreateView,
    EmployeeDetailView,
    EmployeeListCreateView,
    PayrollRunDetailView,
    PayrollRunListCreateView,
    PayslipLineListView,
)

urlpatterns = [
    path('compliance-rules/', ComplianceRuleListCreateView.as_view(),
         name='people-compliance-rules'),
    path('compliance-rules/<int:pk>/', ComplianceRuleDetailView.as_view(),
         name='people-compliance-rule-detail'),
    path('employees/', EmployeeListCreateView.as_view(), name='people-employees'),
    path('employees/<int:pk>/', EmployeeDetailView.as_view(),
         name='people-employee-detail'),
    path('payroll-runs/', PayrollRunListCreateView.as_view(),
         name='people-payroll-runs'),
    path('payroll-runs/<int:pk>/', PayrollRunDetailView.as_view(),
         name='people-payroll-run-detail'),
    path('payslip-lines/', PayslipLineListView.as_view(),
         name='people-payslip-lines'),
]
