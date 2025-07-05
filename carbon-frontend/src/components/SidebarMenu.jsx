import React, { useState, useEffect } from "react";
import {
  List, ListItemButton, ListItemIcon, ListItemText, Collapse, Tooltip, Divider, CircularProgress,
} from "@mui/material";
import {
  ExpandLess, ExpandMore,
  TableChart as TableIcon,
  ListAlt as TableManageIcon,
  SettingsApplications as SchemaAdminIcon,
  Help as HelpIcon,
  Settings as ProjectSettingsIcon,
} from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";
import { Link, useLocation } from "react-router-dom";
import { fetchDataSchemaTables } from "../api/dataschema";
import { fetchModules } from "../api/modules";

// Helper: check permission in current context with project_id and module_id
function hasPermission(user, currentContext, perm) {
  if (!user?.roles || !currentContext) return false;
  return user.roles.some(
    r =>
      r.active &&
      (
        (r.context_type === "project" && String(r.project_id) === String(currentContext.project_id))
        ||
        (r.context_type === "module" && String(r.module_id) === String(currentContext.module_id))
      ) &&
      (r.permissions || []).includes(perm)
  );
}

export default function SidebarMenu({ open }) {
  const { user, currentContext } = useAuth();
  const location = useLocation();
  const [modules, setModules] = useState([]);
  const [moduleOpens, setModuleOpens] = useState({});
  const [moduleTables, setModuleTables] = useState({});
  const [loadingTables, setLoadingTables] = useState({});

  // Always use project_id for fetchModules
  useEffect(() => {
    if (user && currentContext?.project_id) {
      fetchModules(user.token, currentContext.project_id)
        .then(setModules)
        .catch(() => setModules([]));
    }
  }, [user, currentContext]);

  // Fetch tables for each module (for menu display)
  useEffect(() => {
    if (!user || !currentContext?.project_id || !modules.length) return;
    modules.forEach(mod => {
      setLoadingTables(prev => ({ ...prev, [mod.id]: true }));
      fetchDataSchemaTables(user.token, currentContext.project_id, mod.id)
        .then(tables => {
          setModuleTables(prev => ({ ...prev, [mod.id]: tables || [] }));
        })
        .finally(() => setLoadingTables(prev => ({ ...prev, [mod.id]: false })));
    });
  }, [user, currentContext, modules]);

  // "Schema Admin" menu: show if user has manage_schema permission in this context
  const canSchemaAdmin = hasPermission(user, currentContext, "manage_schema");

  const isTableActive = (modId, tableId) =>
    location.pathname === `/dataschema/entry/${modId}/${tableId}`;

  const MenuItem = ({ to, icon, label, tooltip, selected, ...props }) => (
    <Tooltip title={tooltip || label} placement="right" arrow disableHoverListener={open ? true : false}>
      <ListItemButton
        component={Link}
        to={to}
        selected={selected}
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
      {/* SCHEMA ADMIN: Only Table Manager, permission-based */}
      {canSchemaAdmin && (
        <>
          <ListItemButton
            onClick={() => setModuleOpens(prev => ({ ...prev, _schemaAdmin: !prev._schemaAdmin }))}
            sx={{
              minHeight: 36,
              px: open ? 2 : 1.5,
              borderRadius: 1.5,
              justifyContent: open ? "flex-start" : "center"
            }}
            selected={location.pathname.startsWith("/dataschema/manage/tablemanager")}
          >
            <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
              <SchemaAdminIcon />
            </ListItemIcon>
            {open && <ListItemText primary="Schema Admin" />}
            {open && (moduleOpens._schemaAdmin ? <ExpandLess /> : <ExpandMore />)}
          </ListItemButton>
          <Collapse in={moduleOpens._schemaAdmin && open} timeout="auto" unmountOnExit>
            <MenuItem
              to="/dataschema/manage/tablemanagerpage"
              icon={<TableManageIcon />}
              label="Tables Manager"
              tooltip="Manage Tables & Fields"
              sx={{ pl: 4 }}
              selected={location.pathname === "/dataschema/manage/tablemanagerpage"}
            />
          </Collapse>
          <Divider />
        </>
      )}

      {/* MODULES: Only Data Entry (Rows) for each table */}
      {modules.map((mod) => (
        <React.Fragment key={mod.id}>
          <ListItemButton
            sx={{
              minHeight: 36,
              pl: open ? 2 : 1.5,
              borderRadius: 1.5,
              justifyContent: open ? "flex-start" : "center"
            }}
            onClick={() => setModuleOpens(prev => ({ ...prev, [mod.id]: !prev[mod.id] }))}
          >
            <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
              <TableIcon />
            </ListItemIcon>
            {open && <ListItemText primary={mod.name} />}
            {open && (moduleOpens[mod.id] ? <ExpandLess /> : <ExpandMore />)}
          </ListItemButton>
          <Collapse in={moduleOpens[mod.id] && open} timeout="auto" unmountOnExit>
            {loadingTables[mod.id] ? (
              <ListItemButton disabled sx={{ pl: 4 }}>
                <ListItemIcon>
                  <CircularProgress size={20} />
                </ListItemIcon>
                {open && <ListItemText primary="Loading tables..." />}
              </ListItemButton>
            ) : (
              (moduleTables[mod.id] || [])
                .filter(table => table.module === mod.id || table.module_id === mod.id)
                // Only show if user has view_data or manage_data permission for this module context
                .filter(table => {
                  // For module context, check if user has permission in this module
                  const fakeModuleContext = {
                    ...currentContext,
                    module_id: mod.id,
                    context_type: "module",
                  };
                  return (
                    hasPermission(user, fakeModuleContext, "view_data") ||
                    hasPermission(user, fakeModuleContext, "manage_data")
                  );
                })
                .map(table => (
                  <MenuItem
                    key={table.id}
                    to={`/dataschema/entry/${mod.id}/${table.id}`} // <-- Always use mod.id, never mod.name or mod.title!
                    icon={<TableIcon />}
                    label={table.title}
                    tooltip={table.description || table.title}
                    sx={{ pl: 4 }}
                    selected={isTableActive(mod.id, table.id)}
                  />
                ))
            )}
          </Collapse>
        </React.Fragment>
      ))}

      <Divider />

      {/* Help and Project Settings */}
      <MenuItem
        to="/help"
        icon={<HelpIcon />}
        label="Help"
        tooltip="Get Help"
        selected={location.pathname === "/help"}
      />
      <MenuItem
        to="/settings"
        icon={<ProjectSettingsIcon />}
        label="Project Settings"
        tooltip="Manage Project Settings"
        selected={location.pathname === "/settings"}
      />
    </List>
  );
}