// File: src/App.jsx
// App router. Login page has no header/sidebar/footer.

import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import { useThemeMode } from "./theme/ThemeContext";
import AdminRoute from "./components/AdminRoute";
import ItemDefinitionsPage from "./pages/ItemDefinitionsPage";
import TemplateDefinitionsPage from "./pages/TemplateDefinitionsPage";

function RequireAuth() {
  const { user } = useAuth();
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

function RequireContext() {
  const { currentContext } = useAuth();
  if (!currentContext) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        Loading project...
      </div>
    );
  }
  return <Outlet />;
}

export default function App() {
  const { resolvedMode } = useThemeMode();
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Routes>
        {/* Login: no layout */}
        <Route path="/login" element={<Login />} />

        {/* Main app: Require login and project */}
        <Route element={<RequireAuth />}>
          <Route element={<RequireContext />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />

              {/* ----- Admin-only schema routes ----- */}
              <Route
                path="/schema/items"
                element={
                  <AdminRoute>
                    <ItemDefinitionsPage />
                  </AdminRoute>
                }
              />
              <Route
                path="/schema/templates"
                element={
                  <AdminRoute>
                    <TemplateDefinitionsPage />
                  </AdminRoute>
                }
              />

              {/* Not found (fallback inside layout) */}
              <Route path="*" element={<NotFound />} />
            </Route>
          </Route>
        </Route>

        {/* Fallback */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}