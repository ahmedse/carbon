// src/pages/AdminDashboard/components/Sidebar.jsx
import React from "react";
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
} from "@mui/material";
import DashboardIcon from "@mui/icons-material/Dashboard";
import WaterDropIcon from "@mui/icons-material/WaterDrop";
import BoltIcon from "@mui/icons-material/Bolt";
import LocalGasStationIcon from "@mui/icons-material/LocalGasStation";
import { Link, useLocation } from "react-router-dom";

const drawerWidth = 220;

const menuItems = [
  { label: "Dashboard", icon: <DashboardIcon />, path: "/admin" },
  { label: "Water", icon: <WaterDropIcon />, path: "/admin/water" },
  { label: "Electricity", icon: <BoltIcon />, path: "/admin/electricity" },
  { label: "Gas", icon: <LocalGasStationIcon />, path: "/admin/gas" },
];

const Sidebar = ({ open, onClose }) => {
  const location = useLocation();

  return (
    <Drawer
      variant="permanent"
      open={open}
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: drawerWidth,
          boxSizing: "border-box",
          top: { xs: 56, sm: 64 }, // Adjust if your Topbar/AppBar height differs
          height: "auto",
        },
        display: { xs: open ? "block" : "none", md: "block" },
      }}
    >
      <List>
        {menuItems.map((item) => (
          <React.Fragment key={item.label}>
            <ListItem disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={
                  item.path === ""
                    ? location.pathname === "/admin"
                    : location.pathname.startsWith(`/admin/${item.path}`)
                }
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
            {item.label === "Gas" && <Divider />}
          </React.Fragment>
        ))}
      </List>
    </Drawer>
  );
};

export default Sidebar;