// File: src/components/AdminRoute.jsx
// Guards admin pages. Wired to the unified can() authorization gate.
// Two modes:
//   - Without appId: platform admin routes (Users, Groups, OrgUnits, Access Control, Audit, Apps).
//     Gate: can(user, 'access_route', routePath, ctx)
//   - With appId: domain admin pages (e.g. carbon admin, catalog admin).
//     Gate: can(user, 'manage', appId, ctx)
//   - With requiredCapability: explicit capability check via can(user, 'access_route', path, ctx)
//     where the path is looked up in ROUTE_CAPABILITIES to find the matching capability.

import React, { useRef, useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";
import { can } from "../authz";
import { expandCapabilities, hasCap } from "../capabilities";

export default function AdminRoute({ children, redirectTo = "/", appId = null, requiredCapability = null }) {
  const { user, loading, availablePerspectives, isGlobalAdminFlag, userCapabilities, context } = useAuth();
  const location = useLocation();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  // Build unified auth context
  const authCtx = {
    perspectives: availablePerspectives,
    isGlobalAdminFlag,
    capabilities: userCapabilities,
    modules: context?.modules || [],
  };

  // Compute access using the unified can() gate
  let hasAccess = false;
  if (appId) {
    // Domain admin page: check manage + access_route as fallback
    hasAccess = can(user, 'manage', appId, authCtx)
      || can(user, 'access_route', location.pathname, authCtx);
  } else {
    // Platform admin page: check access_route against the current path
    hasAccess = can(user, 'access_route', location.pathname, authCtx);
  }
  // requiredCapability overrides: check if user has the explicit capability
  if (requiredCapability && !hasAccess && user) {
    const caps = (userCapabilities || []).map(c => typeof c === 'string' ? c : (c?.key || c?.capability));
    hasAccess = hasCap(expandCapabilities(caps), requiredCapability);
  }

  useEffect(() => {
    if (!loading && user && !hasAccess && !notifiedRef.current) {
      const msg = appId
        ? `Access denied: ${appId} Domain Lead, platform admin, or required capability needed.`
        : "Access denied: platform admin role required.";
      notify({ message: msg, type: "error" });
      notifiedRef.current = true;
    }
  }, [loading, user, hasAccess, appId, notify]);

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