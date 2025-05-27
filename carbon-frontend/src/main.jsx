// File: src/main.jsx
// Path: src/main.jsx
// App entry point. Wraps App with Theme and Auth providers. ThemeProvider responds to theme changes.

import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { ThemeModeProvider, useThemeMode, getTheme } from "./theme/ThemeContext";
import { NotificationProvider } from "./components/NotificationProvider";

// Import Inter font for modern look
import "@fontsource/inter/index.css";

// Theme wrapper that updates on theme mode change
function ThemedApp() {
  const { mode } = useThemeMode();
  const theme = getTheme(mode);

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

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ThemedApp />
    </ThemeModeProvider>
  </React.StrictMode>
);