// src/pages/AdminDashboard/components/Topbar.jsx
import React from "react";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import MenuIcon from "@mui/icons-material/Menu";

const Topbar = ({ title = "Dashboard", drawerToggle }) => (
  <AppBar
    position="static"
    color="inherit"
    elevation={0}
    sx={{
      borderBottom: (theme) => `1px solid ${theme.palette.divider}`,
      zIndex: (theme) => theme.zIndex.drawer,
    }}
  >
    <Toolbar>
      {/* Sidebar toggle for mobile */}
      <IconButton
        color="inherit"
        edge="start"
        onClick={drawerToggle}
        sx={{ mr: 2, display: { md: "none" } }}
      >
        <MenuIcon />
      </IconButton>
      <Typography variant="h6" noWrap component="div">
        {title}
      </Typography>
    </Toolbar>
  </AppBar>
);

export default Topbar;