// File: src/components/AdminRoute.jsx
// Simple RBAC: allow if user has active "admins_group" role anywhere.

import React, { useRef, useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";

function isAdmin(user, availablePerspectives = []) {
  if (!user?.roles && !availablePerspectives?.length) return false;
  const roles = (user?.roles || []).map(r => r?.role).filter(Boolean);
  return availablePerspectives.includes("admin") || roles.includes("admin") || roles.includes("admins_group");
}

export default function AdminRoute({ children, redirectTo = "/" }) {
  const { user, loading, availablePerspectives } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  useEffect(() => {
    // Only notify once, and only when user is loaded and is not admin
    if (!loading && user && !isAdmin(user, availablePerspectives) && !notifiedRef.current) {
      notify({
        message: "Access denied: admin role required.",
        type: "error",
      });
      notifiedRef.current = true;
    }
  }, [loading, user, notify]);

  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking permissions...</div>;
  }
  if (!user) {
    return null;
  }
  if (!isAdmin(user, availablePerspectives)) {
    return <Navigate to={redirectTo} replace />;
  }
  return children ? children : <Outlet />;
}