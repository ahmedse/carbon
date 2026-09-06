# File: correspondence/urls.py
# e-Office Correspondence engine API routes (Phase OF-7). The
# ``{api_prefix}/correspondence/`` prefix is applied by ``config/urls.py``;
# these paths are relative to that prefix.

from django.urls import path

from .views import CorrespondenceViewSet, WorkflowPolicyViewSet


urlpatterns = [
    path('', CorrespondenceViewSet.as_view({'get': 'list'}),
         name='correspondence-list'),
    path('inbox/', CorrespondenceViewSet.as_view({'get': 'inbox'}),
         name='correspondence-inbox'),
    path('<int:pk>/', CorrespondenceViewSet.as_view({'get': 'retrieve'}),
         name='correspondence-detail'),
    path('<int:pk>/approve/', CorrespondenceViewSet.as_view({'post': 'approve'}),
         name='correspondence-approve'),
    path('<int:pk>/reject/', CorrespondenceViewSet.as_view({'post': 'reject'}),
         name='correspondence-reject'),
    path('<int:pk>/send-back/', CorrespondenceViewSet.as_view({'post': 'send_back'}),
         name='correspondence-send-back'),
    path('<int:pk>/cancel/', CorrespondenceViewSet.as_view({'post': 'cancel'}),
         name='correspondence-cancel'),
    path('<int:pk>/resubmit/', CorrespondenceViewSet.as_view({'post': 'resubmit'}),
         name='correspondence-resubmit'),
    path('policies/', WorkflowPolicyViewSet.as_view({'get': 'list'}),
         name='correspondence-policy-list'),
    path('policies/<int:pk>/', WorkflowPolicyViewSet.as_view({'get': 'retrieve'}),
         name='correspondence-policy-detail'),
]
