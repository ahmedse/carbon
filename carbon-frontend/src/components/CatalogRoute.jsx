// src/components/CatalogRoute.jsx
// Route guard for Catalog Studio pages. Only catalog/studio admin roles should access.

import React, { useRef, useEffect, useMemo } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";
import { isCatalogAdmin } from "../authz";

export default function CatalogRoute({ children, redirectTo = "/" }) {
  const { user, loading, availablePerspectives, userCapabilities } = useAuth();
  const notifyCtx = useNotification();
  const notify = useMemo(
    () => typeof notifyCtx?.notify === "function"
      ? notifyCtx.notify
      : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification")),
    [notifyCtx?.notify]
  );
  const notifiedRef = useRef(false);

  const isCatAdmin = isCatalogAdmin(user, { perspectives: availablePerspectives, capabilities: userCapabilities });

  useEffect(() => {
    if (!loading && user && !isCatAdmin && !notifiedRef.current) {
      notify({
        message: "Access denied: catalog admin role required.",
        type: "error",
      });
      notifiedRef.current = true;
    }
  }, [loading, user, availablePerspectives, userCapabilities, isCatAdmin, notify]);

  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking permissions...</div>;
  }

  if (!user) {
    return null;
  }

  if (!isCatAdmin) {
    return <Navigate to={redirectTo} replace />;
  }

  return children ? children : <Outlet />;
}
