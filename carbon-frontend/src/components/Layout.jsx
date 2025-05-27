// File: src/components/Layout.jsx
// Path: src/components/Layout.jsx
// Main app layout with header, sidebar, content, footer.

import React from "react";
import { Outlet } from "react-router-dom";
import Header from "./Header";
import Sidebar from "./Sidebar";
import Footer from "./Footer";
import { Box } from "@mui/material";
import { useThemeMode } from "../theme/ThemeContext";

export default function Layout() {
  const { resolvedMode } = useThemeMode();
  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: resolvedMode === "dark" ? "#191d23" : "#f8fafb" }}>
      <Header />
      <Box sx={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar />
        <Box
          component="main"
          sx={{
            flex: 1,
            p: { xs: 1, sm: 3 },
            minWidth: 0,
            bgcolor: resolvedMode === "dark" ? "#23272f" : "#fff",
            borderRadius: 3,
            boxShadow: resolvedMode === "dark"
              ? "0 2px 10px #0002"
              : "0 2px 18px #0001",
            mt: 2,
            mb: 2,
            mx: 2,
            transition: "background 0.2s"
          }}
        >
          <Outlet />
        </Box>
      </Box>
      <Footer />
    </Box>
  );
}