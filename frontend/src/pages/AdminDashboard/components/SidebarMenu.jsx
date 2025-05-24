// File: frontend/src/pages/AdminDashboard/components/SidebarMenu.jsx
// Purpose: Renders the navigation menu for the sidebar, including nested submenus.
// Location: frontend/src/pages/AdminDashboard/components/

import React from "react";
import {
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Tooltip,
  Collapse,
  Divider,
} from "@mui/material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { Link, useLocation } from "react-router-dom";

/**
 * SidebarMenu component.
 * Renders main and sub-menu items, supports collapse and tooltips.
 *
 * @param {Array} menuConfig - Array of menu configuration objects.
 * @param {boolean} collapsed - Whether sidebar is collapsed.
 * @param {string} expandedMenu - Which submenu is expanded.
 * @param {function} setExpandedMenu - Setter for expanded menu.
 * @param {number} fontSize - Font size for menu items.
 * @param {number} iconSize - Icon size for menu icons.
 */
const SidebarMenu = ({
  menuConfig,
  collapsed,
  expandedMenu,
  setExpandedMenu,
  fontSize = 14,
  iconSize = 20,
}) => {
  const location = useLocation();

  return (
    <List sx={{ py: 0 }}>
      {menuConfig.map((item, idx) => {
        const selected =
          item.path === "/admin"
            ? location.pathname === "/admin"
            : location.pathname.startsWith(item.path);

        // Has submenu
        if (item.subMenu) {
          const isOpen = expandedMenu === item.label;
          const IconComponent = item.icon;

          const mainMenuListItem = (
            <ListItemButton
              onClick={() => setExpandedMenu(isOpen ? "" : item.label)}
              selected={selected}
              sx={{
                justifyContent: collapsed ? "center" : "flex-start",
                px: collapsed ? 1 : 2,
                minHeight: 40,
                borderRadius: 2,
                my: 0.5,
                fontSize,
                "&.Mui-selected": {
                  background: "rgba(76, 175, 80, 0.18)",
                  color: "#4caf50",
                  "& .MuiListItemIcon-root": { color: "#4caf50" },
                },
                transition: "all 0.2s",
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 0,
                  color: "inherit",
                  justifyContent: "center",
                  fontSize: iconSize,
                }}
              >
                <IconComponent fontSize="small" />
              </ListItemIcon>
              {!collapsed && (
                <>
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{
                      fontSize,
                      fontWeight: 500,
                    }}
                    sx={{ color: "inherit", ml: 1 }}
                  />
                  {isOpen ? (
                    <ExpandLessIcon fontSize="small" />
                  ) : (
                    <ExpandMoreIcon fontSize="small" />
                  )}
                </>
              )}
            </ListItemButton>
          );

          return (
            <React.Fragment key={item.label}>
              <ListItem disablePadding sx={{ display: "block" }}>
                {collapsed ? (
                  <Tooltip title={item.label} placement="right">
                    {mainMenuListItem}
                  </Tooltip>
                ) : (
                  mainMenuListItem
                )}
              </ListItem>
              <Collapse in={isOpen && !collapsed} timeout="auto" unmountOnExit>
                <List component="div" disablePadding>
                  {item.subMenu.map((subItem) => {
                    const subSelected = location.pathname === subItem.path;
                    const SubIconComponent = subItem.icon;
                    const subListItem = (
                      <ListItemButton
                        component={Link}
                        to={subItem.path}
                        selected={subSelected}
                        sx={{
                          pl: 5,
                          minHeight: 32,
                          borderRadius: 2,
                          my: 0.2,
                          fontSize: fontSize - 1,
                          "&.Mui-selected": {
                            background: "rgba(76, 175, 80, 0.12)",
                            color: "#4caf50",
                            "& .MuiListItemIcon-root": { color: "#4caf50" },
                          },
                          transition: "all 0.2s",
                        }}
                      >
                        <ListItemIcon
                          sx={{
                            minWidth: 0,
                            color: "inherit",
                            justifyContent: "center",
                            fontSize: iconSize - 2,
                          }}
                        >
                          <SubIconComponent fontSize="small" />
                        </ListItemIcon>
                        <ListItemText
                          primary={subItem.label}
                          primaryTypographyProps={{
                            fontSize: fontSize - 1,
                          }}
                          sx={{ color: "inherit", ml: 1 }}
                        />
                      </ListItemButton>
                    );
                    return (
                      <ListItem disablePadding key={subItem.label}>
                        {collapsed ? (
                          <Tooltip title={subItem.label} placement="right">
                            {subListItem}
                          </Tooltip>
                        ) : (
                          subListItem
                        )}
                      </ListItem>
                    );
                  })}
                </List>
              </Collapse>
              {idx === 4 || idx === 7 ? (
                <Divider sx={{ borderColor: "rgba(255,255,255,0.10)", my: 1 }} />
              ) : null}
            </React.Fragment>
          );
        }

        // Regular menu items
        const IconComponent = item.icon;
        const listItem = (
          <ListItemButton
            component={Link}
            to={item.path}
            selected={selected}
            sx={{
              justifyContent: collapsed ? "center" : "flex-start",
              px: collapsed ? 1 : 2,
              minHeight: 40,
              borderRadius: 2,
              my: 0.5,
              fontSize,
              "&.Mui-selected": {
                background: "rgba(76, 175, 80, 0.18)",
                color: "#4caf50",
                "& .MuiListItemIcon-root": { color: "#4caf50" },
              },
              transition: "all 0.2s",
            }}
          >
            <ListItemIcon
              sx={{
                minWidth: 0,
                color: "inherit",
                justifyContent: "center",
                fontSize: iconSize,
              }}
            >
              <IconComponent fontSize="small" />
            </ListItemIcon>
            {!collapsed && (
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ fontSize, fontWeight: 500 }}
                sx={{ color: "inherit", ml: 1 }}
              />
            )}
          </ListItemButton>
        );

        return (
          <React.Fragment key={item.label}>
            <ListItem disablePadding sx={{ display: "block" }}>
              {collapsed ? (
                <Tooltip title={item.label} placement="right">
                  {listItem}
                </Tooltip>
              ) : (
                listItem
              )}
            </ListItem>
            {item.label === "Gas" && (
              <Divider sx={{ borderColor: "rgba(255,255,255,0.10)", my: 1 }} />
            )}
          </React.Fragment>
        );
      })}
    </List>
  );
};

export default SidebarMenu;