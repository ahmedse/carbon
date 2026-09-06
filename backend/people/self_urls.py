"""Self-service URL routes (Phase OF-8) — mounted at ``/people/me/``."""

from django.urls import path

from .self_views import (
    EmployeeMeView,
    LeaveBalanceView,
    LeaveSelfCollectionView,
    LeaveSelfDetailView,
)

urlpatterns = [
    path('', EmployeeMeView.as_view(), name='people-me'),
    path('leave-balance/', LeaveBalanceView.as_view(), name='people-me-leave-balance'),
    path('leave/', LeaveSelfCollectionView.as_view(), name='people-me-leave-collection'),
    path('leave/<int:pk>/', LeaveSelfDetailView.as_view(), name='people-me-leave-detail'),
]
