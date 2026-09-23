// carbon-frontend/src/pages/SettingsPage.jsx
// Account Settings — Account · Security · Preferences · Shortcuts
// Spec: docs/shell/SCREEN-SPEC-ACCOUNT-SETTINGS.md
// Pulse key UI removed — provisioning is pulseAuth.ensurePulseKey (auto-connect).

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Alert,
  LinearProgress,
  TextField,
  Chip,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
} from '@mui/material';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import KeyboardOutlinedIcon from '@mui/icons-material/KeyboardOutlined';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import ManageAccountsOutlinedIcon from '@mui/icons-material/ManageAccountsOutlined';
import { useTheme } from '@mui/material/styles';

import { useAuth } from '../auth/AuthContext';
import { apiFetch } from '../api/api';
import useDocumentTitle from '../hooks/useDocumentTitle';
import PageContainer from '../components/layout/PageContainer';
import PageHeader from '../components/Page/PageHeader';
import { useNotification } from '../components/NotificationProvider';
import { useLanguage } from '../i18n/useLanguage';
import { useThemeMode } from '../theme/useThemeMode';
import { FONT } from '../theme/themeTokens';

const SECTION_SX = {
  bgcolor: 'background.paper',
  border: '1px solid',
  borderColor: 'divider',
  borderRadius: 1,
  overflow: 'hidden',
  mb: 1.5,
};

const SECTION_HEAD_SX = {
  display: 'flex',
  alignItems: 'center',
  gap: 0.75,
  px: 2,
  py: 1.25,
  borderBottom: '1px solid',
  borderColor: 'divider',
  bgcolor: 'action.hover',
};

const TAB_IDS = ['account', 'security', 'preferences', 'shortcuts'];
const TAB_ALIASES = { profile: 'account', pulse: 'account' };

function resolveTab(raw) {
  if (!raw) return 'account';
  const aliased = TAB_ALIASES[raw] || raw;
  return TAB_IDS.includes(aliased) ? aliased : 'account';
}

function SectionHead({ icon: Icon, label }) {
  return (
    <Box sx={SECTION_HEAD_SX}>
      <Icon sx={{ fontSize: '0.8125rem', color: 'text.disabled' }} aria-hidden />
      <Typography sx={{ ...FONT.sectionTitle, fontWeight: 700, letterSpacing: '0.07em' }}>
        {label}
      </Typography>
    </Box>
  );
}

function InfoRow({ label, value }) {
  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        py: 0.75,
        borderBottom: '1px solid',
        borderColor: 'divider',
        '&:last-child': { borderBottom: 'none' },
        px: 2,
      }}
    >
      <Typography
        sx={{
          ...FONT.bodySmall,
          color: 'text.disabled',
          fontWeight: 600,
          width: 120,
          flexShrink: 0,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          pt: 0.125,
        }}
      >
        {label}
      </Typography>
      <Typography sx={{ ...FONT.body, color: 'text.primary' }}>{value || '—'}</Typography>
    </Box>
  );
}

function RoleBadge({ role }) {
  const theme = useTheme();
  const roleStr = typeof role === 'string' ? role : role?.role || String(role);
  const palette = {
    admins_group: theme.palette.error,
    dataowners_group: theme.palette.primary,
    auditors_group: theme.palette.warning,
  };
  const p = palette[roleStr];
  const label = String(roleStr).replace(/_group$/, '').replace(/_/g, ' ');
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        bgcolor: p ? `${p.main}1A` : 'action.hover',
        color: p ? p.main : 'text.secondary',
        ...FONT.caption,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}
    />
  );
}

function KbdKey({ k }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        px: 0.75,
        py: 0.125,
        borderRadius: 0.5,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
        ...FONT.bodySmall,
        fontWeight: 600,
        color: 'text.secondary',
        fontFamily: 'monospace',
        lineHeight: 1.6,
      }}
    >
      {k}
    </Box>
  );
}

function dedupeRoles(roles) {
  const seen = new Set();
  const out = [];
  for (const r of roles || []) {
    const key = typeof r === 'string' ? r : r?.role || String(r);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(r);
  }
  return out;
}

