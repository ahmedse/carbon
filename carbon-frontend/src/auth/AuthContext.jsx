// File: src/auth/AuthContext.jsx
import React, { createContext, useState, useContext, useEffect, useRef } from "react";
import { API_BASE_URL, API_ROUTES } from "../config";
import { isJwtExpired } from "../jwt";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const inactivityTimeout = 60 * 60 * 1000; // 1 hour
  const timerRef = useRef();

  // --- Efficient: Initialize ONCE from localStorage ---
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });

  const [currentContext, setCurrentContext] = useState(() => {
    const stored = localStorage.getItem("context");
    return stored ? JSON.parse(stored) : null;
  });

  // --- Loading state for smoother UX ---
  const [loading, setLoading] = useState(true);

  // --- Helper: Save both state and localStorage in sync ---
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

  // --- On mount: check token validity, restore context ---
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

      // Restore context, or set default from roles
      if (restoredUser && restoredUser.roles && restoredUser.roles.length > 0) {
        let ctx = localStorage.getItem("context");
        let parsed = ctx ? JSON.parse(ctx) : null;
        const hasProject = restoredUser.roles.some(
          (r) =>
            r.context_type === "project" &&
            String(r.project_id) === String(parsed?.context_id)
        );
        if (parsed && hasProject) {
          // Only log ONCE
          if (!currentContext) {
            console.log("Restoring context from localStorage:", parsed);
          }
          syncContext(parsed);
        } else {
          // Default to first project role
          const firstProject = restoredUser.roles.find(
            (r) => r.context_type === "project" && r.project_id && r.project
          );
          if (firstProject) {
            const defaultContext = {
              context_id: firstProject.project_id,
              project: firstProject.project,
            };
            console.log("Setting default context:", defaultContext);
            syncContext(defaultContext);
          } else {
            syncContext(null);
          }
        }
      } else {
        syncContext(null);
      }
      setLoading(false);
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

  // --- Project/context switching logic ---
  const setContext = (context) => {
    if (
      user &&
      user.roles &&
      user.roles.some(
        (r) =>
          r.context_type === "project" &&
          String(r.project_id) === String(context.context_id)
      )
    ) {
      console.log("Switching context to:", context);
      syncContext(context);
    } else {
      console.error("Invalid context provided or user does not have access.");
    }
  };

  const login = (userData) => {
    syncUser(userData);
    // Context will be restored/initialized via the effect
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