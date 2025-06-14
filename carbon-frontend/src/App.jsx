// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import AdminRoute from "./components/AdminRoute";
import TableManager from "./pages/TableManager";   
import TableManagerPage from "./pages/TableManagerPage"; // Admin: schema CRUD
import DataEntryPage from "./pages/DataEntryPage";       // Data row CRUD
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs'; 

function RequireAuth() {
  const { user, loading } = useAuth();
  React.useEffect(() => {
    console.debug("RequireAuth: user", user, "loading", loading);
  }, [user, loading]);
  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Loading authentication...</div>;
  }
  if (!user) {
    console.debug("RequireAuth: No user, redirecting to /login");
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

function RequireContext() {
  const { currentContext, loading } = useAuth();
  React.useEffect(() => {
    console.debug("RequireContext: currentContext", currentContext, "loading", loading);
  }, [currentContext, loading]);
  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Loading project context...</div>;
  }
  if (!currentContext) {
    console.debug("RequireContext: No project context found");
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        No project context found. Please contact your admin.
      </div>
    );
  }
  return <Outlet />;
}

export default function App() {
  React.useEffect(() => {
    console.debug("App.jsx: App mounted");
  }, []);
  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <BrowserRouter
        future={{
          v7_startTransition: true, // Enable future flag for startTransition
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireAuth />}>
            <Route element={<RequireContext />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Dashboard />} />

                {/* ---- SCHEMA ADMIN (Admin only) ---- */}
                <Route
                  path="/dataschema/manage/tablemanager"
                  element={
                    <AdminRoute>
                      <TableManager />
                    </AdminRoute>
                  }
                />

                <Route
                  path="/dataschema/manage/tablemanagerpage"
                  element={
                    <AdminRoute>
                      <TableManagerPage />
                    </AdminRoute>
                  }
                />

                {/* ---- DATA ENTRY (Anyone with access; per-table in module) ---- */}
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