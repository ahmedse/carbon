import React, { useState, useEffect } from "react";
import {
  Box, Button, TextField, Typography, Alert, Paper, CircularProgress, useTheme,
} from "@mui/material";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import useDocumentTitle from "../hooks/useDocumentTitle";
import { API_BASE_URL } from "../config";
import { INSTANCE_LOGO, PLATFORM_TITLE } from "../config/branding";

function validatePassword(password) {
  // Returns i18n key suffixes under `reset.passwordRules.*` (translated at render).
  const errors = [];
  if (password.length < 12) errors.push("length");
  if (!/[A-Z]/.test(password)) errors.push("uppercase");
  if (!/[a-z]/.test(password)) errors.push("lowercase");
  if (!/[0-9]/.test(password)) errors.push("number");
  if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password))
    errors.push("special");
  return errors;
}

export default function ResetPasswordPage() {
  const { t } = useTranslation('auth');
  const { t: tShell } = useTranslation('shell');
  useDocumentTitle(t('reset.documentTitle'));
  const theme = useTheme();

  const { uidb64, token } = useParams();
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  const [invalidLink, setInvalidLink] = useState(false);
  const [passwordErrors, setPasswordErrors] = useState([]);

  // Validate the link on mount by checking the token endpoint
  useEffect(() => {
    if (!uidb64 || !token) {
      setInvalidLink(true);
      return;
    }

    const verifyLink = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}password-reset/${uidb64}/${token}/`,
          { headers: { "Accept": "text/html, application/json" } }
        );
        // Django's PasswordResetConfirmView returns 200 with form on valid link
        // or could redirect if token is invalid
        if (res.status === 302 || res.status === 200) {
          // Link looks valid — the redirected page or form page loads
        } else {
          setInvalidLink(true);
        }
      } catch {
        setInvalidLink(true);
      }
    };
    verifyLink();
  }, [uidb64, token]);

  const handlePasswordChange = (value) => {
    setPassword(value);
    setPasswordErrors(validatePassword(value));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Client-side validation
    const errs = validatePassword(password);
    if (errs.length > 0) {
      setError(t('reset.meetRequirements'));
      return;
    }
    if (password !== confirm) {
      setError(t('reset.passwordsDontMatch'));
      return;
    }

    setBusy(true);

    try {
      const formData = new URLSearchParams();
      formData.append("new_password1", password);
      formData.append("new_password2", confirm);

      const res = await fetch(
        `${API_BASE_URL}password-reset/${uidb64}/${token}/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/html",
          },
          body: formData.toString(),
        }
      );

      if (res.status === 302 || res.ok) {
        setSuccess(true);
        setTimeout(() => {
          navigate("/login?reset=1", { replace: true });
        }, 2000);
      } else {
        const contentType = res.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const data = await res.json();
          setError(data.message || data.detail || t('reset.failedToReset'));
        } else {
          // Try to extract error from HTML (Django form errors)
          const text = await res.text();
          if (text.includes("The password reset link was invalid")) {
            setInvalidLink(true);
          } else {
            setError(t('reset.linkExpiredOrUsed'));
          }
        }
      }
    } catch (err) {
      setError(err.message || t('networkError'));
    } finally {
      setBusy(false);
    }
  };

  if (invalidLink) {
    return (
      <Box sx={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", bgcolor: theme.palette.grey[50], p: 2,
      }}>
        <Paper sx={{
          p: 4, borderRadius: 3, maxWidth: 380, width: "100%",
          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        }}>
          <Box sx={{ textAlign: "center" }}>
            <Typography variant="h5" fontWeight={600} color="error" mb={2}>
              {t('reset.invalidLinkTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              {t('reset.invalidLinkBody')}
            </Typography>
            <Button
              variant="contained"
              component={Link}
              to="/forgot-password"
              fullWidth
              sx={{ mb: 1 }}
            >
              {t('reset.requestNewLink')}
            </Button>
            <Typography variant="body2">
              <Link to="/login" style={{ color: "inherit" }}>
                {t('reset.backToSignIn')}
              </Link>
            </Typography>
          </Box>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", bgcolor: theme.palette.grey[50], p: 2,
    }}>
      <Paper sx={{
        p: 4, borderRadius: 3, maxWidth: 380, width: "100%",
        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      }}>
        <Box sx={{ textAlign: "center", mb: 3 }}>
          <img
            src={INSTANCE_LOGO}
            alt={tShell('ui.logo')}
            style={{ height: 44, marginBottom: 12, borderRadius: 6 }}
          />
          <Typography variant="h5" fontWeight={600} sx={{ color: "text.primary" }}>
            {t('reset.title')}
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
            {t('reset.subtitle', { title: PLATFORM_TITLE })}
          </Typography>
        </Box>

        {success ? (
          <Box sx={{ textAlign: "center" }}>
            <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>
              {t('reset.success')}
            </Alert>
          </Box>
        ) : (
          <form onSubmit={handleSubmit} autoComplete="off">
            <TextField
              label={t('reset.newPassword')}
              type="password"
              fullWidth
              required
              margin="normal"
              size="medium"
              value={password}
              onChange={(e) => handlePasswordChange(e.target.value)}
              autoFocus
              autoComplete="new-password"
            />
            {passwordErrors.length > 0 && (
              <Box sx={{ mt: 1 }}>
                {passwordErrors.map((msg, i) => (
                  <Typography key={i} variant="caption" color="warning.main" display="block">
                    • {t(`reset.passwordRules.${msg}`)}
                  </Typography>
                ))}
              </Box>
            )}

            <TextField
              label={t('reset.confirmPassword')}
              type="password"
              fullWidth
              required
              margin="normal"
              size="medium"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />

            {error && (
              <Alert severity="error" sx={{ mt: 2, borderRadius: 2 }}>
                {error}
              </Alert>
            )}

            <Button
              fullWidth
              variant="contained"
              color="primary"
              type="submit"
              disabled={busy || passwordErrors.length > 0 || !confirm}
              sx={{ mt: 3, py: 1.25, fontWeight: 600 }}
            >
              {busy ? (
                <CircularProgress size={22} sx={{ color: "white" }} />
              ) : (
                t('reset.resetButton')
              )}
            </Button>

            <Typography variant="body2" sx={{ textAlign: "center", mt: 2 }}>
              <Link to="/login" style={{ color: "inherit" }}>
                {t('reset.backToSignIn')}
              </Link>
            </Typography>
          </form>
        )}
      </Paper>
    </Box>
  );
}
