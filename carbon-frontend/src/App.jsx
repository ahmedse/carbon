// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useParams } from "react-router-dom";
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import { Shell } from "./shell/Shell";
import AdminRoute from "./components/AdminRoute";
import TableManagerPage from "./pages/TableManagerPage";
import OrgUnitsPage from "./pages/admin/OrgUnitsPage";
import OrgUnitDetailPage from "./pages/admin/OrgUnitDetailPage";
import AccessControlPage from "./pages/admin/AccessControlPage";
import UsersPage from "./pages/admin/UsersPage";
import GroupsPage from "./pages/admin/GroupsPage";
import RoleRegistryPage from "./pages/admin/RoleRegistryPage";
import RegisteredAppsPage from "./pages/admin/RegisteredAppsPage";
import GovernancePolicyPage from "./pages/admin/GovernancePolicyPage";
import GroupDetailPage from "./pages/admin/GroupDetailPage";
import CatalogRoute from "./components/CatalogRoute";
import DataEntryPage from "./pages/DataEntryPage";
import DataHubHome from "./pages/DataHubHome";
import Help from "./pages/Help";
import Feedback from "./pages/Feedback";
import ModuleLandingPage from "./pages/ModuleLandingPage";
import ScopeInfoPage from "./pages/ScopeInfoPage";
import EmissionsDashboard from "./pages/EmissionsDashboard";
import EmissionsReport from "./pages/EmissionsReport";
import SettingsPage from "./pages/SettingsPage";
import RowDetailPage from "./pages/dataschema/RowDetailPage";
import DomainsPage from "./pages/catalog/DomainsPage";
import GlossaryPage from "./pages/catalog/GlossaryPage";
import MetadataManagementPage from "./pages/catalog/MetadataManagementPage";
import AssetsPage from "./pages/catalog/AssetsPage";
import MDMPage from "./pages/catalog/MDMPage";
import ConnectionsPage from "./pages/catalog/ConnectionsPage";
import ImportExportPage from "./pages/catalog/ImportExportPage";
import CatalogHome from "./pages/catalog/CatalogHome";
import SchemaCatalogPage from "./pages/catalog/SchemaCatalogPage";
import SchemaDetailPage from "./pages/catalog/SchemaDetailPage";
import SchemaManagerPage from "./pages/catalog/SchemaManagerPage";
import DataProductsPage from "./pages/catalog/DataProductsPage";
import DataProductDetailPage from "./pages/catalog/DataProductDetailPage";
import DomainDetailPage from "./pages/catalog/DomainDetailPage";
import TagDetailPage from "./pages/catalog/TagDetailPage";
import AssetDetailPage from "./pages/catalog/AssetDetailPage";
import DQDashboardPage from "./pages/catalog/DQDashboardPage";
import DQRulesPage from "./pages/catalog/DQRulesPage";
import ReferenceSetDetailPage from "./pages/catalog/ReferenceSetDetailPage";
import TagsPage from "./pages/catalog/TagsPage";
import ReferenceDataPage from "./pages/catalog/ReferenceDataPage";
import GovernancePage from "./pages/catalog/GovernancePage";
import DataSourcesDetailPage from "./pages/catalog/DataSourcesDetailPage";
import ExportsDetailPage from "./pages/catalog/ExportsDetailPage";
import ImportsDetailPage from "./pages/catalog/ImportsDetailPage";
import DataOwnerPortalPage from "./pages/data-owner/DataOwnerPortalPage";
import DataOwnerDashboardPage from "./pages/data-owner/DataOwnerDashboardPage";
import DataOwnerAssetsPage from "./pages/data-owner/DataOwnerAssetsPage";
import EmissionFactorsPage from "./pages/emissions/EmissionFactorsPage";
import CalculationRulesPage from "./pages/emissions/CalculationRulesPage";
import GWPReferencePage from "./pages/emissions/GWPReferencePage";
import SBTiTargetsPage from "./pages/carbon/SBTiTargetsPage";
import ReportGeneratorPage from "./pages/emissions/ReportGeneratorPage";
import SavedReportsPage from "./pages/emissions/SavedReportsPage";
import ReportingPeriodsPage from "./pages/emissions/ReportingPeriodsPage";
import CarbonConsolePage from "./pages/carbon/CarbonConsolePage";
import MyDataPage from "./pages/carbon/MyDataPage";
import ModuleWorkspacePage from "./pages/carbon/ModuleWorkspacePage";
import CalculationsPage from "./pages/carbon/CalculationsPage";
import VerificationPage from "./pages/carbon/VerificationPage";
import AuditLogPage from "./pages/admin/AuditLogPage";

