// src/components/SidebarMenuRefactored.jsx
// Perspective-driven sidebar refactoring

import React, { useState, useEffect, useMemo } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import {
  List, ListItemButton, ListItemIcon, ListItemText, Tooltip, Divider, Collapse, Box,
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
  CalculateRounded as CalculateIcon,
  AssessmentRounded as ReportIcon,
  ShowChartRounded as AnalyticsIcon,
  TrackChangesRounded as TargetsIcon,
  VerifiedUserRounded as QualityIcon,
  DescriptionRounded as ReportingIcon,
  LocationCityRounded as OrgIcon,
  AdminPanelSettingsRounded as AccessIcon,
} from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";

const SCOPE_META = {
  1: {
    label: "Scope 1",
    icon: <Scope1Icon sx={{ color: "#10b981" }} />,
    desc: "Direct emissions",
  },
  2: {
    label: "Scope 2",
    icon: <Scope2Icon sx={{ color: "#3b82f6" }} />,
    desc: "Indirect energy",
  },
  3: {
    label: "Scope 3",
    icon: <Scope3Icon sx={{ color: "#f97316" }} />,
    desc: "Value chain emissions",
  },
};

function MenuItem({
  to, icon, label, tooltip, selected, collapsed, sx = {}, secondary, ...props
}) {
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
          px: 1.5,
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
        <ListItemIcon
          sx={{
            minWidth: 0,
            mr: collapsed ? 0 : 1.5,
            justifyContent: "center",
            color: selected ? "#16a34a" : "#6b7280",
          }}
        >
          {icon}
        </ListItemIcon>
        {isExpanded && (
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
        )}
      </ListItemButton>
    </Tooltip>
  );
}

// --- Data Entry Sidebar (lean operator view) ---
function DataEntrySidebar({ collapsed, location, navigate, modules, tablesByModule }) {
  const open = !collapsed;
  const [openScopeMenus, setOpenScopeMenus] = useState({ 1: true, 2: true, 3: true });
  const [openModuleMenus, setOpenModuleMenus] = useState({});

  // Group modules by scope
  const modulesByScope = useMemo(() => {
    const grouped = { 1: [], 2: [], 3: [] };
    modules.forEach(mod => {
      const scope = mod.scope || 1;
      if (grouped[scope]) {
        grouped[scope].push(mod);
      }
    });
    return grouped;
  }, [modules]);

  // Auto-expand logic
  useEffect(() => {
    const match = location.pathname.match(/^\/dataschema\/entry\/(\d+)\/(\d+)/);
    if (match) {
      const moduleId = parseInt(match[1]);
      for (const [scope, mods] of Object.entries(modulesByScope)) {
        if (mods.some(m => Number(m.id) === moduleId)) {
          setOpenScopeMenus(prev => ({ ...prev, [scope]: true }));
          setOpenModuleMenus(prev => ({ ...prev, [moduleId]: true }));
          break;
        }
      }
    }
  }, [location.pathname, modulesByScope]);

  return (
    <List sx={{ pt: 0.5, pb: 2, px: 0.5 }}>
      {/* My Dashboard */}
      <MenuItem
        to="/modules"
        icon={<DashboardIcon />}
        label="My Dashboard"
        selected={location.pathname === "/modules" || location.pathname === "/dashboard"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />

      <Divider sx={{ my: 1, mx: 1 }} />

      {/* Scopes with Modules */}
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
                  {openScopeMenus[scope] ? (
                    <ExpandLess sx={{ fontSize: 16, color: "#9ca3af" }} />
                  ) : (
                    <ExpandMore sx={{ fontSize: 16, color: "#9ca3af" }} />
                  )}
                </>
              )}
            </ListItemButton>

            {/* Modules in Scope */}
            <Collapse in={open && openScopeMenus[scope]} timeout="auto" unmountOnExit>
              <List component="div" disablePadding sx={{ pl: 1 }}>
                {mods.map(mod => {
                  const tables = (tablesByModule[String(mod.id)] || []).filter(t => t.is_active !== false);
                  const isActiveModule =
                    location.pathname.startsWith(`/modules/${mod.id}`) ||
                    location.pathname.includes(`/${mod.id}/`);

                  return (
                    <React.Fragment key={mod.id}>
                      <ListItemButton
                        onClick={() =>
                          tables.length > 0
                            ? setOpenModuleMenus(prev => ({ ...prev, [mod.id]: !prev[mod.id] }))
                            : navigate(`/modules/${mod.id}`)
                        }
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
                        {open && (
                          <ListItemText
                            primary={mod.name}
                            primaryTypographyProps={{
                              fontWeight: isActiveModule ? 600 : 500,
                              fontSize: "0.8125rem",
                              color: isActiveModule ? "#16a34a" : "#374151",
                            }}
                          />
                        )}
                      </ListItemButton>
                    </React.Fragment>
                  );
                })}
              </List>
            </Collapse>
          </React.Fragment>
        ) : null
      )}

      <Divider sx={{ my: 1, mx: 1 }} />

      {/* Help & Feedback */}
      <MenuItem
        to="/help"
        icon={<HelpIcon />}
        label="Help"
        selected={location.pathname === "/help"}
        collapsed={collapsed}
      />
      <MenuItem
        to="/feedback"
        icon={<FeedbackIcon />}
        label="Feedback"
        selected={location.pathname === "/feedback"}
        collapsed={collapsed}
      />
    </List>
  );
}

