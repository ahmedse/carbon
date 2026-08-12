// File: src/main.jsx
import { createRoot } from "react-dom/client";
import React from "react";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/inter/800.css";
import { ThemeModeProvider } from "./theme/ThemeContext";
import ThemedApp from "./theme/ThemedApp";

console.debug("main.jsx: Rendering root app...");
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ThemedApp />
    </ThemeModeProvider>
  </React.StrictMode>
);