// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useParams, Outlet } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import AdminRoute from "./components/AdminRoute";
import TableManager from "./pages/TableManager";          // <-- Admin: schema CRUD
import DataEntryPage from "./pages/DataEntryPage";        // <-- Data row CRUD

function RequireAuth() {
  const { user } = useAuth();
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

function RequireContext() {
  const { currentContext } = useAuth();
  if (!currentContext) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        Loading project...
      </div>
    );
  }
  return <Outlet />;
}

export default function App() {
  return (
    <BrowserRouter>
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
  );
}