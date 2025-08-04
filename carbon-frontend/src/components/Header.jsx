// File: src/components/Header.jsx
// Header with logo, account, and theme switcher for 3 custom themes.

import React, { useState } from "react";
import { AppBar, Toolbar, Typography, IconButton, Menu, MenuItem, Tooltip, Box } from "@mui/material";
import { useThemeMode } from "../theme/ThemeContext";
import { useAuth } from "../auth/AuthContext";
import aastLogo from "../assets/aast_carbon_logo_.jpg";

// Use distinct icons for each theme
import { Yard, Water, Park, WbSunny, NightsStay, Person } from "@mui/icons-material";
const themeLabels = {
  environmental: { icon: <Yard />, label: "Environmental" },
  ocean: { icon: <Water />, label: "Ocean" },
  forest: { icon: <Park />, label: "Forest" },
  sunrise: { icon: <WbSunny />, label: "Sunrise" },
  dark: { icon: <NightsStay />, label: "Dark" },
};

export default function Header() {
  const { user, logout } = useAuth();
  const { mode, toggle } = useThemeMode();
  const [anchorEl, setAnchorEl] = useState(null);

  // Defensive fallback in case mode is not as expected
  const currentTheme = themeLabels[mode] || themeLabels.environmental;

  const handleMenu = (e) => setAnchorEl(e.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);
  const handleLogout = () => {
    logout();
    handleMenuClose();
  };

  return (
    <AppBar
      position="sticky"
      color="primary"
      elevation={0}
      sx={{
        zIndex: (t) => t.zIndex.drawer + 1,
        bgcolor: (t) => t.palette.primary.main,
      }}
    >
      <Toolbar variant="dense" sx={{ minHeight: 52 }}>
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <img src={aastLogo} alt="Logo" style={{ height: 32, marginRight: 12, borderRadius: 5 }} />
          <Typography variant="h6" fontWeight={800} sx={{ letterSpacing: 0.5 }}>
            AASTMT Carbon Platform
          </Typography>
        </Box>
        <Box sx={{ flexGrow: 1 }} />
        <Tooltip title={`Theme: ${currentTheme.label}`}>
          <span>
            <IconButton color="inherit" onClick={toggle} sx={{ mx: 1 }}>
              {currentTheme.icon}
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title={user?.username || "Account"}>
          <IconButton color="inherit" onClick={handleMenu}>
            <Person />
          </IconButton>
        </Tooltip>
        <Menu anchorEl={anchorEl} open={!!anchorEl} onClose={handleMenuClose}>
          <MenuItem disabled>{user?.username || "User"}</MenuItem>
          <MenuItem onClick={handleLogout}>Logout</MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
}