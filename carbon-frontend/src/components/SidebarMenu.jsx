// src/components/SidebarMenu.jsx

import React, { useState, useEffect } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import MicroHelp from "./MicroHelp";
import { useMemo } from "react";
import {
  List, ListItemButton, ListItemIcon, ListItemText, Tooltip, Divider, Collapse, Box, IconButton,
} from "@mui/material";
import {
  DashboardRounded as DashboardIcon,
  HelpOutlineRounded as HelpIcon,
  FeedbackOutlined as FeedbackIcon,
  SettingsApplicationsRounded as SchemaAdminIcon,
  TableRowsRounded as TableRowsIcon,
  ExpandLess, ExpandMore,
  NatureRounded as Scope1Icon,
  BoltRounded as Scope2Icon,
  LocalShippingRounded as Scope3Icon,
  DatasetRounded as TableIcon,
  ArrowForwardIos as ArrowIcon,
} from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";

const SCOPE_META = {
  1: {
    label: "Scope 1",
    icon: <Scope1Icon sx={{ color: "#43a047" }} />,
    color: "#eafaf1",
    desc: "Direct emissions",
    helpKey: "scope1_microhelp",
  },
  2: {
    label: "Scope 2",
    icon: <Scope2Icon sx={{ color: "#1e88e5" }} />,
    color: "#e3f2fd",
    desc: "Indirect energy",
    helpKey: "scope2_microhelp",
  },
  3: {
    label: "Scope 3",
    icon: <Scope3Icon sx={{ color: "#ff7043" }} />,
    color: "#fff3e0",
    desc: "Value chain emissions",
    helpKey: "scope3_microhelp",
  },
};

