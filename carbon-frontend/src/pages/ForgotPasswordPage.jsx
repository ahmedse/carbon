import React, { useState } from "react";
import {
  Box, Button, TextField, Typography, Alert, Paper, CircularProgress,
} from "@mui/material";
import { Link } from "react-router-dom";
import useDocumentTitle from "../hooks/useDocumentTitle";
import { API_BASE_URL } from "../config";
import { INSTANCE_LOGO } from "../config/branding";

export default function ForgotPasswordPage() {
  useDocumentTitle("Forgot Password");

  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);

    try {
      const formData = new URLSearchParams();
      formData.append("email", email);

      const res = await fetch(`${API_BASE_URL}password-reset/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Accept": "application/json, text/html",
        },
        body: formData.toString(),
      });

      // Django PasswordResetView returns 302 on success (redirects to done/)
      // or stays on 200 for invalid email
      if (res.status === 302 || res.ok) {
        setSuccess(true);
      } else {
        const contentType = res.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const data = await res.json();
          setError(data.message || data.detail || "Failed to send reset email");
        } else {
          setError("Failed to send reset email. Please try again.");
        }
      }
    } catch (err) {
      setError(err.message || "Network error. Please check your connection.");
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
      p: 2,
    }}>
      <Paper sx={{
        p: 4,
        borderRadius: 3,
        maxWidth: 380,
        width: "100%",
        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      }}>
        <Box sx={{ textAlign: "center", mb: 3 }}>
          <img
            src={INSTANCE_LOGO}
            alt="Logo"
            style={{ height: 44, marginBottom: 12, borderRadius: 6 }}
          />
          <Typography variant="h5" fontWeight={600} sx={{ color: "text.primary" }}>
            Forgot Password
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
            Enter your email to receive a reset link
          </Typography>
        </Box>

        {success ? (
          <Box sx={{ textAlign: "center" }}>
            <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>
              If an account exists with that email, you'll receive a password reset
              link shortly. Please check your inbox and spam folder.
            </Alert>
            <Typography variant="body2" sx={{ mt: 2 }}>
              <Link to="/login" style={{ color: "inherit" }}>
                ← Back to Sign In
              </Link>
            </Typography>
          </Box>
        ) : (
          <form onSubmit={handleSubmit} autoComplete="on">
            <TextField
              label="Email Address"
              type="email"
              fullWidth
              required
              margin="normal"
              size="medium"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              autoComplete="email"
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
              disabled={busy || !email.trim()}
              sx={{ mt: 3, py: 1.25, fontWeight: 600 }}
            >
              {busy ? (
                <CircularProgress size={22} sx={{ color: "white" }} />
              ) : (
                "Send Reset Link"
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
