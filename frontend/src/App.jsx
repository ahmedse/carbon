// File: frontend/src/App.jsx
// Purpose: Root React component, sets up theme, authentication, and routing.
// Location: frontend/src/

import React, { useState, useMemo, useEffect } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Router from "./Router";
import { AuthProvider } from "./context/AuthContext";
import getDesignTokens from "./styles/theme";

/**
 * Determines the preferred color mode from the user's system.
 * @returns {'dark'|'light'}
 */
const getSystemMode = () =>
  window.matchMedia &&
  window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";

/**
 * Returns the user's theme mode preference from localStorage.
 * Defaults to 'system' if not set.
 */
const getStoredMode = () => localStorage.getItem("themeMode") || "system";

/**
 * Main app component. Handles global theme and authentication context.
 * Provides theme toggling and persists preference.
 */
const App = () => {
  const [mode, setMode] = useState(getStoredMode);
  const [systemMode, setSystemMode] = useState(getSystemMode());

  // Listen to system color scheme changes when in 'system' mode
  useEffect(() => {
    if (mode === "system") {
      const matcher = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = (e) => {
        const newSysMode = e.matches ? "dark" : "light";
        setSystemMode(newSysMode);
      };
      matcher.addEventListener("change", onChange);
      return () => matcher.removeEventListener("change", onChange);
    }
  }, [mode]);

  // Save user's mode preference
  useEffect(() => {
    localStorage.setItem("themeMode", mode);
  }, [mode]);

  const effectiveMode = mode === "system" ? systemMode : mode;

  // Memoize theme object for performance
  const theme = useMemo(
    () => createTheme(getDesignTokens(effectiveMode)),
    [effectiveMode]
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <Router mode={mode} setMode={setMode} />
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;