function MenuItem({ to, icon, label, tooltip, selected, collapsed, sx = {}, secondary, arrow, ...props }) {
  const isExpanded = !collapsed;
  return (
    <Tooltip title={tooltip || label} placement="right" arrow disableHoverListener={isExpanded}>
      <ListItemButton
        component={Link}
        to={to}
        selected={selected}
        sx={{
          minHeight: 36,
          py: 0.75,
          px: collapsed ? 1.5 : 1.5,
          mx: 0.5,
          borderRadius: 1,
          justifyContent: collapsed ? "center" : "flex-start",
          color: selected ? "#16a34a" : "#374151",
          bgcolor: selected ? "#f0fdf4" : "transparent",
          "&:hover": { bgcolor: "#f3f4f6" },
          ...sx,
        }}
        {...props}
      >
        <ListItemIcon sx={{ 
          minWidth: 0, 
          mr: collapsed ? 0 : 1.5, 
          justifyContent: "center", 
          color: selected ? "#16a34a" : "#6b7280",
        }}>
          {icon}
        </ListItemIcon>
        {isExpanded && (
          <>
            <ListItemText
              primary={label}
              secondary={secondary}
              primaryTypographyProps={{
                fontWeight: selected ? 600 : 500,
                fontSize: "0.8125rem",
                noWrap: true,
                color: selected ? "#16a34a" : "#374151",
              }}
              secondaryTypographyProps={{
                fontSize: "0.6875rem",
                color: "#9ca3af",
              }}
            />
            {arrow && (
              <IconButton
                edge="end"
                size="small"
                onClick={e => {
                  e.preventDefault();
                  e.stopPropagation();
                  arrow.onClick?.();
                }}
                sx={{ p: 0.25, ml: 0.5, color: "#9ca3af" }}
              >
                {arrow.expanded ? <ExpandLess sx={{ fontSize: 16 }} /> : <ExpandMore sx={{ fontSize: 16 }} />}
              </IconButton>
            )}
          </>
        )}
      </ListItemButton>
    </Tooltip>
  );
}
export default function SidebarMenu({ collapsed }) {
  const open = !collapsed;
  const location = useLocation();
  const navigate = useNavigate();
  const {
    context, canSchemaAdmin, canManageAllModules, canManageAssignedModules,
  } = useAuth();

  const [openMenus, setOpenMenus] = useState({ schemaManager: true });
  const [openScopeMenus, setOpenScopeMenus] = useState({ 1: true, 2: true, 3: true });
  const [openModuleMenus, setOpenModuleMenus] = useState({});

  const modules = context?.modules || [];
  const projectRoles = context?.projectRoles || [];
  const { tablesByModule = {} } = useAuth();

  // Role-based module filtering
  let visibleModules = [];
  if (canSchemaAdmin() || canManageAllModules()) {
    visibleModules = modules;
  } else if (canManageAssignedModules()) {
    const moduleIds = projectRoles
      .filter(r => r.role === "dataowners_group" && r.module_id)
      .map(r => r.module_id);
    visibleModules = modules.filter(m => moduleIds.includes(m.id));
  }

  // Group modules by scope
  const modulesByScope = useMemo(() => {
    const grouped = { 1: [], 2: [], 3: [] };
    visibleModules.forEach(mod => {
      const scope = mod.scope || 1;
      if (grouped[scope]) {
        grouped[scope].push(mod);
      }
    });
    return grouped;
  }, [visibleModules]);

  // Auto-expand logic for current path
  useEffect(() => {
    const match = location.pathname.match(/^\/dataschema\/entry\/(\d+)\/(\d+)/);
    if (match) {
      const moduleId = parseInt(match[1]);
      let foundScope = null;
      for (const [scope, mods] of Object.entries(modulesByScope)) {
        if (mods.some(m => Number(m.id) === moduleId)) {
          foundScope = scope;
          break;
        }
      }
      if (foundScope) {
        setOpenScopeMenus(prev => ({ ...prev, [foundScope]: true }));
        setOpenModuleMenus(prev => ({ ...prev, [moduleId]: true }));
      }
    }
    const modMatch = location.pathname.match(/^\/modules\/(\d+)/);
    if (modMatch) {
      const moduleId = parseInt(modMatch[1]);
      let foundScope = null;
      for (const [scope, mods] of Object.entries(modulesByScope)) {
        if (mods.some(m => Number(m.id) === moduleId)) {
          foundScope = scope;
          break;
        }
      }
      if (foundScope) {
        setOpenScopeMenus(prev => ({ ...prev, [foundScope]: true }));
        setOpenModuleMenus(prev => ({ ...prev, [moduleId]: true }));
      }
    }
  }, [location.pathname, modulesByScope]);

  const isSchemaManagerActive = location.pathname.startsWith("/schema-admin");

  // --- Menu items (Dashboard always on top) ---
  const staticMenu = [
    {
      type: "menu",
      to: "/dashboard",
      icon: <DashboardIcon />,
      label: "Dashboard",
      tooltip: "Dashboard",
      match: path => path === "/dashboard",
    },
    { type: "divider" },
    {
      type: "menu",
      to: "/help",
      icon: <HelpIcon />,
      label: "Help",
      tooltip: "Help and Documentation",
      match: path => path === "/help",
    },
    {
      type: "menu",
      to: "/feedback",
      icon: <FeedbackIcon />,
      label: "Feedback",
      tooltip: "Send us your feedback",
      match: path => path === "/feedback",
    },
  ].filter(Boolean);

  return (
    <List sx={{ pt: 0.5, pb: 2, px: 0.5 }}>
      {/* --- Dashboard always on top --- */}
      <MenuItem
        to="/dashboard"
        icon={<DashboardIcon sx={{ fontSize: 20 }} />}
        label="Dashboard"
        tooltip="Dashboard"
        selected={location.pathname === "/dashboard" || location.pathname === "/"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />

      {/* --- Schema Manager --- */}
      {canSchemaAdmin() && (
        <>
          <ListItemButton
            onClick={() => setOpenMenus(prev => ({ ...prev, schemaManager: !prev.schemaManager }))}
            sx={{
              minHeight: 36,
              py: 0.75,
              px: 1.5,
              mx: 0.5,
              borderRadius: 1,
              justifyContent: open ? "flex-start" : "center",
              color: isSchemaManagerActive ? "#7c3aed" : "#374151",
              bgcolor: isSchemaManagerActive ? "#f5f3ff" : "transparent",
              "&:hover": { bgcolor: "#f3f4f6" },
            }}
          >
            <ListItemIcon sx={{ minWidth: 0, mr: open ? 1.5 : 0, justifyContent: "center" }}>
              <Tooltip title="Schema Manager" placement="right" arrow disableHoverListener={open}>
                <SchemaAdminIcon sx={{ fontSize: 20, color: isSchemaManagerActive ? "#7c3aed" : "#6b7280" }} />
              </Tooltip>
            </ListItemIcon>
            {open && <ListItemText primary="Schema Manager" primaryTypographyProps={{ fontWeight: 600, fontSize: "0.8125rem" }} />}
            {open && (openMenus.schemaManager ? <ExpandLess sx={{ fontSize: 16, color: "#9ca3af" }} /> : <ExpandMore sx={{ fontSize: 16, color: "#9ca3af" }} />)}
          </ListItemButton>
          <Collapse in={open && openMenus.schemaManager} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              <MenuItem
                to="/schema-admin/table-manager"
                icon={<TableRowsIcon sx={{ fontSize: 18, color: "#7c3aed" }} />}
                label="Table Manager"
                selected={location.pathname.startsWith("/schema-admin/table-manager")}
                collapsed={collapsed}
                sx={{ pl: 4.5 }}
              />
            </List>
          </Collapse>
          <Divider sx={{ my: 1, mx: 1 }} />
        </>
      )}

      {/* --- Grouped Modules By Scope, with submenus for modules and tables --- */}
      {Object.entries(modulesByScope).map(([scope, mods]) =>
        mods.length > 0 ? (
          <React.Fragment key={`scope-${scope}`}>
            {/* Scope Header */}
            <ListItemButton
              onClick={() => setOpenScopeMenus(prev => ({ ...prev, [scope]: !prev[scope] }))}
              sx={{
                minHeight: 36,
                py: 0.75,
                px: 1.5,
                mx: 0.5,
                mt: 0.5,
                borderRadius: 1,
                justifyContent: open ? "flex-start" : "center",
                bgcolor: openScopeMenus[scope] ? "#f9fafb" : "transparent",
                "&:hover": { bgcolor: "#f3f4f6" },
              }}
            >
              <ListItemIcon sx={{ minWidth: 0, mr: open ? 1.5 : 0, justifyContent: "center" }}>
                <Tooltip title={SCOPE_META[scope].label} placement="right" arrow disableHoverListener={open}>
                  {React.cloneElement(SCOPE_META[scope].icon, { sx: { fontSize: 20 } })}
                </Tooltip>
              </ListItemIcon>
              {open && (
                <>
                  <ListItemText
                    primary={SCOPE_META[scope].label}
                    secondary={SCOPE_META[scope].desc}
                    primaryTypographyProps={{ fontWeight: 600, fontSize: "0.8125rem", color: "#111827" }}
                    secondaryTypographyProps={{ fontSize: "0.6875rem", color: "#9ca3af" }}
                  />
                  {openScopeMenus[scope] ? <ExpandLess sx={{ fontSize: 16, color: "#9ca3af" }} /> : <ExpandMore sx={{ fontSize: 16, color: "#9ca3af" }} />}
                </>
              )}
            </ListItemButton>

            {/* Scope Modules */}
            <Collapse in={open && openScopeMenus[scope]} timeout="auto" unmountOnExit>
              <List component="div" disablePadding sx={{ pl: 1 }}>
                {mods.map(mod => {
                  const tables = (tablesByModule[String(mod.id)] || []).filter(t => t.is_active !== false);
                  const isActiveModule = location.pathname.startsWith(`/modules/${mod.id}`) ||
                    (location.pathname.startsWith("/dataschema/entry/") && location.pathname.includes(`/${mod.id}/`));
                  const hasTables = tables && tables.length > 0;
                  return (
                    <React.Fragment key={mod.id}>
                      {/* Module */}
                      <ListItemButton
                        onClick={() => hasTables ? setOpenModuleMenus(prev => ({ ...prev, [mod.id]: !prev[mod.id] })) : navigate(`/modules/${mod.id}`)}
                        sx={{
                          minHeight: 32,
                          py: 0.5,
                          pl: 3,
                          pr: 1.5,
                          mx: 0.5,
                          borderRadius: 1,
                          color: isActiveModule ? "#16a34a" : "#4b5563",
                          bgcolor: isActiveModule ? "#f0fdf4" : "transparent",
                          "&:hover": { bgcolor: "#f3f4f6" },
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: 0, mr: 1.5, color: isActiveModule ? "#16a34a" : "#9ca3af" }}>
                          <TableIcon sx={{ fontSize: 16 }} />
                        </ListItemIcon>
                        <ListItemText
                          primary={mod.name}
                          primaryTypographyProps={{ fontSize: "0.8125rem", fontWeight: isActiveModule ? 600 : 500, noWrap: true }}
                        />
                        {hasTables && (openModuleMenus[mod.id] ? <ExpandLess sx={{ fontSize: 14, color: "#9ca3af" }} /> : <ExpandMore sx={{ fontSize: 14, color: "#9ca3af" }} />)}
                      </ListItemButton>

                      {/* Tables under module */}
                      {hasTables && (
                        <Collapse in={openModuleMenus[mod.id]} timeout="auto" unmountOnExit>
                          <List component="div" disablePadding>
                            {tables.map(table => {
                              const isTableActive = location.pathname === `/dataschema/entry/${mod.id}/${table.id}`;
                              return (
                                <ListItemButton
                                  key={table.id}
                                  component={Link}
                                  to={`/dataschema/entry/${mod.id}/${table.id}`}
                                  sx={{
                                    minHeight: 28,
                                    py: 0.25,
                                    pl: 5.5,
                                    pr: 1.5,
                                    mx: 0.5,
                                    borderRadius: 1,
                                    color: isTableActive ? "#16a34a" : "#6b7280",
                                    bgcolor: isTableActive ? "#f0fdf4" : "transparent",
                                    "&:hover": { bgcolor: "#f3f4f6" },
                                  }}
                                >
                                  <ListItemText
                                    primary={table.title || table.name}
                                    primaryTypographyProps={{ fontSize: "0.75rem", fontWeight: isTableActive ? 600 : 400, noWrap: true }}
                                  />
                                </ListItemButton>
                              );
                            })}
                          </List>
                        </Collapse>
                      )}
                    </React.Fragment>
                  );
                })}
              </List>
            </Collapse>
          </React.Fragment>
        ) : null
      )}
    </List>
  );
}