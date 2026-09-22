"""Self-service URL routes (Phase OF-8) — mounted at ``/people/me/``."""

from django.urls import path

from .self_views import (
    AttendancePermissionSelfCollectionView,
    DirectReportsView,
    EmployeeMeView,
    LeaveBalanceView,
    LeaveSelfCollectionView,
    LeaveSelfDetailView,
    LoanSelfCollectionView,
    PayslipSelfCollectionView,
    PayslipSelfDetailView,
    ProfileChangeSelfView,
    TeamLeaveView,
)

urlpatterns = [
    path('', EmployeeMeView.as_view(), name='people-me'),
    path('leave-balance/', LeaveBalanceView.as_view(), name='people-me-leave-balance'),
    path('leave/', LeaveSelfCollectionView.as_view(), name='people-me-leave-collection'),
    path('leave/<int:pk>/', LeaveSelfDetailView.as_view(), name='people-me-leave-detail'),
    path('loan/', LoanSelfCollectionView.as_view(), name='people-me-loan-collection'),
    path(
        'attendance-permissions/',
        AttendancePermissionSelfCollectionView.as_view(),
        name='people-me-attendance-permission-collection',
    ),
    path('payslips/', PayslipSelfCollectionView.as_view(), name='people-me-payslip-collection'),
    path('payslips/<int:pk>/', PayslipSelfDetailView.as_view(), name='people-me-payslip-detail'),
    path('profile-change/', ProfileChangeSelfView.as_view(), name='people-me-profile-change'),
    path('direct-reports/', DirectReportsView.as_view(), name='people-me-direct-reports'),
    path('team-leave/', TeamLeaveView.as_view(), name='people-me-team-leave'),
]
