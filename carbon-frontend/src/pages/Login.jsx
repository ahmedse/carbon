// File: src/pages/Login.jsx
// Path: src/pages/Login.jsx
// Login form, ultra-minimal, modern.

import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { API_BASE_URL, API_ROUTES } from "../config";
import {
  Box, Button, TextField, Typography, Alert, Paper, CircularProgress,
} from "@mui/material";
import { Navigate } from "react-router-dom";
import aastLogo from "../assets/aast_carbon_logo_.jpg";

export default function Login() {
  const { login, user } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}${API_ROUTES.token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        setError("Invalid credentials");
        setLoading(false);
        return;
      }
      const { access, refresh } = await res.json();

      const rolesRes = await fetch(`${API_BASE_URL}${API_ROUTES.myRoles}`, {
        headers: { Authorization: `Bearer ${access}` },
      });
      if (!rolesRes.ok) {
        setError("Failed to fetch roles");
        setLoading(false);
        return;
      }
      const { roles } = await rolesRes.json();

      const userObj = { username, token: access, refresh, roles };
      login(userObj);
      // context will be auto-set by AuthContext
    } catch (err) {
      setError("Network or server error");
    } finally {
      setLoading(false);
    }
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
        <form onSubmit={handleSubmit}>
          <TextField
            label="Username"
            fullWidth
            required
            margin="normal"
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoFocus
          />
          <TextField
            label="Password"
            fullWidth
            required
            margin="normal"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
          <Button
            fullWidth
            variant="contained"
            color="primary"
            type="submit"
            sx={{ mt: 3, fontWeight: 700, fontSize: 16 }}
            disabled={loading}
          >
            {loading ? <CircularProgress size={24} /> : "Login"}
          </Button>
        </form>
      </Paper>
    </Box>
  );
}