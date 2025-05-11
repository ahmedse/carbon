import React, { useState, useMemo, useEffect } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Router from "./Router";
import { AuthProvider } from "./context/AuthContext";
import getDesignTokens from "./styles/theme";

const getSystemMode = () =>
  window.matchMedia &&
  window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";

const getStoredMode = () => localStorage.getItem("themeMode") || "system";

const App = () => {
  const [mode, setMode] = useState(getStoredMode);
  const [systemMode, setSystemMode] = useState(getSystemMode());

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

  useEffect(() => {
    localStorage.setItem("themeMode", mode);
  }, [mode]);

  const effectiveMode = mode === "system" ? systemMode : mode;

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