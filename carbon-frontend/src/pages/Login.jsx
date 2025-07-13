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
      // If only one project, context will be set and redirect will happen automatically
      if (!requireProjectSelection && projects.length === 1) {
        navigate("/dashboard", { replace: true });
      }
    } catch (err) {
      setError(err.message || "Login failed");
    }
    setBusy(false);
  };

  return (
    <Box sx={{ maxWidth: 400, mx: "auto", mt: 10 }}>
      <Paper sx={{ p: 4, borderRadius: 4 }}>
        <Box sx={{ textAlign: "center", mb: 2 }}>
          <img src={aastLogo} alt="Logo" style={{ height: 48, marginBottom: 16, borderRadius: 6 }} />
        </Box>
        <Typography variant="h5" mb={2} align="center" fontWeight={700}>
          Carbon Platform Login
        </Typography>
        <form onSubmit={handleSubmit} autoComplete="on">
          <TextField
            label="Username"
            fullWidth
            required
            margin="normal"
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
            type="password"
            value={form.password}
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
            autoComplete="current-password"
          />
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
          {/* {(expired || error) && (
          <Alert severity="error" sx={{ mt: 2 }}>
              {expired
                ? "Your session expired. Please log in again."
                : error}
            </Alert>
          )} */}
          <Button
            fullWidth
            variant="contained"
            color="primary"
            type="submit"
            sx={{ mt: 3, fontWeight: 700, fontSize: 16 }}
            disabled={busy || loading}
          >
            {busy || loading ? <CircularProgress size={24} /> : "Login"}
          </Button>
        </form>
        
      </Paper>
    </Box>
  );
}