// File: src/theme/ThemeContext.jsx
// Theme provider for the Carbon Data Trust Platform.
// Design language adopted from Gigacast (zinc/blue palette). Light + dark modes.

import React, { createContext, useContext, useState, useEffect } from "react";
import createCarbonTheme from "./carbonTheme";

const ThemeModeContext = createContext();

export function ThemeModeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    const stored = localStorage.getItem("themeMode");
    return stored === "dark" ? "dark" : "light";
  });

  // Toggle between light and dark
  const toggle = () => {
    setMode((prev) => (prev === "light" ? "dark" : "light"));
  };

  useEffect(() => {
    localStorage.setItem("themeMode", mode);
  }, [mode]);

  const resolvedMode = mode === "dark" ? "dark" : "light";

  return (
    <ThemeModeContext.Provider value={{ mode, toggle, resolvedMode }}>
      {children}
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode() {
  const context = useContext(ThemeModeContext);
  if (!context) {
    return { mode: 'light', toggle: () => {} };
  }
  return context;
}

export const getTheme = (mode) => createCarbonTheme(mode === "dark" ? "dark" : "light");
