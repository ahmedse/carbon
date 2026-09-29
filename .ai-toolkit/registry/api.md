# Registry: API Endpoints  (auto-generated 2026-09-29 15:12 — DO NOT EDIT)

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
backend/config/urls.py:27:    path(f'{api_prefix}/health/', health_check),
backend/config/urls.py:28:    path(f'{api_prefix}/health/metrics/', metrics_view),
backend/config/urls.py:30:    path(f'{api_prefix}/health/prometheus/', prometheus_metrics_view),
backend/config/urls.py:33:    path(f'{api_prefix}/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
backend/config/urls.py:34:    path(f'{api_prefix}/token/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),
backend/config/urls.py:37:    path(
backend/config/urls.py:50:    path(
backend/config/urls.py:55:    path(
backend/config/urls.py:62:    path(
backend/config/urls.py:69:    path(f'{api_prefix}/email/test/', include('accounts.email_urls')),
backend/config/urls.py:72:    path(f'{api_prefix}/system/logs/', include('config.log_urls')),
backend/config/urls.py:75:    path(f'{api_prefix}/accounts/', include('accounts.urls')),
backend/config/urls.py:76:    path(f'{api_prefix}/core/', include('core.urls')),
backend/config/urls.py:77:    path(f'{api_prefix}/assurance/', include('core.assurance_urls')),
backend/config/urls.py:78:    path(f'{api_prefix}/excellence/', include('excellence.urls')),
backend/config/urls.py:79:    path(f'{api_prefix}/dataschema/', include('dataschema.urls')),
backend/config/urls.py:80:    path(f'{api_prefix}/carbon/', include(('emissions.urls', 'carbon'), namespace='carbon')),
backend/config/urls.py:81:    path(f'{api_prefix}/catalog/', include('catalog.urls')),
backend/config/urls.py:82:    path(f'{api_prefix}/mdm/', include('mdm.urls')),
backend/config/urls.py:83:    path(f'{api_prefix}/connections/', include('connections.urls')),
backend/config/urls.py:84:    path(f'{api_prefix}/importexport/', include('importexport.urls')),
backend/config/urls.py:85:    path(f'{api_prefix}/inbound/', include('inbound.urls')),
backend/config/urls.py:86:    path(f'{api_prefix}/dq/', include('dq.urls')),
backend/config/urls.py:87:    path(f'{api_prefix}/apps/', include('appregistry.urls')),
backend/config/urls.py:88:    path(f'{api_prefix}/integrations/turnkey/', include('integrations.turnkey.urls')),
backend/config/urls.py:89:    path(f'{api_prefix}/healthy/', include('healthy.urls')),
backend/config/urls.py:90:    path(f'{api_prefix}/people/', include('people.urls')),
backend/config/urls.py:91:    path(f'{api_prefix}/gradevance/', include('gradevance.urls')),
backend/config/urls.py:92:    path(f'{api_prefix}/correspondence/', include('correspondence.urls')),
backend/config/urls.py:93:    path(f'{api_prefix}/ai/workspace/', include('ai.workspace_urls')),
backend/config/urls.py:94:    path(f'{api_prefix}/ai/moodle/ask/', MoodleAskView.as_view(), name='ai-moodle-ask'),
backend/config/urls.py:95:    path(f'{api_prefix}/ai/moodle/embed/', MoodleEmbedView.as_view(), name='ai-moodle-embed'),
backend/config/urls.py:96:    path(f'{api_prefix}/ai/moodle/embed/session/', MoodleEmbedSessionView.as_view(), name='ai-moodle-embed-session'),
backend/config/urls.py:97:    path(f'{api_prefix}/ai/work-objectives/', include('ai.work_objectives_urls')),
backend/config/urls.py:98:    path(f'{api_prefix}/ai/plans/', include('ai.plans_urls')),
backend/config/urls.py:99:    path(f'{api_prefix}/ai/catalog/', include('ai.catalog_urls')),
backend/config/urls.py:100:    path(f'{api_prefix}/ai/registry/', include('ai.registry_urls')),
backend/config/urls.py:101:    path(f'{api_prefix}/ai/skills/', include('ai.skills_decision_urls')),
backend/config/urls.py:102:    path(f'{api_prefix}/ai/inbox/', include('ai.task_inbox_urls')),
backend/config/urls.py:103:    path(f'{api_prefix}/ai/runs/', include('ai.durable_urls')),
backend/config/urls.py:104:    path(f'{api_prefix}/ai/usage/', include('ai.usage_urls')),
backend/config/urls.py:105:    path(f'{api_prefix}/ai/profile/', ai_workspace_views.UserProfileView.as_view(), name='ai-user-profile'),
backend/config/urls.py:106:    path(f'{api_prefix}/ai/memory/', include('ai.memory_urls')),
backend/config/urls.py:107:    path(f'{api_prefix}/ai/knowledge/', include('ai.knowledge_urls')),
backend/config/urls.py:108:    path(f'{api_prefix}/ai/pulse/', include('ai.ops_urls')),
backend/config/urls.py:109:    path(f'{api_prefix}/ai/insights/', include('ai.insights_urls')),
backend/config/urls.py:110:    path(f'{api_prefix}/ai/operations/', include('ai.progress_urls')),
backend/config/urls.py:111:    path(f'{api_prefix}/ai/audit/', include('ai.audit_urls')),
backend/config/urls.py:112:    path(f'{api_prefix}/ai/watches/', include('ai.watches_urls')),
backend/config/urls.py:113:    path(f'{api_prefix}/mcp/', include('ai.mcp.server_urls')),
backend/config/urls.py:114:    path(f'{api_prefix}/', include('evidence.urls')),
backend/config/urls.py:124:    urlpatterns.insert(0, path('admin/', admin.site.urls))
backend/config/urls.py:130:    path(f'{api_prefix}/schema/', SpectacularAPIView.as_view(permission_classes=[AdminOrSuperuserOnly]), name='schema'),
backend/config/urls.py:131:    path(f'{api_prefix}/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='schema-swagger-ui'),
backend/config/urls.py:132:    path(f'{api_prefix}/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='schema-redoc'),
backend/config/urls.py:140:        path('__debug__/', include(debug_toolbar.urls)),
backend/config/urls.py:141:        path('silk/', include('silk.urls', namespace='silk')),
backend/evidence/urls.py:9:router.register(r'evidence', EvidenceViewSet, basename='evidence')
backend/evidence/urls.py:12:    path('', include(router.urls)),
backend/accounts/urls.py:16:router.register(r'users', UserViewSet)
backend/accounts/urls.py:17:router.register(r'roles', GroupViewSet, basename='role')
backend/accounts/urls.py:18:router.register(r'groups', GroupViewSet, basename='group')
backend/accounts/urls.py:19:router.register(r'scoped-roles', ScopedRoleViewSet, basename='scopedrole')
backend/accounts/urls.py:20:router.register(r'duty-profiles', DutyProfileViewSet, basename='dutyprofile')
backend/accounts/urls.py:21:router.register(r'role-audit-logs', RoleAssignmentAuditLogViewSet, basename='roleassignmentauditlog')
backend/accounts/urls.py:22:router.register(r'notifications', NotificationViewSet, basename='user-alert')
backend/accounts/urls.py:25:    path('my-roles/', my_roles, name='my-roles'),
backend/accounts/urls.py:26:    path('me/context/', me_context, name='me-context'),
backend/accounts/urls.py:27:    path('me/preferences/', me_preferences, name='me-preferences'),
backend/accounts/urls.py:28:    path('role-registry/', role_registry, name='role-registry'),
backend/accounts/urls.py:29:    path('duties/', duties, name='duties'),
backend/accounts/urls.py:30:    path('change-password/', change_password, name='change-password'),
backend/accounts/urls.py:31:    path('logout/', LogoutView.as_view(), name='logout'),
backend/accounts/urls.py:32:    path('platform-apps/', platform_apps, name='platform-apps'),
backend/accounts/urls.py:33:    path('platform-apps/<str:app_id>/', platform_apps, name='platform-apps-detail'),
backend/accounts/urls.py:35:    path('pulse-auth/', pulse_auth_view, name='pulse-auth'),
backend/accounts/urls.py:36:    path('pulse-provision/', pulse_provision_view, name='pulse-provision'),
backend/accounts/urls.py:38:    path('audit-log/', RoleAssignmentAuditLogViewSet.as_view({'get': 'list'}), name='audit-log-list'),
backend/accounts/urls.py:39:    path('audit-log/<int:pk>/', RoleAssignmentAuditLogViewSet.as_view({'get': 'retrieve'}), name='audit-log-detail'),
backend/accounts/urls.py:40:    path('access-control/', ScopedRoleViewSet.as_view({'get': 'list', 'post': 'create'}), name='access-control-list'),
backend/accounts/urls.py:41:    path('access-control/<int:pk>/', ScopedRoleViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='access-control-detail'),
backend/accounts/urls.py:42:    path('capability-matrix/', capability_matrix, name='capability-matrix'),
backend/accounts/urls.py:44:    path('config/email/', EmailConfigView.as_view(), name='email-config'),
backend/accounts/urls.py:45:    path('config/backup/', BackupConfigView.as_view(), name='backup-config'),
backend/accounts/urls.py:46:    path('config/logging/', LogConfigView.as_view(), name='log-config'),
backend/accounts/urls.py:47:    path('config/api/', APIConfigView.as_view(), name='api-config'),
backend/importexport/urls.py:7:router.register(r'export-projects', ExportProjectViewSet, basename='exportproject')
backend/importexport/urls.py:8:router.register(r'import', ImportJobViewSet, basename='importjob')
backend/importexport/urls.py:9:router.register(r'export', ExportJobViewSet, basename='exportjob')
backend/connections/urls.py:7:router.register(r'sources', DataSourceViewSet, basename='datasource')
backend/connections/urls.py:8:router.register(r'consuming', ConsumingConnectionViewSet, basename='consumingconnection')
backend/people/urls.py:77:    path('me/', include('people.self_urls')),
backend/people/urls.py:78:    path('compliance-rules/', ComplianceRuleListCreateView.as_view(),
backend/people/urls.py:80:    path('compliance-rules/<int:pk>/', ComplianceRuleDetailView.as_view(),
backend/people/urls.py:82:    path('analytics/', EmployeeAnalyticsView.as_view(),
backend/people/urls.py:84:    path('compliance/kuwaitization/', KuwaitizationQuotaView.as_view(),
backend/people/urls.py:86:    path('employees/', EmployeeListCreateView.as_view(), name='people-employees'),
backend/people/urls.py:87:    path('employees/<int:pk>/', EmployeeDetailView.as_view(),
backend/people/urls.py:89:    path('employees/<int:pk>/eosi/', EmployeeEOSIView.as_view(),
backend/people/urls.py:91:    path('employees/<int:pk>/compensation/', EmployeeCompensationView.as_view(),
backend/people/urls.py:93:    path('employees/<int:pk>/correspondence/', EmployeeCorrespondenceListView.as_view(),
backend/people/urls.py:95:    path('employees/<int:pk>/correspondence/<int:corr_pk>/',
backend/people/urls.py:98:    path('employees/<int:pk>/deactivate/', EmployeeDeactivateView.as_view(),
backend/people/urls.py:100:    path('employees/<int:pk>/reactivate/', EmployeeReactivateView.as_view(),
backend/people/urls.py:102:    path('payroll-runs/', PayrollRunListCreateView.as_view(),
backend/people/urls.py:104:    path('payroll-runs/<int:pk>/', PayrollRunDetailView.as_view(),
backend/people/urls.py:106:    path('payslip-lines/summary/', PayslipLineSummaryView.as_view(),
backend/people/urls.py:108:    path('payslip-lines/gosi-summary/', PayslipLineGosiSummaryView.as_view(),
backend/people/urls.py:110:    path('payslip-lines/', PayslipLineListView.as_view(),
backend/people/urls.py:112:    path('positions/', PositionListCreateView.as_view(),
backend/people/urls.py:114:    path('positions/<int:pk>/', PositionDetailView.as_view(),
backend/people/urls.py:116:    path('leave-policies/', LeavePolicyListCreateView.as_view(),
backend/people/urls.py:118:    path('leave-policies/<int:pk>/propagate/', LeavePolicyPropagateView.as_view(),
backend/people/urls.py:120:    path('leave-policies/<int:pk>/versions/', LeavePolicyVersionListView.as_view(),
backend/people/urls.py:122:    path('leave-policies/<int:pk>/versions/<int:version_pk>/', LeavePolicyVersionDetailView.as_view(),
backend/people/urls.py:124:    path('leave-policies/<int:pk>/', LeavePolicyDetailView.as_view(),
backend/people/urls.py:126:    path('leave-entitlements/summary/', LeaveEntitlementSummaryView.as_view(),
backend/people/urls.py:128:    path('leave-entitlements/', LeaveEntitlementListCreateView.as_view(),
backend/people/urls.py:130:    path('leave-entitlements/<int:pk>/', LeaveEntitlementDetailView.as_view(),
backend/people/urls.py:132:    path('leave-records/presence/', LeavePresenceView.as_view(),
backend/people/urls.py:134:    path('leave-records/', LeaveRecordListCreateView.as_view(),
backend/people/urls.py:136:    path('leave-records/<int:pk>/', LeaveRecordDetailView.as_view(),
backend/people/urls.py:138:    path('benefit-types/', BenefitTypeListCreateView.as_view(),
backend/people/urls.py:140:    path('benefit-types/<int:pk>/', BenefitTypeDetailView.as_view(),
backend/people/urls.py:142:    path('benefits/', EmployeeBenefitListCreateView.as_view(),
backend/people/urls.py:144:    path('benefits/<int:pk>/', EmployeeBenefitDetailView.as_view(),
backend/people/urls.py:146:    path('loans/summary/', LoanBookSummaryView.as_view(),
backend/people/urls.py:148:    path('loans/', LoanListCreateView.as_view(),
backend/people/urls.py:150:    path('loans/<int:pk>/', LoanDetailView.as_view(),
backend/people/urls.py:152:    path('loan-installments/', LoanInstallmentListCreateView.as_view(),
backend/people/urls.py:154:    path('loan-installments/<int:pk>/', LoanInstallmentDetailView.as_view(),
backend/people/urls.py:156:    path('attendance/', AttendanceRecordListCreateView.as_view(),
backend/people/urls.py:158:    path('attendance/<int:pk>/', AttendanceRecordDetailView.as_view(),
backend/people/urls.py:160:    path('attendance-permissions/', AttendancePermissionListCreateView.as_view(),
backend/people/urls.py:162:    path('attendance-permissions/<int:pk>/',
backend/people/urls.py:165:    path('certifications/summary/', CertificationSummaryView.as_view(),
backend/people/urls.py:167:    path('certifications/', CertificationListCreateView.as_view(),
backend/people/urls.py:169:    path('certifications/<int:pk>/', CertificationDetailView.as_view(),
backend/people/urls.py:171:    path('rotation-schedules/', RotationScheduleListCreateView.as_view(),
backend/people/urls.py:173:    path('rotation-schedules/<int:pk>/', RotationScheduleDetailView.as_view(),
backend/people/urls.py:175:    path('payroll-runs/<int:pk>/compute/', PayrollRunComputeView.as_view(),
backend/people/urls.py:177:    path('payroll-runs/<int:pk>/validate/', PayrollRunValidateView.as_view(),
backend/people/urls.py:179:    path('payroll-runs/<int:pk>/commit/', PayrollRunCommitView.as_view(),
backend/people/urls.py:181:    path('payroll-runs/<int:pk>/validations/',
backend/people/urls.py:184:    path('payroll-runs/<int:pk>/wps/', PayrollRunWPSExportView.as_view(),
backend/people/urls.py:186:    path('payroll-runs/<int:pk>/wps/generate/', PayrollRunWpsGenerateView.as_view(),
backend/people/urls.py:188:    path('payroll-runs/<int:pk>/wps/validate/', PayrollRunWpsValidateFilingView.as_view(),
backend/people/urls.py:190:    path('payroll-runs/<int:pk>/wps/submit/', PayrollRunWpsSubmitFilingView.as_view(),
backend/people/urls.py:192:    path('payroll-runs/<int:pk>/wps/filing/', PayrollRunWpsFilingDetailView.as_view(),
backend/people/urls.py:194:    path('employees/<int:pk>/timeline/', EmployeeTimelineView.as_view(),
backend/people/urls.py:196:    path('positions/<int:pk>/timeline/', PositionTimelineView.as_view(),
backend/people/urls.py:198:    path('org-units/<int:pk>/timeline/', OrgUnitTimelineView.as_view(),
backend/people/urls.py:200:    path('events/', PersonnelEventListView.as_view(),
backend/people/urls.py:203:    path('compensation-components/', CompensationComponentListView.as_view(),
backend/people/urls.py:205:    path('compensation-components/<int:pk>/', CompensationComponentDetailView.as_view(),
backend/people/urls.py:207:    path('compensation-plan/', CompensationPlanListView.as_view(),
backend/people/urls.py:209:    path('compensation-plan/<int:pk>/', CompensationPlanDetailView.as_view(),
backend/people/urls.py:211:    path('employees/<int:employee_pk>/compensation/<int:line_pk>/verify/',
backend/gradevance/urls.py:14:    path("me/", include("gradevance.me_urls")),
backend/gradevance/urls.py:15:    path("summary/", views.SummaryView.as_view(), name="gradevance-summary"),
backend/gradevance/urls.py:16:    path("profiles/", views.ProfileCatalogView.as_view(), name="gradevance-profiles"),
backend/gradevance/urls.py:17:    path(
backend/gradevance/urls.py:22:    path("knowledge-bases/", views.KnowledgeBaseListView.as_view(), name="gradevance-kbs"),
backend/gradevance/urls.py:23:    path("examples/", views.DemoExamplesView.as_view(), name="gradevance-examples"),
backend/gradevance/urls.py:24:    path("courses/", views.CourseListCreateView.as_view(), name="gradevance-courses"),
backend/gradevance/urls.py:25:    path("courses/<uuid:course_id>/", views.CourseDetailView.as_view(), name="gradevance-course-detail"),
backend/gradevance/urls.py:26:    path(
backend/gradevance/urls.py:31:    path(
backend/gradevance/urls.py:36:    path("assignments/", views.AssignmentListCreateView.as_view(), name="gradevance-assignments"),
backend/gradevance/urls.py:37:    path(
backend/gradevance/urls.py:42:    path(
backend/gradevance/urls.py:47:    path("submissions/", views.SubmissionListCreateView.as_view(), name="gradevance-submissions"),
backend/gradevance/urls.py:48:    path(
backend/gradevance/urls.py:53:    path(
backend/gradevance/urls.py:58:    path("runs/", views.RunListView.as_view(), name="gradevance-runs"),
backend/gradevance/urls.py:59:    path("runs/<uuid:run_id>/", views.RunDetailView.as_view(), name="gradevance-run-detail"),
backend/gradevance/urls.py:60:    path("runs/<uuid:run_id>/edits/", views.ExpertEditCreateView.as_view(), name="gradevance-edits"),
backend/gradevance/urls.py:61:    path("runs/<uuid:run_id>/release/", views.RunReleaseView.as_view(), name="gradevance-release"),
backend/gradevance/urls.py:62:    path(
backend/gradevance/urls.py:67:    path("review-queue/", views.ReviewQueueView.as_view(), name="gradevance-review-queue"),
backend/gradevance/urls.py:68:    path("appeals/", views.AppealListView.as_view(), name="gradevance-appeals"),
backend/gradevance/urls.py:69:    path(
backend/gradevance/urls.py:74:    path("qa/summary/", views.QaSummaryView.as_view(), name="gradevance-qa-summary"),
backend/gradevance/urls.py:75:    path("proposals/", views.ProposalListView.as_view(), name="gradevance-proposals"),
backend/gradevance/urls.py:76:    path(
backend/gradevance/urls.py:81:    path(
backend/gradevance/urls.py:86:    path(
backend/gradevance/urls.py:91:    path("publish-gate/", views.PublishGatePreviewView.as_view(), name="gradevance-publish-gate"),
backend/gradevance/urls.py:92:    path("calibration/", views.CalibrationPreviewView.as_view(), name="gradevance-calibration"),
backend/gradevance/urls.py:93:    path(
backend/gradevance/urls.py:98:    path(
backend/gradevance/urls.py:103:    path(
backend/gradevance/urls.py:108:    path(
backend/gradevance/urls.py:113:    path(
backend/gradevance/urls.py:118:    path("lti/status/", LtiStatusView.as_view(), name="gradevance-lti-status"),
backend/gradevance/urls.py:119:    path("lti/config/", LtiConfigView.as_view(), name="gradevance-lti-config"),
backend/gradevance/urls.py:120:    path("lti/oidc/login/", LtiOidcLoginView.as_view(), name="gradevance-lti-oidc-login"),
backend/gradevance/urls.py:121:    path("lti/oidc/launch/", LtiOidcLaunchView.as_view(), name="gradevance-lti-oidc-launch"),
backend/gradevance/urls.py:122:    path("lti/deep-link/preview/", DeepLinkPreviewView.as_view(), name="gradevance-lti-deeplink"),
backend/gradevance/urls.py:123:    path("lti/nrps/preview/", NrpsRosterPreviewView.as_view(), name="gradevance-lti-nrps"),
backend/gradevance/urls.py:124:    path("lti/jwks/", ToolJwksView.as_view(), name="gradevance-lti-jwks"),
backend/gradevance/urls.py:125:    path("lti/tool-config/", LtiToolConfigView.as_view(), name="gradevance-lti-tool-config"),
backend/gradevance/urls.py:126:    path("accessibility/", views.AccessibilityChecklistView.as_view(), name="gradevance-a11y"),
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
backend/inbound/urls.py:6:router.register(r'batches', InboundBatchViewSet, basename='inbound-batch')
backend/inbound/urls.py:7:router.register(r'cartridges', InboundCartridgeViewSet, basename='inbound-cartridge')
backend/inbound/urls.py:8:router.register(r'templates', InboundTemplateViewSet, basename='inbound-template')
backend/excellence/urls.py:19:    path('overview/', OverviewView.as_view(), name='excellence-overview'),
backend/excellence/urls.py:20:    path('control-room/', ControlRoomView.as_view(), name='excellence-control-room'),
backend/excellence/urls.py:21:    path('standard/', StandardView.as_view(), name='excellence-standard'),
backend/excellence/urls.py:22:    path('apps/<str:app_id>/', AppView.as_view(), name='excellence-app'),
backend/excellence/urls.py:23:    path('ladder/', LadderView.as_view(), name='excellence-ladder'),
backend/excellence/urls.py:24:    path('subjects/<str:subject_id>/', SubjectView.as_view(), name='excellence-subject'),
backend/excellence/urls.py:25:    path('stream/', StreamView.as_view(), name='excellence-stream'),
backend/excellence/urls.py:26:    path('runs/', RunListCreateView.as_view(), name='excellence-runs'),
backend/excellence/urls.py:27:    path('initiatives/', InitiativeListCreateView.as_view(), name='excellence-initiatives'),
backend/excellence/urls.py:28:    path('initiatives/<int:initiative_id>/close/', InitiativeCloseView.as_view(), name='excellence-initiative-close'),
backend/excellence/urls.py:29:    path('exemptions/', ExemptionListCreateView.as_view(), name='excellence-exemptions'),
backend/excellence/urls.py:30:    path('exemptions/<int:exemption_id>/', ExemptionDeleteView.as_view(), name='excellence-exemption-delete'),
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
backend/correspondence/urls.py:16:    path('history/', CorrespondenceViewSet.as_view({'get': 'history'}),
backend/correspondence/urls.py:18:    path('<int:pk>/', CorrespondenceViewSet.as_view({'get': 'retrieve'}),
backend/correspondence/urls.py:20:    path('<int:pk>/approve/', CorrespondenceViewSet.as_view({'post': 'approve'}),
backend/correspondence/urls.py:22:    path('<int:pk>/acknowledge/', CorrespondenceViewSet.as_view({'post': 'acknowledge'}),
backend/correspondence/urls.py:24:    path('<int:pk>/review/', CorrespondenceViewSet.as_view({'post': 'review'}),
backend/correspondence/urls.py:26:    path('<int:pk>/reject/', CorrespondenceViewSet.as_view({'post': 'reject'}),
backend/correspondence/urls.py:28:    path('<int:pk>/send-back/', CorrespondenceViewSet.as_view({'post': 'send_back'}),
backend/correspondence/urls.py:30:    path('<int:pk>/cancel/', CorrespondenceViewSet.as_view({'post': 'cancel'}),
backend/correspondence/urls.py:32:    path('<int:pk>/edit/', CorrespondenceViewSet.as_view({'post': 'edit'}),
backend/correspondence/urls.py:34:    path('<int:pk>/resubmit/', CorrespondenceViewSet.as_view({'post': 'resubmit'}),
backend/correspondence/urls.py:36:    path('<int:pk>/archive/', CorrespondenceViewSet.as_view({'post': 'archive'}),
backend/correspondence/urls.py:38:    path('<int:pk>/void/', CorrespondenceViewSet.as_view({'post': 'void'}),
backend/correspondence/urls.py:40:    path('<int:pk>/reopen/', CorrespondenceViewSet.as_view({'post': 'reopen'}),
backend/correspondence/urls.py:42:    path('notifications/', NotificationViewSet.as_view({'get': 'list'}),
backend/correspondence/urls.py:44:    path('notifications/read-all/', NotificationViewSet.as_view({'post': 'read_all'}),
backend/correspondence/urls.py:46:    path('notifications/<int:pk>/read/', NotificationViewSet.as_view({'post': 'read'}),
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
backend/accounts/views.py:324:    @action(detail=True, methods=['get'])
backend/accounts/views.py-325-    def members(self, request, pk=None):
backend/accounts/views.py:350:    @action(detail=True, methods=['get'])
backend/accounts/views.py-351-    def scoped_assignments(self, request, pk=None):
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
backend/mdm/views.py:667:    @action(detail=True, methods=['get'])
backend/mdm/views.py-668-    def tree(self, request, pk=None):
backend/mdm/views.py:687:    @action(detail=False, methods=['get'], url_path='tree')
backend/mdm/views.py-688-    def list_tree(self, request):
backend/mdm/views.py:727:    @action(detail=True, methods=['get'])
backend/mdm/views.py-728-    def ancestors(self, request, pk=None):
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
backend/inbound/views.py:47:    @action(detail=False, methods=['get'])
backend/inbound/views.py-48-    def targets(self, request):
backend/inbound/views.py:62:    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
backend/inbound/views.py-63-    def file(self, request, pk=None):
backend/inbound/views.py:75:    @action(detail=True, methods=['put'])
backend/inbound/views.py-76-    def mapping(self, request, pk=None):
backend/inbound/views.py:84:    @action(detail=True, methods=['post'])
backend/inbound/views.py-85-    def smoke(self, request, pk=None):
backend/inbound/views.py:93:    @action(detail=True, methods=['get'])
backend/inbound/views.py-94-    def rejects(self, request, pk=None):
backend/inbound/views.py:106:    @action(detail=True, methods=['post'])
backend/inbound/views.py-107-    def commit(self, request, pk=None):
backend/dataschema/views.py:529:    @action(detail=False, methods=['post'], url_path='bulk-import')
backend/dataschema/views.py-530-    def bulk_import(self, request):
backend/dataschema/views.py:590:    @action(detail=False, methods=['get'], url_path='download-template')
backend/dataschema/views.py-591-    def download_template(self, request):
backend/ai/catalog_api.py:249:    @action(detail=False, methods=["get"], url_path="topology")
backend/ai/catalog_api.py-250-    def topology(self, request):
backend/ai/catalog_api.py:257:    @action(detail=False, methods=["get"], url_path="skills")
backend/ai/catalog_api.py-258-    def skills(self, request):
backend/ai/catalog_api.py:265:    @action(detail=False, methods=["get"], url_path="capabilities")
backend/ai/catalog_api.py-266-    def capabilities(self, request):
backend/ai/catalog_api.py:276:    @action(detail=False, methods=["get"], url_path="index")
backend/ai/catalog_api.py-277-    def federated_index(self, request):
backend/ai/plans_api.py:232:    @action(
backend/ai/plans_api.py:258:    @action(
backend/ai/plans_api.py:314:    @action(
backend/ai/plans_api.py:329:    @action(
backend/ai/plans_api.py:348:    @action(
backend/ai/plans_api.py:384:    @action(detail=True, methods=["post"], url_path="approve", url_name="approve-plan")
backend/ai/plans_api.py-385-    def approve(self, request, pk=None):
backend/ai/plans_api.py:398:    @action(detail=True, methods=["post"], url_path="decline", url_name="decline-plan")
backend/ai/plans_api.py-399-    def decline(self, request, pk=None):
backend/ai/plans_api.py:424:    @action(detail=True, methods=["post"], url_path="pause", url_name="pause-plan")
backend/ai/plans_api.py-425-    def pause(self, request, pk=None):
backend/ai/plans_api.py:438:    @action(detail=True, methods=["post"], url_path="resume", url_name="resume-plan")
backend/ai/plans_api.py-439-    def resume(self, request, pk=None):
backend/ai/plans_api.py:469:    @action(detail=True, methods=["post"], url_path="fork", url_name="fork-plan")
backend/ai/plans_api.py-470-    def fork(self, request, pk=None):
backend/ai/plans_api.py:480:    @action(detail=True, methods=["post"], url_path="rerun", url_name="rerun-plan")
backend/ai/plans_api.py-481-    def rerun(self, request, pk=None):
backend/ai/plans_api.py:606:    @action(detail=True, methods=["post"], url_path="run", url_name="run-plan")
backend/ai/plans_api.py-607-    def run(self, request, pk=None):
backend/ai/plans_api.py:641:    @action(
backend/ai/plans_api.py:668:    @action(
backend/ai/plans_api.py:714:    @action(
backend/ai/plans_api.py:726:    @action(
backend/ai/plans_api.py:738:    @action(
backend/ai/plans_api.py:750:    @action(
backend/ai/plans_api.py:762:    @action(
backend/ai/plans_api.py:776:    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-plan")
backend/ai/plans_api.py-777-    def stop(self, request, pk=None):
backend/ai/plans_api.py:786:    @action(
backend/ai/plans_api.py:820:    @action(detail=True, methods=["get"], url_path="ledger", url_name="plan-ledger")
backend/ai/plans_api.py-821-    def ledger(self, request, pk=None):
backend/ai/plans_api.py:833:    @action(detail=True, methods=["get"], url_path="qos", url_name="plan-qos")
backend/ai/plans_api.py-834-    def qos(self, request, pk=None):
backend/ai/plans_api.py:851:    @action(detail=True, methods=["get"], url_path="flight", url_name="plan-flight")
backend/ai/plans_api.py-852-    def flight(self, request, pk=None):
backend/ai/plans_api.py:871:    @action(
backend/ai/plans_api.py:886:    @action(
backend/ai/durable_api.py:64:    @action(detail=True, methods=["get"], url_path="timeline",
backend/ai/durable_api.py:97:    @action(detail=True, methods=["post"], url_path="resume",
backend/ai/durable_api.py:114:    @action(detail=True, methods=["post"], url_path="replay",
backend/ai/tests/test_plans.py:1888:    """Keep/Cancel must hit wired paths (not Django 404) — as_view, not @action."""
backend/ai/workspace_api.py:163:    @action(detail=True, methods=["get", "post"], url_path="messages", url_name="send-message")
backend/ai/workspace_api.py-164-    def send_message(self, request, pk=None):
backend/ai/workspace_api.py:168:        register two ``@action`` methods on the same ``url_path`` without one
backend/ai/workspace_api.py:218:    @action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback", url_name="message-feedback")
backend/ai/workspace_api.py-219-    def message_feedback(self, request, pk=None, message_id=None):
backend/ai/workspace_api.py:238:    @action(detail=True, methods=["post"], url_path="messages/stream", url_name="send-message-stream")
backend/ai/workspace_api.py-239-    def send_message_stream(self, request, pk=None):
backend/ai/workspace_api.py:273:    @action(detail=True, methods=["post"], url_path="actions/stream", url_name="run-action-stream")
backend/ai/workspace_api.py-274-    def run_action_stream(self, request, pk=None):
backend/ai/workspace_api.py:312:    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-generation")
backend/ai/workspace_api.py-313-    def stop_generation(self, request, pk=None):
backend/ai/workspace_api.py:327:    @action(
backend/ai/workspace_api.py:348:    @action(
backend/ai/workspace_api.py:399:    @action(
backend/ai/workspace_api.py:432:    @action(detail=True, methods=["post"], url_path="summary", url_name="summarize")
backend/ai/workspace_api.py-433-    def summarize(self, request, pk=None):
backend/ai/workspace_api.py:450:    @action(
backend/ai/workspace_api.py:637:    @action(
backend/ai/workspace_api.py:736:    @action(detail=True, methods=["get", "post"], url_path="subagents", url_name="subagents")
backend/ai/workspace_api.py-737-    def subagents(self, request, pk=None):
backend/ai/workspace_api.py:740:        Combined into a single ``@action`` — two actions sharing ``url_path``
backend/ai/workspace_api.py:754:    @action(detail=True, methods=["get"], url_path=r"subagents/(?P<sub_id>[^/.]+)", url_name="subagent-detail")
backend/ai/workspace_api.py-755-    def subagent_detail(self, request, pk=None, sub_id=None):
backend/ai/workspace_api.py:765:    @action(detail=True, methods=["get"], url_path="export", url_name="export")
backend/ai/workspace_api.py-766-    def export(self, request, pk=None):
backend/ai/workspace_api.py:793:    @action(detail=True, methods=["get"], url_path="suggestions", url_name="suggestions")
backend/ai/workspace_api.py-794-    def suggestions(self, request, pk=None):
backend/ai/workspace_api.py:820:    @action(detail=True, methods=["post"], url_path="resume", url_name="resume")
backend/ai/workspace_api.py-821-    def resume(self, request, pk=None):
backend/ai/workspace_api.py:835:    @action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/accept", url_name="suggestion-accept")
backend/ai/workspace_api.py-836-    def accept_suggestion(self, request, pk=None, suggestion_id=None):
backend/ai/workspace_api.py:849:    @action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/dismiss", url_name="suggestion-dismiss")
backend/ai/workspace_api.py-850-    def dismiss_suggestion(self, request, pk=None, suggestion_id=None):
backend/ai/workspace_api.py:864:    @action(detail=False, methods=["get"], url_path="suggestions", url_name="workspace-suggestions")
backend/ai/workspace_api.py-865-    def workspace_suggestions(self, request):
backend/ai/workspace_api.py:880:    @action(detail=True, methods=["post"], url_path="checkpoint", url_name="checkpoint-conversation")
backend/ai/workspace_api.py-881-    def checkpoint(self, request, pk=None):
backend/ai/workspace_api.py:906:    @action(detail=True, methods=["get"], url_path="checkpoints", url_name="checkpoints")
backend/ai/workspace_api.py-907-    def checkpoints(self, request, pk=None):
backend/ai/workspace_api.py:926:    @action(detail=True, methods=["post"], url_path="restore", url_name="restore-conversation")
backend/ai/workspace_api.py-927-    def restore(self, request, pk=None):
backend/ai/workspace_api.py:951:    @action(detail=True, methods=["post"], url_path="fork", url_name="fork-conversation")
backend/ai/workspace_api.py-952-    def fork(self, request, pk=None):
backend/ai/workspace_api.py:978:    @action(detail=True, methods=["post"], url_path="clear-context", url_name="clear-context")
backend/ai/workspace_api.py-979-    def clear_context(self, request, pk=None):
backend/ai/workspace_api.py:998:    @action(
backend/ai/workspace_api.py:1084:    @action(detail=True, methods=["post"], url_path="share", url_name="artifact-share")
backend/ai/workspace_api.py-1085-    def share(self, request, pk=None):
backend/ai/workspace_api.py:1133:    @action(detail=False, methods=["get"], url_path="shared/(?P<token>[^/.]+)", url_name="artifact-shared")
backend/ai/workspace_api.py-1134-    def shared_snapshot(self, request, token=None):
backend/ai/workspace_api.py:1143:    @action(detail=False, methods=["post"], url_path="job-maps", url_name="create-job-map")
backend/ai/workspace_api.py-1144-    def create_job_map(self, request):
backend/ai/workspace_api.py:1222:    @action(detail=True, methods=["get", "post"], url_path="messages", url_name="send-message")
backend/ai/workspace_api.py-1223-    def send_message(self, request, pk=None):
backend/ai/workspace_api.py:1227:        register two ``@action`` methods on the same ``url_path`` without one
backend/ai/workspace_api.py:1272:    @action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback", url_name="message-feedback")
backend/ai/workspace_api.py-1273-    def message_feedback(self, request, pk=None, message_id=None):
backend/ai/workspace_api.py:1292:    @action(detail=True, methods=["post"], url_path="messages/stream", url_name="send-message-stream")
backend/ai/workspace_api.py-1293-    def send_message_stream(self, request, pk=None):
backend/ai/workspace_api.py:1327:    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-generation")
backend/ai/workspace_api.py-1328-    def stop_generation(self, request, pk=None):
backend/ai/workspace_api.py:1342:    @action(
backend/ai/workspace_api.py:1363:    @action(
backend/ai/workspace_api.py:1394:    @action(detail=True, methods=["post"], url_path="summary", url_name="summarize")
backend/ai/workspace_api.py-1395-    def summarize(self, request, pk=None):
backend/ai/workspace_api.py:1412:    @action(detail=True, methods=["get"], url_path="export", url_name="export")
backend/ai/workspace_api.py-1413-    def export(self, request, pk=None):
backend/correspondence/views.py:310:    @action(detail=False, methods=['get'], url_path='inbox')
backend/correspondence/views.py-311-    def inbox(self, request):
backend/correspondence/views.py:345:    @action(detail=False, methods=['get'], url_path='history')
backend/correspondence/views.py-346-    def history(self, request):
```
