// File: src/main.jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { ThemeModeProvider, useThemeMode, getTheme } from "./theme/ThemeContext";
import { NotificationProvider } from "./components/NotificationProvider";
import "@fontsource/inter/index.css";

function ThemedApp() {
  const { mode } = useThemeMode();
  const theme = getTheme(mode);

  React.useEffect(() => {
    // Debug: confirm mount
    console.debug("ThemedApp mounted. Theme mode:", mode);
  }, [mode]);

  return (
    <ThemeProvider theme={theme}>
      <NotificationProvider>
        <CssBaseline />
        <AuthProvider>
          <App />
        </AuthProvider>
      </NotificationProvider>
    </ThemeProvider>
  );
}

console.debug("main.jsx: Rendering root app...");
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ThemedApp />
    </ThemeModeProvider>
  </React.StrictMode>
);