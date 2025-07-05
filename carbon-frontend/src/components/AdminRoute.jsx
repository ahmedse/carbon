// File: src/components/AdminRoute.jsx
// Generic RBAC route guard for any required permission in current project/module context.

import React, { useRef } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";

/**
 * Checks if the user has a given permission in the current context (project/module).
 * @param {object} user 
 * @param {object} currentContext 
 * @param {string} permission 
 * @returns {boolean}
 */
function hasPermission(user, currentContext, permission) {
  if (!user?.roles || !currentContext) return false;
  return user.roles.some(
    r =>
      r.active &&
      (
        // Project-level context
        (r.context_type === "project" && String(r.project_id) === String(currentContext.project_id))
        ||
        // Module-level context
        (r.context_type === "module" && String(r.module_id) === String(currentContext.module_id))
      ) &&
      (r.permissions || []).includes(permission)
  );
}

/**
 * AdminRoute (generic):
 * - Protects route by required permission (default: "manage_schema")
 * - Notifies on denial (once)
 * - Redirects to `redirectTo` (default "/")
 * Usage:
 *   <AdminRoute permission="manage_schema"><SomeComponent/></AdminRoute>
 *   or for nested routes:
 *   <Route element={<AdminRoute permission="manage_schema" />}>
 *      <Route ... />
 *   </Route>
 */
export default function AdminRoute({
  children,
  permission = "manage_schema",
  redirectTo = "/",
}) {
  const { user, currentContext, loading } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  // Wait for auth/context to load
  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking permissions...</div>;
  }
  if (!user || !currentContext) {
    return null;
  }

  if (!hasPermission(user, currentContext, permission)) {
    // Notify only once per denial
    if (!notifiedRef.current) {
      notify({
        message: "Access denied: insufficient permission.",
        type: "error",
      });
      notifiedRef.current = true;
    }
    return <Navigate to={redirectTo} replace />;
  }

  // Render children or nested routes
  return children ? children : <Outlet />;
}