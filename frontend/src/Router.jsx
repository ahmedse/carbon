import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AdminDashboard from "./pages/AdminDashboard";
import AuditorDashboard from "./pages/AuditorDashboard";
import DataOwnerDashboard from "./pages/DataOwnerDashboard";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import { useAuth } from "./context/AuthContext";

// Improved ProtectedRoute: supports multiple roles
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user } = useAuth();

  // If not logged in, redirect to login
  if (!user) return <Navigate to="/login" replace />;

  // Assume user.roles is an array of role names. Adjust if needed.
  const roles = user.roles || (user.role ? [user.role] : []);

  // If allowedRoles is given, check if user has at least one
  if (allowedRoles && !roles.some(r => allowedRoles.includes(r))) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

const Router = () => (
  <BrowserRouter>
    <Routes>
      {/* Default route */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />} />

      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <AdminDashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/auditor"
        element={
          <ProtectedRoute allowedRoles={["auditor"]}>
            <AuditorDashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/data-owner"
        element={
          <ProtectedRoute allowedRoles={["data_owner", "data-owner"]}>
            <DataOwnerDashboard />
          </ProtectedRoute>
        }
      />

      {/* Redirect all unknown routes to login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  </BrowserRouter>
);

export default Router;