// File: src/components/AdminRoute.jsx
// Guards admin pages. Two modes:
//   - Without appId: platform admin only (global admins). Used for Users, Groups, OrgUnits, Access Control.
//   - With appId: global admins OR Domain Leads for that app. Used for app-domain admin pages.
// Domain Leads (carbon_lead, etc.) manage app data/config within org scope.

import React, { useRef, useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";
import { isGlobalAdmin, isDomainLead } from "../utils/rbac";

export default function AdminRoute({ children, redirectTo = "/", appId = null }) {
  const { user, loading, availablePerspectives, isGlobalAdminFlag } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  const hasAccess = isGlobalAdmin(user, availablePerspectives, isGlobalAdminFlag)
    || (appId && isDomainLead(appId, availablePerspectives));

  useEffect(() => {
    if (!loading && user && !hasAccess && !notifiedRef.current) {
      const msg = appId
        ? `Access denied: ${appId} Domain Lead or platform admin role required.`
        : "Access denied: platform admin role required.";
      notify({ message: msg, type: "error" });
      notifiedRef.current = true;
    }
  }, [loading, user, availablePerspectives, isGlobalAdminFlag, hasAccess, appId, notify]);

  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking permissions...</div>;
  }
  if (!user) {
    return null;
  }
  if (!hasAccess) {
    return <Navigate to={redirectTo} replace />;
  }
  return children ? children : <Outlet />;
}