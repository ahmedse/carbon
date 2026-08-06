// File: src/components/AdminRoute.jsx
// Guards admin pages. Two modes:
//   - Without appId: platform admin only (global admins). Used for Users, Groups, OrgUnits, Access Control.
//   - With appId: global admins OR Domain Leads for that app. Used for app-domain admin pages.
// Domain Leads (carbon_lead, etc.) manage app data/config within org scope.

import React, { useRef, useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";
import { isGlobalAdmin, isDomainLead, expandCapabilities, hasCap } from "../authz";

export default function AdminRoute({ children, redirectTo = "/", appId = null, requiredCapability = null }) {
  const { user, loading, availablePerspectives, isGlobalAdminFlag, userCapabilities } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  // Check capabilities via expanded inheritance (BUG-01 fix: was exact-match, now uses expandCapabilities)
  const userCapKeys = userCapabilities?.map(c => typeof c === 'string' ? c : (c?.key || c?.capability)) || [];
  const hasReqCap = requiredCapability && hasCap(expandCapabilities(userCapKeys), requiredCapability);

  const hasAccess = isGlobalAdmin(user, availablePerspectives, isGlobalAdminFlag)
    || (appId && isDomainLead(appId, availablePerspectives))
    || hasReqCap;

  useEffect(() => {
    if (!loading && user && !hasAccess && !notifiedRef.current) {
      const msg = appId
        ? `Access denied: ${appId} Domain Lead, platform admin, or required capability needed.`
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