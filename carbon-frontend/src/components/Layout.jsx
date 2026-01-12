// File: src/components/Layout.jsx
// Modern layout with resizable sidebar

import React, { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import Header from "./Header";
import Sidebar from "./Sidebar";
import { Box, IconButton, Tooltip } from "@mui/material";
import { ChevronLeft, ChevronRight } from "@mui/icons-material";

const MIN_SIDEBAR_WIDTH = 200;
const MAX_SIDEBAR_WIDTH = 400;
const COLLAPSED_WIDTH = 56;
const DEFAULT_WIDTH = 260;

export default function Layout() {
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const stored = localStorage.getItem("sidebarWidth");
    return stored ? parseInt(stored, 10) : DEFAULT_WIDTH;
  });
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sidebarCollapsed") === "true";
  });
  const [isResizing, setIsResizing] = useState(false);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsResizing(true);
    
    const startX = e.clientX;
    const startWidth = sidebarWidth;

    const handleMouseMove = (e) => {
      const newWidth = startWidth + (e.clientX - startX);
      if (newWidth >= MIN_SIDEBAR_WIDTH && newWidth <= MAX_SIDEBAR_WIDTH) {
        setSidebarWidth(newWidth);
        localStorage.setItem("sidebarWidth", newWidth.toString());
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }, [sidebarWidth]);

  const toggleCollapse = () => {
    setCollapsed((prev) => {
      localStorage.setItem("sidebarCollapsed", (!prev).toString());
      return !prev;
    });
  };

  const currentWidth = collapsed ? COLLAPSED_WIDTH : sidebarWidth;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: "#f5f5f5" }}>
      <Header collapsed={collapsed} onToggleCollapse={toggleCollapse} />
      <Box sx={{ display: "flex", flex: 1, minHeight: 0, overflow: "hidden" }}>
        {/* Sidebar */}
        <Box
          sx={{
            width: currentWidth,
            minWidth: currentWidth,
            maxWidth: currentWidth,
            transition: isResizing ? "none" : "width 0.2s ease",
            bgcolor: "#fff",
            borderRight: "1px solid #e5e7eb",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <Sidebar collapsed={collapsed} />
        </Box>

        {/* Resize handle */}
        {!collapsed && (
          <Box
            onMouseDown={handleMouseDown}
            sx={{
              width: 4,
              cursor: "col-resize",
              bgcolor: isResizing ? "primary.main" : "transparent",
              "&:hover": { bgcolor: "primary.light" },
              transition: "background-color 0.15s",
              flexShrink: 0,
            }}
          />
        )}

        {/* Collapse toggle button */}
        <Tooltip title={collapsed ? "Expand sidebar" : "Collapse sidebar"} placement="right">
          <IconButton
            onClick={toggleCollapse}
            size="small"
            sx={{
              position: "absolute",
              left: currentWidth - 12,
              top: 72,
              zIndex: 100,
              width: 24,
              height: 24,
              bgcolor: "#fff",
              border: "1px solid #e5e7eb",
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
              "&:hover": { bgcolor: "#f9fafb" },
              transition: isResizing ? "none" : "left 0.2s ease",
            }}
          >
            {collapsed ? <ChevronRight sx={{ fontSize: 16 }} /> : <ChevronLeft sx={{ fontSize: 16 }} />}
          </IconButton>
        </Tooltip>

        {/* Main content */}
        <Box
          component="main"
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minWidth: 0,
            bgcolor: "#fff",
            overflow: "auto",
          }}
        >
          <Box sx={{ flex: 1, p: 3 }}>
            <Outlet />
          </Box>
        </Box>
      </Box>
    </Box>
  );
}