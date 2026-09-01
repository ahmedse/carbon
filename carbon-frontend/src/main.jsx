// File: src/main.jsx
import { createRoot } from "react-dom/client";
import React from "react";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/inter/800.css";
import "@fontsource/cairo/400.css";
import "@fontsource/cairo/500.css";
import "@fontsource/cairo/600.css";
import "@fontsource/cairo/700.css";
import { ThemeModeProvider } from "./theme/ThemeContext";
import ThemedApp from "./theme/ThemedApp";
import { createLogger } from "./utils/logger";
import { initWebVitals } from "./utils/webVitals";
import "./i18n";

console.debug("main.jsx: Rendering root app...");
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ThemedApp />
    </ThemeModeProvider>
  </React.StrictMode>
);

const webVitalsLogger = createLogger("web-vitals");
initWebVitals((metric) => webVitalsLogger.info("web-vital", metric));