import React, { createContext, useState, useContext } from "react";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);