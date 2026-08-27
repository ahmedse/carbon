import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  Box, Button, TextField, Typography, Alert, Paper, CircularProgress, MenuItem, Select, useTheme,
} from "@mui/material";
import { Navigate, useNavigate, Link } from "react-router-dom";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import useDocumentTitle from "../hooks/useDocumentTitle";
import { INSTANCE_LOGO, PLATFORM_TITLE } from "../config/branding";


export default function Login() {
  const { t } = useTranslation('auth');
  const { t: tShell } = useTranslation('shell');
  useDocumentTitle(t('login.documentTitle'));
  const theme = useTheme();
  const {
    user, projects, context, loading, login, selectProject,
  } = useAuth();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [projectSelection, setProjectSelection] = useState("");
  const [requireProject, setRequireProject] = useState(false);

  const location = useLocation();
  // location.search may contain "expired=1" or "expired%3D1" (double-encoded by some proxies)
  const sessionExpired = /[?&]expired(?:=|%3D)1/.test(location.search);

  const navigate = useNavigate();

  // Already logged in? Redirect to appropriate landing page.
  if (user && context?.projectId) return <Navigate to={context?.landingPath || "/dashboard"} replace />;

  // Project selection UI only at login
  if (user && projects.length > 1 && requireProject) {
    return (
      <Box sx={{ maxWidth: 400, mx: "auto", mt: 10 }}>
        <Paper sx={{ p: 4, borderRadius: 4 }}>
          <Typography variant="h6" align="center" mb={2}>
            {t('login.selectProject')}
          </Typography>
          <Select
            value={projectSelection}
            onChange={e => setProjectSelection(e.target.value)}
            fullWidth
            displayEmpty
            sx={{ mb: 2 }}
          >
            <MenuItem value="" disabled>{t('login.selectProjectPlaceholder')}</MenuItem>
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
                setError(err.message || t('login.failedToSelectProject'));
              }
            }}
          >
            {t('login.continue')}
          </Button>
        </Paper>
      </Box>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);

    try {
      const { requireProjectSelection, landingPath } = await login(form);
      setRequireProject(requireProjectSelection);
      // If single project, login already selected it and set context - navigate now
      if (!requireProjectSelection) {
        navigate(landingPath || "/dashboard", { replace: true });
      }
      // Otherwise, show project selection UI (handled by component render above)
    } catch (err) {
      setError(
        err.message === 'Invalid credentials'
          ? t('login.invalidCredentials')
          : (err.message || t('login.loginFailed'))
      );
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
      bgcolor: theme.palette.grey[50],
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
          <img src={INSTANCE_LOGO} alt={tShell('ui.logo')} style={{ height: 44, marginBottom: 12, borderRadius: 6 }} />
          <Typography variant="h5" fontWeight={600} sx={{ color: "text.primary" }}>
            {t('login.welcome')}
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
            {t('login.subtitle', { title: PLATFORM_TITLE })}
          </Typography>
        </Box>
        {sessionExpired && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t('login.sessionExpired')}
          </Alert>
        )}
        <form onSubmit={handleSubmit} autoComplete="on">
          <TextField
            label={t('login.username')}
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
            label={t('login.password')}
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
          <Typography variant="body2" sx={{ textAlign: 'right', mt: 0.5 }}>
            <Link to="/forgot-password" color="primary" style={{ textDecoration: 'none' }}>
              {t('login.forgotPassword')}
            </Link>
          </Typography>
          <Button
            fullWidth
            variant="contained"
            color="primary"
            type="submit"
            sx={{ mt: 3, py: 1.25, fontWeight: 600 }}
            disabled={busy || loading}
          >
            {busy || loading ? <CircularProgress size={22} sx={{ color: "white" }} /> : t('login.submit')}
          </Button>
        </form>
      </Paper>
    </Box>
  );
}