// carbon-frontend/src/pages/SettingsPage.jsx
// Settings page with Profile, Security, Preferences, and Pulse tabs

import React, { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import {
  Box,
  Typography,
  Button,
  Alert,
  LinearProgress,
  TextField,
  Snackbar,
  Divider,
  Chip,
} from "@mui/material";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import KeyboardOutlinedIcon from "@mui/icons-material/KeyboardOutlined";
import { useAuth } from "../auth/AuthContext";
import { API_BASE_URL } from "../config";

const SECTION_SX = {
  bgcolor: "background.paper",
  border: "1px solid",
  borderColor: "divider",
  borderRadius: 1.5,
  overflow: "hidden",
  mb: 1.5,
};

const SECTION_HEAD_SX = {
  display: "flex",
  alignItems: "center",
  gap: 0.75,
  px: 2,
  py: 1.25,
  borderBottom: "1px solid",
  borderColor: "divider",
  bgcolor: "action.hover",
};

function SectionHead({ icon, label }) {
  const IconComponent = icon;
  return (
    <Box sx={SECTION_HEAD_SX}>
      <IconComponent sx={{ fontSize: 13, color: "text.disabled" }} />
      <Typography sx={{ fontSize: "0.6875rem", fontWeight: 700, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.07em" }}>
        {label}
      </Typography>
    </Box>
  );
}

function InfoRow({ label, value }) {
  return (
    <Box sx={{ display: "flex", gap: 2, py: 0.75, borderBottom: "1px solid", borderColor: "divider", "&:last-child": { borderBottom: "none" }, px: 2 }}>
      <Typography sx={{ fontSize: "0.625rem", color: "text.disabled", fontWeight: 600, width: 120, flexShrink: 0, textTransform: "uppercase", letterSpacing: "0.05em", pt: 0.125 }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: "0.75rem", color: "text.primary" }}>{value || "—"}</Typography>
    </Box>
  );
}

function RoleBadge({ role }) {
  // Handle both string and object formats
  const roleStr = typeof role === "string" ? role : role?.role || String(role);
  
  const colors = {
    admins_group: { bg: "rgba(220,38,38,0.1)", text: "#dc2626" },
    dataowners_group: { bg: "rgba(37,99,235,0.1)", text: "#2563eb" },
    auditors_group: { bg: "rgba(245,158,11,0.1)", text: "#d97706" },
  };
  const s = colors[roleStr] || { bg: "rgba(113,113,122,0.1)", text: "#71717a" };
  const label = String(roleStr).replace("_group", "").replace(/_/g, " ");
  
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        bgcolor: s.bg,
        color: s.text,
        fontSize: "0.5625rem",
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    />
  );
}

const SHORTCUTS = [
  { keys: ["Ctrl", "K"], desc: "Open Command Palette" },
  { keys: ["Ctrl", "B"], desc: "Toggle sidebar" },
  { keys: ["Tab"], desc: "Next perspective" },
  { keys: ["Shift", "Tab"], desc: "Previous perspective" },
];

const VALID_TABS = new Set(["profile", "security", "preferences", "pulse", "shortcuts"]);
const PULSE_HOST = import.meta.env.VITE_PULSE_HOST || "http://127.0.0.1:9100";

async function generatePulseKey(carbonToken) {
  const res = await fetch(`${PULSE_HOST}/instances/carbon/user-keys`, { // Pulse external host
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host_token: carbonToken }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Pulse error (${res.status})`);
  }
  return res.json();
}

async function fetchPulseKeyInfo(carbonToken, pulseKey) {
  const res = await fetch(`${PULSE_HOST}/instances/carbon/user-keys/refresh-token`, { // Pulse external host
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Pulse-Key": pulseKey },
    body: JSON.stringify({ host_token: carbonToken }),
  });
  if (!res.ok) return null;
  return res.json();
}

function KbdKey({ k }) {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        px: 0.75,
        py: 0.125,
        borderRadius: 0.5,
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "background.default",
        fontSize: "0.625rem",
        fontWeight: 600,
        color: "text.secondary",
        fontFamily: "monospace",
        lineHeight: 1.6,
      }}
    >
      {k}
    </Box>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const location = useLocation();
  const requestedTab = new URLSearchParams(location.search).get("tab");
  const defaultTab = VALID_TABS.has(requestedTab) ? requestedTab : "profile";

  const [tab, setTab] = useState(defaultTab);
  const [meData, setMeData] = useState(null);
  const [meLoading, setMeLoading] = useState(true);

  // Password change state
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwLoading, setPwLoading] = useState(false);
  const [pwError, setPwError] = useState("");

  // Pulse state
  const [pulseKeyInfo, setPulseKeyInfo] = useState(() => {
    const k = localStorage.getItem("pulse_key");
    return k ? { key_prefix: k.slice(0, 16) + "…", connected: true } : null;
  });
  const [pulseLoading, setPulseLoading] = useState(false);
  const [pulseError, setPulseError] = useState("");
  const [pulseNewKey, setPulseNewKey] = useState("");

  // Toast
  const [toast, setToast] = useState("");

  // Fetch profile on mount
  useEffect(() => {
    const token = localStorage.getItem("access");
    if (!token) {
      setMeLoading(false);
      return;
    }
    const baseUrl = API_BASE_URL.replace(/\/$/, '');
    fetch(`${baseUrl}/accounts/my-roles/`, { // my-roles endpoint
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setMeData(d))
      .catch(() => {})
      .finally(() => setMeLoading(false));
  }, []);

  // Load Pulse key info when switching to Pulse tab
  useEffect(() => {
    if (tab !== "pulse") return;
    const storedKey = localStorage.getItem("pulse_key");
    if (!storedKey) return;
    const token = localStorage.getItem("access");
    if (!token) return;
    fetchPulseKeyInfo(token, storedKey)
      .then((info) => {
        if (info) setPulseKeyInfo({ ...info, connected: true });
      })
      .catch(() => {});
  }, [tab]);

  const handleGeneratePulseKey = useCallback(async () => {
    setPulseError("");
    setPulseNewKey("");
    setPulseLoading(true);
    try {
      const token = localStorage.getItem("access");
      const data = await generatePulseKey(token);
      localStorage.setItem("pulse_key", data.key);
      setPulseNewKey(data.key);
      setPulseKeyInfo({
        key_prefix: data.key_prefix,
        username: data.username,
        email: data.email,
        roles: data.roles,
        connected: true,
      });
      setToast("Pulse key generated — it has been saved to this browser.");
    } catch (err) {
      setPulseError(err.message);
    } finally {
      setPulseLoading(false);
    }
  }, []);

  const handleDisconnectPulse = useCallback(() => {
    localStorage.removeItem("pulse_key");
    setPulseKeyInfo(null);
    setPulseNewKey("");
    setToast("Pulse AI disconnected from this browser.");
  }, []);

  const handleChangePassword = useCallback(async () => {
    setPwError("");
    if (!currentPw || !newPw || !confirmPw) {
      setPwError("All fields are required.");
      return;
    }
    if (newPw !== confirmPw) {
      setPwError("New passwords do not match.");
      return;
    }
    if (newPw.length < 8) {
      setPwError("Password must be at least 8 characters.");
      return;
    }

    setPwLoading(true);
    try {
      const token = localStorage.getItem("access");
      const baseUrl = API_BASE_URL.replace(/\/$/, '');
      const res = await fetch(`${baseUrl}/accounts/change-password/`, { // change-password endpoint
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setPwError(
          data?.detail ||
            data?.current_password?.[0] ||
            data?.new_password?.[0] ||
            "Failed to change password."
        );
      } else {
        setCurrentPw("");
        setNewPw("");
        setConfirmPw("");
        setToast("Password changed successfully.");
      }
    } catch {
      setPwError("Network error — could not change password.");
    } finally {
      setPwLoading(false);
    }
  }, [currentPw, newPw, confirmPw]);

  const profile = meData || user || {};
  const roles = profile.roles || (user?.roles ?? []);

  const TABS = [
    { id: "profile", label: "Profile", icon: PersonOutlineIcon },
    { id: "security", label: "Security", icon: LockOutlinedIcon },
    { id: "preferences", label: "Preferences", icon: SettingsOutlinedIcon },
    { id: "pulse", label: "Pulse AI", icon: AutoAwesomeOutlinedIcon },
    { id: "shortcuts", label: "Shortcuts", icon: KeyboardOutlinedIcon },
  ];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Page header */}
      <Box sx={{ px: 2.5, pt: 1.75, pb: 1.5, bgcolor: "background.paper", borderBottom: "1px solid", borderColor: "divider", flexShrink: 0 }}>
        <Typography sx={{ fontSize: "0.9375rem", fontWeight: 700, color: "text.primary" }}>
          Account Settings
        </Typography>
        <Typography sx={{ fontSize: "0.6875rem", color: "text.disabled", mt: 0.25 }}>
          {profile.username && `Signed in as ${profile.username}`}
        </Typography>
      </Box>

      {/* Tab bar */}
      <Box sx={{ display: "flex", bgcolor: "background.paper", borderBottom: "1px solid", borderColor: "divider", flexShrink: 0, overflowX: "auto" }}>
        {TABS.map(({ id, label, icon }) => {
          const IconComponent = icon;
          return (
            <Box
              key={id}
              onClick={() => setTab(id)}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.5,
                px: 2,
                py: 1.125,
                cursor: "pointer",
                fontSize: "0.75rem",
                fontWeight: tab === id ? 600 : 400,
                color: tab === id ? "primary.main" : "text.secondary",
                borderBottom: tab === id ? "2px solid" : "2px solid transparent",
                borderColor: tab === id ? "primary.main" : "transparent",
                "&:hover": { color: "text.primary" },
                whiteSpace: "nowrap",
              }}
            >
              <IconComponent sx={{ fontSize: 13 }} />
              {label}
            </Box>
          );
        })}
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: "auto", p: 2.5, bgcolor: "background.default" }}>
        <Box sx={{ width: "100%", maxWidth: 600 }}>
          {/* ── Profile ── */}
          {tab === "profile" && (
            <>
              {meLoading && <LinearProgress sx={{ mb: 2, maxWidth: 240 }} />}
              <Box sx={SECTION_SX}>
                <SectionHead icon={PersonOutlineIcon} label="Identity" />
                <Box sx={{ py: 0.5 }}>
                  <InfoRow label="Username" value={profile.username} />
                  <InfoRow label="Email" value={profile.email} />
                  <InfoRow label="Account type" value={profile.is_superuser ? "Superuser" : "Standard"} />
                </Box>
              </Box>

              {roles.length > 0 && (
                <Box sx={SECTION_SX}>
                  <SectionHead icon={PersonOutlineIcon} label="Roles" />
                  <Box sx={{ px: 2, py: 1.5, display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                    {roles.map((r, idx) => (
                      <RoleBadge key={idx} role={r} />
                    ))}
                  </Box>
                </Box>
              )}
            </>
          )}

          {/* ── Security ── */}
          {tab === "security" && (
            <Box sx={SECTION_SX}>
              <SectionHead icon={LockOutlinedIcon} label="Change Password" />
              <Box sx={{ px: 2, py: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
                {pwError && (
                  <Alert severity="error" sx={{ fontSize: "0.75rem", py: 0.25 }}>
                    {pwError}
                  </Alert>
                )}
                <TextField
                  size="small"
                  label="Current password"
                  type="password"
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  autoComplete="current-password"
                  sx={{ "& .MuiInputBase-input": { fontSize: "0.8125rem" } }}
                />
                <TextField
                  size="small"
                  label="New password"
                  type="password"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  autoComplete="new-password"
                  helperText="Minimum 8 characters"
                  sx={{ "& .MuiInputBase-input": { fontSize: "0.8125rem" } }}
                />
                <TextField
                  size="small"
                  label="Confirm new password"
                  type="password"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  autoComplete="new-password"
                  error={confirmPw.length > 0 && confirmPw !== newPw}
                  helperText={
                    confirmPw.length > 0 && confirmPw !== newPw
                      ? "Passwords do not match"
                      : ""
                  }
                  sx={{ "& .MuiInputBase-input": { fontSize: "0.8125rem" } }}
                />
                {pwLoading && <LinearProgress />}
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleChangePassword}
                  disabled={pwLoading || !currentPw || !newPw || !confirmPw}
                  sx={{
                    alignSelf: "flex-start",
                    textTransform: "none",
                    fontSize: "0.75rem",
                    py: 0.625,
                    px: 2,
                  }}
                >
                  Update Password
                </Button>
              </Box>
            </Box>
          )}

          {/* ── Preferences ── */}
          {tab === "preferences" && (
            <Box sx={SECTION_SX}>
              <SectionHead icon={SettingsOutlinedIcon} label="Preferences" />
              <Box sx={{ px: 2, py: 2 }}>
                <Typography sx={{ fontSize: "0.8125rem", color: "text.secondary", mb: 1 }}>
                  Preference settings coming soon. Customize your dashboard and notification settings here.
                </Typography>
              </Box>
            </Box>
          )}

          {/* ── Pulse AI ── */}
          {tab === "pulse" && (
            <>
              <Box sx={SECTION_SX}>
                <SectionHead icon={AutoAwesomeOutlinedIcon} label="AI Copilot Connection" />
                <Box sx={{ px: 2, py: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
                  {pulseError && (
                    <Alert severity="error" sx={{ fontSize: "0.75rem", py: 0.25 }}>
                      {pulseError}
                    </Alert>
                  )}

                  {pulseKeyInfo && pulseKeyInfo.connected ? (
                    <>
                      <Box>
                        <Typography sx={{ fontSize: "0.6875rem", color: "text.disabled", fontWeight: 600, mb: 0.5, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          Status
                        </Typography>
                        <Chip
                          label="Connected"
                          color="success"
                          variant="outlined"
                          size="small"
                          sx={{ fontSize: "0.75rem" }}
                        />
                      </Box>

                      <Box>
                        <Typography sx={{ fontSize: "0.6875rem", color: "text.disabled", fontWeight: 600, mb: 0.5, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          Key
                        </Typography>
                        <Typography sx={{ fontSize: "0.75rem", fontFamily: "monospace", color: "text.primary", wordBreak: "break-all" }}>
                          {pulseKeyInfo.key_prefix}
                        </Typography>
                      </Box>

                      <Button
                        variant="outlined"
                        color="error"
                        size="small"
                        onClick={handleDisconnectPulse}
                        sx={{
                          alignSelf: "flex-start",
                          textTransform: "none",
                          fontSize: "0.75rem",
                        }}
                      >
                        Disconnect
                      </Button>
                    </>
                  ) : (
                    <>
                      <Alert severity="info" sx={{ fontSize: "0.75rem", py: 0.5 }}>
                        Generate a Pulse AI key to enable AI-powered features in your Carbon workflows.
                      </Alert>
                      {pulseLoading && <LinearProgress />}
                      <Button
                        variant="contained"
                        size="small"
                        onClick={handleGeneratePulseKey}
                        disabled={pulseLoading}
                        sx={{
                          alignSelf: "flex-start",
                          textTransform: "none",
                          fontSize: "0.75rem",
                        }}
                      >
                        Generate Pulse Key
                      </Button>
                    </>
                  )}

                  {pulseNewKey && (
                    <Alert severity="warning" sx={{ fontSize: "0.75rem", py: 0.5 }}>
                      <Typography sx={{ fontSize: "0.6875rem", fontWeight: 600, mb: 0.5 }}>
                        Your Pulse AI Key (save this securely):
                      </Typography>
                      <Typography
                        sx={{
                          fontSize: "0.7rem",
                          fontFamily: "monospace",
                          wordBreak: "break-all",
                          bgcolor: "rgba(0,0,0,0.05)",
                          p: 1,
                          borderRadius: 0.5,
                        }}
                      >
                        {pulseNewKey}
                      </Typography>
                    </Alert>
                  )}
                </Box>
              </Box>
            </>
          )}

          {/* ── Shortcuts ── */}
          {tab === "shortcuts" && (
            <Box sx={SECTION_SX}>
              <SectionHead icon={KeyboardOutlinedIcon} label="Keyboard Shortcuts" />
              <Box sx={{ px: 2, py: 1.5, display: "flex", flexDirection: "column", gap: 1.25 }}>
                {SHORTCUTS.map((shortcut, idx) => (
                  <Box key={idx} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <Typography sx={{ fontSize: "0.75rem", color: "text.secondary" }}>
                      {shortcut.desc}
                    </Typography>
                    <Box sx={{ display: "flex", gap: 0.375 }}>
                      {shortcut.keys.map((key) => (
                        <KbdKey key={key} k={key} />
                      ))}
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Box>
      </Box>

      {/* Toast notification */}
      <Snackbar
        open={!!toast}
        autoHideDuration={3000}
        onClose={() => setToast("")}
        message={toast}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      />
    </Box>
  );
}
