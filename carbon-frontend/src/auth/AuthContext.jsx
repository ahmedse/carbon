// File: src/auth/AuthContext.jsx
// Handles authentication and automatic project selection (project context only).

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

  // --- Token refresh logic (unchanged) ---
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
      setUser((prev) => {
        const updatedUser = { ...prev, token: data.access };
        localStorage.setItem("user", JSON.stringify(updatedUser));
        return updatedUser;
      });
      localStorage.setItem("access", data.access);
      return data.access;
    } else {
      logout();
      throw new Error("No access token returned.");
    }
  };

  // --- On load: check token validity
  useEffect(() => {
    const checkToken = async () => {
      const token = user?.token || localStorage.getItem("access");
      if (token && isJwtExpired(token)) {
        try {
          await refreshAccessToken();
        } catch {
          logout();
        }
      }
    };
    checkToken();
    // eslint-disable-next-line
  }, []);

  // --- Inactivity timer
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

  // --- Project-only selection logic ---
  useEffect(() => {
    if (user && user.roles && user.roles.length > 0) {
      let context = localStorage.getItem("context");
      let defaultProject = null;

      if (context) {
        context = JSON.parse(context);
        // Only allow context if it matches a project the user has via a project-level role
        const hasProject = user.roles.some(
          r =>
            r.context_type === "project" &&
            r.project_id === context.context_id
        );
        if (context && hasProject) {
          setCurrentContext(context);
          localStorage.setItem("context", JSON.stringify(context));
          return;
        }
      }

      // If no saved context or not available, pick first project in roles
      const firstProjectRole = user.roles.find(
        r => r.context_type === "project" && r.project_id && r.project
      );
      if (firstProjectRole) {
        defaultProject = {
          context_id: firstProjectRole.project_id,
          project: firstProjectRole.project
        };
        setCurrentContext(defaultProject);
        localStorage.setItem("context", JSON.stringify(defaultProject));
      } else {
        setCurrentContext(null);
        localStorage.removeItem("context");
      }
    } else {
      setCurrentContext(null);
      localStorage.removeItem("context");
    }
  }, [user]);

  const login = (userData) => {
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
    localStorage.setItem("access", userData.token);
    localStorage.setItem("refresh", userData.refresh || "");
    // context will be set automatically by useEffect above
  };

  const logout = () => {
    setUser(null);
    setCurrentContext(null);
    localStorage.removeItem("user");
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    localStorage.removeItem("context");
  };

  // Only allow setting a context that is a project the user actually has
  const setContext = (context) => {
    if (
      user &&
      user.roles &&
      user.roles.some(
        r =>
          r.context_type === "project" &&
          r.project_id === context.context_id
      )
    ) {
      setCurrentContext(context);
      localStorage.setItem("context", JSON.stringify(context));
    }
  };

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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);