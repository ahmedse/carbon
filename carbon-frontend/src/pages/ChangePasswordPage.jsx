import React, { useState } from "react";
import {
  Box, Button, TextField, Typography, Alert, Paper, CircularProgress, useTheme,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import useDocumentTitle from "../hooks/useDocumentTitle";
import { API_BASE_URL } from "../config";
import { INSTANCE_LOGO, PLATFORM_TITLE } from "../config/branding";
import { useAuth } from "../auth/AuthContext";

export default function ChangePasswordPage() {
  const { t } = useTranslation("auth");
  const { t: tShell } = useTranslation("shell");
  useDocumentTitle(t("passwordChange.documentTitle"));
  const theme = useTheme();
  const navigate = useNavigate();
  const { user, completePasswordChange } = useAuth();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (next !== confirm) {
      setError(t("passwordChange.mismatch"));
      return;
    }
    if (next === current) {
      setError(t("passwordChange.same"));
      return;
    }
    if (next.length < 10 || !/[A-Za-z]/.test(next) || !/[0-9]/.test(next)) {
      setError(t("passwordChange.rules"));
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}accounts/change-password/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${user?.token || ""}`,
        },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const message = data?.new_password?.[0] || data?.current_password?.[0] || data?.detail;
        setError(message || t("passwordChange.failed"));
        return;
      }
      completePasswordChange();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || t("networkError"));
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
      p: 2,
    }}>
      <Paper elevation={1} sx={{ p: 4, borderRadius: 3, maxWidth: 420, width: "100%" }}>
        <Box sx={{ textAlign: "center", mb: 3 }}>
          <img
            src={INSTANCE_LOGO}
            alt={tShell("ui.logo")}
            style={{ height: 44, marginBottom: 12, borderRadius: 6 }}
          />
          <Typography variant="h5">{t("passwordChange.title")}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {t("passwordChange.subtitle", { title: PLATFORM_TITLE })}
          </Typography>
        </Box>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            fullWidth
            margin="normal"
            type="password"
            label={t("passwordChange.current")}
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            autoComplete="current-password"
            required
          />
          <TextField
            fullWidth
            margin="normal"
            type="password"
            label={t("passwordChange.newPassword")}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            autoComplete="new-password"
            helperText={t("passwordChange.rules")}
            required
          />
          <TextField
            fullWidth
            margin="normal"
            type="password"
            label={t("passwordChange.confirm")}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            required
          />
          <Button type="submit" variant="contained" fullWidth disabled={busy} sx={{ mt: 2 }}>
            {busy ? <CircularProgress size={22} color="inherit" /> : t("passwordChange.submit")}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
