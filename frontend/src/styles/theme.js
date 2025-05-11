import { createTheme } from "@mui/material/styles";

const fontFamily = [
  "'Inter'", "'Montserrat'", "'Roboto'", "'Segoe UI'", "Arial", "sans-serif"
].join(",");

const getDesignTokens = (mode) => ({
  palette: {
    mode,
    primary: { main: "#388e3c", contrastText: "#fff" },
    secondary: { main: "#1976d2", contrastText: "#fff" },
    ...(mode === "light"
      ? {
          background: { default: "#f6faf6", paper: "#fff" },
          text: { primary: "#232323", secondary: "#5f5f5f" },
        }
      : {
          background: { default: "#161b1a", paper: "#222b23" },
          text: { primary: "#f1f7f2", secondary: "#b5ccb5" },
        }),
  },
  typography: {
    fontFamily,
    fontSize: 14,
    h5: { fontWeight: 500, letterSpacing: 1, fontSize: "1.0rem" },
    h6: { fontWeight: 500, letterSpacing: 1, fontSize: ".9rem" },
    body1: { fontSize: "0.90rem" },
    body2: { fontSize: "0.80rem" },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: "none",
          borderBottom: mode === "light"
            ? "1px solid #e0e0e0"
            : "1px solid #223322",
        }
      }
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiButton: {
      styleOverrides: {
        root: { textTransform: "none", fontWeight: 600, borderRadius: 8 }
      }
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow:
            mode === "light"
              ? "0 2px 16px 0 rgba(56,142,60,0.04)"
              : "0 2px 16px 0 rgba(25,118,210,0.10)",
        }
      }
    }
  }
});

export default getDesignTokens;