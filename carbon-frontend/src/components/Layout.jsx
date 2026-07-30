// File: src/components/Layout.jsx
// Modern layout with resizable sidebar and AI Copilot panel

import React, { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import HeaderEnhanced from "./HeaderEnhanced";
import Sidebar from "./Sidebar";
import { Box, IconButton, Tooltip, Alert } from "@mui/material";
import { ChevronLeft, ChevronRight, LocationOn as LocationOnIcon } from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";

const MIN_SIDEBAR_WIDTH = 200;
const MAX_SIDEBAR_WIDTH = 400;
const COLLAPSED_WIDTH = 56;
const DEFAULT_WIDTH = 260;

export default function Layout() {
  const { context, availablePerspectives, currentPerspective, _user } = useAuth();
  
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const stored = localStorage.getItem("sidebarWidth");
    return stored ? parseInt(stored, 10) : DEFAULT_WIDTH;
  });
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sidebarCollapsed") === "true";
  });
  const [isResizing, setIsResizing] = useState(false);

  // Determine if user is admin and get org unit info for banner
  const isAdmin = availablePerspectives?.includes('admin');
  const _isDataEntry = currentPerspective === 'data_entry';
  
  // Get user's primary org unit name from context
  const userOrgUnitName = context?.org_units?.[0]?.name || null;

  const showScopeBanner = !isAdmin && userOrgUnitName;

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
    <Box sx={{ display: "flex", flexDirection: "column", height: "100vh", bgcolor: 'background.default', overflow: "hidden" }}>
      <HeaderEnhanced collapsed={collapsed} onToggleCollapse={toggleCollapse} />
      <Box sx={{ display: "flex", flex: 1, minHeight: 0, overflow: "hidden", isolation: "isolate" }}>
        {/* Sidebar */}
        <Box
          sx={{
            width: currentWidth,
            minWidth: currentWidth,
            maxWidth: currentWidth,
            transition: isResizing ? "none" : "width 0.2s ease",
            bgcolor: 'background.paper',
            borderRight: '1px solid',
            borderColor: 'divider',
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
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
              "&:hover": { bgcolor: 'action.hover' },
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
            minHeight: 0,
            bgcolor: 'background.paper',
            overflow: "hidden",
          }}
        >
          <Box sx={{ flex: 1, p: 3, overflow: "auto", overscrollBehavior: "contain" }}>
            {/* Scope banner for data-entry users */}
            {showScopeBanner && (
              <Alert
                severity="info"
                icon={<LocationOnIcon />}
                sx={{
                  mb: 2,
                  borderRadius: 1,
                  backgroundColor: 'action.hover',
                  color: 'text.primary',
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                You are viewing: <strong>{userOrgUnitName}</strong>
              </Alert>
            )}
            <Outlet />
          </Box>
        </Box>

      </Box>
    </Box>
  );
}