import PlatformHome from "./pages/PlatformHome";

// Dashboard components — used by /carbon/* domain app routes only
import AnalyticsDashboard from "./pages/dashboards/AnalyticsDashboard";

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
 * Role-aware landing redirect for non-admin users
 * - Data-only users (no admin role) → redirect to first module
 * - Admin users → PlatformHome (app portal)
 */
function RoleAwareLanding() {
  const { availablePerspectives, context, loading } = useAuth();
  
  if (loading) return <div className="centered">Loading…</div>;

  // Check if user has admin perspective
  const hasAdminPerspective = availablePerspectives?.includes('admin');
  
  // Check if user has data entry perspective but not admin
  const hasDataOnly = availablePerspectives?.includes('data_entry') && !hasAdminPerspective;
  
  // Users with assigned modules get redirected to their first module
  const firstModule = context?.modules?.[0];
  
  // Redirect data-only users to their first module
  if (hasDataOnly && firstModule) {
    return <Navigate to={`/modules/${firstModule.id}`} replace />;
  }
  
  // Non-admin users who have modules: redirect to first module (viewer, analyst, data owner)
  if (!hasAdminPerspective && firstModule) {
    return <Navigate to={`/modules/${firstModule.id}`} replace />;
  }
  
  // No modules assigned - show empty state
  if (!hasAdminPerspective) {
    return (
      <div style={{ padding: '4rem 2rem', textAlign: 'center' }}>
        <h2>No Data Modules Assigned</h2>
        <p style={{ color: '#666' }}>
          Contact your administrator to get access to data entry modules.
        </p>
      </div>
    );
  }
  
  // For admins and others, show PlatformHome app portal
  return <PlatformHome />;
}

export default function App() {
  const RootLayout = Shell;

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
     <BrowserRouter basename={import.meta.env.VITE_BASE}>
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
                
                {/* Legacy Dashboard (keeping for backwards compatibility) */}
                <Route path="/dashboard-legacy" element={<Dashboard />} />
                
                {/* Emissions Calculator Routes */}
                <Route path="/emissions" element={<EmissionsDashboard />} />
                <Route path="/emissions/dashboard" element={<EmissionsDashboard />} />
                <Route path="/emissions/report" element={<EmissionsReport />} />
                
                {/* Carbon App — all routes under /carbon/* namespace */}
                <Route path="/carbon/console" element={<CarbonConsolePage />} />
                <Route path="/carbon/dashboard" element={<EmissionsDashboard />} />
                <Route path="/carbon/analytics" element={<AnalyticsDashboard />} />
                <Route path="/carbon/my-data" element={<MyDataPage />} />
                <Route path="/carbon/my-data/:moduleId" element={<ModuleWorkspacePage />} />
                <Route path="/carbon/my-data/:moduleId/:tableId" element={<DataEntryPage />} />
                <Route path="/carbon/my-data/row/:tableId/:rowId" element={<RowDetailPage />} />
                <Route path="/carbon/calculations" element={<CalculationsPage />} />
                <Route path="/carbon/verification" element={<VerificationPage />} />
                <Route path="/carbon/admin/factors" element={<AdminRoute><EmissionFactorsPage /></AdminRoute>} />
                <Route path="/carbon/admin/rules" element={<AdminRoute><CalculationRulesPage /></AdminRoute>} />
                <Route path="/carbon/admin/gwp" element={<AdminRoute><GWPReferencePage /></AdminRoute>} />
                <Route path="/carbon/admin/targets" element={<AdminRoute><SBTiTargetsPage /></AdminRoute>} />
                <Route path="/carbon/reporting/generate" element={<ReportGeneratorPage />} />
                <Route path="/carbon/reporting/saved" element={<SavedReportsPage />} />
                <Route path="/carbon/reporting/periods" element={<AdminRoute><ReportingPeriodsPage /></AdminRoute>} />
                
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
      </BrowserRouter>
    </LocalizationProvider>
  );
}