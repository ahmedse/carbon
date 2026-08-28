// carbon-frontend/src/pages/SettingsPage.jsx
// Settings page with Profile, Security, Preferences, and Pulse tabs

import React, { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
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
import { apiFetch } from "../api/api";
import useDocumentTitle from "../hooks/useDocumentTitle";
import PageContainer from "../components/layout/PageContainer";
import { FONT } from "../theme/themeTokens";
import { useTheme } from "@mui/material/styles";

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
      <IconComponent sx={{ fontSize: '0.8125rem', color: "text.disabled" }} />
      <Typography sx={{ ...FONT.sectionTitle, fontWeight: 700, letterSpacing: "0.07em" }}>
        {label}
      </Typography>
    </Box>
  );
}

function InfoRow({ label, value }) {
  return (
    <Box sx={{ display: "flex", gap: 2, py: 0.75, borderBottom: "1px solid", borderColor: "divider", "&:last-child": { borderBottom: "none" }, px: 2 }}>
      <Typography sx={{ ...FONT.bodySmall, color: "text.disabled", fontWeight: 600, width: 120, flexShrink: 0, textTransform: "uppercase", letterSpacing: "0.05em", pt: 0.125 }}>
        {label}
      </Typography>
      <Typography sx={{ ...FONT.body, color: "text.primary" }}>{value || "—"}</Typography>
    </Box>
  );
}