export default function SettingsPage() {
  const { t } = useTranslation(['common', 'shell']);
  useDocumentTitle(t('accountSettings'));
  const { user, employee } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const { lang, setLanguage } = useLanguage();
  const { mode, toggle } = useThemeMode();
  const navigate = useNavigate();
  const location = useLocation();

  const requested = new URLSearchParams(location.search).get('tab');
  const tab = resolveTab(requested);

  // Canonicalize legacy ?tab=profile|pulse and missing tab in the URL.
  useEffect(() => {
    const raw = new URLSearchParams(location.search).get('tab');
    const next = resolveTab(raw);
    if (raw !== next) {
      navigate(`/settings?tab=${next}`, { replace: true });
    }
  }, [location.search, navigate]);

  const setTab = useCallback(
    (_e, value) => {
      navigate(`/settings?tab=${value}`, { replace: true });
    },
    [navigate],
  );

  const [meData, setMeData] = useState(null);
  const [meLoading, setMeLoading] = useState(true);
  const [meError, setMeError] = useState(false);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwLoading, setPwLoading] = useState(false);
  const [pwError, setPwError] = useState('');
  const [langSaving, setLangSaving] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('access')) {
      setMeLoading(false);
      return;
    }
    let cancelled = false;
    setMeLoading(true);
    setMeError(false);
    apiFetch('accounts/my-roles/')
      .then((d) => {
        if (!cancelled) setMeData(d);
      })
      .catch(() => {
        if (!cancelled) setMeError(true);
      })
      .finally(() => {
        if (!cancelled) setMeLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleChangePassword = useCallback(async () => {
    setPwError('');
    if (!currentPw || !newPw || !confirmPw) {
      setPwError(t('allFieldsRequired'));
      return;
    }
    if (newPw !== confirmPw) {
      setPwError(t('newPasswordsNotMatch'));
      return;
    }
    if (newPw.length < 8) {
      setPwError(t('passwordTooShort'));
      return;
    }
    setPwLoading(true);
    try {
      await apiFetch('accounts/change-password/', {
        method: 'POST',
        body: { current_password: currentPw, new_password: newPw },
      });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
                  notify({ message: t('passwordChanged'), type: 'success' });
    } catch (err) {
      setPwError(err?.message || t('networkErrorPw'));
      notifyFromError?.(err);
    } finally {
      setPwLoading(false);
    }
  }, [currentPw, newPw, confirmPw, t, notify, notifyFromError]);

  const handleLanguageChange = useCallback(
    async (nextLang) => {
      if (nextLang !== 'en' && nextLang !== 'ar') return;
      setLanguage(nextLang);
      setLangSaving(true);
      try {
        await apiFetch('accounts/me/preferences/', {
          method: 'PATCH',
          body: { language: nextLang },
        });
      } catch {
        // Best-effort — local language already applied.
      } finally {
        setLangSaving(false);
      }
    },
    [setLanguage],
  );

  const profile = meData || user || {};
  const roles = useMemo(
    () => dedupeRoles(profile.roles || user?.roles || []),
    [profile.roles, user?.roles],
  );
  const isSuperuser = Boolean(profile.is_superuser ?? user?.is_superuser);

  const TABS = [
    { id: 'account', label: t('tabAccount'), icon: ManageAccountsOutlinedIcon },
    { id: 'security', label: t('tabSecurity'), icon: LockOutlinedIcon },
    { id: 'preferences', label: t('tabPreferences'), icon: SettingsOutlinedIcon },
    { id: 'shortcuts', label: t('tabShortcuts'), icon: KeyboardOutlinedIcon },
  ];

  const SHORTCUTS = [
    { keys: ['Ctrl', 'K'], desc: t('shortcutCommandPalette') },
    { keys: ['Ctrl', 'B'], desc: t('shortcutToggleSidebar') },
    { keys: ['Tab'], desc: t('shortcutNextPerspective') },
    { keys: ['Shift', 'Tab'], desc: t('shortcutPrevPerspective') },
  ];

  return (
    <PageContainer sx={{ height: '100%', overflow: 'hidden' }}>
      <Box
        sx={{
          px: 2.5,
          pt: 1.75,
          pb: 0.5,
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
          flexShrink: 0,
        }}
      >
        <PageHeader
          title={t('accountSettings')}
          subtitle={profile.username ? t('signedInAs', { username: profile.username }) : ''}
        />
      </Box>

      <Box
        sx={{
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
          flexShrink: 0,
          px: 1,
        }}
      >
        <Tabs
          value={tab}
          onChange={setTab}
          variant="scrollable"
          scrollButtons="auto"
          aria-label={t('accountSettings')}
        >
          {TABS.map(({ id, label, icon: Icon }) => (
            <Tab
              key={id}
              value={id}
              icon={<Icon sx={{ fontSize: '0.875rem' }} />}
              iconPosition="start"
              label={label}
              sx={{ minHeight: 40, textTransform: 'none', ...FONT.body }}
            />
          ))}
        </Tabs>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2.5, bgcolor: 'background.default' }}>
        <Box sx={{ width: '100%', maxWidth: 600 }}>
          {tab === 'account' && (
            <>
              {meLoading && <LinearProgress sx={{ mb: 2, maxWidth: 240 }} />}
              {meError && !meLoading && (
                <Alert severity="warning" sx={{ mb: 1.5, ...FONT.body }}>
                  {t('accountLoadPartial')}
                </Alert>
              )}
              <Box sx={SECTION_SX}>
                <SectionHead icon={PersonOutlineIcon} label={t('identity')} />
                <Box sx={{ py: 0.5 }}>
                  <InfoRow label={t('username')} value={profile.username} />
                  <InfoRow label={t('email')} value={profile.email || user?.email} />
                  <InfoRow
                    label={t('accountType')}
                    value={isSuperuser ? t('superuser') : t('standard')}
                  />
                </Box>
              </Box>

              {employee?.full_name && (
                <Box sx={SECTION_SX}>
                  <SectionHead icon={BadgeOutlinedIcon} label={t('linkedEmployee')} />
                  <Box sx={{ py: 0.5 }}>
                    <InfoRow label={t('fullName')} value={employee.full_name} />
                    <InfoRow label={t('employeeNo')} value={employee.employee_no} />
                    <InfoRow label={t('orgUnit')} value={employee.org_unit_name} />
                    {employee.job_title && (
                      <InfoRow label={t('jobTitle')} value={employee.job_title} />
                    )}
                  </Box>
                  <Box sx={{ px: 2, py: 1.25, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Button
                      size="small"
                      startIcon={<OpenInNewIcon sx={{ fontSize: '0.875rem !important' }} />}
                      onClick={() => navigate('/my')}
                      sx={{ textTransform: 'none', ...FONT.body }}
                    >
                      {t('openInMy')}
                    </Button>
                  </Box>
                </Box>
              )}

              {roles.length > 0 && (
                <Box sx={SECTION_SX}>
                  <SectionHead icon={PersonOutlineIcon} label={t('roles')} />
                  <Box sx={{ px: 2, py: 1.5, display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                    {roles.map((r, idx) => (
                      <RoleBadge key={idx} role={r} />
                    ))}
                  </Box>
                </Box>
              )}
            </>
          )}

          {tab === 'security' && (
            <Box sx={SECTION_SX}>
              <SectionHead icon={LockOutlinedIcon} label={t('changePassword')} />
              <Box sx={{ px: 2, py: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {pwError && (
                  <Alert severity="error" sx={{ ...FONT.body, py: 0.25 }}>
                    {pwError}
                  </Alert>
                )}
                <TextField
                  size="small"
                  label={t('currentPassword')}
                  type="password"
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  autoComplete="current-password"
                />
                <TextField
                  size="small"
                  label={t('newPassword')}
                  type="password"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  autoComplete="new-password"
                  helperText={t('min8Chars')}
                />
                <TextField
                  size="small"
                  label={t('confirmNewPassword')}
                  type="password"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  autoComplete="new-password"
                  error={confirmPw.length > 0 && confirmPw !== newPw}
                  helperText={
                    confirmPw.length > 0 && confirmPw !== newPw ? t('passwordsDontMatch') : ''
                  }
                />
                {pwLoading && <LinearProgress />}
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleChangePassword}
                  disabled={pwLoading || !currentPw || !newPw || !confirmPw}
                  sx={{ alignSelf: 'flex-start', textTransform: 'none' }}
                >
                  {t('updatePassword')}
                </Button>
              </Box>
            </Box>
          )}

          {tab === 'preferences' && (
            <Box sx={SECTION_SX}>
              <SectionHead icon={SettingsOutlinedIcon} label={t('preferences')} />
              <Box sx={{ px: 2, py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FormControl size="small" fullWidth disabled={langSaving}>
                  <InputLabel id="settings-lang-label">{t('language')}</InputLabel>
                  <Select
                    labelId="settings-lang-label"
                    label={t('language')}
                    value={lang === 'ar' ? 'ar' : 'en'}
                    onChange={(e) => handleLanguageChange(e.target.value)}
                  >
                    <MenuItem value="en">{t('langEnglish')}</MenuItem>
                    <MenuItem value="ar">{t('langArabic')}</MenuItem>
                  </Select>
                </FormControl>
                <FormControlLabel
                  control={
                    <Switch
                      size="small"
                      checked={mode === 'dark'}
                      onChange={toggle}
                      inputProps={{ 'aria-label': t('themeDark') }}
                    />
                  }
                  label={mode === 'dark' ? t('themeDark') : t('themeLight')}
                  sx={{ ...FONT.body, ml: 0 }}
                />
              </Box>
            </Box>
          )}

          {tab === 'shortcuts' && (
            <Box sx={SECTION_SX}>
              <SectionHead icon={KeyboardOutlinedIcon} label={t('keyboardShortcuts')} />
              <Box sx={{ px: 2, py: 1.5, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
                {SHORTCUTS.map((shortcut) => (
                  <Box
                    key={shortcut.desc}
                    sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                  >
                    <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
                      {shortcut.desc}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.375 }}>
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
    </PageContainer>
  );
}
