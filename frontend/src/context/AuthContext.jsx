import React, { createContext, useState, useContext, useEffect, useRef } from "react";
import { API_BASE_URL, API_ROUTES } from "../config";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const inactivityTimeout = 60 * 60 * 1000; // 60 minutes (adjust as needed)
  const timerRef = useRef();

  // Restore user from localStorage if available
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });

  // Restore context from localStorage if available
  const [currentContext, setCurrentContext] = useState(() => {
    const stored = localStorage.getItem("context");
    return stored ? JSON.parse(stored) : null;
  });

  // Helper: Refresh access token using refresh token
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
      // Update user state and localStorage with new access token
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

  // Reset inactivity timer
  const resetTimer = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      logout();
      window.location.href = "/login"; // Force redirect
    }, inactivityTimeout);
  };

  useEffect(() => {
    // Start/reset timer on user activity
    const events = ["mousemove", "keydown", "mousedown", "touchstart"];
    events.forEach(event => window.addEventListener(event, resetTimer));
    resetTimer(); // Initialize timer

    return () => {
      events.forEach(event => window.removeEventListener(event, resetTimer));
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [user]); // Restart timer on user login/logout

  const login = (userData) => {
    console.log("[AuthContext] Logging in user:", userData);
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
    localStorage.setItem("access", userData.token);
    localStorage.setItem("refresh", userData.refresh || "");
  };

  const logout = () => {
    console.log("[AuthContext] Logging out");
    setUser(null);
    setCurrentContext(null);
    localStorage.removeItem("user");
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    localStorage.removeItem("context");
  };

  const setContext = (context) => {
    setCurrentContext(context);
    localStorage.setItem("context", JSON.stringify(context));
    console.log("[AuthContext] Context set:", context);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        token: user?.token,
        currentContext,
        setContext,
        refreshAccessToken, // Expose the refresh method
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);