// src/components/CatalogRoute.jsx
// Route guard for Catalog Studio pages. Only catalog/studio admin roles should access.

import React, { useRef, useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";
import { isCatalogAdmin } from "../utils/rbac";

export default function CatalogRoute({ children, redirectTo = "/" }) {
  const { user, loading, availablePerspectives } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  useEffect(() => {
    if (!loading && user && !isCatalogAdmin(user, availablePerspectives) && !notifiedRef.current) {
      notify({
        message: "Access denied: catalog admin role required.",
        type: "error",
      });
      notifiedRef.current = true;
    }
  }, [loading, user, availablePerspectives, notify]);

  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking permissions...</div>;
  }

  if (!user) {
    return null;
  }

  if (!isCatalogAdmin(user, availablePerspectives)) {
    return <Navigate to={redirectTo} replace />;
  }

  return children ? children : <Outlet />;
}
