// File: src/components/AdminRoute.jsx
import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "./NotificationProvider";

// Helper: Check if the user is an admin for the current project
function isAdmin(user, currentContext) {
  return user?.roles?.some(
    (r) =>
      r.active &&
      r.role === "admin_role" &&
      r.project_id === (currentContext?.context_id || currentContext?.project_id)
  );
}

export default function AdminRoute({ children, redirectTo = "/" }) {
  const { user, currentContext } = useAuth();
  const { notify } = useNotification();

  // Wait for auth/context to load
  if (!user || !currentContext) {
    console.log("AdminRoute: Waiting for user or currentContext to load...");
    return null;
  }

  if (!isAdmin(user, currentContext)) {
    notify({
      message: "Access denied: Admins only.",
      type: "error",
    });
    console.error("Access denied: User is not an admin.");
    return <Navigate to={redirectTo} replace />;
  }

  // Render children or nested routes
  return children ? children : <Outlet />;
}