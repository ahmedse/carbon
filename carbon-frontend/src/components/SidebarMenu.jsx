// src/components/SidebarMenu.jsx

import React, { useState, useEffect } from "react";
import {
  List, ListItemButton, ListItemIcon, ListItemText, Tooltip, Divider, Collapse,
} from "@mui/material";
import {
  TableChart as TableIcon, SettingsApplications as SchemaAdminIcon,
  Help as HelpIcon, Feedback as FeedbackIcon, Dashboard as DashboardIcon,
  ExpandLess, ExpandMore, TableRows as TableRowsIcon,
} from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";
import { Link, useLocation } from "react-router-dom";

// Generic MenuItem for all menu links
function MenuItem({ to, icon, label, tooltip, selected, open, ...props }) {
  return (
    <Tooltip title={tooltip || label} placement="right" arrow disableHoverListener={open}>
      <ListItemButton
        component={Link}
        to={to}
        selected={selected}
        sx={{
          minHeight: 36,
          px: open ? 2 : 1.5,
          borderRadius: 1.5,
          justifyContent: open ? "flex-start" : "center",
          ...props.sx,
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
}

export default function SidebarMenu({ open }) {
  const location = useLocation();
  const {
    context, canSchemaAdmin, canManageAllModules, canManageAssignedModules,
  } = useAuth();

  // Collapsible menu state
  const [openMenus, setOpenMenus] = useState({ schemaManager: true });
  const [openModuleMenus, setOpenModuleMenus] = useState({});

  // Get modules and roles from context
  const modules = context?.modules || [];
  const projectRoles = context?.projectRoles || [];
  const { tablesByModule = {} } = useAuth();

  // Show modules based on role
  let visibleModules = [];
  if (canSchemaAdmin() || canManageAllModules()) {
    visibleModules = modules;
  } else if (canManageAssignedModules()) {
    const moduleIds = projectRoles
      .filter(r => r.role === "dataowners_group" && r.module_id)
      .map(r => r.module_id);
    visibleModules = modules.filter(m => moduleIds.includes(m.id));
  }

  // --- Auto-expand module if current route is viewing one of its tables ---
  useEffect(() => {
    const path = location.pathname;
    const match = path.match(/^\/dataschema\/entry\/(\d+)\/(\d+)/);
    if (match) {
      const moduleId = parseInt(match[1]);
      setOpenModuleMenus(prev => ({ ...prev, [moduleId]: true }));
    }
  }, [location.pathname]);

  const isSchemaManagerActive = location.pathname.startsWith("/schema-admin");

  const menu = [
    {
      type: "menu",
      to: "/dashboard",
      icon: <DashboardIcon />,
      label: "Dashboard",
      tooltip: "Dashboard",
      match: path => path === "/dashboard",
    },
    ...visibleModules.map(mod => ({
      type: "module",
      module: mod,
      to: `/modules/${mod.id}`,
      icon: <TableIcon />,
      label: mod.name,
      tooltip: mod.description || mod.name,
      match: path => path.startsWith(`/modules/${mod.id}`),
      tables: tablesByModule[String(mod.id)] || [],
    })),
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
    <List sx={{ pt: 1 }}>
      {/* --- Schema Manager parent --- */}
      {canSchemaAdmin() && (
        <>
          <ListItemButton
            onClick={() => setOpenMenus(prev => ({ ...prev, schemaManager: !prev.schemaManager }))}
            sx={{
              minHeight: 36,
              px: open ? 2 : 1.5,
              borderRadius: 1.5,
              justifyContent: open ? "flex-start" : "center",
              bgcolor: isSchemaManagerActive ? "action.selected" : "transparent"
            }}
          >
            <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
              <Tooltip title="Schema Manager" placement="right" arrow disableHoverListener={open}>
                <SchemaAdminIcon />
              </Tooltip>
            </ListItemIcon>
            {open && <ListItemText primary="Schema Manager" />}
            {open && (openMenus.schemaManager ? <ExpandLess /> : <ExpandMore />)}
          </ListItemButton>
          <Collapse in={open && openMenus.schemaManager} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              <MenuItem
                to="/schema-admin/table-manager"
                icon={<TableRowsIcon />}
                label="Table Manager"
                selected={location.pathname.startsWith("/schema-admin/table-manager")}
                open={open}
                sx={{ pl: open ? 4 : 1.5 }}
              />
            </List>
          </Collapse>
        </>
      )}

      {/* --- Render Modules and their tables --- */}
      {menu.map((item, idx) => {
        if (item.type === "divider") return <Divider key={`div-${idx}`} />;
        if (item.type === "module") {
          const { module, tables, ...rest } = item;
          const isActiveModule = location.pathname.startsWith(`/modules/${module.id}`) ||
            (location.pathname.startsWith("/dataschema/entry/") && location.pathname.includes(`/${module.id}/`));
          const hasTables = tables && tables.length > 0;

          return (
            <React.Fragment key={module.id}>
              <ListItemButton
                onClick={() => hasTables ? setOpenModuleMenus(prev => ({ ...prev, [module.id]: !prev[module.id] })) : undefined}
                component={hasTables ? undefined : Link}
                to={hasTables ? undefined : `/modules/${module.id}`}
                selected={isActiveModule && !hasTables}
                sx={{
                  minHeight: 36,
                  px: open ? 2 : 1.5,
                  borderRadius: 1.5,
                  justifyContent: open ? "flex-start" : "center",
                  ...(open && hasTables ? { fontWeight: 500 } : {}),
                }}
              >
                <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
                  {item.icon}
                </ListItemIcon>
                {open && <ListItemText primary={item.label} />}
                {open && hasTables && (openModuleMenus[module.id] ? <ExpandLess /> : <ExpandMore />)}
              </ListItemButton>
              {/* Tables under this module */}
              {hasTables && (
                <Collapse in={open && openModuleMenus[module.id]} timeout="auto" unmountOnExit>
                  <List component="div" disablePadding>
                    {tables.map(table => (
                      <MenuItem
                        key={table.id}
                        to={`/dataschema/entry/${module.id}/${table.id}`}
                        icon={<TableRowsIcon />}
                        label={table.title}
                        tooltip={table.title}
                        selected={location.pathname === `/dataschema/entry/${module.id}/${table.id}`}
                        open={open}
                        sx={{ pl: open ? 4 : 1.5 }}
                      />
                    ))}
                  </List>
                </Collapse>
              )}
            </React.Fragment>
          );
        }
        return (
          <MenuItem
            key={item.to}
            to={item.to}
            icon={item.icon}
            label={item.label}
            tooltip={item.tooltip}
            selected={item.match(location.pathname)}
            open={open}
          />
        );
      })}
    </List>
  );
}