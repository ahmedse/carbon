import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  Box, Button, TextField, Typography, Alert, Paper, CircularProgress, MenuItem, Select,
} from "@mui/material";
import { Navigate, useNavigate } from "react-router-dom";
import aastLogo from "../assets/aast_carbon_logo_.jpg";
import { useLocation } from "react-router-dom";


export default function Login() {
  const {
    user, projects, context, loading, login, selectProject,
  } = useAuth();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [projectSelection, setProjectSelection] = useState("");
  const [requireProject, setRequireProject] = useState(false);

  const location = useLocation();
  const expired = location.search.includes("expired=1");

  const navigate = useNavigate();

  // Already logged in and project selected? Go to dashboard.
  if (user && context?.projectId) return <Navigate to="/dashboard" replace />;

  // Project selection UI only at login
  if (user && projects.length > 1 && requireProject) {
    return (
      <Box sx={{ maxWidth: 400, mx: "auto", mt: 10 }}>
        <Paper sx={{ p: 4, borderRadius: 4 }}>
          <Typography variant="h6" align="center" mb={2}>
            Select a Project
          </Typography>
          <Select
            value={projectSelection}
            onChange={e => setProjectSelection(e.target.value)}
            fullWidth
            displayEmpty
            sx={{ mb: 2 }}
          >
            <MenuItem value="" disabled>Select Project</MenuItem>
            {projects.map(p => (
              <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
            ))}
          </Select>
          <Button
            fullWidth
            variant="contained"
            disabled={!projectSelection}
            onClick={async () => {
              try {
                await selectProject(projectSelection);
                navigate("/dashboard", { replace: true });
              } catch (err) {
                setError(err.message || "Failed to select project");
              }
            }}
          >
            Continue
          </Button>
        </Paper>
      </Box>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);

    try {
      const { requireProjectSelection } = await login(form);
      setRequireProject(requireProjectSelection);
      // If single project, login already selected it and set context - navigate now
      if (!requireProjectSelection) {
        navigate("/dashboard", { replace: true });
      }
      // Otherwise, show project selection UI (handled by component render above)
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ 
      minHeight: "100vh", 
      display: "flex", 
      alignItems: "center", 
      justifyContent: "center",
      bgcolor: "#f8fafc",
      p: 2
    }}>
      <Paper sx={{ 
        p: 4, 
        borderRadius: 3, 
        maxWidth: 380, 
        width: "100%",
        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)"
      }}>
        <Box sx={{ textAlign: "center", mb: 3 }}>
          <img src={aastLogo} alt="Logo" style={{ height: 44, marginBottom: 12, borderRadius: 6 }} />
          <Typography variant="h5" fontWeight={600} sx={{ color: "text.primary" }}>
            Welcome back
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
            Sign in to Carbon Platform
          </Typography>
        </Box>
        <form onSubmit={handleSubmit} autoComplete="on">
          <TextField
            label="Username"
            fullWidth
            required
            margin="normal"
            size="medium"
            value={form.username}
            onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
            autoFocus
            autoComplete="username"
          />
          <TextField
            label="Password"
            fullWidth
            required
            margin="normal"
            size="medium"
            type="password"
            value={form.password}
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
            autoComplete="current-password"
          />
          {error && <Alert severity="error" sx={{ mt: 2, borderRadius: 2 }}>{error}</Alert>}
          <Button
            fullWidth
            variant="contained"
            color="primary"
            type="submit"
            sx={{ mt: 3, py: 1.25, fontWeight: 600 }}
            disabled={busy || loading}
          >
            {busy || loading ? <CircularProgress size={22} sx={{ color: "white" }} /> : "Sign in"}
          </Button>
        </form>
      </Paper>
    </Box>
  );
}