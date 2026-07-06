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
import AdminRoute from "./components/AdminRoute";
import TableManagerPage from "./pages/TableManagerPage";
import OrgUnitsPage from "./pages/admin/OrgUnitsPage";
import AccessControlPage from "./pages/admin/AccessControlPage";
import UsersPage from "./pages/admin/UsersPage";
import DataEntryPage from "./pages/DataEntryPage";
import Help from "./pages/Help";
import Feedback from "./pages/Feedback";
import ModuleLandingPage from "./pages/ModuleLandingPage";
import ScopeInfoPage from "./pages/ScopeInfoPage";
import EmissionsDashboard from "./pages/EmissionsDashboard";
import EmissionsReport from "./pages/EmissionsReport";

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

export default function App() {
  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
     <BrowserRouter basename={import.meta.env.VITE_BASE}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireAuth />}>
            <Route element={<RequireContext />}>
              <Route element={<Layout />}>
                <Route path="help" element={<Help />} />
                <Route path="feedback" element={<Feedback />} />
                <Route path="/" element={<ExecutiveSummary />} />
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
                {/* Data entry */}
                <Route
                  path="/dataschema/entry/:moduleName/:tableId"
                  element={<DataEntryPage />}
                />
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