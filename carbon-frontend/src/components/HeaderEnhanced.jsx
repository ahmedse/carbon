// carbon-frontend/src/components/HeaderEnhanced.jsx
// Enhanced header with user menu (based on Gigacast pattern)

import React, { useState } from "react";
import { AppBar, Toolbar, Typography, IconButton, Menu, MenuItem, Tooltip, Box, Avatar, Divider, Popover, Tabs, Tab, useTheme } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import { useNavigate } from "react-router-dom";
import { 
  INSTANCE_LOGO, 
  INSTANCE_NAME, 
  PLATFORM_NAME 
} from "../config/branding";
import { 
  KeyboardArrowDown, 
  Notifications, 
  Settings, 
  HelpOutline,
  Logout as LogoutIcon,
  Settings as SettingsIcon,
  Person as PersonIcon,
  Keyboard as KeyboardIcon,
  DarkMode,
  LightMode
} from "@mui/icons-material";
import { useThemeMode } from "../theme/useThemeMode";

const PERSPECTIVE_LABELS = {
  data_entry: 'Data Entry',
  dashboards: 'Dashboards',
  admin: 'Admin',
};

function MenuRow({ icon: _Icon, label, onClick, danger, disabled }) {
  return (
    <Box
      onClick={onClick}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        px: 1.5,
        py: 0.875,
        cursor: disabled ? "not-allowed" : "pointer",
        borderRadius: 0.75,
        mx: 0.5,
        color: danger ? "error.main" : disabled ? "text.disabled" : "text.secondary",
        opacity: disabled ? 0.6 : 1,
        "&:hover": disabled ? {} : { 
          bgcolor: "action.hover", 
          color: danger ? "error.main" : "text.primary" 
        },
        transition: "background 120ms",
      }}
    >
      <_Icon sx={{ fontSize: 13, flexShrink: 0 }} />
      <Typography sx={{ fontSize: "0.75rem" }}>{label}</Typography>
    </Box>
  );
}

