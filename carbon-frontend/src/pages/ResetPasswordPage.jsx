import React, { useState, useEffect } from "react";
import {
  Box, Button, TextField, Typography, Alert, Paper, CircularProgress,
} from "@mui/material";
import { useParams, useNavigate, Link } from "react-router-dom";
import useDocumentTitle from "../hooks/useDocumentTitle";
import { API_BASE_URL } from "../config";
import { INSTANCE_LOGO, PLATFORM_NAME } from "../config/branding";

function validatePassword(password) {
  const errors = [];
  if (password.length < 12) errors.push("At least 12 characters");
  if (!/[A-Z]/.test(password)) errors.push("One uppercase letter");
  if (!/[a-z]/.test(password)) errors.push("One lowercase letter");
  if (!/[0-9]/.test(password)) errors.push("One number");
  if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password))
    errors.push("One special character");
  return errors;
}

export default function ResetPasswordPage() {
  useDocumentTitle("Reset Password");

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
      setError("Please meet all password requirements.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
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
          setError(data.message || data.detail || "Failed to reset password");
        } else {
          // Try to extract error from HTML (Django form errors)
          const text = await res.text();
          if (text.includes("The password reset link was invalid")) {
            setInvalidLink(true);
          } else {
            setError(
              "Failed to reset password. The link may have expired or already been used."
            );
          }
        }
      }
    } catch (err) {
      setError(err.message || "Network error. Please check your connection.");
    } finally {
      setBusy(false);
    }
  };

  if (invalidLink) {
    return (
      <Box sx={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", bgcolor: "#f8fafc", p: 2,
      }}>
        <Paper sx={{
          p: 4, borderRadius: 3, maxWidth: 380, width: "100%",
          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        }}>
          <Box sx={{ textAlign: "center" }}>
            <Typography variant="h5" fontWeight={600} color="error" mb={2}>
              Invalid or Expired Link
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              This password reset link is invalid or has expired. Please request a new one.
            </Typography>
            <Button
              variant="contained"
              component={Link}
              to="/forgot-password"
              fullWidth
              sx={{ mb: 1 }}
            >
              Request New Link
            </Button>
            <Typography variant="body2">
              <Link to="/login" style={{ color: "inherit" }}>
                ← Back to Sign In
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
      justifyContent: "center", bgcolor: "#f8fafc", p: 2,
    }}>
      <Paper sx={{
        p: 4, borderRadius: 3, maxWidth: 380, width: "100%",
        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      }}>
        <Box sx={{ textAlign: "center", mb: 3 }}>
          <img
            src={INSTANCE_LOGO}
            alt="Logo"
            style={{ height: 44, marginBottom: 12, borderRadius: 6 }}
          />
          <Typography variant="h5" fontWeight={600} sx={{ color: "text.primary" }}>
            Reset Password
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
            Choose a strong new password for your {PLATFORM_NAME} account
          </Typography>
        </Box>

        {success ? (
          <Box sx={{ textAlign: "center" }}>
            <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>
              Your password has been reset successfully! Redirecting to login…
            </Alert>
          </Box>
        ) : (
          <form onSubmit={handleSubmit} autoComplete="off">
            <TextField
              label="New Password"
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
                    • {msg}
                  </Typography>
                ))}
              </Box>
            )}

            <TextField
              label="Confirm Password"
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
                "Reset Password"
              )}
            </Button>

            <Typography variant="body2" sx={{ textAlign: "center", mt: 2 }}>
              <Link to="/login" style={{ color: "inherit" }}>
                ← Back to Sign In
              </Link>
            </Typography>
          </form>
        )}
      </Paper>
    </Box>
  );
}
