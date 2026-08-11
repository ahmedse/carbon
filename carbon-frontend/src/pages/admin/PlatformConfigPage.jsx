import React, { useState, useEffect, useCallback } from "react";
import {
  Box, Paper, Typography, Tabs, Tab, TextField, Select, MenuItem,
  FormControl, InputLabel, Button, Switch, FormControlLabel,
  CircularProgress, Alert, Grid, InputAdornment, IconButton,
  Card, CardContent, Divider, Chip,
} from "@mui/material";
import { Save as SaveIcon, Visibility, VisibilityOff } from "@mui/icons-material";
import useDocumentTitle from "../../hooks/useDocumentTitle";
import { apiFetch } from "../../api/api";

const TAB_LABELS = ["Email", "Backup", "Logging", "API"];

const EMAIL_BACKENDS = [
  { value: "django.core.mail.backends.console.EmailBackend", label: "Console (dev only)" },
  { value: "django.core.mail.backends.smtp.EmailBackend", label: "Generic SMTP" },
  { value: "anymail.backends.sendgrid.EmailBackend", label: "SendGrid" },
  { value: "anymail.backends.mailgun.EmailBackend", label: "Mailgun" },
  { value: "anymail.backends.brevo.EmailBackend", label: "Brevo (Sendinblue)" },
  { value: "anymail.backends.amazon_ses.EmailBackend", label: "Amazon SES" },
  { value: "anymail.backends.resend.EmailBackend", label: "Resend" },
];

const FREQUENCIES = [
  { value: "daily", label: "Daily (2 AM)" },
  { value: "twice_daily", label: "Twice Daily (2 AM + 2 PM)" },
  { value: "hourly", label: "Hourly" },
  { value: "manual", label: "Manual Only" },
];

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"];

const ENDPOINTS = {
  0: "/accounts/config/email/",
  1: "/accounts/config/backup/",
  2: "/accounts/config/logging/",
  3: "/accounts/config/api/",
};

export default function PlatformConfigPage() {
  useDocumentTitle("Platform Config");

  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Config state for all tabs
  const [emailConfig, setEmailConfig] = useState({});
  const [backupConfig, setBackupConfig] = useState({});
  const [logConfig, setLogConfig] = useState({});
  const [apiConfig, setApiConfig] = useState({});

  const [showPassword, setShowPassword] = useState(false);

  const configs = [emailConfig, backupConfig, logConfig, apiConfig];
  const setters = [setEmailConfig, setBackupConfig, setLogConfig, setApiConfig];

  const fetchConfig = useCallback(async (idx) => {
    try {
      const data = await apiFetch(ENDPOINTS[idx]);
      setters[idx](data);
    } catch {
      // ignore — user may not have perms
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    Promise.all([0, 1, 2, 3].map(i => fetchConfig(i))).finally(() => setLoading(false));
  }, [fetchConfig]);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const data = await apiFetch(ENDPOINTS[tab], {
        method: "PUT",
        body: configs[tab],
      });
      setters[tab](data);
      setSuccess("Saved successfully.");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      setError(e.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (idx, field, value) => {
    setters[idx](prev => ({ ...prev, [field]: value }));
  };

  const updateField = (field, value) => updateConfig(tab, field, value);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Box>
          <Typography variant="h5">Platform Configuration</Typography>
          <Typography variant="body2" color="text.secondary">
            Manage system-level settings for email, backups, logging, and API defaults
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={saving ? <CircularProgress size={18} /> : <SaveIcon />}
          onClick={handleSave}
          disabled={saving}
        >
          Save
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Paper sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => { setTab(v); setError(""); setSuccess(""); }}>
          {TAB_LABELS.map((label, i) => <Tab key={i} label={label} />)}
        </Tabs>
      </Paper>

      <Card>
        <CardContent>
          {tab === 0 && <EmailTab config={emailConfig} updateField={updateField} showPassword={showPassword} setShowPassword={setShowPassword} />}
          {tab === 1 && <BackupTab config={backupConfig} updateField={updateField} />}
          {tab === 2 && <LoggingTab config={logConfig} updateField={updateField} />}
          {tab === 3 && <APITab config={apiConfig} updateField={updateField} />}
        </CardContent>
      </Card>
    </Box>
  );
}

