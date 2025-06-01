// File: src/auth/AuthContext.jsx
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

  // --- Project selection logic ---
  useEffect(() => {
    if (user && user.roles && user.roles.length > 0) {
      let context = localStorage.getItem("context");

      if (context) {
        context = JSON.parse(context);
        const hasProject = user.roles.some(
          (r) =>
            r.context_type === "project" &&
            r.project_id === context.context_id
        );
        if (context && hasProject) {
          console.log("Restoring context from localStorage:", context);
          setCurrentContext(context);
          localStorage.setItem("context", JSON.stringify(context));
          return;
        }
      }

      const firstProjectRole = user.roles.find(
        (r) => r.context_type === "project" && r.project_id && r.project
      );
      if (firstProjectRole) {
        const defaultContext = {
          context_id: firstProjectRole.project_id,
          project: firstProjectRole.project,
        };
        console.log("Setting default context:", defaultContext);
        setCurrentContext(defaultContext);
        localStorage.setItem("context", JSON.stringify(defaultContext));
      } else {
        console.log("No valid project context available.");
        setCurrentContext(null);
        localStorage.removeItem("context");
      }
    } else {
      console.log("No user or roles available to set context.");
      setCurrentContext(null);
      localStorage.removeItem("context");
    }
  }, [user]);

  // --- Define setContext ---
  const setContext = (context) => {
    if (
      user &&
      user.roles &&
      user.roles.some(
        (r) =>
          r.context_type === "project" &&
          r.project_id === context.context_id
      )
    ) {
      console.log("Switching context to:", context);
      setCurrentContext(context);
      localStorage.setItem("context", JSON.stringify(context));
    } else {
      console.error("Invalid context provided or user does not have access.");
    }
  };

  const login = (userData) => {
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
    localStorage.setItem("access", userData.token);
    localStorage.setItem("refresh", userData.refresh || "");
  };

  const logout = () => {
    setUser(null);
    setCurrentContext(null);
    localStorage.clear();
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
        setContext, // Export setContext
        refreshAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);