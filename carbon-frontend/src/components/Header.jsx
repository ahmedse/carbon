// File: src/components/Header.jsx
// Clean, neutral header

import React, { useState } from "react";
import { AppBar, Toolbar, Typography, IconButton, Menu, MenuItem, Tooltip, Box, Avatar, Divider } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import aastLogo from "../assets/aast_carbon_logo_.jpg";
import { KeyboardArrowDown, Notifications, Settings, HelpOutline } from "@mui/icons-material";

export default function Header() {
  const { user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = useState(null);

  const handleMenu = (e) => setAnchorEl(e.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);
  const handleLogout = () => {
    logout();
    handleMenuClose();
  };

  const initials = user?.username?.slice(0, 2).toUpperCase() || "U";

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: "#fff",
        borderBottom: "1px solid #e5e7eb",
        color: "#111827",
      }}
    >
      <Toolbar sx={{ minHeight: 56, px: 2 }}>
        {/* Logo and title */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <img src={aastLogo} alt="Logo" style={{ height: 32, borderRadius: 6 }} />
          <Typography fontWeight={600} fontSize="1rem" color="#111827">
            AASTMT Carbon Platform
          </Typography>
        </Box>

        <Box sx={{ flexGrow: 1 }} />

        {/* Right side icons */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Tooltip title="Help">
            <IconButton size="small" sx={{ color: "#6b7280" }}>
              <HelpOutline sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Notifications">
            <IconButton size="small" sx={{ color: "#6b7280" }}>
              <Notifications sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Settings">
            <IconButton size="small" sx={{ color: "#6b7280" }}>
              <Settings sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>

          <Divider orientation="vertical" flexItem sx={{ mx: 1, height: 24, alignSelf: "center" }} />

          {/* User menu */}
          <Box
            onClick={handleMenu}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              cursor: "pointer",
              borderRadius: 2,
              px: 1,
              py: 0.5,
              "&:hover": { bgcolor: "#f3f4f6" },
            }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                fontSize: "0.8125rem",
                bgcolor: "#16a34a",
                color: "#fff",
                fontWeight: 600,
              }}
            >
              {initials}
            </Avatar>
            <Box sx={{ display: { xs: "none", sm: "block" } }}>
              <Typography fontSize="0.8125rem" fontWeight={500} color="#111827" lineHeight={1.2}>
                {user?.username}
              </Typography>
              <Typography fontSize="0.6875rem" color="#6b7280" lineHeight={1.2}>
                Administrator
              </Typography>
            </Box>
            <KeyboardArrowDown sx={{ color: "#9ca3af", fontSize: 18 }} />
          </Box>

          <Menu
            anchorEl={anchorEl}
            open={!!anchorEl}
            onClose={handleMenuClose}
            transformOrigin={{ horizontal: "right", vertical: "top" }}
            anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
            PaperProps={{
              sx: {
                mt: 1,
                minWidth: 180,
                borderRadius: 2,
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
              },
            }}
          >
            <Box sx={{ px: 2, py: 1.5 }}>
              <Typography fontSize="0.8125rem" fontWeight={600} color="#111827">
                {user?.username}
              </Typography>
              <Typography fontSize="0.75rem" color="#6b7280">
                {user?.email || "admin@example.com"}
              </Typography>
            </Box>
            <Divider />
            <MenuItem onClick={handleMenuClose} sx={{ fontSize: "0.8125rem", py: 1 }}>
              Profile Settings
            </MenuItem>
            <MenuItem onClick={handleMenuClose} sx={{ fontSize: "0.8125rem", py: 1 }}>
              Preferences
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleLogout} sx={{ fontSize: "0.8125rem", py: 1, color: "#dc2626" }}>
              Sign out
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
}