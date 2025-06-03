// File: src/components/AdminRoute.jsx
import React, { useRef } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";

// Helper: Check if the user is an admin for the current project
function isAdmin(user, currentContext) {
  return user?.roles?.some(
    (r) =>
      r.active &&
      r.role === "admin_role" &&
      String(r.project_id) === String(currentContext?.context_id)
  );
}

export default function AdminRoute({ children, redirectTo = "/" }) {
  const { user, currentContext, loading } = useAuth();
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));
  const notifiedRef = useRef(false);

  // Wait for auth/context to load
  if (loading) {
    return <div style={{ padding: 48, textAlign: "center" }}>Checking admin permissions...</div>;
  }
  if (!user || !currentContext) {
    return null;
  }

  if (!isAdmin(user, currentContext)) {
    // Only notify once per denial
    if (!notifiedRef.current) {
      notify({
        message: "Access denied: Admins only.",
        type: "error",
      });
      notifiedRef.current = true;
    }
    return <Navigate to={redirectTo} replace />;
  }

  // Render children or nested routes
  return children ? children : <Outlet />;
}