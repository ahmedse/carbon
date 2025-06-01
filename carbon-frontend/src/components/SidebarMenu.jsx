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

function isAdmin(user, currentContext) {
  return user?.roles?.some(
    r => r.project_id === currentContext.context_id &&
      r.active &&
      r.role === "admin_role"
  );
}

export default function SidebarMenu({ open }) {
  const { user, currentContext } = useAuth();
  const location = useLocation();
  const [modules, setModules] = useState([]);
  const [moduleOpens, setModuleOpens] = useState({});
  const [moduleTables, setModuleTables] = useState({});
  const [loadingTables, setLoadingTables] = useState({});

  useEffect(() => {
    if (user && currentContext) {
      fetchModules(user.token, currentContext.context_id)
        .then(setModules)
        .catch(() => setModules([]));
    }
  }, [user, currentContext]);

  // Fetch tables for each module (for menu display)
  useEffect(() => {
    if (!user || !currentContext || !modules.length) return;
    modules.forEach(mod => {
      setLoadingTables(prev => ({ ...prev, [mod.name]: true }));
      fetchDataSchemaTables(user.token, currentContext.context_id, mod.id)
        .then(tables => {
          setModuleTables(prev => ({ ...prev, [mod.name]: tables || [] }));
        })
        .finally(() => setLoadingTables(prev => ({ ...prev, [mod.name]: false })));
    });
  }, [user, currentContext, modules]);

  // Top-level: Schema Admin with Table Manager only
  const admin = isAdmin(user, currentContext);

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
      {/* SCHEMA ADMIN: Only Table Manager */}
      {admin && (
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
              to="/dataschema/manage/tablemanager"
              icon={<TableManageIcon />}
              label="Table Manager"
              tooltip="Manage Tables & Fields"
              sx={{ pl: 4 }}
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
            onClick={() => setModuleOpens(prev => ({ ...prev, [mod.name]: !prev[mod.name] }))}
          >
            <ListItemIcon sx={{ minWidth: 0, mr: open ? 2 : "auto", justifyContent: "center" }}>
              <TableIcon />
            </ListItemIcon>
            {open && <ListItemText primary={mod.name} />}
            {open && (moduleOpens[mod.name] ? <ExpandLess /> : <ExpandMore />)}
          </ListItemButton>
          <Collapse in={moduleOpens[mod.name] && open} timeout="auto" unmountOnExit>
            {loadingTables[mod.name] ? (
              <ListItemButton disabled sx={{ pl: 4 }}>
                <ListItemIcon>
                  <CircularProgress size={20} />
                </ListItemIcon>
                {open && <ListItemText primary="Loading tables..." />}
              </ListItemButton>
            ) : (
              (moduleTables[mod.name] || [])
              .filter(table => table.module === mod.id || table.module_id === mod.id)
              .map(table => (
                <MenuItem
                  key={table.id}
                  to={`/dataschema/entry/${mod.name.toLowerCase()}/${table.id}`}
                  icon={<TableIcon />}
                  label={table.title}
                  tooltip={table.description || table.title}
                  sx={{ pl: 4 }}
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
      />
      <MenuItem
        to="/settings"
        icon={<ProjectSettingsIcon />}
        label="Project Settings"
        tooltip="Manage Project Settings"
      />
    </List>
  );
}