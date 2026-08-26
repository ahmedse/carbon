# dq/urls.py
from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    FieldProfileViewSet, TableProfileViewSet, DQRuleViewSet, DQResultViewSet,
    ProfileTriggerView, BulkProfileView, DQRunView,
    DQMetricsView, TableDQMetricsView, FieldDQMetricsView, RunDQValidationView,
    DQSuggestView, GateCheckView, DQJobViewSet,
    FreshnessCheckViewSet, SchemaSnapshotViewSet, SchemaChangeViewSet,
    RuleTagViewSet, RuleFieldAssignmentViewSet,
    DQSuggestionViewSet, DQAnomalyViewSet,
    TableProfileView, RunProfileView, TableScorecardView,
)
from .config_views import DQProfileConfigView

router = DefaultRouter()
router.register(r'profiles', FieldProfileViewSet, basename='fieldprofile')
router.register(r'table-profiles', TableProfileViewSet, basename='tableprofile')
router.register(r'rules', DQRuleViewSet, basename='dqrule')
router.register(r'results', DQResultViewSet, basename='dqresult')
router.register(r'freshness', FreshnessCheckViewSet, basename='freshnesscheck')
router.register(r'schema-snapshots', SchemaSnapshotViewSet, basename='schemasnapshot')
router.register(r'schema-changes', SchemaChangeViewSet, basename='schemachange')
router.register(r'tags', RuleTagViewSet, basename='ruletag')
router.register(r'rule-assignments', RuleFieldAssignmentViewSet, basename='rulefieldassignment')
router.register(r'jobs', DQJobViewSet, basename='dqjob')
router.register(r'suggestions', DQSuggestionViewSet, basename='dqsuggestion')
router.register(r'anomalies', DQAnomalyViewSet, basename='dqanomaly')

urlpatterns = [
    path('profile/', ProfileTriggerView.as_view(), name='dq-profile'),
    path('profile/bulk/', BulkProfileView.as_view(), name='dq-profile-bulk'),
    path('profile/config/', DQProfileConfigView.as_view(), name='dq-profile-config'),
    path('run/', DQRunView.as_view(), name='dq-run'),
    path('metrics/', DQMetricsView.as_view(), name='dq-metrics'),
    path('metrics/table/<int:table_id>/', TableDQMetricsView.as_view(), name='dq-metrics-table'),
    path('metrics/field/<int:field_id>/', FieldDQMetricsView.as_view(), name='dq-metrics-field'),
    path('run-validation/', RunDQValidationView.as_view(), name='dq-run-validation'),
    path('gate/check/', GateCheckView.as_view(), name='dq-gate-check'),
    path('suggest/', DQSuggestView.as_view(), name='dq-suggest'),
    # EPH-3A — table-scoped profile + scorecard
    path('tables/<int:table_id>/profile/', TableProfileView.as_view(), name='dq-table-profile'),
    path('tables/<int:table_id>/profile/run/', RunProfileView.as_view(), name='dq-table-profile-run'),
    path('tables/<int:table_id>/scorecard/', TableScorecardView.as_view(), name='dq-table-scorecard'),
]
urlpatterns += router.urls
