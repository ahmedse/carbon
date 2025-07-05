// src/auth/AuthContext.jsx
import React, { createContext, useState, useContext, useEffect, useRef } from "react";
import { API_BASE_URL, API_ROUTES } from "../config";
import { isJwtExpired } from "../jwt";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const inactivityTimeout = 60 * 60 * 1000; // 1 hour
  const timerRef = useRef();

  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });

  const [currentContext, setCurrentContext] = useState(() => {
    const stored = localStorage.getItem("context");
    return stored ? JSON.parse(stored) : null;
  });

  const [loading, setLoading] = useState(true);

  const syncUser = (userData) => {
    setUser(userData);
    if (userData) localStorage.setItem("user", JSON.stringify(userData));
    else localStorage.removeItem("user");
    if (userData?.token) localStorage.setItem("access", userData.token);
    if (userData?.refresh) localStorage.setItem("refresh", userData.refresh);
  };

  const syncContext = (ctx) => {
    setCurrentContext(ctx);
    if (ctx) localStorage.setItem("context", JSON.stringify(ctx));
    else localStorage.removeItem("context");
  };

  // --- Refresh token logic ---
  const refreshAccessToken = async () => {
    const refresh = localStorage.getItem("refresh");
    if (!refresh) {
      logout();
      throw new Error("No refresh token available.");
    }
    const response = await fetch(`${API_BASE_URL}${API_ROUTES.tokenRefresh}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) {
      logout();
      throw new Error("Failed to refresh token.");
    }
    const data = await response.json();
    if (data.access) {
      const updatedUser = { ...user, token: data.access };
      syncUser(updatedUser);
      return data.access;
    } else {
      logout();
      throw new Error("No access token returned.");
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      let restoredUser = user;
      let restoredContext = currentContext;

      // Check token expiry and refresh if needed
      const token = restoredUser?.token || localStorage.getItem("access");
      if (token && isJwtExpired(token)) {
        try {
          await refreshAccessToken();
        } catch {
          logout();
          setLoading(false);
          return;
        }
      }

      // Restore context, or set default from roles (project OR module)
      if (restoredUser && restoredUser.roles && restoredUser.roles.length > 0) {
        let ctx = localStorage.getItem("context");
        let parsed = ctx ? JSON.parse(ctx) : null;

        // Try to restore existing context (project or module)
        const hasContext = restoredUser.roles.some(
          (r) =>
            ((r.context_type === "project" && Number(r.project_id) === Number(parsed?.context_id)) ||
             (r.context_type === "module" && Number(r.module_id) === Number(parsed?.context_id)))
        );
        if (parsed && hasContext) {
          if (!currentContext) {
            console.log("Restoring context from localStorage:", parsed);
          }
          // Ensure all IDs are numbers
          if (parsed.project_id) parsed.project_id = Number(parsed.project_id);
          if (parsed.module_id) parsed.module_id = Number(parsed.module_id);
          if (parsed.context_id) parsed.context_id = Number(parsed.context_id);
          syncContext(parsed);
        } else {
          // Prefer project context if available
          const firstProject = restoredUser.roles.find(
            (r) => r.context_type === "project" && r.project_id && r.project
          );
          if (firstProject) {
            const defaultContext = {
              context_id: Number(firstProject.project_id),
              project: firstProject.project,
              context_type: "project",
              project_id: Number(firstProject.project_id),
            };
            console.log("Setting default context (project):", defaultContext);
            syncContext(defaultContext);
          } else {
            // Else, use first module context
            const firstModule = restoredUser.roles.find(
              (r) => r.context_type === "module" && r.module_id && r.module
            );
            if (firstModule) {
              const defaultContext = {
                context_id: Number(firstModule.module_id),
                module: firstModule.module,
                module_id: Number(firstModule.module_id),
                context_type: "module",
                project: firstModule.project,
                project_id: Number(firstModule.project_id),
              };
              console.log("Setting default context (module):", defaultContext);
              syncContext(defaultContext);
            } else {
              syncContext(null);
            }
          }
        }
      } else {
        syncContext(null);
      }
      setLoading(false);

      console.log("User roles after login:", restoredUser?.roles);
      console.log("Context in localStorage:", localStorage.getItem("context"));
    };
    bootstrap();
    // eslint-disable-next-line
  }, []);

  // --- Inactivity timer ---
  const resetTimer = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      logout();
      window.location.href = "/login";
    }, inactivityTimeout);
  };

  useEffect(() => {
    const events = ["mousemove", "keydown", "mousedown", "touchstart"];
    events.forEach(event => window.addEventListener(event, resetTimer));
    resetTimer();
    return () => {
      events.forEach(event => window.removeEventListener(event, resetTimer));
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [user]);

  // --- Project/module context switching logic ---
  const setContext = (context) => {
    // Always coerce IDs to numbers
    const contextId = context.context_id ? Number(context.context_id) : undefined;
    const projectId = context.project_id ? Number(context.project_id) : undefined;
    const moduleId = context.module_id ? Number(context.module_id) : undefined;

    const normalizedContext = {
      ...context,
      context_id: contextId,
      project_id: projectId,
      module_id: moduleId,
    };

    if (
      user &&
      user.roles &&
      (
        user.roles.some(
          (r) =>
            r.context_type === "project" &&
            Number(r.project_id) === contextId
        ) ||
        user.roles.some(
          (r) =>
            r.context_type === "module" &&
            Number(r.module_id) === contextId
        )
      )
    ) {
      console.log("Switching context to:", normalizedContext);
      syncContext(normalizedContext);
    } else {
      console.error("Invalid context provided or user does not have access.");
    }
  };

  const login = (userData) => {
    syncUser(userData);
    window.location.reload(); // Optionally reload to reset all app state
  };

  const logout = () => {
    setUser(null);
    setCurrentContext(null);
    localStorage.clear();
  };

  // For debugging
  window.refreshAccessToken = refreshAccessToken;
  window.logout = logout;

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        token: user?.token,
        currentContext,
        setContext,
        refreshAccessToken,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);