function RoleBadge({ role, theme }) {
  const ROLE_COLOR = {
    admins_group: { bg: `${theme.palette.error.main}15`, text: "error.main" },
    dataowners_group: { bg: `${theme.palette.primary.main}15`, text: "primary.main" },
    auditors_group: { bg: `${theme.palette.warning.main}15`, text: "warning.main" },
  };
  const s = ROLE_COLOR[role] || { bg: `${theme.palette.text.secondary}15`, text: "text.secondary" };
  return (
    <Box sx={{ display: "inline-flex", px: 0.75, py: 0.125, borderRadius: 0.5, bgcolor: s.bg }}>
      <Typography sx={{ fontSize: "0.5625rem", fontWeight: 700, color: s.text, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {role.replace("_group", "").replace("_", " ")}
      </Typography>
    </Box>
  );
}

export default function HeaderEnhanced() {
  const { user, logout, availablePerspectives, currentPerspective, setPerspective } = useAuth();
  const { mode, toggle } = useThemeMode();
  const theme = useTheme();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);

  const initials = user?.username?.slice(0, 2).toUpperCase() || "U";
  const primaryRole = user?.roles?.[0]?.role;

  const handleMenuOpen = (e) => setAnchorEl(e.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  const handleLogout = () => {
    handleMenuClose();
    logout();
  };

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: "background.paper",
        borderBottom: `1px solid ${theme.palette.divider}`,
        color: "text.primary",
      }}
    >
      <Toolbar sx={{ minHeight: 56, px: 2 }}>
        {/* Logo and title */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <img src={INSTANCE_LOGO} alt="Logo" style={{ height: 32, borderRadius: 6 }} />
          <Typography fontWeight={600} fontSize="1rem" color="text.primary">
            {INSTANCE_NAME ? `${INSTANCE_NAME} · ${PLATFORM_NAME}` : PLATFORM_NAME}
          </Typography>
        </Box>

        <Box sx={{ flexGrow: 1 }} />

        {/* Perspective tabs - show only if user has multiple perspectives */}
        {availablePerspectives && availablePerspectives.length > 1 && (
          <Tabs
            value={currentPerspective || availablePerspectives[0]}
            onChange={(_, value) => setPerspective(value)}
            sx={{
              mr: 2,
              '& .MuiTab-root': {
                textTransform: 'none',
                fontSize: '0.875rem',
                fontWeight: 500,
                color: 'text.secondary',
                '&.Mui-selected': {
                  color: 'success.main',
                  fontWeight: 600,
                },
                minWidth: 'auto',
                px: 1.5,
              },
              '& .MuiTabs-indicator': {
                backgroundColor: 'success.main',
              },
            }}
          >
            {availablePerspectives.map(perspective => (
              <Tab
                key={perspective}
                value={perspective}
                label={PERSPECTIVE_LABELS[perspective]}
              />
            ))}
          </Tabs>
        )}

        <Box sx={{ flexGrow: 1 }} />

        {/* Right side controls */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Tooltip title={mode === "light" ? "Dark mode" : "Light mode"}>
            <IconButton size="small" onClick={toggle} sx={{ color: "text.secondary" }}>
              {mode === "light" ? <DarkMode sx={{ fontSize: 20 }} /> : <LightMode sx={{ fontSize: 20 }} />}
            </IconButton>
          </Tooltip>

          <Tooltip title="Help">
            <IconButton size="small" sx={{ color: "text.secondary" }}>
              <HelpOutline sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>

          <Tooltip title="Notifications">
            <IconButton size="small" sx={{ color: "text.secondary" }}>
              <Notifications sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>

          <Divider orientation="vertical" flexItem sx={{ mx: 1, height: 24, alignSelf: "center" }} />

          {/* User menu trigger */}
          <Box
            onClick={handleMenuOpen}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              cursor: "pointer",
              borderRadius: 2,
              px: 1,
              py: 0.5,
              "&:hover": { bgcolor: "action.hover" },
            }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                fontSize: "0.8125rem",
                bgcolor: "success.main",
                color: "common.white",
                fontWeight: 600,
              }}
            >
              {initials}
            </Avatar>
            <Box sx={{ display: { xs: "none", sm: "block" } }}>
              <Typography fontSize="0.8125rem" fontWeight={500} color="text.primary" lineHeight={1.2}>
                {user?.username}
              </Typography>
              <Typography fontSize="0.6875rem" color="text.secondary" lineHeight={1.2}>
                {availablePerspectives?.includes("admin") ? "Administrator" : "Operator"}
              </Typography>
            </Box>
            <KeyboardArrowDown sx={{ color: "text.disabled", fontSize: 18 }} />
          </Box>
        </Box>

        {/* User menu popover */}
        <Popover
          open={!!anchorEl}
          anchorEl={anchorEl}
          onClose={handleMenuClose}
          anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
          transformOrigin={{ horizontal: "right", vertical: "top" }}
          slotProps={{
            paper: {
              sx: {
                width: 220,
                mt: 0.5,
                borderRadius: 1.5,
                border: `1px solid ${theme.palette.divider}`,
                boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
                py: 0.5,
              },
            },
          }}
        >
          {/* Identity section */}
          <Box sx={{ px: 1.5, pt: 1.25, pb: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.625 }}>
              <Box
                sx={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  bgcolor: "success.main",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "0.6875rem",
                  fontWeight: 700,
                  color: "common.white",
                  flexShrink: 0,
                }}
              >
                {initials}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: "0.75rem", fontWeight: 600, color: "text.primary", lineHeight: 1.3 }}>
                  {user?.username || "—"}
                </Typography>
                {user?.email && (
                  <Typography sx={{ fontSize: "0.5625rem", color: "text.disabled", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {user.email}
                  </Typography>
                )}
              </Box>
            </Box>
            {primaryRole && <RoleBadge role={primaryRole} theme={theme} />}
          </Box>

          <Divider sx={{ my: 0.5 }} />

          <MenuRow
            icon={PersonIcon}
            label="Account Settings"
            onClick={() => {
              navigate("/settings?tab=profile");
              handleMenuClose();
            }}
          />
          <MenuRow
            icon={SettingsIcon}
            label="Preferences"
            onClick={() => {
              navigate("/settings?tab=preferences");
              handleMenuClose();
            }}
          />
          <MenuRow
            icon={KeyboardIcon}
            label="Keyboard Shortcuts"
            onClick={() => {
              navigate("/settings?tab=shortcuts");
              handleMenuClose();
            }}
          />

          <Divider sx={{ my: 0.5 }} />

          <MenuRow
            icon={LogoutIcon}
            label="Sign out"
            onClick={handleLogout}
            danger
          />
        </Popover>
      </Toolbar>
    </AppBar>
  );
}