// --- Admin Sidebar (organized admin view) ---
function AdminSidebar({ collapsed, location }) {
  const open = !collapsed;
  const [openMenus, setOpenMenus] = useState({ org: true, schema: true, dashboards: true });

  return (
    <List sx={{ pt: 0.5, pb: 2, px: 0.5 }}>
      {/* Organization Section */}
      <ListItemButton
        onClick={() => setOpenMenus(prev => ({ ...prev, org: !prev.org }))}
        sx={{
          minHeight: 36,
          py: 0.75,
          px: 1.5,
          mx: 0.5,
          borderRadius: 1,
          justifyContent: open ? "flex-start" : "center",
          color: location.pathname.startsWith("/admin/org") ? "#0ea5e9" : "#374151",
          bgcolor: location.pathname.startsWith("/admin/org") ? "#f0f9ff" : "transparent",
          "&:hover": { bgcolor: "#f3f4f6" },
        }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: open ? 1.5 : 0, justifyContent: "center" }}>
          <Tooltip title="Organization" placement="right" arrow disableHoverListener={open}>
            <OrgIcon sx={{ fontSize: 20, color: location.pathname.startsWith("/admin/org") ? "#0ea5e9" : "#6b7280" }} />
          </Tooltip>
        </ListItemIcon>
        {open && (
          <>
            <ListItemText primary="Organization" primaryTypographyProps={{ fontWeight: 600, fontSize: "0.8125rem" }} />
            {openMenus.org ? (
              <ExpandLess sx={{ fontSize: 16, color: "#9ca3af" }} />
            ) : (
              <ExpandMore sx={{ fontSize: 16, color: "#9ca3af" }} />
            )}
          </>
        )}
      </ListItemButton>
      <Collapse in={open && openMenus.org} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          <MenuItem
            to="/admin/org-units"
            icon={<OrgIcon sx={{ fontSize: 18 }} />}
            label="Org Units"
            selected={location.pathname.startsWith("/admin/org-units")}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
          <MenuItem
            to="/admin/users"
            icon={<TableRowsIcon sx={{ fontSize: 18 }} />}
            label="Users"
            selected={location.pathname.startsWith("/admin/users")}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
          <MenuItem
            to="/admin/access"
            icon={<AccessIcon sx={{ fontSize: 18 }} />}
            label="Access Control"
            selected={location.pathname.startsWith("/admin/access")}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
        </List>
      </Collapse>

      <Divider sx={{ my: 1, mx: 1 }} />

      {/* Schema Section */}
      <ListItemButton
        onClick={() => setOpenMenus(prev => ({ ...prev, schema: !prev.schema }))}
        sx={{
          minHeight: 36,
          py: 0.75,
          px: 1.5,
          mx: 0.5,
          borderRadius: 1,
          justifyContent: open ? "flex-start" : "center",
          color: location.pathname.startsWith("/schema-admin") ? "#7c3aed" : "#374151",
          bgcolor: location.pathname.startsWith("/schema-admin") ? "#f5f3ff" : "transparent",
          "&:hover": { bgcolor: "#f3f4f6" },
        }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: open ? 1.5 : 0, justifyContent: "center" }}>
          <Tooltip title="Schema" placement="right" arrow disableHoverListener={open}>
            <SchemaAdminIcon sx={{ fontSize: 20, color: location.pathname.startsWith("/schema-admin") ? "#7c3aed" : "#6b7280" }} />
          </Tooltip>
        </ListItemIcon>
        {open && (
          <>
            <ListItemText primary="Schema Management" primaryTypographyProps={{ fontWeight: 600, fontSize: "0.8125rem" }} />
            {openMenus.schema ? (
              <ExpandLess sx={{ fontSize: 16, color: "#9ca3af" }} />
            ) : (
              <ExpandMore sx={{ fontSize: 16, color: "#9ca3af" }} />
            )}
          </>
        )}
      </ListItemButton>
      <Collapse in={open && openMenus.schema} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          <MenuItem
            to="/schema-admin/table-manager"
            icon={<TableRowsIcon sx={{ fontSize: 18 }} />}
            label="Table Manager"
            selected={location.pathname.startsWith("/schema-admin/table-manager")}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
        </List>
      </Collapse>

      <Divider sx={{ my: 1, mx: 1 }} />

      {/* Dashboards Section */}
      <ListItemButton
        onClick={() => setOpenMenus(prev => ({ ...prev, dashboards: !prev.dashboards }))}
        sx={{
          minHeight: 36,
          py: 0.75,
          px: 1.5,
          mx: 0.5,
          borderRadius: 1,
          justifyContent: open ? "flex-start" : "center",
          color: location.pathname.startsWith("/dashboard") || location.pathname === "/" ? "#16a34a" : "#374151",
          bgcolor: location.pathname.startsWith("/dashboard") || location.pathname === "/" ? "#f0fdf4" : "transparent",
          "&:hover": { bgcolor: "#f3f4f6" },
        }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: open ? 1.5 : 0, justifyContent: "center" }}>
          <Tooltip title="Dashboards" placement="right" arrow disableHoverListener={open}>
            <DashboardIcon sx={{ fontSize: 20, color: location.pathname.startsWith("/dashboard") || location.pathname === "/" ? "#16a34a" : "#6b7280" }} />
          </Tooltip>
        </ListItemIcon>
        {open && (
          <>
            <ListItemText primary="Dashboards" primaryTypographyProps={{ fontWeight: 600, fontSize: "0.8125rem" }} />
            {openMenus.dashboards ? (
              <ExpandLess sx={{ fontSize: 16, color: "#9ca3af" }} />
            ) : (
              <ExpandMore sx={{ fontSize: 16, color: "#9ca3af" }} />
            )}
          </>
        )}
      </ListItemButton>
      <Collapse in={open && openMenus.dashboards} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          <MenuItem
            to="/dashboard"
            icon={<DashboardIcon sx={{ fontSize: 18 }} />}
            label="Executive Summary"
            selected={location.pathname === "/dashboard" || location.pathname === "/"}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
          <MenuItem
            to="/dashboards/analytics"
            icon={<AnalyticsIcon sx={{ fontSize: 18 }} />}
            label="Analytics"
            selected={location.pathname === "/dashboards/analytics"}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
          <MenuItem
            to="/dashboards/targets"
            icon={<TargetsIcon sx={{ fontSize: 18 }} />}
            label="Targets & Progress"
            selected={location.pathname === "/dashboards/targets"}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
          <MenuItem
            to="/dashboards/data-quality"
            icon={<QualityIcon sx={{ fontSize: 18 }} />}
            label="Data Quality"
            selected={location.pathname === "/dashboards/data-quality"}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
          <MenuItem
            to="/dashboards/reporting"
            icon={<ReportingIcon sx={{ fontSize: 18 }} />}
            label="Reporting"
            selected={location.pathname === "/dashboards/reporting"}
            collapsed={collapsed}
            sx={{ pl: 4 }}
          />
        </List>
      </Collapse>

      <Divider sx={{ my: 1, mx: 1 }} />

      {/* Help & Feedback */}
      <MenuItem
        to="/help"
        icon={<HelpIcon />}
        label="Help"
        selected={location.pathname === "/help"}
        collapsed={collapsed}
      />
      <MenuItem
        to="/feedback"
        icon={<FeedbackIcon />}
        label="Feedback"
        selected={location.pathname === "/feedback"}
        collapsed={collapsed}
      />
    </List>
  );
}

