// src/components/Sidebar.jsx
import React, { useState } from "react";
import {
  Drawer, Box, Typography, Tooltip, Divider, IconButton, Toolbar
} from "@mui/material";
import { ChevronLeft, ChevronRight, PushPin, PushPinOutlined } from "@mui/icons-material";
import { useTheme } from "@mui/material/styles";
import { useAuth } from "../auth/AuthContext";
import SidebarMenu from "./SidebarMenu";

const drawerWidth = 210;
const miniWidth = 54;

export default function Sidebar() {
  const theme = useTheme();
  const { projects, context, loading } = useAuth();

  const [open, setOpen] = useState(() => localStorage.getItem("sidebarPinned") !== "false");
  const [pinned, setPinned] = useState(() => localStorage.getItem("sidebarPinned") !== "false");

  if (loading) return null;
  if (!projects.length) {
    return (
      <Box sx={{ p: 3, textAlign: "center" }}>
        <Typography color="error" fontWeight={600} gutterBottom>
          No projects found.
        </Typography>
        <Typography variant="body2">
          Please contact your administrator.
        </Typography>
      </Box>
    );
  }

  const project = projects.find(p => String(p.id) === String(context?.projectId)) || projects[0];

  return (
    <Drawer
      variant="permanent"
      open={open}
      sx={{
        width: open ? drawerWidth : miniWidth,
        flexShrink: 0,
        zIndex: theme.zIndex.appBar - 1,
        [`& .MuiDrawer-paper`]: {
          width: open ? drawerWidth : miniWidth,
          boxSizing: "border-box",
          overflowX: "hidden",
          transition: "width 0.22s cubic-bezier(0.4,0,0.2,1)",
          bgcolor: theme.palette.background.paper,
          borderRight: `1px solid ${theme.palette.divider}`,
        },
      }}
    >
      <Toolbar variant="dense" />
      <Box sx={{
        display: "flex",
        alignItems: "center",
        px: 1,
        py: 1.5,
        justifyContent: open ? "space-between" : "center"
      }}>
        {open ? (
          <Typography fontWeight={700} fontSize={13} color="primary" sx={{ ml: 1 }}>
            {project.name}
          </Typography>
        ) : (
          <Tooltip title={project.name || "Project"} placement="right" arrow>
            <Typography fontWeight={700} fontSize={14} color="primary">
              {project.name?.[0] || "-"}
            </Typography>
          </Tooltip>
        )}
        <Box>
          <Tooltip title={pinned ? "Unpin Sidebar" : "Pin Sidebar"}>
            <span>
              <IconButton size="small" onClick={() => {
                setPinned(v => {
                  localStorage.setItem("sidebarPinned", (!v).toString());
                  if (!v) setOpen(true);
                  return !v;
                });
              }}>
                {pinned ? <PushPin fontSize="small" /> : <PushPinOutlined fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={open ? "Collapse Sidebar" : "Expand Sidebar"}>
            <span>
              <IconButton size="small" onClick={() => { if (!pinned) setOpen(v => !v); }} disabled={pinned}>
                {open ? <ChevronLeft fontSize="small" /> : <ChevronRight fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>
      <Divider />
      <SidebarMenu open={open} />
    </Drawer>
  );
}