function EmailTab({ config, updateField, showPassword, setShowPassword }) {
  return (
    <Grid container spacing={3}>
      <Grid size={{ xs: 12, sm: 6 }}>
        <FormControl fullWidth>
          <InputLabel>Backend</InputLabel>
          <Select value={config.backend || ""} label="Backend" onChange={e => updateField("backend", e.target.value)}>
            {EMAIL_BACKENDS.map(b => <MenuItem key={b.value} value={b.value}>{b.label}</MenuItem>)}
          </Select>
        </FormControl>
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <FormControlLabel
          control={<Switch checked={!!config.enabled} onChange={e => updateField("enabled", e.target.checked)} />}
          label={<Typography variant="body2">Enable outgoing email</Typography>}
        />
      </Grid>
      <Grid size={{ xs: 12 }}>
        <Divider><Chip label="SMTP / API Settings" size="small" /></Divider>
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField fullWidth label="SMTP Host" value={config.host || ""} onChange={e => updateField("host", e.target.value)} placeholder="smtp.example.com" />
      </Grid>
      <Grid size={{ xs: 12, sm: 3 }}>
        <TextField fullWidth label="Port" type="number" value={config.port ?? 587} onChange={e => updateField("port", parseInt(e.target.value) || 0)} />
      </Grid>
      <Grid size={{ xs: 12, sm: 3 }}>
        <Box sx={{ display: "flex", gap: 2, mt: 1 }}>
          <FormControlLabel control={<Switch checked={!!config.use_tls} onChange={e => updateField("use_tls", e.target.checked)} />} label="TLS" />
          <FormControlLabel control={<Switch checked={!!config.use_ssl} onChange={e => updateField("use_ssl", e.target.checked)} />} label="SSL" />
        </Box>
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField fullWidth label="Username / API Key" value={config.username || ""} onChange={e => updateField("username", e.target.value)} />
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField
          fullWidth label="Password / Secret"
          type={showPassword ? "text" : "password"}
          value={config.password || ""}
          onChange={e => updateField("password", e.target.value)}
          slotProps={{ input: { endAdornment: <InputAdornment position="end"><IconButton size="small" onClick={() => setShowPassword(!showPassword)}>{showPassword ? <VisibilityOff /> : <Visibility />}</IconButton></InputAdornment> } }}
        />
      </Grid>
      <Grid size={{ xs: 12 }}>
        <Divider><Chip label="From Address" size="small" /></Divider>
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField fullWidth label="From Email" value={config.from_email || ""} onChange={e => updateField("from_email", e.target.value)} placeholder="noreply@example.com" />
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField fullWidth label="From Name" value={config.from_name || ""} onChange={e => updateField("from_name", e.target.value)} placeholder="Carbon Data Trust" />
      </Grid>
    </Grid>
  );
}

function BackupTab({ config, updateField }) {
  const sizeMB = config.last_backup_size_bytes ? (config.last_backup_size_bytes / 1048576).toFixed(1) : null;
  return (
    <Grid container spacing={3}>
      <Grid size={{ xs: 12, sm: 6 }}>
        <FormControl fullWidth>
          <InputLabel>Frequency</InputLabel>
          <Select value={config.frequency || "daily"} label="Frequency" onChange={e => updateField("frequency", e.target.value)}>
            {FREQUENCIES.map(f => <MenuItem key={f.value} value={f.value}>{f.label}</MenuItem>)}
          </Select>
        </FormControl>
      </Grid>
      <Grid size={{ xs: 12, sm: 3 }}>
        <TextField fullWidth label="Retention (days)" type="number" value={config.retention_days ?? 30} onChange={e => updateField("retention_days", parseInt(e.target.value) || 0)} />
      </Grid>
      <Grid size={{ xs: 12, sm: 3 }}>
        <FormControlLabel
          control={<Switch checked={!!config.enabled} onChange={e => updateField("enabled", e.target.checked)} />}
          label={<Typography variant="body2">Auto-backup</Typography>}
        />
        {config.last_backup_at && (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
            Last: {new Date(config.last_backup_at).toLocaleString()}{sizeMB ? ` (${sizeMB} MB)` : ""}
          </Typography>
        )}
      </Grid>
      <Grid size={{ xs: 12 }}>
        <Divider><Chip label="Offsite (S3)" size="small" /></Divider>
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField fullWidth label="S3 Bucket" value={config.s3_bucket || ""} onChange={e => updateField("s3_bucket", e.target.value)} placeholder="my-backups-bucket" />
      </Grid>
      <Grid size={{ xs: 12, sm: 6 }}>
        <TextField fullWidth label="S3 Path Prefix" value={config.s3_path || ""} onChange={e => updateField("s3_path", e.target.value)} placeholder="carbon-backups/" />
      </Grid>
    </Grid>
  );
}

function LoggingTab({ config, updateField }) {
  return (
    <Grid container spacing={3}>
      <Grid size={{ xs: 12, sm: 4 }}>
        <FormControl fullWidth>
          <InputLabel>Default Log Level</InputLabel>
          <Select value={config.default_level || "INFO"} label="Default Log Level" onChange={e => updateField("default_level", e.target.value)}>
            {LOG_LEVELS.map(l => <MenuItem key={l} value={l}>{l}</MenuItem>)}
          </Select>
        </FormControl>
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <FormControl fullWidth>
          <InputLabel>DB Log Level</InputLabel>
          <Select value={config.db_log_level || "ERROR"} label="DB Log Level" onChange={e => updateField("db_log_level", e.target.value)}>
            {LOG_LEVELS.map(l => <MenuItem key={l} value={l}>{l}</MenuItem>)}
          </Select>
        </FormControl>
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <TextField fullWidth label="Retention (days)" type="number" value={config.retention_days ?? 90} onChange={e => updateField("retention_days", parseInt(e.target.value) || 0)} />
      </Grid>
      <Grid size={{ xs: 12 }}>
        <FormControlLabel
          control={<Switch checked={!!config.json_format} onChange={e => updateField("json_format", e.target.checked)} />}
          label={<Typography variant="body2">JSON structured logging</Typography>}
        />
      </Grid>
    </Grid>
  );
}

function APITab({ config, updateField }) {
  return (
    <Grid container spacing={3}>
      <Grid size={{ xs: 12, sm: 4 }}>
        <TextField fullWidth label="Page Size" type="number" value={config.page_size ?? 50} onChange={e => updateField("page_size", parseInt(e.target.value) || 10)} helperText="Default items per API page" />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <TextField fullWidth label="Max Page Size" type="number" value={config.max_page_size ?? 200} onChange={e => updateField("max_page_size", parseInt(e.target.value) || 10)} helperText="Hard cap on items per page" />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <FormControlLabel
          control={<Switch checked={!!config.enable_pagination} onChange={e => updateField("enable_pagination", e.target.checked)} />}
          label={<Typography variant="body2">Enable pagination</Typography>}
        />
      </Grid>
    </Grid>
  );
}
