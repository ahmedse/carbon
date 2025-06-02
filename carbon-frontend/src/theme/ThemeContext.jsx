// File: src/theme/ThemeContext.jsx
// Five distinct themes: environmental, ocean, forest, sunrise, dark. Small fonts.

import React, { createContext, useContext, useState, useEffect } from "react";
import { createTheme } from "@mui/material/styles";

const palettes = {
  environmental: {
    primary: { main: "#1bb36f" },
    secondary: { main: "#26a69a" },
    background: { default: "#f6f8fa", paper: "#fff" },
    text: { primary: "#212b36", secondary: "#637381" },
  },
  ocean: {
    primary: { main: "#1976d2" },
    secondary: { main: "#00bcd4" },
    background: { default: "#e3f2fd", paper: "#f5fafd" },
    text: { primary: "#154360", secondary: "#387ca3" },
  },
  forest: {
    primary: { main: "#33691e" },
    secondary: { main: "#8d6e63" },
    background: { default: "#eef7f0", paper: "#e8f5e9" },
    text: { primary: "#204421", secondary: "#6d8c68" },
  },
  sunrise: {
    primary: { main: "#ff9800" },
    secondary: { main: "#ffd600" },
    background: { default: "#fff8e1", paper: "#fffde7" },
    text: { primary: "#a65c00", secondary: "#bfa345" },
  },
  dark: {
    primary: { main: "#00bfae" },
    secondary: { main: "#0ff1ce" },
    background: { default: "#181c1f", paper: "#23272b" },
    text: { primary: "#f6f8fa", secondary: "#b3b8c3" },
  }
};

const fontFamily = [
  "InterVariable",
  "Inter",
  "-apple-system",
  "BlinkMacSystemFont",
  "Segoe UI",
  "Roboto",
  "Helvetica Neue",
  "Arial",
  "sans-serif"
].join(",");

const themeOrder = ["environmental", "ocean", "forest", "sunrise", "dark"];

const ThemeModeContext = createContext();

export function ThemeModeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    const stored = localStorage.getItem("themeMode");
    return stored && palettes[stored] ? stored : "environmental";
  });

  // Cycle through all themes in order
  const toggle = () => {
    setMode(prev => {
      const idx = themeOrder.indexOf(prev);
      return themeOrder[(idx + 1) % themeOrder.length];
    });
  };

  useEffect(() => {
    localStorage.setItem("themeMode", mode);
  }, [mode]);

  return (
    <ThemeModeContext.Provider value={{ mode, toggle }}>
      {children}
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode() {
  return useContext(ThemeModeContext);
}

export const getTheme = (mode) =>
  createTheme({
    palette: { ...palettes[mode] || palettes.environmental },
    typography: {
      fontFamily,
      fontSize: 11,
      h6: { fontWeight: 700, fontSize: 14, letterSpacing: 0.3 },
      h4: { fontWeight: 800, fontSize: 16 },
      body1: { fontSize: 11 },
      body2: { fontSize: 12 }
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: { borderRadius: 9, textTransform: "none", fontWeight: 600, fontSize: 12 }
        }
      },
      MuiListItemText: {
        styleOverrides: {
          primary: { fontSize: 12, fontWeight: 500 },
        }
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { fontSize: 10, borderRadius: 6 }
        }
      }
    }
  });