function RoleBadge({ role }) {
  const theme = useTheme();
  // Handle both string and object formats
  const roleStr = typeof role === "string" ? role : role?.role || String(role);
  
  const palette = {
    admins_group: theme.palette.error,
    dataowners_group: theme.palette.primary,
    auditors_group: theme.palette.warning,
  };
  const p = palette[roleStr];
  const bg = p ? `${p.main}1A` : 'action.hover';
  const text = p ? p.main : 'text.secondary';
  const label = String(roleStr).replace("_group", "").replace(/_/g, " ");
  
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        bgcolor: bg,
        color: text,
        ...FONT.caption,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    />
  );
}

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
        ...FONT.bodySmall,
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
  const { t } = useTranslation(["common", "connections", "shell"]);
  useDocumentTitle(t("nav.settings"));
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
    if (!localStorage.getItem("access")) {
      setMeLoading(false);
      return;
    }
    apiFetch('accounts/my-roles/')
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
      setToast(t("pulseKeyGenerated"));
    } catch (err) {
      setPulseError(err.message);
    } finally {
      setPulseLoading(false);
    }
  }, [t]);

  const handleDisconnectPulse = useCallback(() => {
    localStorage.removeItem("pulse_key");
    setPulseKeyInfo(null);
    setPulseNewKey("");
    setToast(t("pulseDisconnected"));
  }, [t]);

  const handleChangePassword = useCallback(async () => {
    setPwError("");
    if (!currentPw || !newPw || !confirmPw) {
      setPwError(t("allFieldsRequired"));
      return;
    }
    if (newPw !== confirmPw) {
      setPwError(t("newPasswordsNotMatch"));
      return;
    }
    if (newPw.length < 8) {
      setPwError(t("passwordTooShort"));
      return;
    }

    setPwLoading(true);
    try {
      await apiFetch('accounts/change-password/', {
        method: "POST",
        body: { current_password: currentPw, new_password: newPw },
      });
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      setToast(t("passwordChanged"));
    } catch (err) {
      setPwError(err?.message || t("networkErrorPw"));
    } finally {
      setPwLoading(false);
    }
  }, [currentPw, newPw, confirmPw, t]);

  const profile = meData || user || {};
  const roles = profile.roles || (user?.roles ?? []);

  const TABS = [
    { id: "profile", label: t("tabProfile"), icon: PersonOutlineIcon },
    { id: "security", label: t("tabSecurity"), icon: LockOutlinedIcon },
    { id: "preferences", label: t("tabPreferences"), icon: SettingsOutlinedIcon },
    { id: "pulse", label: t("tabPulse"), icon: AutoAwesomeOutlinedIcon },
    { id: "shortcuts", label: t("tabShortcuts"), icon: KeyboardOutlinedIcon },
  ];

  const SHORTCUTS = [
    { keys: ["Ctrl", "K"], desc: t("shortcutCommandPalette") },
    { keys: ["Ctrl", "B"], desc: t("shortcutToggleSidebar") },
    { keys: ["Tab"], desc: t("shortcutNextPerspective") },
    { keys: ["Shift", "Tab"], desc: t("shortcutPrevPerspective") },
  ];

  return (
    <PageContainer sx={{ height: '100%', overflow: 'hidden' }}>
      {/* Page header */}
      <Box sx={{ px: 2.5, pt: 1.75, pb: 1.5, bgcolor: "background.paper", borderBottom: "1px solid", borderColor: "divider", flexShrink: 0 }}>
        <Typography variant="h4">
          {t("accountSettings")}
        </Typography>
        <Typography sx={{ ...FONT.body, color: "text.disabled", mt: 0.25 }}>
          {profile.username && t("signedInAs", { username: profile.username })}
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
                ...FONT.body,
                fontWeight: tab === id ? 600 : 400,
                color: tab === id ? "primary.main" : "text.secondary",
                borderBottom: tab === id ? "2px solid" : "2px solid transparent",
                borderColor: tab === id ? "primary.main" : "transparent",
                "&:hover": { color: "text.primary" },
                whiteSpace: "nowrap",
              }}
            >
              <IconComponent sx={{ fontSize: '0.8125rem' }} />
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
                <SectionHead icon={PersonOutlineIcon} label={t("identity")} />
                <Box sx={{ py: 0.5 }}>
                  <InfoRow label={t("username")} value={profile.username} />
                  <InfoRow label={t("email")} value={profile.email} />
                  <InfoRow label={t("accountType")} value={profile.is_superuser ? t("superuser") : t("standard")} />
                </Box>
              </Box>

              {roles.length > 0 && (
                <Box sx={SECTION_SX}>
                  <SectionHead icon={PersonOutlineIcon} label={t("roles")} />
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
              <SectionHead icon={LockOutlinedIcon} label={t("changePassword")} />
              <Box sx={{ px: 2, py: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
                {pwError && (
                  <Alert severity="error" sx={{ ...FONT.body, py: 0.25 }}>
                    {pwError}
                  </Alert>
                )}
                <TextField
                  size="small"
                  label={t("currentPassword")}
                  type="password"
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  autoComplete="current-password"
                  sx={{ "& .MuiInputBase-input": { ...FONT.body } }}
                />
                <TextField
                  size="small"
                  label={t("newPassword")}
                  type="password"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  autoComplete="new-password"
                  helperText={t("min8Chars")}
                  sx={{ "& .MuiInputBase-input": { ...FONT.body } }}
                />
                <TextField
                  size="small"
                  label={t("confirmNewPassword")}
                  type="password"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  autoComplete="new-password"
                  error={confirmPw.length > 0 && confirmPw !== newPw}
                  helperText={
                    confirmPw.length > 0 && confirmPw !== newPw
                      ? t("passwordsDontMatch")
                      : ""
                  }
                  sx={{ "& .MuiInputBase-input": { ...FONT.body } }}
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
                    ...FONT.body,
                    py: 0.625,
                    px: 2,
                  }}
                >
                  {t("updatePassword")}
                </Button>
              </Box>
            </Box>
          )}

          {/* ── Preferences ── */}
          {tab === "preferences" && (
            <Box sx={SECTION_SX}>
              <SectionHead icon={SettingsOutlinedIcon} label={t("preferences")} />
              <Box sx={{ px: 2, py: 2 }}>
                <Typography sx={{ ...FONT.body, color: "text.secondary", mb: 1 }}>
                  {t("preferencesComingSoon")}
                </Typography>
              </Box>
            </Box>
          )}

          {/* ── Pulse AI ── */}
          {tab === "pulse" && (
            <>
              <Box sx={SECTION_SX}>
                <SectionHead icon={AutoAwesomeOutlinedIcon} label={t("pulseSectionTitle")} />
                <Box sx={{ px: 2, py: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
                  {pulseError && (
                    <Alert severity="error" sx={{ ...FONT.body, py: 0.25 }}>
                      {pulseError}
                    </Alert>
                  )}

                  {pulseKeyInfo && pulseKeyInfo.connected ? (
                    <>
                      <Box>
                        <Typography sx={{ ...FONT.sectionTitle, color: "text.disabled", mb: 0.5 }}>
                          {t("pulseStatus")}
                        </Typography>
                        <Chip
                          label={t("pulseConnected")}
                          color="success"
                          variant="outlined"
                          size="small"
                          sx={{ ...FONT.body }}
                        />
                      </Box>

                      <Box>
                        <Typography sx={{ ...FONT.sectionTitle, color: "text.disabled", mb: 0.5 }}>
                          {t("pulseKey")}
                        </Typography>
                        <Typography sx={{ ...FONT.body, fontFamily: "monospace", color: "text.primary", wordBreak: "break-all" }}>
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
                          ...FONT.body,
                        }}
                      >
                        {t("pulseDisconnect")}
                      </Button>
                    </>
                  ) : (
                    <>
                      <Alert severity="info" sx={{ ...FONT.body, py: 0.5 }}>
                        {t("pulseGenerateHint")}
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
                          ...FONT.body,
                        }}
                      >
                        {t("pulseGenerateKey")}
                      </Button>
                    </>
                  )}

                  {pulseNewKey && (
                    <Alert severity="warning" sx={{ ...FONT.body, py: 0.5 }}>
                      <Typography sx={{ ...FONT.bodySmall, fontWeight: 600, mb: 0.5 }}>
                        {t("pulseNewKeyTitle")}
                      </Typography>
                      <Typography
                        sx={{
                          ...FONT.bodySmall,
                          fontFamily: "monospace",
                          wordBreak: "break-all",
                          bgcolor: "action.hover",
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
              <SectionHead icon={KeyboardOutlinedIcon} label={t("keyboardShortcuts")} />
              <Box sx={{ px: 2, py: 1.5, display: "flex", flexDirection: "column", gap: 1.25 }}>
                {SHORTCUTS.map((shortcut, idx) => (
                  <Box key={idx} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <Typography sx={{ ...FONT.body, color: "text.secondary" }}>
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
    </PageContainer>
  );
}
