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

function MenuItem({ to, icon, label, tooltip, selected, open, sx = {}, secondary, arrow, ...props }) {
  // arrow: { expanded: boolean, onClick: fn }  (optional)
  return (
    <Tooltip title={tooltip || label} placement="right" arrow disableHoverListener={open}>
      <ListItemButton
        component={Link}
        to={to}
        selected={selected}
        sx={{
          minHeight: 40,
          pl: open ? 4 : 1.5,
          borderRadius: 2,
          bgcolor: selected ? "primary.lighter" : "transparent",
          color: selected ? "primary.main" : "inherit",
          transition: "background 0.2s",
          ...sx,
        }}
        {...props}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
          {icon}
        </ListItemIcon>
        {open && (
          <>
            <ListItemText
              primary={label}
              secondary={secondary}
              primaryTypographyProps={{
                fontWeight: selected ? 600 : 500,
                fontSize: 15,
              }}
              secondaryTypographyProps={{
                fontSize: 12,
                color: "text.secondary",
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
                sx={{ ml: 1 }}
              >
                {arrow.expanded ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
            )}
          </>
        )}
      </ListItemButton>
    </Tooltip>
  );
}

export default function SidebarMenu({ open }) {
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
    <List sx={{ pt: 1, pb: 2, minWidth: open ? 250 : 64 }}>
      {/* --- Dashboard always on top --- */}
      <MenuItem
        to="/dashboard"
        icon={<DashboardIcon />}
        label="Dashboard"
        tooltip="Dashboard"
        selected={location.pathname === "/dashboard"}
        open={open}
        sx={{ mb: 0.5 }}
      />

      {/* --- Schema Manager --- */}
      {canSchemaAdmin() && (
        <>
          <ListItemButton
            onClick={() => setOpenMenus(prev => ({ ...prev, schemaManager: !prev.schemaManager }))}
            sx={{
              minHeight: 40,
              px: open ? 2 : 1.5,
              borderRadius: 2,
              justifyContent: open ? "flex-start" : "center",
              bgcolor: isSchemaManagerActive ? "action.selected" : "transparent"
            }}
          >
            <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
              <Tooltip title="Schema Manager" placement="right" arrow disableHoverListener={open}>
                <SchemaAdminIcon sx={{ color: "#7b1fa2" }} />
              </Tooltip>
            </ListItemIcon>
            {open && <ListItemText primary="Schema Manager" primaryTypographyProps={{ fontWeight: 600 }} />}
            {open && (
              <IconButton
                edge="end"
                size="small"
                onClick={e => {
                  e.preventDefault();
                  e.stopPropagation();
                  setOpenMenus(prev => ({ ...prev, schemaManager: !prev.schemaManager }));
                }}
              >
                {openMenus.schemaManager ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
            )}
          </ListItemButton>
          <Collapse in={open && openMenus.schemaManager} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              <MenuItem
                to="/schema-admin/table-manager"
                icon={<TableRowsIcon sx={{ color: "#7b1fa2" }} />}
                label="Table Manager"
                selected={location.pathname.startsWith("/schema-admin/table-manager")}
                open={open}
                sx={{ pl: open ? 6 : 1.5 }}
              />
            </List>
          </Collapse>
          <Divider sx={{ my: 1 }} />
        </>
      )}

      {/* --- Grouped Modules By Scope, with submenus for modules and tables --- */}
      {Object.entries(modulesByScope).map(([scope, mods]) =>
        mods.length > 0 ? (
          <React.Fragment key={`scope-${scope}`}>
            <Box
              sx={{
                bgcolor: open ? SCOPE_META[scope].color : "transparent",
                borderRadius: 2,
                mx: open ? 1 : 0,
                my: 0.5,
                boxShadow: open ? 1 : 0,
              }}
            >
              {/* Scope Group Header */}
              <ListItemButton
                onClick={e => {
                  // Only expand/collapse on arrow click
                  e.preventDefault();
                  e.stopPropagation();
                  setOpenScopeMenus(prev => ({ ...prev, [scope]: !prev[scope] }));
                }}
                sx={{
                  minHeight: 42,
                  px: open ? 2 : 1.5,
                  borderRadius: 2,
                  justifyContent: open ? "flex-start" : "center",
                  fontWeight: 700,
                  bgcolor: "transparent",
                  color: "#222",
                  cursor: "pointer",
                }}
                disableRipple
              >
                <ListItemIcon
                  sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center", cursor: "pointer" }}
                  onClick={e => { e.stopPropagation(); navigate(`/scopes/${scope}`); }}
                >
                  {SCOPE_META[scope].icon}
                </ListItemIcon>
                {open && (
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center">
                        <span
                          style={{ cursor: "pointer", fontWeight: 700 }}
                          onClick={e => { e.stopPropagation(); navigate(`/scopes/${scope}`); }}
                        >
                          {SCOPE_META[scope].label}
                        </span>
                        <MicroHelp
                          helpKey={SCOPE_META[scope].helpKey}
                          lang="en"
                          sx={{ ml: 1 }}
                          onClick={e => {
                            e.stopPropagation();
                            navigate(`/scopes/${scope}`);
                          }}
                        />
                      </Box>
                    }
                    secondary={SCOPE_META[scope].desc}
                    primaryTypographyProps={{ fontWeight: 700, fontSize: 16 }}
                    secondaryTypographyProps={{ fontSize: 11, color: "#888" }}
                  />
                )}
                {open && mods.length > 0 && (
                  <IconButton
                    edge="end"
                    size="small"
                    sx={{ ml: 1 }}
                    onClick={e => {
                      e.preventDefault();
                      e.stopPropagation();
                      setOpenScopeMenus(prev => ({ ...prev, [scope]: !prev[scope] }));
                    }}
                  >
                    {openScopeMenus[scope] ? <ExpandLess /> : <ExpandMore />}
                  </IconButton>
                )}
              </ListItemButton>
              <Collapse in={open && openScopeMenus[scope]} timeout="auto" unmountOnExit>
                <List component="div" disablePadding>
                  {mods.map(mod => {
                    const tables = (tablesByModule[String(mod.id)] || []).filter(t => t.is_active !== false);
                    const isActiveModule = location.pathname.startsWith(`/modules/${mod.id}`) ||
                      (location.pathname.startsWith("/dataschema/entry/") && location.pathname.includes(`/${mod.id}/`));
                    const hasTables = tables && tables.length > 0;
                    return (
                      <React.Fragment key={mod.id}>
                        {/* Module Menu */}
                        <ListItemButton
                          onClick={e => {
                            // Navigate on label/icon click, expand/collapse on arrow click
                            e.preventDefault();
                            e.stopPropagation();
                            navigate(`/modules/${mod.id}`);
                          }}
                          selected={isActiveModule && !hasTables}
                          sx={{
                            minHeight: 38,
                            pl: open ? 6 : 1.5,
                            borderRadius: 2,
                            justifyContent: open ? "flex-start" : "center",
                            fontWeight: open && hasTables ? 600 : 500,
                            bgcolor: isActiveModule ? "action.selected" : "transparent",
                            mb: 0.5,
                            color: isActiveModule ? "primary.main" : "#444",
                            cursor: "pointer",
                          }}
                        >
                          <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center", cursor: "pointer" }}>
                            <TableIcon sx={{ color: "#757575" }} />
                          </ListItemIcon>
                          {open && (
                            <ListItemText
                              primary={
                                <span
                                  style={{ cursor: "pointer" }}
                                  onClick={e => { e.stopPropagation(); navigate(`/modules/${mod.id}`); }}
                                >
                                  {mod.name}
                                </span>
                              }
                              secondary={mod.description}
                              primaryTypographyProps={{ fontWeight: 500 }}
                              secondaryTypographyProps={{ fontSize: 11, color: "#aaa" }}
                            />
                          )}
                          {open && hasTables && (
                            <IconButton
                              edge="end"
                              size="small"
                              sx={{ ml: 1 }}
                              onClick={e => {
                                e.preventDefault();
                                e.stopPropagation();
                                setOpenModuleMenus(prev => ({
                                  ...prev,
                                  [mod.id]: !prev[mod.id]
                                }));
                              }}
                            >
                              {openModuleMenus[mod.id] ? <ExpandLess /> : <ExpandMore />}
                            </IconButton>
                          )}
                        </ListItemButton>
                        {/* Tables under this module */}
                        {hasTables && (
                          <Collapse in={open && openModuleMenus[mod.id]} timeout="auto" unmountOnExit>
                            <List component="div" disablePadding>
                              {tables.map(table => (
                                <MenuItem
                                  key={table.id}
                                  to={`/dataschema/entry/${mod.id}/${table.id}`}
                                  icon={<TableRowsIcon sx={{ color: "#2196f3" }} />}
                                  label={table.title}
                                  tooltip={table.title}
                                  selected={location.pathname === `/dataschema/entry/${mod.id}/${table.id}`}
                                  open={open}
                                  sx={{ pl: open ? 10 : 1.5, mb: 0.5 }}
                                />
                              ))}
                            </List>
                          </Collapse>
                        )}
                      </React.Fragment>
                    );
                  })}
                </List>
              </Collapse>
            </Box>
          </React.Fragment>
        ) : null
      )}

      <Divider sx={{ my: 1, mx: open ? 1 : 0 }} />

      {/* --- Static Menu (Help, Feedback) --- */}
      {staticMenu.slice(1).map((item, idx) => {
        if (item.type === "divider") return <Divider key={`div-${idx}`} />;
        return (
          <MenuItem
            key={item.to}
            to={item.to}
            icon={item.icon}
            label={item.label}
            tooltip={item.tooltip}
            selected={item.match(location.pathname)}
            open={open}
            sx={{ mb: 0.5 }}
          />
        );
      })}
    </List>
  );
}