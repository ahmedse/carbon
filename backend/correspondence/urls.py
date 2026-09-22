# File: correspondence/urls.py
# e-Office Correspondence engine API routes (Phase OF-7). The
# ``{api_prefix}/correspondence/`` prefix is applied by ``config/urls.py``;
# these paths are relative to that prefix.

from django.urls import path

from .views import CorrespondenceViewSet, NotificationViewSet, WorkflowPolicyViewSet


urlpatterns = [
    path('', CorrespondenceViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='correspondence-list'),
    path('inbox/', CorrespondenceViewSet.as_view({'get': 'inbox'}),
         name='correspondence-inbox'),
    path('history/', CorrespondenceViewSet.as_view({'get': 'history'}),
         name='correspondence-history'),
    path('<int:pk>/', CorrespondenceViewSet.as_view({'get': 'retrieve'}),
         name='correspondence-detail'),
    path('<int:pk>/approve/', CorrespondenceViewSet.as_view({'post': 'approve'}),
         name='correspondence-approve'),
    path('<int:pk>/acknowledge/', CorrespondenceViewSet.as_view({'post': 'acknowledge'}),
         name='correspondence-acknowledge'),
    path('<int:pk>/review/', CorrespondenceViewSet.as_view({'post': 'review'}),
         name='correspondence-review'),
    path('<int:pk>/reject/', CorrespondenceViewSet.as_view({'post': 'reject'}),
         name='correspondence-reject'),
    path('<int:pk>/send-back/', CorrespondenceViewSet.as_view({'post': 'send_back'}),
         name='correspondence-send-back'),
    path('<int:pk>/cancel/', CorrespondenceViewSet.as_view({'post': 'cancel'}),
         name='correspondence-cancel'),
    path('<int:pk>/resubmit/', CorrespondenceViewSet.as_view({'post': 'resubmit'}),
         name='correspondence-resubmit'),
    path('<int:pk>/archive/', CorrespondenceViewSet.as_view({'post': 'archive'}),
         name='correspondence-archive'),
    path('notifications/', NotificationViewSet.as_view({'get': 'list'}),
         name='correspondence-notifications'),
    path('notifications/read-all/', NotificationViewSet.as_view({'post': 'read_all'}),
         name='correspondence-notifications-read-all'),
    path('notifications/<int:pk>/read/', NotificationViewSet.as_view({'post': 'read'}),
         name='correspondence-notification-read'),
    path('policies/', WorkflowPolicyViewSet.as_view({'get': 'list'}),
         name='correspondence-policy-list'),
    path('policies/<int:pk>/', WorkflowPolicyViewSet.as_view({'get': 'retrieve'}),
         name='correspondence-policy-detail'),
]
