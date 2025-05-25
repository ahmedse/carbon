// File: frontend/src/Router.jsx
// Purpose: Application router, handles route protection and layout structure.
// Location: frontend/src/

import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import AdminDashboard from "./pages/AdminDashboard/AdminDashboard";
import AuditorDashboard from "./pages/AuditorDashboard";
import DataOwnerDashboard from "./pages/DataOwnerDashboard";
import { useAuth } from "./context/AuthContext";
import NotFound from "./pages/NotFound";

/**
 * Protects routes based on authenticated user and allowed roles.
 * Redirects to login if not authenticated or not authorized.
 */
const ProtectedRoute = ({ allowedRoles, children }) => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles) {
    const allRoles = (user.roles || []).map(r => r.role);
    if (!allRoles.some(r => allowedRoles.includes(r))) {
      return <Navigate to="/login" replace />;
    }
  }
  return children;
};

/**
 * Layout wrapper for routes, passing theme mode controls.
 */
const LayoutRoute = ({ mode, setMode }) => (
  <MainLayout mode={mode} setMode={setMode}>
    <Outlet />
  </MainLayout>
);

/**
 * Root router configuration.
 */
const Router = ({ mode, setMode }) => (
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <LayoutRoute mode={mode} setMode={setMode} />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route
          path="/admin/*"
          element={
            <ProtectedRoute allowedRoles={["admin_role"]}>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/auditor/*"
          element={
            <ProtectedRoute allowedRoles={["auditor"]}>
              <AuditorDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/data-owner/*"
          element={
            <ProtectedRoute allowedRoles={["data_owner", "data-owner"]}>
              <DataOwnerDashboard />
            </ProtectedRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  </BrowserRouter>
);

export default Router;