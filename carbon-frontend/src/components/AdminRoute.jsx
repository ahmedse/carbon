// File: src/components/AdminRoute.jsx
// Simple RBAC: allow if user has active "admins_group" role anywhere.

import React, { useRef } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";

/**
 * Returns true if user has an active "admins_group" role.
 */
function isAdmin(user) {
  if (!user?.roles) return false;
  return user.roles.some(r => r.active && r.role === "admins_group");
}

export default function AdminRoute({
  children,
  redirectTo = "/",
}) {
  const { user, loading } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking permissions...</div>;
  }
  if (!user) {
    return null;
  }

  if (!isAdmin(user)) {
    if (!notifiedRef.current) {
      notify({
        message: "Access denied: admin role required.",
        type: "error",
      });
      notifiedRef.current = true;
    }
    return <Navigate to={redirectTo} replace />;
  }

  return children ? children : <Outlet />;
}