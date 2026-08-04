// src/App.jsx
import React, { Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useParams } from "react-router-dom";
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { Box, Typography } from '@mui/material';
import { useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
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
} from "./capabilities";
// ── Lazy-loaded page imports ──────────────────────────────────────────
const TableManagerPage = React.lazy(() => import("./pages/TableManagerPage"));
const OrgUnitsPage = React.lazy(() => import("./pages/admin/OrgUnitsPage"));
const OrgUnitDetailPage = React.lazy(() => import("./pages/admin/OrgUnitDetailPage"));
const AccessControlPage = React.lazy(() => import("./pages/admin/AccessControlPage"));
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
const DomainDetailPage = React.lazy(() => import("./pages/catalog/DomainDetailPage"));
const TagDetailPage = React.lazy(() => import("./pages/catalog/TagDetailPage"));
const AssetDetailPage = React.lazy(() => import("./pages/catalog/AssetDetailPage"));
const DQDashboardPage = React.lazy(() => import("./pages/catalog/DQDashboardPage"));
const DQRulesPage = React.lazy(() => import("./pages/catalog/DQRulesPage"));
const ReferenceSetDetailPage = React.lazy(() => import("./pages/catalog/ReferenceSetDetailPage"));
const ReferenceDataPage = React.lazy(() => import("./pages/catalog/ReferenceDataPage"));
const GovernancePage = React.lazy(() => import("./pages/catalog/GovernancePage"));
const DataSourcesDetailPage = React.lazy(() => import("./pages/catalog/DataSourcesDetailPage"));
const ExportsDetailPage = React.lazy(() => import("./pages/catalog/ExportsDetailPage"));
const ImportsDetailPage = React.lazy(() => import("./pages/catalog/ImportsDetailPage"));
const DataOwnerAssetsPage = React.lazy(() => import("./pages/data-owner/DataOwnerAssetsPage"));
const EmissionFactorsPage = React.lazy(() => import("./pages/emissions/EmissionFactorsPage"));
const CalculationRulesPage = React.lazy(() => import("./pages/emissions/CalculationRulesPage"));
const GWPReferencePage = React.lazy(() => import("./pages/emissions/GWPReferencePage"));
const SBTiTargetsPage = React.lazy(() => import("./pages/carbon/SBTiTargetsPage"));
const ReportGeneratorPage = React.lazy(() => import("./pages/emissions/ReportGeneratorPage"));
const SavedReportsPage = React.lazy(() => import("./pages/emissions/SavedReportsPage"));
const ReportingPeriodsPage = React.lazy(() => import("./pages/emissions/ReportingPeriodsPage"));
const CarbonConsolePage = React.lazy(() => import("./pages/carbon/CarbonConsolePage"));
const MyDataPage = React.lazy(() => import("./pages/carbon/MyDataPage"));
const ModuleWorkspacePage = React.lazy(() => import("./pages/carbon/ModuleWorkspacePage"));
const CalculationsPage = React.lazy(() => import("./pages/carbon/CalculationsPage"));
const VerificationPage = React.lazy(() => import("./pages/carbon/VerificationPage"));
const AuditLogPage = React.lazy(() => import("./pages/admin/AuditLogPage"));
const AnalyticsDashboard = React.lazy(() => import("./pages/dashboards/AnalyticsDashboard"));

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
          <BrowserRouter basename={import.meta.env.VITE_BASE}>
            <Suspense fallback={<LoadingSpinner />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route element={<RequireAuth />}>
                  <Route element={<RequireContext />}>
                    <Route element={<RootLayout />}>
                <Route path="help" element={<Help />} />
                <Route path="feedback" element={<Feedback />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/" element={<RoleAwareLanding />} />
                
                {/* /dashboard redirects to PlatformHome (/) — backward compat */}
                <Route path="/dashboard" element={<Navigate to="/" replace />} />
                
                {/* Legacy dashboards redirect to domain app equivalents */}
                <Route path="/dashboards/executive" element={<Navigate to="/carbon/console" replace />} />
                <Route path="/dashboards/analytics" element={<Navigate to="/carbon/analytics" replace />} />
                <Route path="/dashboards/targets" element={<Navigate to="/carbon/admin/targets" replace />} />
                <Route path="/dashboards/data-quality" element={<Navigate to="/catalog/dq-dashboard" replace />} />
                <Route path="/dashboards/reporting" element={<Navigate to="/carbon/reporting/generate" replace />} />
                
                {/* Legacy Dashboard — removed P10a (blank content, dead page) */}
                
                {/* Emissions Calculator Routes */}
                <Route path="/emissions" element={<EmissionsDashboard />} />
                <Route path="/emissions/report" element={<EmissionsReport />} />
                
                {/* Carbon App — all routes under /carbon/* namespace */}
                <Route path="/carbon/console" element={<CarbonConsolePage />} />
                <Route path="/carbon/dashboard" element={<EmissionsDashboard />} />
                {/* Carbon-domain admin routes — accessible by global admins OR carbon_lead Domain Leads */}
                <Route path="/carbon/analytics" element={<AdminRoute appId="carbon" requiredCapability={CARBON_VIEW_ANALYTICS}><AnalyticsDashboard /></AdminRoute>} />
                <Route path="/carbon/my-data" element={<MyDataPage />} />
                <Route path="/carbon/my-data/:moduleId" element={<ModuleWorkspacePage />} />
                <Route path="/carbon/my-data/:moduleId/:tableId" element={<DataEntryPage />} />
                <Route path="/carbon/my-data/row/:tableId/:rowId" element={<RowDetailPage />} />
                <Route path="/carbon/calculations" element={<AdminRoute appId="carbon" requiredCapability={CARBON_VIEW_CALCULATIONS}><CalculationsPage /></AdminRoute>} />
                <Route path="/carbon/verification" element={<AdminRoute appId="carbon" requiredCapability={CARBON_VIEW_VERIFICATION}><VerificationPage /></AdminRoute>} />
                <Route path="/carbon/admin/factors" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_EMISSION_FACTORS}><EmissionFactorsPage /></AdminRoute>} />
                <Route path="/carbon/admin/rules" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_CALCULATION_RULES}><CalculationRulesPage /></AdminRoute>} />
                <Route path="/carbon/admin/gwp" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_GWP}><GWPReferencePage /></AdminRoute>} />
                <Route path="/carbon/admin/targets" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_SBTI_TARGETS}><SBTiTargetsPage /></AdminRoute>} />
                <Route path="/carbon/reporting/generate" element={<AdminRoute appId="carbon" requiredCapability={CARBON_GENERATE_REPORTS}><ReportGeneratorPage /></AdminRoute>} />
                <Route path="/carbon/reporting/saved" element={<AdminRoute appId="carbon" requiredCapability={CARBON_GENERATE_REPORTS}><SavedReportsPage /></AdminRoute>} />
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
                {/* Admin-only: Schema Admin > Table Manager */}
                <Route
                  path="/schema-admin/table-manager"
                  element={
                    <AdminRoute>
                      <TableManagerPage />
                    </AdminRoute>
                  }
                />
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
                <Route path="/admin/policies" element={<Navigate to="/catalog/policies" replace />} />
                <Route path="/modules/:moduleId" element={<ModuleLandingPage />} />
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
                  <Route path="/catalog/dq-dashboard" element={<DQDashboardPage />} />
                  <Route path="/catalog/dq-rules" element={<DQRulesPage />} />
                  <Route path="/catalog/mdm" element={<MDMPage />} />
                  <Route path="/catalog/mdm/reference-sets/:setId" element={<ReferenceSetDetailPage />} />
                  <Route path="/catalog/connections" element={<ConnectionsPage />} />
                  <Route path="/catalog/importexport" element={<ImportExportPage />} />
                  <Route path="/catalog/tags/:tagId" element={<TagDetailPage />} />
                  <Route path="/catalog/reference-data" element={<ReferenceDataPage />} />
                  <Route path="/catalog/governance" element={<GovernancePage />} />
                  <Route path="/catalog/sources" element={<DataSourcesDetailPage />} />
                  <Route path="/catalog/exports" element={<ExportsDetailPage />} />
                  <Route path="/catalog/imports" element={<ImportsDetailPage />} />
                </Route>

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