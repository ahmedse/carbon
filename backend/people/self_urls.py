"""Self-service URL routes (Phase OF-8) — mounted at ``/people/me/``."""

from django.urls import path

from .self_views import (
    EmployeeMeView,
    LeaveBalanceView,
    LeaveSelfCollectionView,
    LeaveSelfDetailView,
    LoanSelfCollectionView,
    PayslipSelfCollectionView,
    PayslipSelfDetailView,
    ProfileChangeSelfView,
)

urlpatterns = [
    path('', EmployeeMeView.as_view(), name='people-me'),
    path('leave-balance/', LeaveBalanceView.as_view(), name='people-me-leave-balance'),
    path('leave/', LeaveSelfCollectionView.as_view(), name='people-me-leave-collection'),
    path('leave/<int:pk>/', LeaveSelfDetailView.as_view(), name='people-me-leave-detail'),
    path('loan/', LoanSelfCollectionView.as_view(), name='people-me-loan-collection'),
    path('payslips/', PayslipSelfCollectionView.as_view(), name='people-me-payslip-collection'),
    path('payslips/<int:pk>/', PayslipSelfDetailView.as_view(), name='people-me-payslip-detail'),
    path('profile-change/', ProfileChangeSelfView.as_view(), name='people-me-profile-change'),
]
