// src/components/Sidebar.jsx
// Clean sidebar with collapsible support

import React from "react";
import { Box, Typography, Tooltip, Divider } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import SidebarMenu from "./SidebarMenu";

export default function Sidebar({ collapsed = false }) {
  const { projects, context, loading } = useAuth();

  if (loading) return null;

  if (!projects.length) {
    return (
      <Box sx={{ p: 2, textAlign: "center" }}>
        <Typography color="error" fontSize="0.75rem" fontWeight={600}>
          No projects
        </Typography>
      </Box>
    );
  }

  const project = projects.find(p => String(p.id) === String(context?.projectId)) || projects[0];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Project header */}
      <Box
        sx={{
          px: collapsed ? 1 : 2,
          py: 1.5,
          borderBottom: "1px solid #e5e7eb",
          minHeight: 48,
          display: "flex",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "flex-start",
        }}
      >
        {collapsed ? (
          <Tooltip title={project.name} placement="right" arrow>
            <Box
              sx={{
                width: 32,
                height: 32,
                borderRadius: 1,
                bgcolor: "#16a34a",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: "0.875rem",
              }}
            >
              {project.name?.[0] || "P"}
            </Box>
          </Tooltip>
        ) : (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Box
              sx={{
                width: 32,
                height: 32,
                borderRadius: 1,
                bgcolor: "#16a34a",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: "0.875rem",
                flexShrink: 0,
              }}
            >
              {project.name?.[0] || "P"}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography
                fontSize="0.8125rem"
                fontWeight={600}
                color="#111827"
                noWrap
              >
                {project.name}
              </Typography>
              <Typography fontSize="0.6875rem" color="#6b7280" noWrap>
                Carbon Project
              </Typography>
            </Box>
          </Box>
        )}
      </Box>

      {/* Menu */}
      <Box sx={{ flex: 1, overflow: "auto", py: 1 }}>
        <SidebarMenu collapsed={collapsed} />
      </Box>
    </Box>
  );
}