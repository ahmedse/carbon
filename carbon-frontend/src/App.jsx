// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
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
import AccessControlPage from "./pages/admin/AccessControlPage";
import UsersPage from "./pages/admin/UsersPage";
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
import AssetsPage from "./pages/catalog/AssetsPage";
import MDMPage from "./pages/catalog/MDMPage";
import ConnectionsPage from "./pages/catalog/ConnectionsPage";
import ImportExportPage from "./pages/catalog/ImportExportPage";
import CatalogHome from "./pages/catalog/CatalogHome";
import SchemaCatalogPage from "./pages/catalog/SchemaCatalogPage";
import SchemaDetailPage from "./pages/catalog/SchemaDetailPage";
import SchemaManagerPage from "./pages/catalog/SchemaManagerPage";
import TagsPage from "./pages/catalog/TagsPage";
import ReferenceDataPage from "./pages/catalog/ReferenceDataPage";
import GovernancePage from "./pages/catalog/GovernancePage";
import DataSourcesDetailPage from "./pages/catalog/DataSourcesDetailPage";
import ExportsDetailPage from "./pages/catalog/ExportsDetailPage";
import ImportsDetailPage from "./pages/catalog/ImportsDetailPage";

// New Dashboard Architecture
import {
  ExecutiveSummary,
  AnalyticsDashboard,
  TargetsDashboard,
  DataQualityDashboard,
  ReportingDashboard,
} from "./pages/dashboards";

/**
 * Protects all routes that require authentication.
 */
function RequireAuth() {
  const { user, loading } = useAuth();
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
 * - Admin users → stay at ExecutiveSummary dashboard
 */
function RoleAwareLanding() {
  const { availablePerspectives, context, loading } = useAuth();
  
  if (loading) return <div className="centered">Loading…</div>;

  // Check if user has admin perspective
  const hasAdminPerspective = availablePerspectives?.includes('admin');
  
  // Check if user has data entry perspective but not admin
  const hasDataOnly = availablePerspectives?.includes('data_entry') && !hasAdminPerspective;
  
  // Redirect data-only users to their first module
  if (hasDataOnly) {
    const firstModule = context?.modules?.[0];
    if (firstModule) {
      return <Navigate to={`/modules/${firstModule.id}`} replace />;
    }
    // No modules assigned - show empty state
    return (
      <div style={{ padding: '4rem 2rem', textAlign: 'center' }}>
        <h2>No Data Modules Assigned</h2>
        <p style={{ color: '#666' }}>
          Contact your administrator to get access to data entry modules.
        </p>
      </div>
    );
  }
  
  // For admins and others, show dashboard
  return <ExecutiveSummary />;
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
                <Route path="/dashboard" element={<ExecutiveSummary />} />
                
                {/* New Dashboard Architecture */}
                <Route path="/dashboards/executive" element={<ExecutiveSummary />} />
                <Route path="/dashboards/analytics" element={<AnalyticsDashboard />} />
                <Route path="/dashboards/targets" element={<TargetsDashboard />} />
                <Route path="/dashboards/data-quality" element={<DataQualityDashboard />} />
                <Route path="/dashboards/reporting" element={<ReportingDashboard />} />
                
                {/* Legacy Dashboard (keeping for backwards compatibility) */}
                <Route path="/dashboard-legacy" element={<Dashboard />} />
                
                {/* Emissions Calculator Routes */}
                <Route path="/emissions" element={<EmissionsDashboard />} />
                <Route path="/emissions/dashboard" element={<EmissionsDashboard />} />
                <Route path="/emissions/report" element={<EmissionsReport />} />
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
                 <Route path="/modules/:moduleId" element={<ModuleLandingPage />} />
                 <Route path="/scopes/:scopeId" element={<ScopeInfoPage />} />
                {/* Data Hub */}
                <Route path="/dataschema" element={<DataHubHome />} />
                <Route
                  path="/dataschema/entry/:moduleName/:tableId"
                  element={<DataEntryPage />}
                />
                {/* Row Detail Page */}
                <Route
                  path="/dataschema/row/:tableId/:rowId"
                  element={<RowDetailPage />}
                />

                {/* Catalog Studio Routes */}
                <Route path="/catalog" element={<CatalogHome />} />
                <Route path="/catalog/schemas" element={<SchemaCatalogPage />} />
                <Route path="/catalog/schemas/:tableId" element={<SchemaDetailPage />} />
                <Route path="/catalog/schema-manager" element={<SchemaManagerPage />} />
                <Route path="/catalog/domains" element={<DomainsPage />} />
                <Route path="/catalog/glossary" element={<GlossaryPage />} />
                <Route path="/catalog/assets" element={<AssetsPage />} />
                <Route path="/catalog/mdm" element={<MDMPage />} />
                <Route path="/catalog/connections" element={<ConnectionsPage />} />
                <Route path="/catalog/importexport" element={<ImportExportPage />} />
                <Route path="/catalog/tags" element={<TagsPage />} />
                <Route path="/catalog/reference-data" element={<ReferenceDataPage />} />
                <Route path="/catalog/governance" element={<GovernancePage />} />
                <Route path="/catalog/sources" element={<DataSourcesDetailPage />} />
                <Route path="/catalog/exports" element={<ExportsDetailPage />} />
                <Route path="/catalog/imports" element={<ImportsDetailPage />} />

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