// File: src/components/Layout.jsx
// Modern layout with resizable sidebar and AI Copilot panel

import React, { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import Header from "./Header";
import Sidebar from "./Sidebar";
import AICopilotPanel from "./ai/AICopilotPanel";
import { Box, IconButton, Tooltip } from "@mui/material";
import { ChevronLeft, ChevronRight } from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";

const MIN_SIDEBAR_WIDTH = 200;
const MAX_SIDEBAR_WIDTH = 400;
const COLLAPSED_WIDTH = 56;
const DEFAULT_WIDTH = 260;

const MIN_AI_PANEL_WIDTH = 320;
const MAX_AI_PANEL_WIDTH = 600;
const AI_PANEL_COLLAPSED_WIDTH = 60;
const DEFAULT_AI_PANEL_WIDTH = 360;

export default function Layout() {
  const { context } = useAuth();
  
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const stored = localStorage.getItem("sidebarWidth");
    return stored ? parseInt(stored, 10) : DEFAULT_WIDTH;
  });
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sidebarCollapsed") === "true";
  });
  const [isResizing, setIsResizing] = useState(false);

  // AI Panel state
  const [aiPanelWidth, setAIPanelWidth] = useState(() => {
    const stored = localStorage.getItem("aiPanelWidth");
    return stored ? parseInt(stored, 10) : DEFAULT_AI_PANEL_WIDTH;
  });
  const [aiPanelCollapsed, setAIPanelCollapsed] = useState(() => {
    return localStorage.getItem("aiPanelCollapsed") === "true";
  });
  const [isResizingAI, setIsResizingAI] = useState(false);

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

  // AI Panel resize handler
  const handleAIPanelMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsResizingAI(true);
    
    const startX = e.clientX;
    const startWidth = aiPanelWidth;

    const handleMouseMove = (e) => {
      const newWidth = startWidth + (startX - e.clientX);
      if (newWidth >= MIN_AI_PANEL_WIDTH && newWidth <= MAX_AI_PANEL_WIDTH) {
        setAIPanelWidth(newWidth);
        localStorage.setItem("aiPanelWidth", newWidth.toString());
      }
    };

    const handleMouseUp = () => {
      setIsResizingAI(false);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }, [aiPanelWidth]);

  const toggleAIPanel = () => {
    setAIPanelCollapsed((prev) => {
      localStorage.setItem("aiPanelCollapsed", (!prev).toString());
      return !prev;
    });
  };

  const currentWidth = collapsed ? COLLAPSED_WIDTH : sidebarWidth;
  const currentAIWidth = aiPanelCollapsed ? AI_PANEL_COLLAPSED_WIDTH : aiPanelWidth;

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

        {/* AI Panel Resize Handle */}
        {!aiPanelCollapsed && (
          <Box
            onMouseDown={handleAIPanelMouseDown}
            sx={{
              width: 4,
              cursor: "col-resize",
              bgcolor: isResizingAI ? "primary.main" : "transparent",
              "&:hover": { bgcolor: "primary.light" },
              transition: "background-color 0.15s",
              flexShrink: 0,
            }}
          />
        )}

        {/* AI Panel Collapse Toggle */}
        <Tooltip title={aiPanelCollapsed ? "Expand AI Copilot" : "Collapse AI Copilot"} placement="left">
          <IconButton
            onClick={toggleAIPanel}
            size="small"
            sx={{
              position: "absolute",
              right: currentAIWidth - 12,
              top: 72,
              zIndex: 100,
              width: 24,
              height: 24,
              bgcolor: "#fff",
              border: "1px solid #e5e7eb",
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
              "&:hover": { bgcolor: "#f9fafb" },
              transition: isResizingAI ? "none" : "right 0.2s ease",
            }}
          >
            {aiPanelCollapsed ? <ChevronLeft sx={{ fontSize: 16 }} /> : <ChevronRight sx={{ fontSize: 16 }} />}
          </IconButton>
        </Tooltip>

        {/* AI Copilot Panel */}
        <Box
          sx={{
            width: currentAIWidth,
            minWidth: currentAIWidth,
            maxWidth: currentAIWidth,
            transition: isResizingAI ? "none" : "width 0.2s ease",
            bgcolor: "#fff",
            borderLeft: aiPanelCollapsed ? "none" : "1px solid #e5e7eb",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <AICopilotPanel 
            projectId={context?.project_id}
            collapsed={aiPanelCollapsed}
          />
        </Box>
      </Box>
    </Box>
  );
}