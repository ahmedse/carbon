# dq/urls.py
from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    FieldProfileViewSet, TableProfileViewSet, DQRuleViewSet, DQResultViewSet,
    ProfileTriggerView, DQRunView,
)

router = DefaultRouter()
router.register(r'profiles', FieldProfileViewSet, basename='fieldprofile')
router.register(r'table-profiles', TableProfileViewSet, basename='tableprofile')
router.register(r'rules', DQRuleViewSet, basename='dqrule')
router.register(r'results', DQResultViewSet, basename='dqresult')

urlpatterns = [
    path('profile/', ProfileTriggerView.as_view(), name='dq-profile'),
    path('run/', DQRunView.as_view(), name='dq-run'),
]
urlpatterns += router.urls
