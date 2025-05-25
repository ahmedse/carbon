import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import AdminDashboard from "./AdminDashboard/AdminDashboard";
import DataOwnerDashboard from "./DataOwnerDashboard";
import AuditorDashboard from "./AuditorDashboard";
import { Box, CircularProgress, Typography, Alert, MenuItem, Select, FormControl, InputLabel } from "@mui/material";
import { API_BASE_URL, API_ROUTES } from "../config";

/**
 * Main dashboard component.
 * Lets the user select a context and loads the appropriate dashboard based on their role.
 */
const Dashboard = () => {
  const { user } = useAuth();
  const token = user?.token;

  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [contexts, setContexts] = useState([]);
  const [selectedContext, setSelectedContext] = useState("");
  const navigate = useNavigate();

  // Fetch user roles and available contexts on mount
  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }

    const fetchRoles = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}${API_ROUTES.myRoles}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setRoles(data.roles || []);
          // Extract available contexts for selection
          const contextList = (data.roles || []).map((r, idx) => ({
            key: `${r.context_type}:${r.project || r.cycle || r.module || idx}`,
            label: `${r.context_type === "project" ? r.project : r.context_type === "cycle" ? r.cycle : r.module} (${r.role})`,
            ...r
          }));
          setContexts(contextList);
        } else {
          setError("Failed to fetch roles.");
        }
      } catch (err) {
        setError("Error fetching roles.");
      } finally {
        setLoading(false);
      }
    };

    fetchRoles();
  }, [token, navigate]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }
  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }
  if (!roles.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <Typography variant="h5">No roles assigned to you.</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        flex: 1,
        width: "100vw",
        maxWidth: "100vw",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        px: 0,
        py: 0,
        minHeight: "100vh",
      }}
    >
      {/* Only show the context selector if no context is selected */}
      {!selectedContext && (
        <>
          <Typography variant="h5" gutterBottom>
            Select your context
          </Typography>
          <FormControl sx={{ minWidth: 300, mb: 3 }}>
            <InputLabel id="context-select-label">Context</InputLabel>
            <Select
              labelId="context-select-label"
              value={selectedContext}
              label="Context"
              onChange={e => setSelectedContext(e.target.value)}
            >
              {contexts.map(ctx => (
                <MenuItem key={ctx.key} value={ctx.key}>
                  {ctx.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </>
      )}
      {/* Show dashboard for the selected context */}
      {selectedContext && (() => {
        const ctx = contexts.find(c => c.key === selectedContext);
        if (!ctx) return null;
        if (ctx.role.includes("admin")) return <AdminDashboard context={ctx} />;
        if (ctx.role.includes("data_owner") || ctx.role.includes("data-owner")) return <DataOwnerDashboard context={ctx} />;
        if (ctx.role.includes("auditor")) return <AuditorDashboard context={ctx} />;
        return <Typography>No dashboard available for your role in this context.</Typography>;
      })()}
    </Box>
  );
};

export default Dashboard;