// File: src/components/AdminRoute.jsx
// Restricts access to admin_role users only (for selected project). Shows error and redirects if not admin.

import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";

// Helper: is the user active admin for this project?
function isAdmin(user, currentContext) {
  return user?.roles?.some(
    r =>
      r.active &&
      r.role === "admin_role" &&
      r.project_id === (currentContext?.context_id || currentContext?.project_id)
  );
}

/**
 * Usage:
 * <Route
 *   path="/schema/items"
 *   element={
 *     <AdminRoute>
 *       <ItemDefinitionsPage />
 *     </AdminRoute>
 *   }
 * />
 */
export default function AdminRoute({ children, redirectTo = "/" }) {
  const { user, currentContext } = useAuth();
  const { notify } = useNotification();

  // Wait for auth/context to load
  if (!user || !currentContext) return null;

  if (!isAdmin(user, currentContext)) {
    notify({
      message: "Access denied: Admins only.",
      type: "error"
    });
    return <Navigate to={redirectTo} replace />;
  }

  // Render children or nested routes
  return children ? children : <Outlet />;
}