// --- Dashboard Sidebar (all 5 dashboard views) ---
function DashboardSidebar({ collapsed, location }) {
  const open = !collapsed;

  return (
    <List sx={{ pt: 0.5, pb: 2, px: 0.5 }}>
      <MenuItem
        to="/dashboard"
        icon={<DashboardIcon />}
        label="Executive Summary"
        tooltip="Overview of your carbon footprint"
        selected={location.pathname === "/dashboard" || location.pathname === "/" || location.pathname === "/dashboards/executive"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />
      <MenuItem
        to="/dashboards/analytics"
        icon={<AnalyticsIcon />}
        label="Analytics"
        tooltip="Deep dive with date range analysis"
        selected={location.pathname === "/dashboards/analytics"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />
      <MenuItem
        to="/dashboards/targets"
        icon={<TargetsIcon />}
        label="Targets & Progress"
        tooltip="Track SBTi and net-zero goals"
        selected={location.pathname === "/dashboards/targets"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />
      <MenuItem
        to="/dashboards/data-quality"
        icon={<QualityIcon />}
        label="Data Quality"
        tooltip="Data completeness and audit readiness"
        selected={location.pathname === "/dashboards/data-quality"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />
      <MenuItem
        to="/dashboards/reporting"
        icon={<ReportingIcon />}
        label="Reporting"
        tooltip="Framework compliance and reports"
        selected={location.pathname === "/dashboards/reporting"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />

      <Divider sx={{ my: 1, mx: 1 }} />

      <MenuItem
        to="/help"
        icon={<HelpIcon />}
        label="Help"
        selected={location.pathname === "/help"}
        collapsed={collapsed}
      />
      <MenuItem
        to="/feedback"
        icon={<FeedbackIcon />}
        label="Feedback"
        selected={location.pathname === "/feedback"}
        collapsed={collapsed}
      />
    </List>
  );
}

// --- Data Owner Sidebar (scoped data owner view) ---
function DataOwnerSidebar({ collapsed, location }) {
  const open = !collapsed;

  return (
    <List sx={{ pt: 0.5, pb: 2, px: 0.5 }}>
      {/* My Data Section */}
      <Typography
        variant="caption"
        sx={{
          fontWeight: 700,
          fontSize: "0.7rem",
          color: "#9ca3af",
          textTransform: "uppercase",
          px: 1.5,
          py: 1,
          display: "block",
        }}
      >
        {open ? "My Data" : ""}
      </Typography>

      <MenuItem
        to="/data-owner"
        icon={<DashboardIcon />}
        label="My Portal"
        tooltip="Overview of your domain assets"
        selected={location.pathname === "/data-owner"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />
      <MenuItem
        to="/data-owner/dashboard"
        icon={<AnalyticsIcon />}
        label="My Dashboard"
        tooltip="Emissions KPIs and data quality"
        selected={location.pathname === "/data-owner/dashboard"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />
      <MenuItem
        to="/data-owner/assets"
        icon={<TableIcon />}
        label="My Assets"
        tooltip="Scoped asset browser"
        selected={location.pathname === "/data-owner/assets"}
        collapsed={collapsed}
        sx={{ mb: 0.5 }}
      />

      <Divider sx={{ my: 1, mx: 1 }} />

      <MenuItem
        to="/help"
        icon={<HelpIcon />}
        label="Help"
        selected={location.pathname === "/help"}
        collapsed={collapsed}
      />
      <MenuItem
        to="/feedback"
        icon={<FeedbackIcon />}
        label="Feedback"
        selected={location.pathname === "/feedback"}
        collapsed={collapsed}
      />
    </List>
  );
}

// --- Main Perspective-Driven Dispatcher ---
export default function SidebarMenu({ collapsed }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { currentPerspective, context, tablesByModule } = useAuth();

  const modules = context?.modules || [];
  const hasDataOwnerScope = context?.org_units && context.org_units.length > 0;

  // Render correct sidebar based on perspective or role
  if (currentPerspective === "admin") {
    return <AdminSidebar collapsed={collapsed} location={location} />;
  }
  if (currentPerspective === "dashboards") {
    return <DashboardSidebar collapsed={collapsed} location={location} />;
  }
  // Data owner with scoped role gets dedicated sidebar
  if (hasDataOwnerScope && !modules.length) {
    return <DataOwnerSidebar collapsed={collapsed} location={location} />;
  }
  // Default: data_entry
  return (
    <DataEntrySidebar
      collapsed={collapsed}
      location={location}
      navigate={navigate}
      modules={modules}
      tablesByModule={tablesByModule}
    />
  );
}
