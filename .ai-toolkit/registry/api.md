# Registry: API Endpoints  (auto-generated 2026-09-16 15:38 — DO NOT EDIT)

> Before adding an endpoint, search here. Reuse or extend — never duplicate a route.

## DRF Routers & url paths
```
backend/integrations/turnkey/urls.py:15:    path('configs/', TurnKeyConfigListCreateView.as_view(), name='turnkey-configs'),
backend/integrations/turnkey/urls.py:16:    path('links/', TurnKeyLinkListCreateView.as_view(), name='turnkey-links'),
backend/integrations/turnkey/urls.py:17:    path('links/<uuid:link_id>/promote/',
backend/integrations/turnkey/urls.py:19:    path('links/<uuid:link_id>/predictions/',
backend/integrations/turnkey/urls.py:21:    path('links/<uuid:link_id>/predictions/<uuid:prediction_id>/feedback/',
backend/integrations/turnkey/urls.py:23:    path('links/<uuid:link_id>/drift-alerts/',
backend/integrations/turnkey/urls.py:26:    path('callback/predictions/',
backend/integrations/turnkey/urls.py:28:    path('callback/drift-alerts/',
backend/core/urls.py:7:router.register(r'modules', ModuleViewSet)
backend/core/urls.py:8:router.register(r'feedback', FeedbackViewSet, basename='feedback')
backend/core/urls.py:9:router.register(r'notifications', NotificationViewSet, basename='notification')
backend/core/urls.py:10:router.register(r'audit-logs', RequestAuditLogViewSet, basename='requestauditlog')
backend/config/urls.py:26:    path(f'{api_prefix}/health/', health_check),
backend/config/urls.py:27:    path(f'{api_prefix}/health/metrics/', metrics_view),
backend/config/urls.py:29:    path(f'{api_prefix}/health/prometheus/', prometheus_metrics_view),
backend/config/urls.py:32:    path(f'{api_prefix}/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
backend/config/urls.py:33:    path(f'{api_prefix}/token/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),
backend/config/urls.py:36:    path(
backend/config/urls.py:49:    path(
backend/config/urls.py:54:    path(
backend/config/urls.py:61:    path(
backend/config/urls.py:68:    path(f'{api_prefix}/email/test/', include('accounts.email_urls')),
backend/config/urls.py:71:    path(f'{api_prefix}/system/logs/', include('config.log_urls')),
backend/config/urls.py:74:    path(f'{api_prefix}/accounts/', include('accounts.urls')),
backend/config/urls.py:75:    path(f'{api_prefix}/core/', include('core.urls')),
backend/config/urls.py:76:    path(f'{api_prefix}/dataschema/', include('dataschema.urls')),
backend/config/urls.py:77:    path(f'{api_prefix}/carbon/', include(('emissions.urls', 'carbon'), namespace='carbon')),
backend/config/urls.py:78:    path(f'{api_prefix}/catalog/', include('catalog.urls')),
backend/config/urls.py:79:    path(f'{api_prefix}/mdm/', include('mdm.urls')),
backend/config/urls.py:80:    path(f'{api_prefix}/connections/', include('connections.urls')),
backend/config/urls.py:81:    path(f'{api_prefix}/importexport/', include('importexport.urls')),
backend/config/urls.py:82:    path(f'{api_prefix}/dq/', include('dq.urls')),
backend/config/urls.py:83:    path(f'{api_prefix}/apps/', include('appregistry.urls')),
backend/config/urls.py:84:    path(f'{api_prefix}/integrations/turnkey/', include('integrations.turnkey.urls')),
backend/config/urls.py:85:    path(f'{api_prefix}/healthy/', include('healthy.urls')),
backend/config/urls.py:86:    path(f'{api_prefix}/people/', include('people.urls')),
backend/config/urls.py:87:    path(f'{api_prefix}/correspondence/', include('correspondence.urls')),
backend/config/urls.py:88:    path(f'{api_prefix}/ai/workspace/', include('ai.workspace_urls')),
backend/config/urls.py:89:    path(f'{api_prefix}/ai/work-objectives/', include('ai.work_objectives_urls')),
backend/config/urls.py:90:    path(f'{api_prefix}/ai/plans/', include('ai.plans_urls')),
backend/config/urls.py:91:    path(f'{api_prefix}/ai/catalog/', include('ai.catalog_urls')),
backend/config/urls.py:92:    path(f'{api_prefix}/ai/registry/', include('ai.registry_urls')),
backend/config/urls.py:93:    path(f'{api_prefix}/ai/inbox/', include('ai.task_inbox_urls')),
backend/config/urls.py:94:    path(f'{api_prefix}/ai/runs/', include('ai.durable_urls')),
backend/config/urls.py:95:    path(f'{api_prefix}/ai/usage/', include('ai.usage_urls')),
backend/config/urls.py:96:    path(f'{api_prefix}/ai/profile/', ai_workspace_views.UserProfileView.as_view(), name='ai-user-profile'),
backend/config/urls.py:97:    path(f'{api_prefix}/ai/memory/', include('ai.memory_urls')),
backend/config/urls.py:98:    path(f'{api_prefix}/ai/pulse/', include('ai.ops_urls')),
backend/config/urls.py:99:    path(f'{api_prefix}/ai/insights/', include('ai.insights_urls')),
backend/config/urls.py:100:    path(f'{api_prefix}/ai/operations/', include('ai.progress_urls')),
backend/config/urls.py:101:    path(f'{api_prefix}/ai/audit/', include('ai.audit_urls')),
backend/config/urls.py:102:    path(f'{api_prefix}/ai/watches/', include('ai.watches_urls')),
backend/config/urls.py:103:    path(f'{api_prefix}/mcp/', include('ai.mcp.server_urls')),
backend/config/urls.py:104:    path(f'{api_prefix}/', include('evidence.urls')),
backend/config/urls.py:114:    urlpatterns.insert(0, path('admin/', admin.site.urls))
backend/config/urls.py:120:    path(f'{api_prefix}/schema/', SpectacularAPIView.as_view(permission_classes=[AdminOrSuperuserOnly]), name='schema'),
backend/config/urls.py:121:    path(f'{api_prefix}/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='schema-swagger-ui'),
backend/config/urls.py:122:    path(f'{api_prefix}/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='schema-redoc'),
backend/config/urls.py:130:        path('__debug__/', include(debug_toolbar.urls)),
backend/config/urls.py:131:        path('silk/', include('silk.urls', namespace='silk')),
backend/evidence/urls.py:9:router.register(r'evidence', EvidenceViewSet, basename='evidence')
backend/evidence/urls.py:12:    path('', include(router.urls)),
backend/accounts/urls.py:16:router.register(r'users', UserViewSet)
backend/accounts/urls.py:17:router.register(r'roles', GroupViewSet, basename='role')
backend/accounts/urls.py:18:router.register(r'groups', GroupViewSet, basename='group')
backend/accounts/urls.py:19:router.register(r'scoped-roles', ScopedRoleViewSet, basename='scopedrole')
backend/accounts/urls.py:20:router.register(r'role-audit-logs', RoleAssignmentAuditLogViewSet, basename='roleassignmentauditlog')
backend/accounts/urls.py:21:router.register(r'notifications', NotificationViewSet, basename='user-alert')
backend/accounts/urls.py:24:    path('my-roles/', my_roles, name='my-roles'),
backend/accounts/urls.py:25:    path('me/context/', me_context, name='me-context'),
backend/accounts/urls.py:26:    path('me/preferences/', me_preferences, name='me-preferences'),
backend/accounts/urls.py:27:    path('role-registry/', role_registry, name='role-registry'),
backend/accounts/urls.py:28:    path('change-password/', change_password, name='change-password'),
backend/accounts/urls.py:29:    path('logout/', LogoutView.as_view(), name='logout'),
backend/accounts/urls.py:30:    path('platform-apps/', platform_apps, name='platform-apps'),
backend/accounts/urls.py:31:    path('platform-apps/<str:app_id>/', platform_apps, name='platform-apps-detail'),
backend/accounts/urls.py:33:    path('pulse-auth/', pulse_auth_view, name='pulse-auth'),
backend/accounts/urls.py:34:    path('pulse-provision/', pulse_provision_view, name='pulse-provision'),
backend/accounts/urls.py:36:    path('audit-log/', RoleAssignmentAuditLogViewSet.as_view({'get': 'list'}), name='audit-log-list'),
backend/accounts/urls.py:37:    path('audit-log/<int:pk>/', RoleAssignmentAuditLogViewSet.as_view({'get': 'retrieve'}), name='audit-log-detail'),
backend/accounts/urls.py:38:    path('access-control/', ScopedRoleViewSet.as_view({'get': 'list', 'post': 'create'}), name='access-control-list'),
backend/accounts/urls.py:39:    path('access-control/<int:pk>/', ScopedRoleViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='access-control-detail'),
backend/accounts/urls.py:40:    path('capability-matrix/', capability_matrix, name='capability-matrix'),
backend/accounts/urls.py:42:    path('config/email/', EmailConfigView.as_view(), name='email-config'),
backend/accounts/urls.py:43:    path('config/backup/', BackupConfigView.as_view(), name='backup-config'),
backend/accounts/urls.py:44:    path('config/logging/', LogConfigView.as_view(), name='log-config'),
backend/accounts/urls.py:45:    path('config/api/', APIConfigView.as_view(), name='api-config'),
backend/importexport/urls.py:7:router.register(r'export-projects', ExportProjectViewSet, basename='exportproject')
backend/importexport/urls.py:8:router.register(r'import', ImportJobViewSet, basename='importjob')
backend/importexport/urls.py:9:router.register(r'export', ExportJobViewSet, basename='exportjob')
backend/connections/urls.py:7:router.register(r'sources', DataSourceViewSet, basename='datasource')
backend/connections/urls.py:8:router.register(r'consuming', ConsumingConnectionViewSet, basename='consumingconnection')
backend/people/urls.py:63:    path('me/', include('people.self_urls')),
backend/people/urls.py:64:    path('compliance-rules/', ComplianceRuleListCreateView.as_view(),
backend/people/urls.py:66:    path('compliance-rules/<int:pk>/', ComplianceRuleDetailView.as_view(),
backend/people/urls.py:68:    path('employees/', EmployeeListCreateView.as_view(), name='people-employees'),
backend/people/urls.py:69:    path('employees/<int:pk>/', EmployeeDetailView.as_view(),
backend/people/urls.py:71:    path('employees/<int:pk>/eosi/', EmployeeEOSIView.as_view(),
backend/people/urls.py:73:    path('employees/<int:pk>/compensation/', EmployeeCompensationView.as_view(),
backend/people/urls.py:75:    path('employees/<int:pk>/correspondence/', EmployeeCorrespondenceListView.as_view(),
backend/people/urls.py:77:    path('employees/<int:pk>/correspondence/<int:corr_pk>/',
backend/people/urls.py:80:    path('employees/<int:pk>/deactivate/', EmployeeDeactivateView.as_view(),
backend/people/urls.py:82:    path('employees/<int:pk>/reactivate/', EmployeeReactivateView.as_view(),
backend/people/urls.py:84:    path('payroll-runs/', PayrollRunListCreateView.as_view(),
backend/people/urls.py:86:    path('payroll-runs/<int:pk>/', PayrollRunDetailView.as_view(),
backend/people/urls.py:88:    path('payslip-lines/', PayslipLineListView.as_view(),
backend/people/urls.py:90:    path('positions/', PositionListCreateView.as_view(),
backend/people/urls.py:92:    path('positions/<int:pk>/', PositionDetailView.as_view(),
backend/people/urls.py:94:    path('leave-policies/', LeavePolicyListCreateView.as_view(),
backend/people/urls.py:96:    path('leave-policies/<int:pk>/propagate/', LeavePolicyPropagateView.as_view(),
backend/people/urls.py:98:    path('leave-policies/<int:pk>/versions/', LeavePolicyVersionListView.as_view(),
backend/people/urls.py:100:    path('leave-policies/<int:pk>/versions/<int:version_pk>/', LeavePolicyVersionDetailView.as_view(),
backend/people/urls.py:102:    path('leave-policies/<int:pk>/', LeavePolicyDetailView.as_view(),
backend/people/urls.py:104:    path('leave-entitlements/', LeaveEntitlementListCreateView.as_view(),
backend/people/urls.py:106:    path('leave-entitlements/<int:pk>/', LeaveEntitlementDetailView.as_view(),
backend/people/urls.py:108:    path('leave-records/', LeaveRecordListCreateView.as_view(),
backend/people/urls.py:110:    path('leave-records/<int:pk>/', LeaveRecordDetailView.as_view(),
backend/people/urls.py:112:    path('benefit-types/', BenefitTypeListCreateView.as_view(),
backend/people/urls.py:114:    path('benefit-types/<int:pk>/', BenefitTypeDetailView.as_view(),
backend/people/urls.py:116:    path('benefits/', EmployeeBenefitListCreateView.as_view(),
backend/people/urls.py:118:    path('benefits/<int:pk>/', EmployeeBenefitDetailView.as_view(),
backend/people/urls.py:120:    path('loans/', LoanListCreateView.as_view(),
backend/people/urls.py:122:    path('loans/<int:pk>/', LoanDetailView.as_view(),
backend/people/urls.py:124:    path('loan-installments/', LoanInstallmentListCreateView.as_view(),
backend/people/urls.py:126:    path('loan-installments/<int:pk>/', LoanInstallmentDetailView.as_view(),
backend/people/urls.py:128:    path('attendance/', AttendanceRecordListCreateView.as_view(),
backend/people/urls.py:130:    path('attendance/<int:pk>/', AttendanceRecordDetailView.as_view(),
backend/people/urls.py:132:    path('attendance-permissions/', AttendancePermissionListCreateView.as_view(),
backend/people/urls.py:134:    path('attendance-permissions/<int:pk>/',
backend/people/urls.py:137:    path('certifications/', CertificationListCreateView.as_view(),
backend/people/urls.py:139:    path('certifications/<int:pk>/', CertificationDetailView.as_view(),
backend/people/urls.py:141:    path('rotation-schedules/', RotationScheduleListCreateView.as_view(),
backend/people/urls.py:143:    path('rotation-schedules/<int:pk>/', RotationScheduleDetailView.as_view(),
backend/people/urls.py:145:    path('payroll-runs/<int:pk>/compute/', PayrollRunComputeView.as_view(),
backend/people/urls.py:147:    path('payroll-runs/<int:pk>/validate/', PayrollRunValidateView.as_view(),
backend/people/urls.py:149:    path('payroll-runs/<int:pk>/commit/', PayrollRunCommitView.as_view(),
backend/people/urls.py:151:    path('payroll-runs/<int:pk>/validations/',
backend/people/urls.py:154:    path('payroll-runs/<int:pk>/wps/', PayrollRunWPSExportView.as_view(),
backend/people/urls.py:156:    path('employees/<int:pk>/timeline/', EmployeeTimelineView.as_view(),
backend/people/urls.py:158:    path('positions/<int:pk>/timeline/', PositionTimelineView.as_view(),
backend/people/urls.py:160:    path('org-units/<int:pk>/timeline/', OrgUnitTimelineView.as_view(),
backend/people/urls.py:162:    path('events/', PersonnelEventListView.as_view(),
backend/people/urls.py:165:    path('compensation-components/', CompensationComponentListView.as_view(),
backend/people/urls.py:167:    path('compensation-plan/', CompensationPlanListView.as_view(),
backend/people/urls.py:169:    path('employees/<int:employee_pk>/compensation/<int:line_pk>/verify/',
backend/mdm/urls.py:13:router.register(r'reference-sets', ReferenceSetViewSet, basename='referenceset')
backend/mdm/urls.py:14:router.register(r'reference-values', ReferenceValueViewSet, basename='referencevalue')
backend/mdm/urls.py:15:router.register(r'org-units', OrgUnitViewSet, basename='orgunit')
backend/mdm/urls.py:18:    path('bind-field/', BindFieldView.as_view(), name='bind-field'),
backend/mdm/urls.py:19:    path('field-options/', FieldOptionsView.as_view(), name='field-options'),
backend/healthy/urls.py:11:    path('snapshots/', SnapshotListCreateView.as_view(), name='healthy-snapshots'),
backend/healthy/urls.py:12:    path('loadout/', LoadoutListView.as_view(), name='healthy-loadout-list'),
backend/healthy/urls.py:13:    path('loadout/<str:week>/', LoadoutWeekView.as_view(), name='healthy-loadout-week'),
backend/healthy/urls.py:14:    path('loadout/<str:week>/<str:rep>/', LoadoutRepView.as_view(), name='healthy-loadout-rep'),
backend/healthy/urls.py:15:    path('loadout/<str:week>/<str:rep>/actuals/', LoadoutActualsView.as_view(),
backend/healthy/urls.py:17:    path('rep-health/', RepHealthListView.as_view(), name='healthy-rep-health-list'),
backend/healthy/urls.py:18:    path('rep-health/<str:week>/<str:rep>/', RepHealthDetailView.as_view(),
backend/healthy/urls.py:20:    path('dashboards/summary/', DashboardSummaryView.as_view(),
backend/healthy/urls.py:22:    path('dashboards/ar-queue/', DashboardARQueueView.as_view(),
backend/healthy/urls.py:24:    path('dashboards/slow-movers/', DashboardSlowMoversView.as_view(),
backend/dq/urls.py:17:router.register(r'profiles', FieldProfileViewSet, basename='fieldprofile')
backend/dq/urls.py:18:router.register(r'table-profiles', TableProfileViewSet, basename='tableprofile')
backend/dq/urls.py:19:router.register(r'rules', DQRuleViewSet, basename='dqrule')
backend/dq/urls.py:20:router.register(r'results', DQResultViewSet, basename='dqresult')
backend/dq/urls.py:21:router.register(r'freshness', FreshnessCheckViewSet, basename='freshnesscheck')
backend/dq/urls.py:22:router.register(r'schema-snapshots', SchemaSnapshotViewSet, basename='schemasnapshot')
backend/dq/urls.py:23:router.register(r'schema-changes', SchemaChangeViewSet, basename='schemachange')
backend/dq/urls.py:24:router.register(r'tags', RuleTagViewSet, basename='ruletag')
backend/dq/urls.py:25:router.register(r'rule-assignments', RuleFieldAssignmentViewSet, basename='rulefieldassignment')
backend/dq/urls.py:26:router.register(r'jobs', DQJobViewSet, basename='dqjob')
backend/dq/urls.py:27:router.register(r'suggestions', DQSuggestionViewSet, basename='dqsuggestion')
backend/dq/urls.py:28:router.register(r'anomalies', DQAnomalyViewSet, basename='dqanomaly')
backend/dq/urls.py:31:    path('profile/', ProfileTriggerView.as_view(), name='dq-profile'),
backend/dq/urls.py:32:    path('profile/bulk/', BulkProfileView.as_view(), name='dq-profile-bulk'),
backend/dq/urls.py:33:    path('profile/config/', DQProfileConfigView.as_view(), name='dq-profile-config'),
backend/dq/urls.py:34:    path('run/', DQRunView.as_view(), name='dq-run'),
backend/dq/urls.py:35:    path('metrics/', DQMetricsView.as_view(), name='dq-metrics'),
backend/dq/urls.py:36:    path('metrics/table/<int:table_id>/', TableDQMetricsView.as_view(), name='dq-metrics-table'),
backend/dq/urls.py:37:    path('metrics/field/<int:field_id>/', FieldDQMetricsView.as_view(), name='dq-metrics-field'),
backend/dq/urls.py:38:    path('run-validation/', RunDQValidationView.as_view(), name='dq-run-validation'),
backend/dq/urls.py:39:    path('gate/check/', GateCheckView.as_view(), name='dq-gate-check'),
backend/dq/urls.py:40:    path('suggest/', DQSuggestView.as_view(), name='dq-suggest'),
backend/dq/urls.py:42:    path('tables/<int:table_id>/profile/', TableProfileView.as_view(), name='dq-table-profile'),
backend/dq/urls.py:43:    path('tables/<int:table_id>/profile/run/', RunProfileView.as_view(), name='dq-table-profile-run'),
backend/dq/urls.py:44:    path('tables/<int:table_id>/scorecard/', TableScorecardView.as_view(), name='dq-table-scorecard'),
backend/dataschema/urls.py:15:router.register(r'tables', DataTableViewSet, basename='dataschema-table')
backend/dataschema/urls.py:16:router.register(r'fields', DataFieldViewSet, basename='dataschema-field')
backend/dataschema/urls.py:17:router.register(r'rows', DataRowViewSet, basename='dataschema-row')
backend/dataschema/urls.py:18:router.register(r'schema-logs', SchemaChangeLogViewSet, basename='dataschema-schemalog')
backend/dataschema/urls.py:19:router.register(r'relations', TableRelationViewSet, basename='dataschema-relation')
backend/dataschema/urls.py:22:    path('fields/<int:field_id>/policies/', FieldAccessPolicyView.as_view(), name='field-policies'),
backend/dataschema/urls.py:23:    path('fields/<int:field_id>/policies/<int:pk>/', FieldAccessPolicyDetailView.as_view(), name='field-policy-detail'),
backend/dataschema/urls.py:24:    path('', include(router.urls)),
backend/appregistry/urls.py:8:    path('', AppManifestViewSet.as_view({'get': 'list'}),
backend/appregistry/urls.py:10:    path('<slug:slug>/', AppManifestViewSet.as_view({'get': 'retrieve'}),
backend/appregistry/urls.py:12:    path('<slug:slug>/activate/', ActivateAppView.as_view(),
backend/appregistry/urls.py:14:    path('<slug:slug>/deactivate/', DeactivateAppView.as_view(),
backend/correspondence/urls.py:12:    path('', CorrespondenceViewSet.as_view({'get': 'list', 'post': 'create'}),
backend/correspondence/urls.py:14:    path('inbox/', CorrespondenceViewSet.as_view({'get': 'inbox'}),
backend/correspondence/urls.py:16:    path('<int:pk>/', CorrespondenceViewSet.as_view({'get': 'retrieve'}),
backend/correspondence/urls.py:18:    path('<int:pk>/approve/', CorrespondenceViewSet.as_view({'post': 'approve'}),
backend/correspondence/urls.py:20:    path('<int:pk>/acknowledge/', CorrespondenceViewSet.as_view({'post': 'acknowledge'}),
backend/correspondence/urls.py:22:    path('<int:pk>/review/', CorrespondenceViewSet.as_view({'post': 'review'}),
backend/correspondence/urls.py:24:    path('<int:pk>/reject/', CorrespondenceViewSet.as_view({'post': 'reject'}),
backend/correspondence/urls.py:26:    path('<int:pk>/send-back/', CorrespondenceViewSet.as_view({'post': 'send_back'}),
backend/correspondence/urls.py:28:    path('<int:pk>/cancel/', CorrespondenceViewSet.as_view({'post': 'cancel'}),
backend/correspondence/urls.py:30:    path('<int:pk>/resubmit/', CorrespondenceViewSet.as_view({'post': 'resubmit'}),
backend/correspondence/urls.py:32:    path('<int:pk>/archive/', CorrespondenceViewSet.as_view({'post': 'archive'}),
backend/correspondence/urls.py:34:    path('notifications/', NotificationViewSet.as_view({'get': 'list'}),
backend/correspondence/urls.py:36:    path('notifications/read-all/', NotificationViewSet.as_view({'post': 'read_all'}),
backend/correspondence/urls.py:38:    path('notifications/<int:pk>/read/', NotificationViewSet.as_view({'post': 'read'}),
backend/correspondence/urls.py:40:    path('policies/', WorkflowPolicyViewSet.as_view({'get': 'list'}),
backend/correspondence/urls.py:42:    path('policies/<int:pk>/', WorkflowPolicyViewSet.as_view({'get': 'retrieve'}),
backend/catalog/urls.py:18:router.register(r'domains', DataDomainViewSet, basename='datadomain')
backend/catalog/urls.py:19:router.register(r'glossary', GlossaryTermViewSet, basename='glossaryterm')
backend/catalog/urls.py:20:router.register(r'tags', TagViewSet, basename='tag')
backend/catalog/urls.py:21:router.register(r'assets', AssetProfileViewSet, basename='assetprofile')
backend/catalog/urls.py:22:router.register(r'governance-events', GovernanceEventViewSet, basename='governanceevent')
backend/catalog/urls.py:23:router.register(r'governance-policies', GovernancePolicyViewSet, basename='governancepolicy')
backend/catalog/urls.py:24:router.register(r'datasets', DatasetViewSet, basename='dataset')
backend/catalog/urls.py:25:router.register(r'lineage', LineageEdgeViewSet, basename='lineageedge')
backend/catalog/urls.py:26:router.register(r'notes', NoteViewSet, basename='note')
backend/catalog/urls.py:27:router.register(r'notes/(?P<note_id>[^/.]+)/comments', NoteCommentViewSet, basename='notecomment')
backend/catalog/urls.py:30:    path('search/', CatalogSearchView.as_view(), name='catalog-search'),
backend/catalog/urls.py:31:    path('governance/compliance/', GovernanceComplianceView.as_view(), name='governance-compliance'),
backend/catalog/urls.py:33:    path('tables/<int:table_id>/lineage/', TableLineageView.as_view(), name='table-lineage'),
backend/catalog/urls.py:34:    path('tables/<int:table_id>/impact/', TableImpactView.as_view(), name='table-impact'),
backend/catalog/urls.py:35:    path('tables/<int:table_id>/freshness/', FreshnessPolicyView.as_view(), name='table-freshness'),
backend/catalog/urls.py:37:    path('datasets/<uuid:dataset_id>/versions/',
backend/catalog/urls.py:39:    path('datasets/<uuid:dataset_id>/versions/<uuid:version_id>/',
backend/catalog/urls.py:41:    path('datasets/<uuid:dataset_id>/versions/<uuid:version_id>/approve/',
backend/catalog/urls.py:43:    path('datasets/<uuid:dataset_id>/versions/<uuid:version_id>/reject/',
backend/catalog/urls.py:46:    path('datasets/<uuid:dataset_id>/contract/',
backend/catalog/urls.py:48:    path('datasets/<uuid:dataset_id>/contract/violations/',
backend/catalog/urls.py:51:    path('datasets/<uuid:dataset_id>/ingest/erp/',
backend/catalog/urls.py:53:    path('datasets/<uuid:dataset_id>/ingest/upload/',
backend/emissions/urls.py:93:router.register(r'periods', ReportingPeriodViewSet, basename='reporting-period')
backend/emissions/urls.py:94:router.register(r'factors', EmissionFactorViewSet, basename='emission-factor')
backend/emissions/urls.py:95:router.register(r'gwp', GWPViewSet, basename='gwp')
backend/emissions/urls.py:96:router.register(r'calculations', CalculationViewSet, basename='calculation')
backend/emissions/urls.py:97:router.register(r'rules', CalculationRuleViewSet, basename='calculation-rule')
backend/emissions/urls.py:98:router.register(r'report-configs', ReportConfigViewSet, basename='report-config')
backend/emissions/urls.py:101:verification_router.register(r'verifications', VerificationRecordViewSet, basename='verification')
backend/emissions/urls.py:104:audit_router.register(r'calculation-audits', CalculationAuditViewSet, basename='calculation-audit')
backend/emissions/urls.py:107:targets_router.register(r'targets', SBTiTargetViewSet, basename='sbti-target')
backend/emissions/urls.py:110:export_audit_router.register(r'export-audits', ExportAuditViewSet, basename='export-audit')
backend/emissions/urls.py:114:boundary_router.register(r'boundaries', OrganizationalBoundaryViewSet, basename='organizational-boundary')
backend/emissions/urls.py:117:base_year_router.register(r'base-years', BaseYearViewSet, basename='base-year')
backend/emissions/urls.py:120:recalc_router.register(r'recalculation-triggers', RecalculationTriggerViewSet, basename='recalculation-trigger')
backend/emissions/urls.py:124:inventory_source_router.register(r'inventory-sources', InventorySourceViewSet, basename='inventory-source')
backend/emissions/urls.py:127:inventory_source_status_router.register(
backend/emissions/urls.py:132:coverage_goal_router.register(r'coverage-goals', CoverageGoalViewSet, basename='coverage-goal')
backend/emissions/urls.py:135:coverage_action_router.register(r'coverage-actions', CoverageActionViewSet, basename='coverage-action')
backend/emissions/urls.py:139:    path('calculations/summary/', CalculationSummaryAPIView.as_view(), name='calculation-summary'),
backend/emissions/urls.py:142:    path('', include(router.urls)),
backend/emissions/urls.py:145:    path('', include(verification_router.urls)),
backend/emissions/urls.py:148:    path('', include(audit_router.urls)),
backend/emissions/urls.py:151:    path('', include(targets_router.urls)),
backend/emissions/urls.py:154:    path('', include(export_audit_router.urls)),
backend/emissions/urls.py:157:    path('', include(boundary_router.urls)),
backend/emissions/urls.py:158:    path('', include(base_year_router.urls)),
backend/emissions/urls.py:159:    path('', include(recalc_router.urls)),
backend/emissions/urls.py:162:    path('', include(inventory_source_router.urls)),
backend/emissions/urls.py:163:    path('', include(inventory_source_status_router.urls)),
backend/emissions/urls.py:164:    path('', include(coverage_goal_router.urls)),
backend/emissions/urls.py:165:    path('', include(coverage_action_router.urls)),
backend/emissions/urls.py:166:    path('coverage/', InventoryCoverageAPIView.as_view(), name='inventory-coverage'),
backend/emissions/urls.py:169:    path('dashboard/', DashboardAPIView.as_view(), name='dashboard'),
backend/emissions/urls.py:172:    path('chairman/', ChairmanAPIView.as_view(), name='chairman'),
backend/emissions/urls.py:175:    path('owner-dashboard/', OwnerDashboardAPIView.as_view(), name='owner-dashboard'),
backend/emissions/urls.py:176:    path('owner/summary/', OwnerSummaryAPIView.as_view(), name='owner-summary'),
backend/emissions/urls.py:177:    path('owner/assets/', OwnerAssetsAPIView.as_view(), name='owner-assets'),
backend/emissions/urls.py:178:    path('owner/activity/', OwnerActivityAPIView.as_view(), name='owner-activity'),
backend/emissions/urls.py:181:    path('my-data/', MyDataAPIView.as_view(), name='my-data'),
backend/emissions/urls.py:184:    path('yearly-comparison/', YearlyComparisonAPIView.as_view(), name='yearly-comparison'),
backend/emissions/urls.py:187:    path('report/', ReportAPIView.as_view(), name='report'),
backend/emissions/urls.py:190:    path('calculate/', CalculateAPIView.as_view(), name='calculate'),
backend/emissions/urls.py:191:    path('batch-calculate/', BatchCalculateAPIView.as_view(), name='batch-calculate'),
backend/emissions/urls.py:194:    path('console/', ConsoleAPIView.as_view(), name='console'),
```

