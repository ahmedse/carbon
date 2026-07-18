// carbon-frontend/src/components/HeaderEnhanced.jsx
// Enhanced header with user menu (based on Gigacast pattern)

import React, { useState } from "react";
import { AppBar, Toolbar, Typography, IconButton, Menu, MenuItem, Tooltip, Box, Avatar, Divider, Popover, Tabs, Tab } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import { useNavigate } from "react-router-dom";
import aastLogo from "../assets/aast_carbon_logo_.jpg";
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
import { useThemeMode } from "../theme/ThemeContext";

const PERSPECTIVE_LABELS = {
  data_entry: 'Data Entry',
  dashboards: 'Dashboards',
  admin: 'Admin',
};

function MenuRow({ icon: Icon, label, onClick, danger, disabled }) {
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
      <Icon sx={{ fontSize: 13, flexShrink: 0 }} />
      <Typography sx={{ fontSize: "0.75rem" }}>{label}</Typography>
    </Box>
  );
}

function RoleBadge({ role }) {
  const ROLE_COLOR = {
    admins_group: { bg: "rgba(220,38,38,0.1)", text: "#dc2626" },
    dataowners_group: { bg: "rgba(37,99,235,0.1)", text: "#2563eb" },
    auditors_group: { bg: "rgba(245,158,11,0.1)", text: "#d97706" },
  };
  const s = ROLE_COLOR[role] || { bg: "rgba(113,113,122,0.1)", text: "#71717a" };
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
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);

  const initials = user?.username?.slice(0, 2).toUpperCase() || "U";
  const primaryRole = user?.roles?.[0];

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
                color: '#6b7280',
                '&.Mui-selected': {
                  color: '#16a34a',
                  fontWeight: 600,
                },
                minWidth: 'auto',
                px: 1.5,
              },
              '& .MuiTabs-indicator': {
                backgroundColor: '#16a34a',
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
            <IconButton size="small" onClick={toggle} sx={{ color: "#6b7280" }}>
              {mode === "light" ? <DarkMode sx={{ fontSize: 20 }} /> : <LightMode sx={{ fontSize: 20 }} />}
            </IconButton>
          </Tooltip>

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
                {availablePerspectives?.includes("admin") ? "Administrator" : "Operator"}
              </Typography>
            </Box>
            <KeyboardArrowDown sx={{ color: "#9ca3af", fontSize: 18 }} />
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
                border: "1px solid #e5e7eb",
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
                  bgcolor: "#16a34a",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "0.6875rem",
                  fontWeight: 700,
                  color: "#fff",
                  flexShrink: 0,
                }}
              >
                {initials}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: "0.75rem", fontWeight: 600, color: "#111827", lineHeight: 1.3 }}>
                  {user?.username || "—"}
                </Typography>
                {user?.email && (
                  <Typography sx={{ fontSize: "0.5625rem", color: "#9ca3af", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {user.email}
                  </Typography>
                )}
              </Box>
            </Box>
            {primaryRole && <RoleBadge role={primaryRole} />}
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
