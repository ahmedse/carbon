// src/pages/AdminDashboard/AdminDashboard.jsx

import React, { useState } from "react";
import { Box, Toolbar, useMediaQuery } from "@mui/material";
import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import DashboardHome from "./DashboardHome";
import WaterModule from "./WaterModule";
import ElectricityModule from "./ElectricityModule";
import GasModule from "./GasModule";

const drawerWidth = 220;

const AdminDashboard = ({ context }) => {
  // Responsive sidebar drawer state
  const [mobileOpen, setMobileOpen] = useState(false);
  const isMdUp = useMediaQuery((theme) => theme.breakpoints.up("md"));

  const handleDrawerToggle = () => setMobileOpen(!mobileOpen);

  const dashboardTitle =
    context?.project
      ? `Admin Dashboard (Project: ${context.project})`
      : context?.cycle
      ? `Admin Dashboard (Cycle: ${context.cycle})`
      : context?.module
      ? `Admin Dashboard (Module: ${context.module})`
      : "Admin Dashboard";

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <Sidebar open={isMdUp || mobileOpen} onClose={handleDrawerToggle} />
      <Box sx={{ flexGrow: 1, ml: { md: `${drawerWidth}px` }, width: "100%" }}>
        <Topbar title={dashboardTitle} drawerToggle={handleDrawerToggle} />
        <Toolbar /> {/* Spacer below Topbar */}
        <Box sx={{ p: { xs: 1, sm: 2, md: 3 }, maxWidth: 1400, mx: "auto", width: "100%" }}>
          <Routes>
            <Route index element={<DashboardHome context={context} />} />
            <Route path="water" element={<WaterModule context={context} />} />
            <Route path="electricity" element={<ElectricityModule context={context} />} />
            <Route path="gas" element={<GasModule context={context} />} />
            {/* fallback */}
            <Route path="*" element={<Navigate to="." replace />} />
          </Routes>
        </Box>
      </Box>
    </Box>
  );
};

export default AdminDashboard;