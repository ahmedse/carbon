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
import DataEntryPage from "./pages/DataEntryPage";
import Help from "./pages/Help";
import Feedback from "./pages/Feedback";
import ModuleLandingPage from "./pages/ModuleLandingPage";
import ScopeInfoPage from "./pages/ScopeInfoPage";

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
  const { context, loading } = useAuth();
  if (loading) return <div className="centered">Loading project context...</div>;
  if (!context) {
    return (
      <div className="centered">
        No project context found.<br />
        Please select a project or contact your administrator.
      </div>
    );
  }
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
                <Route path="/" element={<Dashboard />} />
                <Route path="/dashboard" element={<Dashboard />} />
                {/* Admin-only: Schema Admin > Table Manager */}
                <Route
                  path="/schema-admin/table-manager"
                  element={
                    <AdminRoute>
                      <TableManagerPage />
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