## @action custom endpoints (ViewSet extra routes)
```
backend/core/views.py:99:    @action(detail=True, methods=['get'])
backend/core/views.py-100-    def quality_summary(self, request, pk=None):
backend/core/views.py:117:    @action(detail=True, methods=['get'])
backend/core/views.py-118-    def audit_trail(self, request, pk=None):
backend/core/views.py:159:    @action(detail=True, methods=['post'])
backend/core/views.py-160-    def mark_read(self, request, pk=None):
backend/core/views.py:168:    @action(detail=False, methods=['post'])
backend/core/views.py-169-    def mark_all_read(self, request):
backend/evidence/views.py:51:    @action(detail=True, methods=['get'], url_path='download')
backend/evidence/views.py-52-    def download(self, request, pk=None):
backend/evidence/views.py:82:    @action(detail=False, methods=['post'], url_path='bulk-upload')
backend/evidence/views.py-83-    def bulk_upload(self, request):
backend/accounts/views.py:301:    @action(detail=True, methods=['get'])
backend/accounts/views.py-302-    def members(self, request, pk=None):
backend/accounts/views.py:327:    @action(detail=True, methods=['get'])
backend/accounts/views.py-328-    def scoped_assignments(self, request, pk=None):
backend/accounts/notification_views.py:22:    @action(detail=False, methods=['post'])
backend/accounts/notification_views.py-23-    def mark_all_read(self, request):
backend/accounts/notification_views.py:28:    @action(detail=True, methods=['post'])
backend/accounts/notification_views.py-29-    def mark_read(self, request, pk=None):
backend/accounts/notification_views.py:36:    @action(detail=False, methods=['get'])
backend/accounts/notification_views.py-37-    def unread_count(self, request):
backend/importexport/views.py:32:    @action(detail=True, methods=['post'])
backend/importexport/views.py-33-    def run(self, request, pk=None):
backend/importexport/views.py:121:    @action(detail=True, methods=['get'])
backend/importexport/views.py-122-    def download(self, request, pk=None):
backend/importexport/views.py:150:    @action(detail=True, methods=['get'])
backend/importexport/views.py-151-    def download(self, request, pk=None):
backend/connections/views.py:26:    @action(detail=True, methods=['post'])
backend/connections/views.py-27-    def test(self, request, pk=None):
backend/connections/views.py:59:    @action(detail=True, methods=['post'])
backend/connections/views.py-60-    def rotate_key(self, request, pk=None):
backend/mdm/views.py:172:    @action(detail=True, methods=['get'])
backend/mdm/views.py-173-    def values(self, request, pk=None):
backend/mdm/views.py:209:    @action(detail=True, methods=['post'])
backend/mdm/views.py-210-    def transition(self, request, pk=None):
backend/mdm/views.py:228:    @action(detail=True, methods=['post'])
backend/mdm/views.py-229-    def add_value(self, request, pk=None):
backend/mdm/views.py:266:    @action(detail=False, methods=['post'], url_path='archive-bulk')
backend/mdm/views.py-267-    def archive_bulk(self, request):
backend/mdm/views.py:289:    @action(detail=False, methods=['post'], url_path='bulk-create')
backend/mdm/views.py-290-    def bulk_create(self, request):
backend/mdm/views.py:620:    @action(detail=True, methods=['get'])
backend/mdm/views.py-621-    def tree(self, request, pk=None):
backend/mdm/views.py:640:    @action(detail=False, methods=['get'], url_path='tree')
backend/mdm/views.py-641-    def list_tree(self, request):
backend/mdm/views.py:680:    @action(detail=True, methods=['get'])
backend/mdm/views.py-681-    def ancestors(self, request, pk=None):
backend/dq/views.py:270:    @action(detail=True, methods=['post'], url_path='run')
backend/dq/views.py-271-    def run(self, request, pk=None):
backend/dq/views.py:306:    @action(detail=True, methods=['get'])
backend/dq/views.py-307-    def history(self, request, pk=None):
backend/dq/views.py:349:    @action(detail=False, methods=['get'], url_path='contradictions')
backend/dq/views.py-350-    def contradictions(self, request):
backend/dq/views.py:421:    @action(detail=False, methods=['post'], url_path='bulk-execute')
backend/dq/views.py-422-    def bulk_execute(self, request):
backend/dq/views.py:559:    @action(detail=True, methods=['get'])
backend/dq/views.py-560-    def failures(self, request, pk=None):
backend/dq/views.py:1598:    @action(detail=True, methods=['post'])
backend/dq/views.py-1599-    def cancel(self, request, pk=None):
backend/dq/views.py:1659:    @action(detail=True, methods=['post'])
backend/dq/views.py-1660-    def accept(self, request, pk=None):
backend/dq/views.py:1757:    @action(detail=True, methods=['post'])
backend/dq/views.py-1758-    def reject(self, request, pk=None):
backend/dataschema/views.py:529:    @action(detail=False, methods=['post'], url_path='bulk-import')
backend/dataschema/views.py-530-    def bulk_import(self, request):
backend/dataschema/views.py:590:    @action(detail=False, methods=['get'], url_path='download-template')
backend/dataschema/views.py-591-    def download_template(self, request):
backend/ai/catalog_api.py:225:    @action(detail=False, methods=["get"], url_path="topology")
backend/ai/catalog_api.py-226-    def topology(self, request):
backend/ai/catalog_api.py:233:    @action(detail=False, methods=["get"], url_path="skills")
backend/ai/catalog_api.py-234-    def skills(self, request):
backend/ai/catalog_api.py:241:    @action(detail=False, methods=["get"], url_path="index")
backend/ai/catalog_api.py-242-    def federated_index(self, request):
backend/ai/plans_api.py:202:    @action(
backend/ai/plans_api.py:262:    @action(
backend/ai/plans_api.py:297:    @action(detail=True, methods=["post"], url_path="approve", url_name="approve-plan")
backend/ai/plans_api.py-298-    def approve(self, request, pk=None):
backend/ai/plans_api.py:311:    @action(detail=True, methods=["post"], url_path="decline", url_name="decline-plan")
backend/ai/plans_api.py-312-    def decline(self, request, pk=None):
backend/ai/plans_api.py:337:    @action(detail=True, methods=["post"], url_path="pause", url_name="pause-plan")
backend/ai/plans_api.py-338-    def pause(self, request, pk=None):
backend/ai/plans_api.py:351:    @action(detail=True, methods=["post"], url_path="resume", url_name="resume-plan")
backend/ai/plans_api.py-352-    def resume(self, request, pk=None):
backend/ai/plans_api.py:382:    @action(detail=True, methods=["post"], url_path="fork", url_name="fork-plan")
backend/ai/plans_api.py-383-    def fork(self, request, pk=None):
backend/ai/plans_api.py:393:    @action(detail=True, methods=["post"], url_path="rerun", url_name="rerun-plan")
backend/ai/plans_api.py-394-    def rerun(self, request, pk=None):
backend/ai/plans_api.py:519:    @action(detail=True, methods=["post"], url_path="run", url_name="run-plan")
backend/ai/plans_api.py-520-    def run(self, request, pk=None):
backend/ai/plans_api.py:554:    @action(
backend/ai/plans_api.py:578:    @action(
backend/ai/plans_api.py:624:    @action(
backend/ai/plans_api.py:636:    @action(
backend/ai/plans_api.py:648:    @action(
backend/ai/plans_api.py:660:    @action(
backend/ai/plans_api.py:672:    @action(
backend/ai/plans_api.py:686:    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-plan")
backend/ai/plans_api.py-687-    def stop(self, request, pk=None):
backend/ai/plans_api.py:696:    @action(
backend/ai/plans_api.py:730:    @action(detail=True, methods=["get"], url_path="ledger", url_name="plan-ledger")
backend/ai/plans_api.py-731-    def ledger(self, request, pk=None):
backend/ai/plans_api.py:743:    @action(detail=True, methods=["get"], url_path="qos", url_name="plan-qos")
backend/ai/plans_api.py-744-    def qos(self, request, pk=None):
backend/ai/plans_api.py:761:    @action(detail=True, methods=["get"], url_path="flight", url_name="plan-flight")
backend/ai/plans_api.py-762-    def flight(self, request, pk=None):
backend/ai/plans_api.py:781:    @action(
backend/ai/plans_api.py:796:    @action(
backend/ai/durable_api.py:64:    @action(detail=True, methods=["get"], url_path="timeline",
backend/ai/durable_api.py:97:    @action(detail=True, methods=["post"], url_path="resume",
backend/ai/durable_api.py:114:    @action(detail=True, methods=["post"], url_path="replay",
backend/ai/workspace_api.py:163:    @action(detail=True, methods=["get", "post"], url_path="messages", url_name="send-message")
backend/ai/workspace_api.py-164-    def send_message(self, request, pk=None):
backend/ai/workspace_api.py:168:        register two ``@action`` methods on the same ``url_path`` without one
backend/ai/workspace_api.py:217:    @action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback", url_name="message-feedback")
backend/ai/workspace_api.py-218-    def message_feedback(self, request, pk=None, message_id=None):
backend/ai/workspace_api.py:237:    @action(detail=True, methods=["post"], url_path="messages/stream", url_name="send-message-stream")
backend/ai/workspace_api.py-238-    def send_message_stream(self, request, pk=None):
backend/ai/workspace_api.py:265:    @action(detail=True, methods=["post"], url_path="actions/stream", url_name="run-action-stream")
backend/ai/workspace_api.py-266-    def run_action_stream(self, request, pk=None):
backend/ai/workspace_api.py:304:    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-generation")
backend/ai/workspace_api.py-305-    def stop_generation(self, request, pk=None):
backend/ai/workspace_api.py:319:    @action(
backend/ai/workspace_api.py:340:    @action(
backend/ai/workspace_api.py:391:    @action(
backend/ai/workspace_api.py:423:    @action(detail=True, methods=["post"], url_path="summary", url_name="summarize")
backend/ai/workspace_api.py-424-    def summarize(self, request, pk=None):
backend/ai/workspace_api.py:441:    @action(
backend/ai/workspace_api.py:628:    @action(
backend/ai/workspace_api.py:727:    @action(detail=True, methods=["get"], url_path="subagents", url_name="list-subagents")
backend/ai/workspace_api.py-728-    def list_subagents(self, request, pk=None):
backend/ai/workspace_api.py:736:    @action(detail=True, methods=["post"], url_path="subagents", url_name="dispatch-subagent")
backend/ai/workspace_api.py-737-    def dispatch_subagent(self, request, pk=None):
backend/ai/workspace_api.py:747:    @action(detail=True, methods=["get"], url_path=r"subagents/(?P<sub_id>[^/.]+)", url_name="subagent-detail")
backend/ai/workspace_api.py-748-    def subagent_detail(self, request, pk=None, sub_id=None):
backend/ai/workspace_api.py:758:    @action(detail=True, methods=["get"], url_path="export", url_name="export")
backend/ai/workspace_api.py-759-    def export(self, request, pk=None):
backend/ai/workspace_api.py:786:    @action(detail=True, methods=["get"], url_path="suggestions", url_name="suggestions")
backend/ai/workspace_api.py-787-    def suggestions(self, request, pk=None):
backend/ai/workspace_api.py:813:    @action(detail=True, methods=["post"], url_path="resume", url_name="resume")
backend/ai/workspace_api.py-814-    def resume(self, request, pk=None):
backend/ai/workspace_api.py:828:    @action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/accept", url_name="suggestion-accept")
backend/ai/workspace_api.py-829-    def accept_suggestion(self, request, pk=None, suggestion_id=None):
backend/ai/workspace_api.py:842:    @action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/dismiss", url_name="suggestion-dismiss")
backend/ai/workspace_api.py-843-    def dismiss_suggestion(self, request, pk=None, suggestion_id=None):
backend/ai/workspace_api.py:857:    @action(detail=False, methods=["get"], url_path="suggestions", url_name="workspace-suggestions")
backend/ai/workspace_api.py-858-    def workspace_suggestions(self, request):
backend/ai/workspace_api.py:873:    @action(detail=True, methods=["post"], url_path="checkpoint", url_name="checkpoint-conversation")
backend/ai/workspace_api.py-874-    def checkpoint(self, request, pk=None):
backend/ai/workspace_api.py:899:    @action(detail=True, methods=["get"], url_path="checkpoints", url_name="checkpoints")
backend/ai/workspace_api.py-900-    def checkpoints(self, request, pk=None):
backend/ai/workspace_api.py:919:    @action(detail=True, methods=["post"], url_path="restore", url_name="restore-conversation")
backend/ai/workspace_api.py-920-    def restore(self, request, pk=None):
backend/ai/workspace_api.py:944:    @action(detail=True, methods=["post"], url_path="fork", url_name="fork-conversation")
backend/ai/workspace_api.py-945-    def fork(self, request, pk=None):
backend/ai/workspace_api.py:971:    @action(detail=True, methods=["post"], url_path="clear-context", url_name="clear-context")
backend/ai/workspace_api.py-972-    def clear_context(self, request, pk=None):
backend/ai/workspace_api.py:1056:    @action(detail=True, methods=["get", "post"], url_path="messages", url_name="send-message")
backend/ai/workspace_api.py-1057-    def send_message(self, request, pk=None):
backend/ai/workspace_api.py:1061:        register two ``@action`` methods on the same ``url_path`` without one
backend/ai/workspace_api.py:1105:    @action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback", url_name="message-feedback")
backend/ai/workspace_api.py-1106-    def message_feedback(self, request, pk=None, message_id=None):
backend/ai/workspace_api.py:1125:    @action(detail=True, methods=["post"], url_path="messages/stream", url_name="send-message-stream")
backend/ai/workspace_api.py-1126-    def send_message_stream(self, request, pk=None):
backend/ai/workspace_api.py:1153:    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-generation")
backend/ai/workspace_api.py-1154-    def stop_generation(self, request, pk=None):
backend/ai/workspace_api.py:1168:    @action(
backend/ai/workspace_api.py:1189:    @action(
backend/ai/workspace_api.py:1220:    @action(detail=True, methods=["post"], url_path="summary", url_name="summarize")
backend/ai/workspace_api.py-1221-    def summarize(self, request, pk=None):
backend/ai/workspace_api.py:1238:    @action(detail=True, methods=["get"], url_path="export", url_name="export")
backend/ai/workspace_api.py-1239-    def export(self, request, pk=None):
backend/correspondence/views.py:243:    @action(detail=False, methods=['get'], url_path='inbox')
backend/correspondence/views.py-244-    def inbox(self, request):
backend/correspondence/views.py:256:    @action(detail=True, methods=['post'], url_path='approve')
backend/correspondence/views.py-257-    def approve(self, request, pk=None):
backend/correspondence/views.py:264:    @action(detail=True, methods=['post'], url_path='acknowledge')
backend/correspondence/views.py-265-    def acknowledge(self, request, pk=None):
backend/correspondence/views.py:273:    @action(detail=True, methods=['post'], url_path='review')
backend/correspondence/views.py-274-    def review(self, request, pk=None):
backend/correspondence/views.py:282:    @action(detail=True, methods=['post'], url_path='reject')
backend/correspondence/views.py-283-    def reject(self, request, pk=None):
backend/correspondence/views.py:295:    @action(detail=True, methods=['post'], url_path='send-back')
backend/correspondence/views.py-296-    def send_back(self, request, pk=None):
backend/correspondence/views.py:309:    @action(detail=True, methods=['post'], url_path='cancel')
backend/correspondence/views.py-310-    def cancel(self, request, pk=None):
backend/correspondence/views.py:316:    @action(detail=True, methods=['post'], url_path='resubmit')
backend/correspondence/views.py-317-    def resubmit(self, request, pk=None):
backend/correspondence/views.py:323:    @action(detail=True, methods=['post'], url_path='archive')
backend/correspondence/views.py-324-    def archive(self, request, pk=None):
backend/correspondence/views.py:386:    @action(detail=True, methods=['post'], url_path='read')
backend/correspondence/views.py-387-    def read(self, request, pk=None):
backend/correspondence/views.py:394:    @action(detail=False, methods=['post'], url_path='read-all')
backend/correspondence/views.py-395-    def read_all(self, request):
backend/catalog/views.py:174:    @action(detail=False, methods=['post'], url_path='archive-bulk')
backend/catalog/views.py-175-    def archive_bulk(self, request):
backend/catalog/views.py:625:    @action(detail=True, methods=['post'], url_path='reactions')
backend/catalog/views.py-626-    def reactions(self, request, pk=None):
backend/catalog/views.py:698:    @action(detail=True, methods=['post'], url_path='reactions')
backend/catalog/views.py-699-    def reactions(self, request, note_id=None, pk=None):
```
