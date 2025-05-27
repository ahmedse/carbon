// File: src/components/SidebarMenu.jsx
// Each module as menu with submenus, Data Schema only for admin_role.

import React, { useState } from "react";
import {
  List, ListItemButton, ListItemIcon, ListItemText, Collapse, Tooltip,
} from "@mui/material";
import {
  Dashboard as DashboardIcon,
  Schema as SchemaIcon,
  Category as ItemsIcon,
  Description as TemplatesIcon,
  ImportExport as ImportExportIcon,
  ShowChart as ReadingsIcon,
  Settings as SettingsIcon,
  SettingsApplications as ProjectSettingsIcon,
  HelpOutline as HelpIcon,
  ExpandLess, ExpandMore,
} from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";
import { Link, useLocation } from "react-router-dom";

export default function SidebarMenu({ open }) {
  const { user, currentContext } = useAuth();
  const location = useLocation();
  const [schemaOpen, setSchemaOpen] = useState(true);
  const [moduleOpens, setModuleOpens] = useState({});

  if (!user || !currentContext) return null;

  const isAdmin = user?.roles?.some(
    r =>
      r.project_id === currentContext.context_id &&
      r.active &&
      r.role === "admin_role"
  );

  // Get modules for current project (admin: show all, else only what user has)
  const allModules = ["Energy", "Water", "Gas"];
  const userModules = Array.from(
    new Set(
      user.roles
        .filter(
          r =>
            r.project_id === currentContext.context_id &&
            r.active &&
            r.module &&
            r.permissions &&
            r.permissions.length > 0
        )
        .map(r => r.module)
    )
  );
  const modules = isAdmin ? allModules : userModules;

  const MenuItem = ({ to, icon, label, tooltip, ...props }) => (
    <Tooltip title={tooltip || label} placement="right" arrow disableHoverListener={open ? true : false}>
      <ListItemButton
        component={Link}
        to={to}
        selected={location.pathname === to}
        sx={{
          minHeight: 36,
          px: open ? 2 : 1.5,
          borderRadius: 1.5,
          justifyContent: open ? "flex-start" : "center"
        }}
        {...props}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
          {icon}
        </ListItemIcon>
        {open && <ListItemText primary={label} />}
      </ListItemButton>
    </Tooltip>
  );

  return (
    <List sx={{ pt: 1 }}>
      <MenuItem
        to="/"
        icon={<DashboardIcon />}
        label="Dashboard"
        tooltip="Dashboard"
      />

      {/* Data Schema -- ONLY ADMIN */}
      {isAdmin && (
        <>
          <Tooltip title="Data Schema" placement="right" arrow disableHoverListener={open}>
            <ListItemButton
              onClick={() => setSchemaOpen((o) => !o)}
              sx={{
                minHeight: 36,
                px: open ? 2 : 1.5,
                borderRadius: 1.5,
                justifyContent: open ? "flex-start" : "center"
              }}
            >
              <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
                <SchemaIcon />
              </ListItemIcon>
              {open && <ListItemText primary="Data Schema" />}
              {open && (schemaOpen ? <ExpandLess /> : <ExpandMore />)}
            </ListItemButton>
          </Tooltip>
          <Collapse in={schemaOpen && open} timeout="auto" unmountOnExit>
            <MenuItem
              to="/schema/items"
              icon={<ItemsIcon />}
              label="Items"
              tooltip="Data Items"
              sx={{ pl: 4 }}
            />
            <MenuItem
              to="/schema/templates"
              icon={<TemplatesIcon />}
              label="Templates"
              tooltip="Templates"
              sx={{ pl: 4 }}
            />
          </Collapse>
        </>
      )}

      {/* Each module as its own menu, with submenus */}
      {modules.map((mod) => (
        <React.Fragment key={mod}>
          <Tooltip title={mod} placement="right" arrow disableHoverListener={open}>
            <ListItemButton
              onClick={() =>
                setModuleOpens((prev) => ({
                  ...prev,
                  [mod]: !prev[mod]
                }))
              }
              sx={{
                minHeight: 36,
                px: open ? 2 : 1.5,
                borderRadius: 1.5,
                justifyContent: open ? "flex-start" : "center"
              }}
            >
              <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
                <ImportExportIcon />
              </ListItemIcon>
              {open && <ListItemText primary={mod} />}
              {open && (moduleOpens[mod] ? <ExpandLess /> : <ExpandMore />)}
            </ListItemButton>
          </Tooltip>
          <Collapse in={moduleOpens[mod] && open} timeout="auto" unmountOnExit>
            <MenuItem
              to={`/modules/${mod.toLowerCase()}/readings`}
              icon={<ReadingsIcon />}
              label="Readings"
              tooltip={`${mod} Readings`}
              sx={{ pl: 4 }}
            />
            <MenuItem
              to={`/modules/${mod.toLowerCase()}/import`}
              icon={<ImportExportIcon />}
              label="Import"
              tooltip={`${mod} Import`}
              sx={{ pl: 4 }}
            />
            <MenuItem
              to={`/modules/${mod.toLowerCase()}/export`}
              icon={<ImportExportIcon />}
              label="Export"
              tooltip={`${mod} Export`}
              sx={{ pl: 4 }}
            />
            {isAdmin && (
              <MenuItem
                to={`/modules/${mod.toLowerCase()}/settings`}
                icon={<SettingsIcon />}
                label="Module Settings"
                tooltip={`${mod} Settings`}
                sx={{ pl: 4 }}
              />
            )}
          </Collapse>
        </React.Fragment>
      ))}

      {/* Project Settings (admin only) */}
      {isAdmin && (
        <MenuItem
          to="/project/settings"
          icon={<ProjectSettingsIcon />}
          label="Project Settings"
          tooltip="Project Settings"
        />
      )}
      <MenuItem
        to="/help"
        icon={<HelpIcon />}
        label="Help"
        tooltip="Help"
      />
    </List>
  );
}