// File: src/components/Sidebar.jsx
// Sidebar with Toolbar offset, robust project switcher, auto-hide, pin, and tooltips.

import React, { useState } from "react";
import {
  Drawer, Box, Typography, Tooltip, Divider, IconButton, Select, MenuItem, Toolbar
} from "@mui/material";
import { ChevronLeft, ChevronRight, PushPin, PushPinOutlined } from "@mui/icons-material";
import { useTheme } from "@mui/material/styles";
import { useAuth } from "../auth/AuthContext";
import SidebarMenu from "./SidebarMenu";

const drawerWidth = 210;
const miniWidth = 54;

export default function Sidebar() {
  const { user, currentContext, setContext } = useAuth();
  const theme = useTheme();

  const [open, setOpen] = useState(() => {
    const pinned = localStorage.getItem("sidebarPinned");
    return pinned ? pinned === "true" : true;
  });
  const [pinned, setPinned] = useState(() => {
    const pinned = localStorage.getItem("sidebarPinned");
    return pinned ? pinned === "true" : true;
  });

  // Extract distinct projects from user roles
  const projects = Array.from(
    new Map(
      (user?.roles || [])
        .filter(r => r.project_id && r.project)
        .map(r => [String(r.project_id), { id: r.project_id, name: r.project }])
    ).values()
  );

  const handleProjectChange = (e) => {
    const selectedValue = e.target.value;
    const selectedId = Number(selectedValue);
    console.log("Selected value:", selectedValue, "typeof:", typeof selectedValue);
    console.log("Converted to number:", selectedId, "typeof:", typeof selectedId);
    const proj = projects.find(p => p.id === selectedId);
    console.log("Matched project:", proj);
    if (proj) {
      setContext({
        project_id: proj.id,
        project: proj.name,
        context_type: "project",
      });
    }
  };
  
  const toggleSidebar = () => {
    if (pinned) return;
    setOpen((prev) => !prev);
  };

  const togglePin = () => {
    setPinned((prev) => {
      localStorage.setItem("sidebarPinned", (!prev).toString());
      if (!prev) setOpen(true);
      return !prev;
    });
  };

  if (!projects.length) return null;
  const showDropdown = projects.length > 1;
  const projectName = (() => {
    const activeProj = projects.find(p =>
      currentContext?.project_id && String(p.id) === String(currentContext.project_id)
    );
    return activeProj?.name || projects[0].name;
  })();

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
          showDropdown ? (
            <Select
              value={currentContext?.project_id || projects[0].id}
              onChange={handleProjectChange}
              size="small"
              variant="standard"
              disableUnderline
              sx={{
                fontWeight: 700,
                fontSize: 13,
                minWidth: 120,
                ml: 1
              }}
              MenuProps={{ PaperProps: { sx: { minWidth: 160 } } }}
            >
              {projects.map(p => (
                <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
              ))}
            </Select>
          ) : (
            <Typography fontWeight={700} fontSize={12} color="primary" sx={{ pl: 1 }}>
              {projectName}
            </Typography>
          )
        ) : (
          <Tooltip title={projectName || "Project"} placement="right" arrow>
            <Typography fontWeight={700} fontSize={14} color="primary">
              {projectName?.[0] || "-"}
            </Typography>
          </Tooltip>
        )}
        <Box>
          <Tooltip title={pinned ? "Unpin Sidebar" : "Pin Sidebar"}>
            <span>
              <IconButton size="small" onClick={togglePin}>
                {pinned ? <PushPin fontSize="small" /> : <PushPinOutlined fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={open ? "Collapse Sidebar" : "Expand Sidebar"}>
            <span>
              <IconButton size="small" onClick={toggleSidebar} disabled={pinned}>
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