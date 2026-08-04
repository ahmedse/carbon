// File: src/components/AdminRoute.jsx
// Guards platform admin pages (Users, Groups, OrgUnits, Access Control).
// Only global admins (is_global_admin=True from backend) pass through.
// Domain Leads (carbon_lead, etc.) are REDIRECTED — they manage app data, not the platform.

import React, { useRef, useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";
import { isGlobalAdmin } from "../utils/rbac";

export default function AdminRoute({ children, redirectTo = "/" }) {
  const { user, loading, availablePerspectives, isGlobalAdminFlag } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  useEffect(() => {
    // Only notify once, and only when user is loaded and is not a global admin
    if (!loading && user && !isGlobalAdmin(user, availablePerspectives, isGlobalAdminFlag) && !notifiedRef.current) {
      notify({
        message: "Access denied: platform admin role required.",
        type: "error",
      });
      notifiedRef.current = true;
    }
  }, [loading, user, availablePerspectives, isGlobalAdminFlag, notify]);

  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking permissions...</div>;
  }
  if (!user) {
    return null;
  }
  if (!isGlobalAdmin(user, availablePerspectives, isGlobalAdminFlag)) {
    return <Navigate to={redirectTo} replace />;
  }
  return children ? children : <Outlet />;
}