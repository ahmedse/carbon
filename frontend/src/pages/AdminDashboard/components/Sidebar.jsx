// File: frontend/src/pages/AdminDashboard/components/Sidebar.jsx

import React, { useState } from "react";
import { Drawer, Box, Tooltip, IconButton, Divider } from "@mui/material";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import PushPinIcon from "@mui/icons-material/PushPin";
import PushPinOutlinedIcon from "@mui/icons-material/PushPinOutlined";
import SidebarHeader from "./SidebarHeader";
import SidebarMenu from "./SidebarMenu";
import menuConfig from "./menuConfig";

const drawerWidth = 200;
const collapsedWidth = 56;
const headerHeight = 64;
const footerHeight = 48;
const sidebarFontSize = 14;
const sidebarIconSize = 20;

const Sidebar = ({
  open = true,
  onClose,
  currentProject = "Green HQ",
  currentCycle = "2024 Q2",
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const [fixed, setFixed] = useState(true);
  const [expandedMenu, setExpandedMenu] = useState("");

  const handleCollapse = () => setCollapsed((prev) => !prev);
  const handleFix = () => setFixed((prev) => !prev);

  return (
    <Drawer
      variant={fixed ? "permanent" : "temporary"}
      open={fixed ? true : open}
      onClose={onClose}
      sx={{
        width: collapsed ? collapsedWidth : drawerWidth,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: collapsed ? collapsedWidth : drawerWidth,
          boxSizing: "border-box",
          transition: "width 0.2s",
          overflowX: "hidden",
          background: "linear-gradient(135deg, #232526 0%, #414345 100%)",
          color: "#fff",
          borderRight: "none",
          minHeight: `calc(100vh - ${headerHeight}px - ${footerHeight}px)`,
          top: `${headerHeight}px`,
          height: `calc(100vh - ${headerHeight}px - ${footerHeight}px)`,
        },
        display: { xs: open ? "block" : "none", md: "block" },
        zIndex: 1201,
      }}
    >
      <SidebarHeader project={currentProject} cycle={currentCycle} />
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "space-between",
          p: 1,
          height: 40,
        }}
      >
        {!collapsed && (
          <Box component="span" sx={{ fontWeight: 600, fontSize: 15 }}>
            Menu
          </Box>
        )}
        <Box>
          <Tooltip title={collapsed ? "Expand" : "Collapse"}>
            <IconButton
              onClick={handleCollapse}
              sx={{
                color: "inherit",
                mr: 1,
                p: 0.5,
              }}
              size="small"
            >
              {collapsed ? <ChevronRightIcon fontSize="small" /> : <ChevronLeftIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
          <Tooltip title={fixed ? "Unpin" : "Pin"}>
            <IconButton
              onClick={handleFix}
              sx={{
                color: fixed ? "#4caf50" : "inherit",
                p: 0.5,
              }}
              size="small"
            >
              {fixed ? <PushPinIcon fontSize="small" /> : <PushPinOutlinedIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      <Divider sx={{ borderColor: "rgba(255,255,255,0.10)", mb: 1 }} />
      <SidebarMenu
        menuConfig={menuConfig}
        collapsed={collapsed}
        expandedMenu={expandedMenu}
        setExpandedMenu={setExpandedMenu}
        fontSize={sidebarFontSize}
        iconSize={sidebarIconSize}
      />
    </Drawer>
  );
};

export default Sidebar;