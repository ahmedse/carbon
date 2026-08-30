// carbon-frontend/src/components/HeaderEnhanced.jsx
// Enhanced header with user menu (based on Gigacast pattern)

import React, { useState } from "react";
import { AppBar, Toolbar, Typography, IconButton, Menu, MenuItem, Tooltip, Box, Avatar, Divider, Popover, Tabs, Tab, useTheme, Badge, Chip } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import { useNavigate } from "react-router-dom";
import { INSTANCE_LOGO, PLATFORM_TITLE } from "../config/branding";
import { 
  KeyboardArrowDown, 
  Notifications, 
  Insights,
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
import { useTranslation } from "react-i18next";
import LanguageSwitcher from "./LanguageSwitcher";
import { useNotifications } from "../hooks/useNotifications";
import { NotificationCenter } from "./notifications/NotificationCenter";
import { useInsightStream } from "../hooks/useInsightStream";
import { InsightNotificationPanel } from "./notifications/InsightNotificationPanel";

// Perspective tab labels -> shell.nav.* keys (translated at render time).
const PERSPECTIVE_LABEL_KEYS = {
  data_entry: 'nav.dataEntry',
  dashboards: 'nav.dashboards',
  admin: 'nav.admin',
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
      <_Icon sx={{ fontSize: '0.8125rem', flexShrink: 0 }} />
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
  const { t } = useTranslation('shell');
  const { t: tAuth } = useTranslation('auth');
  const { user, logout, availablePerspectives } = useAuth();
  const { unreadCount } = useNotifications();
  const { unreadCount: insightUnreadCount } = useInsightStream();
  const { mode, toggle } = useThemeMode();
  const theme = useTheme();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);
  const [notifAnchor, setNotifAnchor] = useState(null);
  const [insightAnchor, setInsightAnchor] = useState(null);

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
        {/* Logo and title — clickable, navigates home */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Box
            component="button"
            type="button"
            onClick={() => navigate('/')}
            title={t('ui.goHome')}
            aria-label={t('ui.goHome')}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              p: 0,
              m: 0,
              background: "none",
              border: "none",
              cursor: "pointer",
              borderRadius: 1,
              '&:hover': { opacity: 0.8 },
              '&:focus-visible': { outline: `2px solid ${theme.palette.primary.main}`, outlineOffset: 2 },
            }}
          >
            <img src={INSTANCE_LOGO} alt={t('ui.logo')} style={{ height: 32, borderRadius: 6 }} />
            <Typography fontWeight={600} fontSize="1rem" color="text.primary">
              {PLATFORM_TITLE}
            </Typography>
          </Box>
          <Chip
            label={t('devBanner.label')}
            size="small"
            variant="outlined"
            color="info"
            sx={{
              height: 18,
              fontSize: '0.5625rem',
              fontWeight: 700,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
        </Box>

        <Box sx={{ flexGrow: 1 }} />

        {/* Right side controls */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Tooltip title={mode === "light" ? t('ui.darkMode') : t('ui.lightMode')}>
            <IconButton size="small" onClick={toggle} sx={{ color: "text.secondary" }}>
              {mode === "light" ? <DarkMode sx={{ fontSize: '1.25rem' }} /> : <LightMode sx={{ fontSize: '1.25rem' }} />}
            </IconButton>
          </Tooltip>

          <Tooltip title={t('nav.help')}>
            <IconButton size="small" sx={{ color: "text.secondary" }}>
              <HelpOutline sx={{ fontSize: '1.25rem' }} />
            </IconButton>
          </Tooltip>

          <Tooltip title={t('ui.notifications')}>
            <IconButton
              size="small"
              aria-label={t('ui.notifications')}
              sx={{ color: "text.secondary" }}
              onClick={(e) => setNotifAnchor(e.currentTarget)}
            >
              <Badge badgeContent={unreadCount} color="error" max={99} showZero={false}>
                <Notifications sx={{ fontSize: '1.25rem' }} />
              </Badge>
            </IconButton>
          </Tooltip>

          <Tooltip title={t('ui.insights.title')}>
            <IconButton
              size="small"
              aria-label={t('ui.insights.title')}
              sx={{ color: "text.secondary" }}
              onClick={(e) => setInsightAnchor(e.currentTarget)}
            >
              <Badge badgeContent={insightUnreadCount} color="error" max={99} showZero={false}>
                <Insights sx={{ fontSize: '1.25rem' }} />
              </Badge>
            </IconButton>
          </Tooltip>

          <Divider orientation="vertical" flexItem sx={{ mx: 1, height: 24, alignSelf: "center" }} />

          <LanguageSwitcher />

          {/* User menu trigger - styled as profile card for clarity */}
          <Tooltip title={t('ui.userProfileTooltip') || 'User Profile — manage account, language, or logout'} arrow placement="bottom">
            <Box
              onClick={handleMenuOpen}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                cursor: "pointer",
                borderRadius: 2,
                px: 1.25,
                py: 0.625,
                bgcolor: "action.hover",
                border: `1px solid ${theme.palette.divider}`,
                transition: "all 0.15s ease",
                "&:hover": { 
                  bgcolor: "action.selected",
                  borderColor: theme.palette.primary.main,
                  boxShadow: `0 0 0 1px ${theme.palette.primary.main}`,
                },
              }}
            >
              <Avatar
                sx={{
                  width: 32,
                  height: 32,
                  fontSize: "0.8125rem",
                  bgcolor: availablePerspectives?.includes("admin") ? "primary.main" : "success.main",
                  color: "common.white",
                  fontWeight: 600,
                }}
              >
                {initials}
              </Avatar>
              <Box sx={{ display: { xs: "none", sm: "block" } }}>
                <Typography fontSize="0.8125rem" fontWeight={600} color="text.primary" lineHeight={1.2}>
                  {user?.username}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.25 }}>
                  <Box sx={{ 
                    px: 0.5, py: 0.125, borderRadius: 0.5, 
                    bgcolor: availablePerspectives?.includes("admin") ? "primary.light" : "success.light",
                    display: 'inline-block',
                  }}>
                    <Typography fontSize="0.5625rem" fontWeight={700} color={availablePerspectives?.includes("admin") ? "primary.dark" : "success.dark"} textTransform="uppercase" letterSpacing="0.05em">
                      {availablePerspectives?.includes("admin") ? "Admin" : "User"}
                    </Typography>
                  </Box>
                </Box>
              </Box>
              <KeyboardArrowDown sx={{ color: "text.disabled", fontSize: '1.125rem' }} />
            </Box>
          </Tooltip>
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
            label={t('ui.accountSettings')}
            onClick={() => {
              navigate("/settings?tab=profile");
              handleMenuClose();
            }}
          />
          <MenuRow
            icon={SettingsIcon}
            label={t('nav.preferences')}
            onClick={() => {
              navigate("/settings?tab=preferences");
              handleMenuClose();
            }}
          />
          <MenuRow
            icon={KeyboardIcon}
            label={t('ui.keyboardShortcuts')}
            onClick={() => {
              navigate("/settings?tab=shortcuts");
              handleMenuClose();
            }}
          />

          <Divider sx={{ my: 0.5 }} />

          <MenuRow
            icon={LogoutIcon}
            label={tAuth('logout')}
            onClick={handleLogout}
            danger
          />
        </Popover>
        <NotificationCenter anchorEl={notifAnchor} onClose={() => setNotifAnchor(null)} />
        <InsightNotificationPanel anchorEl={insightAnchor} onClose={() => setInsightAnchor(null)} />
      </Toolbar>
    </AppBar>
  );
}
