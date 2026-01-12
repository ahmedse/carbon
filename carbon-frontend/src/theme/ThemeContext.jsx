// File: src/theme/ThemeContext.jsx
// Clean, professional themes with compact styling

import React, { createContext, useContext, useState, useEffect } from "react";
import { createTheme } from "@mui/material/styles";

const palettes = {
  environmental: {
    primary: { main: "#16a34a", light: "#22c55e", dark: "#15803d" },
    secondary: { main: "#64748b" },
    background: { default: "#f8fafc", paper: "#ffffff" },
    text: { primary: "#1e293b", secondary: "#64748b" },
    divider: "#e2e8f0",
  },
  ocean: {
    primary: { main: "#0284c7", light: "#38bdf8", dark: "#0369a1" },
    secondary: { main: "#64748b" },
    background: { default: "#f0f9ff", paper: "#ffffff" },
    text: { primary: "#0c4a6e", secondary: "#64748b" },
    divider: "#e0f2fe",
  },
  forest: {
    primary: { main: "#166534", light: "#22c55e", dark: "#14532d" },
    secondary: { main: "#78716c" },
    background: { default: "#f0fdf4", paper: "#ffffff" },
    text: { primary: "#14532d", secondary: "#6b7280" },
    divider: "#dcfce7",
  },
  sunrise: {
    primary: { main: "#ea580c", light: "#fb923c", dark: "#c2410c" },
    secondary: { main: "#78716c" },
    background: { default: "#fffbeb", paper: "#ffffff" },
    text: { primary: "#7c2d12", secondary: "#78716c" },
    divider: "#fef3c7",
  },
  dark: {
    primary: { main: "#10b981", light: "#34d399", dark: "#059669" },
    secondary: { main: "#94a3b8" },
    background: { default: "#0f172a", paper: "#1e293b" },
    text: { primary: "#f1f5f9", secondary: "#94a3b8" },
    divider: "#334155",
  }
};

const fontFamily = [
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

  const resolvedMode = mode === "dark" ? "dark" : "light";

  return (
    <ThemeModeContext.Provider value={{ mode, toggle, resolvedMode }}>
      {children}
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode() {
  return useContext(ThemeModeContext);
}

export const getTheme = (mode) =>
  createTheme({
    palette: {
      mode: mode === "dark" ? "dark" : "light",
      ...palettes[mode] || palettes.environmental
    },
    typography: {
      fontFamily,
      fontSize: 13,
      h1: { fontWeight: 700, fontSize: "1.75rem", lineHeight: 1.3 },
      h2: { fontWeight: 700, fontSize: "1.5rem", lineHeight: 1.35 },
      h3: { fontWeight: 600, fontSize: "1.25rem", lineHeight: 1.4 },
      h4: { fontWeight: 600, fontSize: "1.125rem", lineHeight: 1.4 },
      h5: { fontWeight: 600, fontSize: "1rem", lineHeight: 1.5 },
      h6: { fontWeight: 600, fontSize: "0.875rem", lineHeight: 1.5 },
      body1: { fontSize: "0.875rem", lineHeight: 1.5 },
      body2: { fontSize: "0.8125rem", lineHeight: 1.5 },
      button: { fontWeight: 500, fontSize: "0.8125rem" },
    },
    shape: {
      borderRadius: 8,
    },
    shadows: [
      "none",
      "0 1px 2px 0 rgb(0 0 0 / 0.05)",
      "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
      "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
      ...Array(20).fill("0 10px 15px -3px rgb(0 0 0 / 0.1)"),
    ],
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            scrollbarWidth: "thin",
            "&::-webkit-scrollbar": { width: "6px", height: "6px" },
            "&::-webkit-scrollbar-thumb": { backgroundColor: "#94a3b8", borderRadius: "3px" },
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 6,
            textTransform: "none",
            fontWeight: 500,
            boxShadow: "none",
            "&:hover": { boxShadow: "none" },
          },
          sizeSmall: { padding: "4px 10px", fontSize: "0.75rem" },
          sizeMedium: { padding: "6px 14px" },
        },
        defaultProps: { disableElevation: true },
      },
      MuiPaper: {
        styleOverrides: {
          root: { backgroundImage: "none" },
        },
        defaultProps: { elevation: 0 },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            border: "1px solid",
            borderColor: palettes[mode]?.divider || "#e2e8f0",
          },
        },
        defaultProps: { elevation: 0 },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { padding: "10px 14px", fontSize: "0.8125rem" },
          head: { fontWeight: 600, backgroundColor: "transparent" },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 6,
            marginBottom: 2,
            "&.Mui-selected": {
              backgroundColor: mode === "dark" ? "rgba(16, 185, 129, 0.15)" : "rgba(22, 163, 74, 0.08)",
            },
          },
        },
      },
      MuiListItemText: {
        styleOverrides: {
          primary: { fontSize: "0.8125rem", fontWeight: 500 },
          secondary: { fontSize: "0.75rem" },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { fontSize: "0.75rem", borderRadius: 4, padding: "4px 8px" },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: { border: "none" },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: { boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1)" },
        },
      },
      MuiDataGrid: {
        styleOverrides: {
          root: {
            border: "none",
            fontSize: "0.8125rem",
            "& .MuiDataGrid-columnHeaders": {
              backgroundColor: mode === "dark" ? "#1e293b" : "#f8fafc",
              borderBottom: "1px solid",
              borderColor: palettes[mode]?.divider || "#e2e8f0",
            },
            "& .MuiDataGrid-cell": {
              borderBottom: "1px solid",
              borderColor: palettes[mode]?.divider || "#e2e8f0",
            },
            "& .MuiDataGrid-row:hover": {
              backgroundColor: mode === "dark" ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.02)",
            },
          },
        },
      },
      MuiTextField: {
        defaultProps: { size: "small" },
        styleOverrides: {
          root: { "& .MuiOutlinedInput-root": { borderRadius: 6 } },
        },
      },
      MuiSelect: {
        defaultProps: { size: "small" },
      },
      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 500, fontSize: "0.75rem" },
          sizeSmall: { height: 22 },
        },
      },
    },
  });