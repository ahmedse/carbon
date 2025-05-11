import React from "react";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import Avatar from "@mui/material/Avatar";
import AccountCircle from "@mui/icons-material/AccountCircle";
import Brightness4 from "@mui/icons-material/Brightness4";
import Brightness7 from "@mui/icons-material/Brightness7";
import LaptopMacIcon from "@mui/icons-material/LaptopMac";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Box from "@mui/material/Box";
import Tooltip from "@mui/material/Tooltip";
import { useAuth } from "../context/AuthContext";

const LOGO_SRC = "/aast_carbon_logo_.jpg";
const MODES = ["system", "light", "dark"];
const MODE_ICONS = {
  system: <LaptopMacIcon />,
  light: <Brightness7 />,
  dark: <Brightness4 />,
};
const MODE_LABELS = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

function getNextMode(current) {
  const idx = MODES.indexOf(current);
  return MODES[(idx + 1) % MODES.length];
}

function getInitials(name = "") {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function Header({ mode, setMode }) {
  const [anchorEl, setAnchorEl] = React.useState(null);
  const { user, logout } = useAuth();

  const handleProfileMenuOpen = (event) => setAnchorEl(event.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  return (
    <AppBar
      position="static"
      color="default"
      elevation={2}
      sx={{
        minHeight: 48,
        justifyContent: "center",
        px: { xs: 1, md: 3 },
        borderBottom: (theme) => `1px solid ${theme.palette.divider}`,
      }}
      data-testid="header-appbar"
    >
      <Toolbar
        sx={{
          minHeight: 48,
          display: "flex",
          justifyContent: "space-between",
          p: 0,
        }}
      >
        {/* Logo & Brand */}
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <img
            src={LOGO_SRC}
            alt="AAST Carbon Logo"
            style={{ height: 28, marginRight: 10 }}
            data-testid="header-logo"
          />
          <Typography
            variant="h6"
            color="primary"
            sx={{
              fontWeight: 700,
              letterSpacing: 1,
              fontFamily: "'Inter', 'Montserrat', 'Roboto', 'Segoe UI', Arial, sans-serif",
              fontSize: { xs: "0.98rem", md: "1.08rem" },
              textTransform: "uppercase",
              whiteSpace: "nowrap",
              userSelect: "none",
              lineHeight: 1.2,
            }}
            data-testid="header-title"
          >
            AAST Carbon Platform
          </Typography>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center" }}>
          {/* Theme toggle */}
          <Tooltip title={`Switch theme (now: ${MODE_LABELS[mode]})`} arrow>
            <IconButton
              sx={{ ml: 1 }}
              onClick={() => {
                const next = getNextMode(mode);
                console.log("Theme toggle clicked. Changing from", mode, "to", next);
                setMode(next);
              }}
              color="inherit"
              aria-label="Toggle theme"
              size="large"
              data-testid="theme-toggle"
            >
              {MODE_ICONS[mode]}
            </IconButton>
          </Tooltip>

          {/* Profile/Avatar */}
          <Tooltip title={user?.username || "Account"} arrow>
            <IconButton
              size="large"
              edge="end"
              aria-label="account of current user"
              aria-controls="profile-menu"
              aria-haspopup="true"
              onClick={handleProfileMenuOpen}
              color="inherit"
              sx={{ ml: 1 }}
              data-testid="profile-avatar"
            >
              {user?.username ? (
                <Avatar
                  sx={{
                    width: 30,
                    height: 30,
                    bgcolor: "primary.main",
                    fontSize: 15,
                    fontWeight: 600,
                    fontFamily: "'Inter', 'Montserrat', 'Roboto', 'Segoe UI', Arial, sans-serif"
                  }}
                >
                  {getInitials(user.username)}
                </Avatar>
              ) : (
                <AccountCircle fontSize="inherit" />
              )}
            </IconButton>
          </Tooltip>
          <Menu
            id="profile-menu"
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
          >
            <MenuItem disabled>
              <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "'Inter', 'Montserrat', 'Roboto', 'Segoe UI', Arial, sans-serif", fontSize: "0.9rem" }}>
                v1.0.0 · AAST
              </Typography>
            </MenuItem>
            {user?.username && (
              <MenuItem disabled>
                <Typography variant="body2" sx={{ fontSize: "0.98rem" }}>
                  {user.username}
                </Typography>
              </MenuItem>
            )}
            <MenuItem onClick={handleMenuClose}>Profile/Settings</MenuItem>
            <MenuItem
              onClick={() => {
                handleMenuClose();
                logout();
              }}
            >
              Logout
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
}

export default Header;