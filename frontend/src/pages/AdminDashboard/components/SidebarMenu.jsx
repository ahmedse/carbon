import React, { useEffect, useState } from "react";
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
import { useAuth } from "../../../context/AuthContext";
import { apiFetch } from "../../../api";

const SidebarMenu = ({
  menuConfig,
  collapsed,
  expandedMenu,
  setExpandedMenu,
  fontSize = 14,
  iconSize = 20,
}) => {
  const location = useLocation();
  const { user, currentContext } = useAuth();
  const token = user?.token;
  const context_type = currentContext?.context_type;
  const context_name = currentContext?.[context_type];
  const context = { context_type, context_name };

  // Store all templates fetched from the backend
  const [templates, setTemplates] = useState([]);

  useEffect(() => {
    if (token && context_type && context_name) {
      apiFetch("/api/datacollection/templates/", { token, context })
        .then((res) => res.json())
        .then((data) => setTemplates(data || []));
    }
  }, [token, context_type, context_name]);

  const getModuleTemplates = (module) =>
    templates.filter((tpl) => tpl.module && tpl.module.toLowerCase() === module);

  return (
    <List sx={{ py: 0 }}>
      {menuConfig.map((item, idx) => {
        // Static submenus (e.g. Data Schema)
        if (item.subMenu) {
          const isOpen = expandedMenu === item.label;
          const IconComponent = item.icon;
          const mainMenuListItem = (
            <ListItemButton
              onClick={() => setExpandedMenu(isOpen ? "" : item.label)}
              selected={
                item.subMenu.some((sub) => location.pathname.startsWith(sub.path))
              }
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
              <Divider sx={{ borderColor: "rgba(255,255,255,0.10)", my: 1 }} />
            </React.Fragment>
          );
        }

        // Dynamic templates submenu for modules
        if (item.dynamicTemplates) {
          const subTemplates = getModuleTemplates(item.moduleName);
          const isOpen = expandedMenu === item.label;
          const IconComponent = item.icon;
          const mainMenuListItem = (
            <ListItemButton
              onClick={() => setExpandedMenu(isOpen ? "" : item.label)}
              selected={location.pathname.startsWith(item.path)}
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
                  {subTemplates.map((tpl) => {
                    const subPath = `/admin/${item.moduleName}/template/${tpl.id}`;
                    const subSelected = location.pathname === subPath;
                    return (
                      <ListItem disablePadding key={tpl.id}>
                        <ListItemButton
                          component={Link}
                          to={subPath}
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
                            },
                            transition: "all 0.2s",
                          }}
                        >
                          <ListItemText
                            primary={tpl.name}
                            primaryTypographyProps={{
                              fontSize: fontSize - 1,
                            }}
                            sx={{ color: "inherit", ml: 1 }}
                          />
                        </ListItemButton>
                      </ListItem>
                    );
                  })}
                </List>
              </Collapse>
              <Divider sx={{ borderColor: "rgba(255,255,255,0.10)", my: 1 }} />
            </React.Fragment>
          );
        }

        // Regular menu items
        const IconComponent = item.icon;
        const listItem = (
          <ListItemButton
            component={Link}
            to={item.path}
            selected={location.pathname === item.path}
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
          </React.Fragment>
        );
      })}
    </List>
  );
};

export default SidebarMenu;