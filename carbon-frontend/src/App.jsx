// src/App.jsx
import React, { Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useParams } from "react-router-dom";
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { Box, Typography } from '@mui/material';
import { useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
const ForgotPasswordPage = React.lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = React.lazy(() => import("./pages/ResetPasswordPage"));
const NotFound = React.lazy(() => import("./pages/NotFound"));
import { Shell } from "./shell/Shell";
import AdminRoute from "./components/AdminRoute";
import ErrorBoundary from "./shell/ErrorBoundary";
import { NetworkStatusProvider } from "./components/NetworkStatusBanner";
import { LoadingSpinner } from "./shell/LoadingFallback";
import {
  CARBON_VIEW_CALCULATIONS, CARBON_VIEW_VERIFICATION, CARBON_VIEW_ANALYTICS,
  CARBON_MANAGE_EMISSION_FACTORS, CARBON_MANAGE_CALCULATION_RULES,
  CARBON_MANAGE_GWP, CARBON_MANAGE_SBTI_TARGETS,
  CARBON_GENERATE_REPORTS, CARBON_MANAGE_REPORTING_PERIODS,
  CARBON_MANAGE_INVENTORY_COVERAGE,
  AI_VIEW_CONSOLE,
  DATASCHEMA_MANAGE,
} from "./capabilities";
// ── Lazy-loaded page imports ──────────────────────────────────────────
const OrgUnitsPage = React.lazy(() => import("./pages/admin/OrgUnitsPage"));
const OrgUnitDetailPage = React.lazy(() => import("./pages/admin/OrgUnitDetailPage"));
const AccessControlPage = React.lazy(() => import("./pages/admin/AccessControlPage"));
const FieldPoliciesPanel = React.lazy(() => import("./pages/admin/catalog/FieldPoliciesPanel"));
const UsersPage = React.lazy(() => import("./pages/admin/UsersPage"));
const GroupsPage = React.lazy(() => import("./pages/admin/GroupsPage"));
const RoleRegistryPage = React.lazy(() => import("./pages/admin/RoleRegistryPage"));
const RegisteredAppsPage = React.lazy(() => import("./pages/admin/RegisteredAppsPage"));
const GovernancePolicyPage = React.lazy(() => import("./pages/admin/GovernancePolicyPage"));
const GroupDetailPage = React.lazy(() => import("./pages/admin/GroupDetailPage"));
import CatalogRoute from "./components/CatalogRoute";
const DataEntryPage = React.lazy(() => import("./pages/DataEntryPage"));
const DataHubHome = React.lazy(() => import("./pages/DataHubHome"));
const Help = React.lazy(() => import("./pages/Help"));
const Feedback = React.lazy(() => import("./pages/Feedback"));
const ModuleLandingPage = React.lazy(() => import("./pages/ModuleLandingPage"));
const ScopeInfoPage = React.lazy(() => import("./pages/ScopeInfoPage"));
const EmissionsDashboard = React.lazy(() => import("./pages/EmissionsDashboard"));
const EmissionsReport = React.lazy(() => import("./pages/EmissionsReport"));
const SettingsPage = React.lazy(() => import("./pages/SettingsPage"));
const RowDetailPage = React.lazy(() => import("./pages/dataschema/RowDetailPage"));
const MetadataManagementPage = React.lazy(() => import("./pages/catalog/MetadataManagementPage"));
const AssetsPage = React.lazy(() => import("./pages/catalog/AssetsPage"));
const MDMPage = React.lazy(() => import("./pages/catalog/MDMPage"));
const ConnectionsPage = React.lazy(() => import("./pages/catalog/ConnectionsPage"));
const ImportExportPage = React.lazy(() => import("./pages/catalog/ImportExportPage"));
const CatalogHome = React.lazy(() => import("./pages/catalog/CatalogHome"));
const SchemaDetailPage = React.lazy(() => import("./pages/catalog/SchemaDetailPage"));
const DataProductsPage = React.lazy(() => import("./pages/catalog/DataProductsPage"));
const DataProductDetailPage = React.lazy(() => import("./pages/catalog/DataProductDetailPage"));
const SearchPage = React.lazy(() => import("./pages/catalog/SearchPage"));
const DomainDetailPage = React.lazy(() => import("./pages/catalog/DomainDetailPage"));
const TagDetailPage = React.lazy(() => import("./pages/catalog/TagDetailPage"));
const AssetDetailPage = React.lazy(() => import("./pages/catalog/AssetDetailPage"));
const DQWorkspacePage = React.lazy(() => import("./pages/dq/DQWorkspacePage"));
const RuleDetailPage = React.lazy(() => import("./pages/dq/RuleDetailPage"));
const ReferenceSetDetailPage = React.lazy(() => import("./pages/catalog/ReferenceSetDetailPage"));
const GovernancePage = React.lazy(() => import("./pages/catalog/GovernancePage"));
const DataSourcesDetailPage = React.lazy(() => import("./pages/catalog/DataSourcesDetailPage"));
const ExportsDetailPage = React.lazy(() => import("./pages/catalog/ExportsDetailPage"));
const ImportsDetailPage = React.lazy(() => import("./pages/catalog/ImportsDetailPage"));
const DataOwnerAssetsPage = React.lazy(() => import("./pages/data-owner/DataOwnerAssetsPage"));
const FactorsHubPage = React.lazy(() => import("./pages/emissions/FactorsHubPage"));
const CalculationRulesPage = React.lazy(() => import("./pages/emissions/CalculationRulesPage"));
const SBTiTargetsPage = React.lazy(() => import("./pages/carbon/SBTiTargetsPage"));
const OrganizationalBoundariesPage = React.lazy(() => import("./pages/carbon/OrganizationalBoundariesPage"));
const BaseYearsPage = React.lazy(() => import("./pages/carbon/BaseYearsPage"));
const InventoryCoveragePage = React.lazy(() => import("./pages/carbon/InventoryCoveragePage"));
const ReportingPeriodsPage = React.lazy(() => import("./pages/emissions/ReportingPeriodsPage"));
const CarbonConsolePage = React.lazy(() => import("./pages/carbon/CarbonConsolePage"));
const CarbonDashboardPage = React.lazy(() => import("./pages/carbon/CarbonDashboardPage"));
const AnalyticsDashboard = React.lazy(() => import("./pages/dashboards/AnalyticsDashboard"));
const ChairmanDashboard = React.lazy(() => import("./pages/carbon/ChairmanDashboard"));
const ReportsPage = React.lazy(() => import("./pages/carbon/ReportsPage"));
const MyDataPage = React.lazy(() => import("./pages/carbon/MyDataPage"));
const ModuleWorkspacePage = React.lazy(() => import("./pages/carbon/ModuleWorkspacePage"));
const CalculationsPage = React.lazy(() => import("./pages/carbon/CalculationsPage"));
const VerificationPage = React.lazy(() => import("./pages/carbon/VerificationPage"));
const AuditLogPage = React.lazy(() => import("./pages/admin/AuditLogPage"));
const LogViewerPage = React.lazy(() => import("./pages/admin/LogViewerPage"));
const PlatformConfigPage = React.lazy(() => import("./pages/admin/PlatformConfigPage"));
const PulseOverviewPage = React.lazy(() => import("./pages/admin/ai/PulseOverviewPage"));
const AIExpertisePanel = React.lazy(() => import("./pages/admin/ai/AIExpertisePanel"));
const AIWorkspacePage = React.lazy(() => import("./pages/admin/ai/AIWorkspacePage"));
const AIConversationsPage = React.lazy(() => import("./pages/admin/ai/AIConversationsPage"));
const KnowledgeBasePanel = React.lazy(() => import("./pages/admin/ai/KnowledgeBasePanel"));
const MemoryPanel = React.lazy(() => import("./pages/admin/ai/MemoryPanel"));
const KnowledgeGraphPanel = React.lazy(() => import("./pages/admin/ai/KnowledgeGraphPanel"));
const AgentsPanel = React.lazy(() => import("./pages/admin/ai/AgentsPanel"));
const McpServersPanel = React.lazy(() => import("./pages/admin/ai/McpServersPanel"));
const ToolsPanel = React.lazy(() => import("./pages/admin/ai/ToolsPanel"));
const SkillsPanel = React.lazy(() => import("./pages/admin/ai/SkillsPanel"));
const SkillLearningPanel = React.lazy(() => import("./pages/admin/ai/SkillLearningPanel"));
const PulseArchetypesPanel = React.lazy(() => import("./pages/admin/ai/PulseArchetypesPanel"));
const BudgetUsagePanel = React.lazy(() => import("./pages/admin/ai/BudgetUsagePanel"));
const EngineSettingsPanel = React.lazy(() => import("./pages/admin/ai/EngineSettingsPanel"));
const PromptsPanel = React.lazy(() => import("./pages/admin/ai/PromptsPanel"));
const FeedbackPanel = React.lazy(() => import("./pages/admin/ai/FeedbackPanel"));
const LearningJobsPanel = React.lazy(() => import("./pages/admin/ai/LearningJobsPanel"));
const LearningFlywheelPanel = React.lazy(() => import("./pages/admin/ai/LearningFlywheelPanel"));
const MonitoringPanel = React.lazy(() => import("./pages/admin/ai/MonitoringPanel"));
const OutputQualityPanel = React.lazy(() => import("./pages/admin/ai/OutputQualityPanel"));
const AuditPanel = React.lazy(() => import("./pages/admin/ai/AuditPanel"));
const WatchesPanel = React.lazy(() => import("./pages/admin/ai/WatchesPanel"));
const AILogsPanel = React.lazy(() => import("./pages/admin/ai/AILogsPanel"));
const AgentTopologyPanel = React.lazy(() => import("./pages/admin/ai/AgentTopologyPanel"));
const RunTimelinePanel = React.lazy(() => import("./pages/admin/ai/RunTimelinePanel"));
const HealthyDashboard = React.lazy(() => import("./apps/healthy/HealthyDashboard"));
const LoadoutSheetPage = React.lazy(() => import("./apps/healthy/LoadoutSheetPage"));
const RepHealthPage = React.lazy(() => import("./apps/healthy/RepHealthPage"));
const ARQueuePage = React.lazy(() => import("./apps/healthy/ARQueuePage"));
const SlowMoversPage = React.lazy(() => import("./apps/healthy/SlowMoversPage"));
const PeopleHome = React.lazy(() => import("./apps/people/PeopleHome"));
const EmployeesPage = React.lazy(() => import("./apps/people/EmployeesPage"));
const EmployeeDetailPage = React.lazy(() => import("./apps/people/EmployeeDetailPage"));
const LeavePage = React.lazy(() => import("./apps/people/LeavePage"));
const PayrollRunsPage = React.lazy(() => import("./apps/people/PayrollRunsPage"));
const PayslipPage = React.lazy(() => import("./apps/people/PayslipPage"));
const BenefitsPage = React.lazy(() => import("./apps/people/BenefitsPage"));
const AttendancePage = React.lazy(() => import("./apps/people/AttendancePage"));
const PeopleConfigPage = React.lazy(() => import("./apps/people/PeopleConfigPage"));
const PositionsPage = React.lazy(() => import("./apps/people/PositionsPage"));
const LoansPage = React.lazy(() => import("./apps/people/LoansPage"));
const CertificationsPage = React.lazy(() => import("./apps/people/CertificationsPage"));
const RotationSchedulesPage = React.lazy(() => import("./apps/people/RotationSchedulesPage"));

import PlatformHome from "./pages/PlatformHome";

/** Redirect legacy /catalog/schemas/:tableId → /catalog/tables/:tableId (preserves id). */
function RedirectSchemaToTable() {
  const { tableId } = useParams();
  return <Navigate to={`/catalog/tables/${tableId}`} replace />;
}

/** Redirect legacy /carbon/data-entry/entry/:moduleName/:tableId → /carbon/my-data/:moduleName/:tableId */
function RedirectLegacyEntry() {
  const { moduleName, tableId } = useParams();
  return <Navigate to={`/carbon/my-data/${moduleName}/${tableId}`} replace />;
}

/** Redirect legacy /carbon/data-entry/row/:tableId/:rowId → /carbon/my-data/row/:tableId/:rowId */
function RedirectLegacyRow() {
  const { tableId, rowId } = useParams();
  return <Navigate to={`/carbon/my-data/row/${tableId}/${rowId}`} replace />;
}

/**
 * Protects all routes that require authentication.
 */
function RequireAuth() {  const { user, loading } = useAuth();
  if (loading) return <div className="centered">Loading authentication...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

/**
 * Protects all routes that require a valid project/module context.
 */
function RequireContext() {
  const { user, loading } = useAuth();
  if (loading) return <div className="centered">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

/**
 * Role-aware landing — everyone with any access sees PlatformHome first.
 * PlatformHome's own hasAppAccess filtering shows only the cards you can use.
 * Fallback: users with literally no permissions see an empty state.
 */
function RoleAwareLanding() {
  const { availablePerspectives, context, loading } = useAuth();
  
  if (loading) return <div className="centered">Loading…</div>;

  const perspectives = availablePerspectives || [];
  const hasModules = (context?.modules?.length || 0) > 0;

  // Anyone with a perspective or modules → PlatformHome (which filters cards)
  if (perspectives.length > 0 || hasModules) {
    return <PlatformHome />;
  }
  
  // Truly empty — no roles, no modules
  return (
    <Box sx={{ p: 8, textAlign: 'center' }}>
      <Typography variant="h6">No Data Products Assigned</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        Contact your administrator to get access to data products.
      </Typography>
    </Box>
  );
}

export default function App() {
  const RootLayout = Shell;

  return (
    <ErrorBoundary>
      <NetworkStatusProvider>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <BrowserRouter basename={import.meta.env.VITE_BASE} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <Suspense fallback={<LoadingSpinner />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password/:uidb64/:token" element={<ResetPasswordPage />} />
                <Route element={<RequireAuth />}>
                  <Route element={<RequireContext />}>
                    <Route element={<RootLayout />}>
                <Route path="help" element={<Help />} />
                <Route path="feedback" element={<Feedback />} />
                <Route path="/settings" element={<SettingsPage />} />
                {/* Settings sub-nav aliases — sidebar links Profile/Preferences to the tabbed Settings page. RULE_22. */}
                <Route path="/settings/profile" element={<Navigate to="/settings" replace />} />
                <Route path="/settings/preferences" element={<Navigate to="/settings" replace />} />
                <Route path="/" element={<RoleAwareLanding />} />
                
                {/* /dashboard redirects to PlatformHome (/) — backward compat */}
                <Route path="/dashboard" element={<Navigate to="/" replace />} />
                
                {/* Legacy dashboards redirect to domain app equivalents */}
                {/* Namespace root redirect — bare /dashboards root. RULE_22. */}
                <Route path="/dashboards" element={<Navigate to="/carbon/dashboard" replace />} />
                <Route path="/dashboards/executive" element={<Navigate to="/carbon/console" replace />} />
                <Route path="/dashboards/analytics" element={<Navigate to="/carbon/analytics" replace />} />
                <Route path="/dashboards/targets" element={<Navigate to="/carbon/admin/targets" replace />} />
                <Route path="/dashboards/data-quality" element={<Navigate to="/dq" replace />} />
                <Route path="/dashboards/reporting" element={<Navigate to="/carbon/reporting/generate" replace />} />
                
                {/* Legacy Dashboard — removed P10a (blank content, dead page) */}
                
                {/* Emissions Calculator Routes */}
                <Route path="/emissions" element={<EmissionsDashboard />} />
                {/* Legacy command-palette alias — /emissions/dashboard resolves to the canonical dashboard */}
                <Route path="/emissions/dashboard" element={<Navigate to="/carbon/dashboard" replace />} />
                <Route path="/emissions/report" element={<EmissionsReport />} />
                
                {/* Carbon App — all routes under /carbon/* namespace */}
                {/* Namespace root redirect — hitting the bare /carbon root (e.g. the
                    /carbon/ deployment mount path) must never 404. RULE_22. */}
                <Route path="/carbon" element={<Navigate to="/carbon/chairman" replace />} />
                <Route path="/carbon/chairman" element={<ChairmanDashboard />} />
                <Route path="/carbon/console" element={<CarbonConsolePage />} />
                <Route path="/carbon/dashboard" element={<CarbonDashboardPage />} />
                <Route path="/carbon/analytics" element={<AdminRoute appId="carbon" requiredCapability={CARBON_VIEW_ANALYTICS}><AnalyticsDashboard /></AdminRoute>} />
                {/* Carbon-domain admin routes — accessible by global admins OR carbon_lead Domain Leads */}
                <Route path="/carbon/my-data" element={<MyDataPage />} />
                <Route path="/carbon/my-data/:moduleId" element={<ModuleWorkspacePage />} />
                <Route path="/carbon/my-data/:moduleId/:tableId" element={<DataEntryPage />} />
                <Route path="/carbon/my-data/row/:tableId/:rowId" element={<RowDetailPage />} />
                <Route path="/carbon/calculations" element={<AdminRoute appId="carbon" requiredCapability={CARBON_VIEW_CALCULATIONS}><CalculationsPage /></AdminRoute>} />
                <Route path="/carbon/verification" element={<AdminRoute appId="carbon" requiredCapability={CARBON_VIEW_VERIFICATION}><VerificationPage /></AdminRoute>} />
                <Route path="/carbon/admin/factors" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_EMISSION_FACTORS}><FactorsHubPage /></AdminRoute>} />
                <Route path="/carbon/admin/rules" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_CALCULATION_RULES}><CalculationRulesPage /></AdminRoute>} />
                <Route path="/carbon/admin/gwp" element={<Navigate to="/carbon/admin/factors" replace />} />
                <Route path="/carbon/admin/targets" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_SBTI_TARGETS}><SBTiTargetsPage /></AdminRoute>} />
                <Route path="/carbon/admin/boundaries" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_REPORTING_PERIODS}><OrganizationalBoundariesPage /></AdminRoute>} />
                <Route path="/carbon/admin/base-years" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_REPORTING_PERIODS}><BaseYearsPage /></AdminRoute>} />
                <Route path="/carbon/admin/inventory-coverage" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_INVENTORY_COVERAGE}><InventoryCoveragePage /></AdminRoute>} />
                <Route path="/carbon/reporting" element={<AdminRoute appId="carbon" requiredCapability={CARBON_GENERATE_REPORTS}><ReportsPage /></AdminRoute>} />
                <Route path="/carbon/reporting/generate" element={<Navigate to="/carbon/reporting" replace />} />
                <Route path="/carbon/reporting/saved" element={<Navigate to="/carbon/reporting" replace />} />
                <Route path="/carbon/reporting/periods" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_REPORTING_PERIODS}><ReportingPeriodsPage /></AdminRoute>} />
                
                {/* Carbon App — Data Owner Routes (namespace: /carbon/owner/*) */}
                <Route path="/carbon/owner/assets" element={<DataOwnerAssetsPage />} />
                {/* Legacy redirects — old paths redirect to unified My Data page */}
                <Route path="/carbon/data-entry" element={<Navigate to="/carbon/my-data" replace />} />
                <Route path="/carbon/data-entry/entry/:moduleName/:tableId" element={<RedirectLegacyEntry />} />
                <Route path="/carbon/data-entry/row/:tableId/:rowId" element={<RedirectLegacyRow />} />
                <Route path="/carbon/owner/portal" element={<Navigate to="/carbon/console" replace />} />
                <Route path="/carbon/owner/dashboard" element={<Navigate to="/carbon/console" replace />} />
                <Route path="/data-owner" element={<Navigate to="/carbon/console" replace />} />
                <Route path="/data-owner/dashboard" element={<Navigate to="/carbon/console" replace />} />
                <Route path="/data-owner/assets" element={<Navigate to="/carbon/owner/assets" replace />} />
                <Route path="/data-owner/reports/generate" element={<Navigate to="/carbon/reporting/generate" replace />} />
                {/* Apps namespace — Healthy Foods Factory domain app */}
                {/* Namespace root redirect — bare /apps root. RULE_22. */}
                <Route path="/apps" element={<Navigate to="/apps/healthy" replace />} />
                <Route path="/apps/healthy" element={<HealthyDashboard />} />
                <Route path="/apps/healthy/loadout" element={<LoadoutSheetPage />} />
                <Route path="/apps/healthy/reps" element={<RepHealthPage />} />
                <Route path="/apps/healthy/collections" element={<ARQueuePage />} />
                <Route path="/apps/healthy/inventory" element={<SlowMoversPage />} />
                {/* People app — Nibras HR & payroll. Bare namespace root resolves to PeopleHome. RULE_22. */}
                <Route path="/people" element={<PeopleHome />} />
                <Route path="/people/positions" element={<PositionsPage />} />
                <Route path="/people/employees" element={<EmployeesPage />} />
                <Route path="/people/employees/:employeeId" element={<EmployeeDetailPage />} />
                <Route path="/people/leave" element={<LeavePage />} />
                <Route path="/people/payroll" element={<PayrollRunsPage />} />
                <Route path="/people/payslip" element={<PayslipPage />} />
                <Route path="/people/benefits" element={<BenefitsPage />} />
                <Route path="/people/attendance" element={<AttendancePage />} />
                <Route path="/people/config" element={<PeopleConfigPage />} />
                <Route path="/people/loans" element={<LoansPage />} />
                <Route path="/people/certifications" element={<CertificationsPage />} />
                <Route path="/people/rotation" element={<RotationSchedulesPage />} />
                {/* Schema Manager decommissioned — schema authoring lives in Data Products (SchemaDetailPage). */}
                {/* Namespace root redirect — bare /schema-admin root. RULE_22. */}
                <Route path="/schema-admin" element={<Navigate to="/catalog/products" replace />} />
                <Route path="/schema-admin/*" element={<Navigate to="/catalog/products" replace />} />
                {/* Namespace root redirect — the "Admin" breadcrumb parent links here. RULE_22. */}
                <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
                <Route
                  path="/admin/org-units"
                  element={
                    <AdminRoute>
                      <OrgUnitsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/org-units/:orgUnitId"
                  element={
                    <AdminRoute>
                      <OrgUnitDetailPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/access"
                  element={
                    <AdminRoute>
                      <AccessControlPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/users"
                  element={
                    <AdminRoute>
                      <UsersPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/groups"
                  element={
                    <AdminRoute>
                      <GroupsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/groups/:groupId"
                  element={
                    <AdminRoute>
                      <GroupDetailPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/role-matrix"
                  element={
                    <AdminRoute>
                      <RoleRegistryPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/apps"
                  element={
                    <AdminRoute>
                      <RegisteredAppsPage />
                    </AdminRoute>
                  }
                />
                <Route path="/admin/audit" element={<AdminRoute><AuditLogPage /></AdminRoute>} />
                <Route
                  path="/admin/catalog/field-policies"
                  element={
                    <AdminRoute requiredCapability={DATASCHEMA_MANAGE}>
                      <FieldPoliciesPanel />
                    </AdminRoute>
                  }
                />
                <Route path="/admin/logs" element={<AdminRoute><LogViewerPage /></AdminRoute>} />
                <Route path="/admin/config" element={<AdminRoute><PlatformConfigPage /></AdminRoute>} />
                <Route path="/admin/ai" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><PulseOverviewPage /></AdminRoute>} />
                <Route path="/admin/ai/expertise" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><AIExpertisePanel /></AdminRoute>} />
                <Route path="/admin/ai/workspace" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><AIWorkspacePage /></AdminRoute>} />
                <Route path="/admin/ai/conversations" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><AIConversationsPage /></AdminRoute>} />
                <Route path="/admin/ai/knowledge" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><KnowledgeBasePanel /></AdminRoute>} />
                <Route path="/admin/ai/memory" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><MemoryPanel /></AdminRoute>} />
                <Route path="/admin/ai/graph" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><KnowledgeGraphPanel /></AdminRoute>} />
                <Route path="/admin/ai/agents" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><AgentsPanel /></AdminRoute>} />
                <Route path="/admin/ai/mcp" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><McpServersPanel /></AdminRoute>} />
                <Route path="/admin/ai/tools" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><ToolsPanel /></AdminRoute>} />
                <Route path="/admin/ai/skills" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><SkillsPanel /></AdminRoute>} />
                <Route path="/admin/ai/archetypes" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><PulseArchetypesPanel /></AdminRoute>} />
                <Route path="/admin/ai/budget-usage" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><BudgetUsagePanel /></AdminRoute>} />
                <Route path="/admin/ai/engine-settings" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><EngineSettingsPanel /></AdminRoute>} />
                <Route path="/admin/ai/prompts" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><PromptsPanel /></AdminRoute>} />
                <Route path="/admin/ai/feedback" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><FeedbackPanel /></AdminRoute>} />
                <Route path="/admin/ai/learning" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><LearningJobsPanel /></AdminRoute>} />
                <Route path="/admin/ai/learning-flywheel" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><LearningFlywheelPanel /></AdminRoute>} />
                <Route path="/admin/ai/skill-learning" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><SkillLearningPanel /></AdminRoute>} />
                <Route path="/admin/ai/monitoring" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><MonitoringPanel /></AdminRoute>} />
                <Route path="/admin/ai/output-quality" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><OutputQualityPanel /></AdminRoute>} />
                <Route path="/admin/ai/audit" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><AuditPanel /></AdminRoute>} />
                <Route path="/admin/ai/watches" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><WatchesPanel /></AdminRoute>} />
                <Route path="/admin/ai/logs" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><AILogsPanel /></AdminRoute>} />
                <Route path="/admin/ai/topology" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><AgentTopologyPanel /></AdminRoute>} />
                <Route path="/admin/ai/runs" element={<AdminRoute requiredCapability={AI_VIEW_CONSOLE}><RunTimelinePanel /></AdminRoute>} />
                <Route path="/admin/policies" element={<Navigate to="/catalog/policies" replace />} />
                {/* Namespace root redirects — bare /modules and /scopes roots. RULE_22. */}
                <Route path="/modules" element={<Navigate to="/carbon/my-data" replace />} />
                <Route path="/modules/:moduleId" element={<ModuleLandingPage />} />
                <Route path="/scopes" element={<Navigate to="/carbon/console" replace />} />
                 <Route path="/scopes/:scopeId" element={<ScopeInfoPage />} />
                {/* Dataschema legacy routes */}
                <Route path="/dataschema" element={<DataHubHome />} />
                <Route path="/dataschema/entry/:moduleId/:tableId" element={<DataEntryPage />} />
                <Route path="/dataschema/row/:tableId/:rowId" element={<RowDetailPage />} />

                {/* Catalog Studio Routes */}
                <Route element={<CatalogRoute />}>
                  <Route path="/catalog" element={<CatalogHome />} />
                  {/* Data Products (Modules) → Tables → table workbench */}
                  <Route path="/catalog/products" element={<DataProductsPage />} />
                  <Route path="/catalog/products/:moduleId" element={<DataProductDetailPage />} />
                  <Route path="/catalog/policies" element={
                    <AdminRoute>
                      <GovernancePolicyPage />
                    </AdminRoute>
                  } />
                  <Route path="/catalog/search" element={<SearchPage />} />
                  <Route path="/catalog/tables/:tableId" element={<SchemaDetailPage />} />
                  {/* Legacy redirects */}
                  <Route path="/catalog/schemas" element={<Navigate to="/catalog/products" replace />} />
                  <Route path="/catalog/schemas/:tableId" element={<RedirectSchemaToTable />} />
                  <Route path="/catalog/schema-manager" element={<Navigate to="/catalog/products" replace />} />
                  {/* Consolidated metadata management */}
                  <Route path="/catalog/metadata" element={<MetadataManagementPage />} />
                  {/* Redirect old separate pages to consolidated metadata page */}
                  <Route path="/catalog/domains" element={<Navigate to="/catalog/metadata#domains" replace />} />
                  <Route path="/catalog/glossary" element={<Navigate to="/catalog/metadata#glossary" replace />} />
                  <Route path="/catalog/tags" element={<Navigate to="/catalog/metadata#tags" replace />} />
                  {/* Keep detail pages for now */}
                  <Route path="/catalog/domains/:domainId" element={<DomainDetailPage />} />
                  <Route path="/catalog/assets" element={<AssetsPage />} />
                  <Route path="/catalog/assets/:assetId" element={<AssetDetailPage />} />
                  <Route path="/catalog/dq" element={<Navigate to="/dq" replace />} />
                  <Route path="/catalog/dq-dashboard" element={<Navigate to="/dq" replace />} />
                  <Route path="/catalog/dq-rules" element={<Navigate to="/dq" replace />} />
                  <Route path="/catalog/mdm" element={<MDMPage />} />
                  <Route path="/catalog/mdm/reference-sets/:setId" element={<ReferenceSetDetailPage />} />
                  <Route path="/catalog/connections" element={<ConnectionsPage />} />
                  <Route path="/catalog/importexport" element={<ImportExportPage />} />
                  <Route path="/catalog/tags/:tagId" element={<TagDetailPage />} />
                  {/* Legacy redirect: Reference Data was merged into the Master Data page */}
                  <Route path="/catalog/reference-data" element={<Navigate to="/catalog/mdm" replace />} />
                  <Route path="/catalog/governance" element={<GovernancePage />} />
                  <Route path="/catalog/sources" element={<DataSourcesDetailPage />} />
                  <Route path="/catalog/exports" element={<ExportsDetailPage />} />
                  <Route path="/catalog/imports" element={<ImportsDetailPage />} />
                </Route>

                {/* DQ Workspace — outside CatalogRoute: DQ has its own capability gates (dq:view / dq:manage_rules) */}
                <Route path="/dq" element={<DQWorkspacePage />} />
                <Route path="/dq/rules/:id" element={<RuleDetailPage />} />
                <Route path="/dq/rules/:id/results" element={<RuleDetailPage />} />

                <Route path="*" element={<NotFound />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </LocalizationProvider>
      </NetworkStatusProvider>
    </ErrorBoundary>
  );
}