// src/shell/AISettingsTab.jsx
// Phase 22-B — User preferences (Settings tab): default model, temperature,
// auto-title, long-term memory, and usage-alert threshold. Self-fetching
// sibling of AIUsageTab — reads/writes /carbon-api/ai/profile/ through the
// workspace api module (RULE_10: apiFetch only; RULE_8: theme tokens only).
//
// Form contract (Phase 22-A backend):
//   GET  /ai/profile/ → { default_model_id, resolved_model_id, temperature,
//                        auto_title, memory_enabled, usage_alert_threshold }
//   PATCH /ai/profile/ accepts the same fields; default_model_id null clears.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  ListSubheader,
  MenuItem,
  Paper,
  Select,
  Slider,
  Stack,
  Switch,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { getProfile, listModels, patchProfile } from '../api/aiWorkspace';

// Tier order + labels (user-facing buckets — never provider internals).
const TIER_ORDER = ['fast', 'balanced', 'brain'];
const TIER_META = {
  fast: { icon: '⚡', label: 'Fast' },
  balanced: { icon: '⚖', label: 'Balanced' },
  brain: { icon: '🧠', label: 'Brain' },
};

// Server defaults (backend `AIGenerationProfile` prefs).
const DEFAULT_FORM = {
  default_model_id: null,
  temperature: 0.3,
  auto_title: true,
  memory_enabled: true,
  usage_alert_threshold: 80,
};

function SettingRow({ title, hint, control }) {
  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={1.5}
      sx={{ py: 1, borderBottom: 1, borderColor: 'divider', '&:last-of-type': { borderBottom: 0 } }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.8125rem' }}>
          {title}
        </Typography>
        {hint && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
            {hint}
          </Typography>
        )}
      </Box>
      {control}
    </Stack>
  );
}

function AISettingsTab() {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const [profile, setProfile] = useState(null); // last server truth
  const [form, setForm] = useState(DEFAULT_FORM); // editable copy
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const normalizeProfile = useCallback((data = {}) => ({
    default_model_id: data.default_model_id || null,
    temperature: Number(data.temperature ?? DEFAULT_FORM.temperature),
    auto_title: data.auto_title ?? DEFAULT_FORM.auto_title,
    memory_enabled: data.memory_enabled ?? DEFAULT_FORM.memory_enabled,
    usage_alert_threshold: Number(data.usage_alert_threshold ?? DEFAULT_FORM.usage_alert_threshold),
  }), []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, modelData] = await Promise.all([
        getProfile(token),
        listModels(token),
      ]);
      const next = normalizeProfile(profileData);
      setProfile(next);
      setForm(next);
      setModels(
        Array.isArray(modelData?.models)
          ? modelData.models.filter((m) => !m.deprecated)
          : [],
      );
    } catch (err) {
      setError(err.message || 'Could not load preferences');
      notifyFromError(err, 'Could not load preferences');
    } finally {
      setLoading(false);
    }
  }, [token, normalizeProfile, notifyFromError]);

  useEffect(() => {
    load();
  }, [load]);

  const dirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(profile || DEFAULT_FORM),
    [form, profile],
  );

  const set = useCallback((key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const updated = await patchProfile(token, form);
      const next = normalizeProfile(updated);
      setProfile(next);
      setForm(next);
      notify({ message: 'Preferences saved', type: 'success' });
    } catch (err) {
      notifyFromError(err, 'Could not save preferences');
    } finally {
      setSaving(false);
    }
  }, [token, form, normalizeProfile, notify, notifyFromError]);

  // Model options: "System default" (clear) + active catalog models grouped by
  // tier. Flat array — MUI Select clones every child with role="option", so no
  // Fragment wrappers (they would swallow the clone).
  const modelOptions = useMemo(() => {
    const groups = TIER_ORDER.flatMap((tierKey) => {
      const tier = TIER_META[tierKey];
      const group = models.filter((m) => (m.tier || 'balanced') === tierKey);
      if (!group.length) return [];
      return [
        <ListSubheader
          key={`tier-${tierKey}`}
          disableSticky
          sx={{
            bgcolor: 'transparent',
            color: 'text.secondary',
            lineHeight: 1.8,
            py: 0.5,
            fontSize: '0.68rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {tier.icon} {tier.label}
        </ListSubheader>,
        ...group.map((m) => (
          <MenuItem key={m.id} value={m.id} sx={{ fontSize: '0.8125rem' }}>
            {m.label}
            {m.is_default ? ' · default' : ''}
          </MenuItem>
        )),
      ];
    });
    return [
      <MenuItem key="system-default" value="" sx={{ fontSize: '0.8125rem', fontStyle: 'italic' }}>
        System default
      </MenuItem>,
      ...groups,
    ];
  }, [models]);

  if (loading) {
    return (
      <Box sx={{ p: 2, height: '100%', overflow: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={14} />
        <Typography variant="caption" color="text.secondary">Loading…</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
        <Stack spacing={1} alignItems="flex-start">
          <Typography variant="caption" color="error">{error}</Typography>
          <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={load}>
            Retry
          </Button>
        </Stack>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ flex: 1, fontSize: '0.8125rem' }}>
          Preferences
        </Typography>
        <Button
          size="small"
          variant="text"
          onClick={() => setForm(profile || DEFAULT_FORM)}
          disabled={!dirty || saving}
          sx={{ fontSize: '0.7rem', minWidth: 0 }}
        >
          Reset
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={handleSave}
          disabled={!dirty || saving}
          sx={{ fontSize: '0.7rem' }}
        >
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </Stack>

      <Paper variant="outlined" sx={{ p: 1.5, maxWidth: 560 }}>
        <SettingRow
          title="Default model"
          hint="Used for new chats; per-message picks still win."
          control={(
            <Select
              size="small"
              value={form.default_model_id || ''}
              onChange={(event) => set('default_model_id', event.target.value || null)}
              inputProps={{ 'aria-label': 'Default model' }}
              sx={{ minWidth: 180, fontSize: '0.8125rem' }}
            >
              {modelOptions}
            </Select>
          )}
        />

        <SettingRow
          title="Temperature"
          hint="0 = deterministic, 1 = balanced, 2 = most creative."
          control={(
            <Box sx={{ width: 180 }}>
              <Slider
                size="small"
                value={form.temperature}
                min={0}
                max={2}
                step={0.1}
                valueLabelDisplay="auto"
                aria-label="Temperature"
                onChange={(event, value) => set('temperature', Number(value))}
              />
            </Box>
          )}
        />

        <SettingRow
          title="Auto-title conversations"
          hint="Generate a short title for each new chat."
          control={(
            <Switch
              size="small"
              checked={form.auto_title}
              onChange={(event) => set('auto_title', event.target.checked)}
              inputProps={{ 'aria-label': 'Auto-title conversations' }}
            />
          )}
        />

        <SettingRow
          title="Long-term memory"
          hint="Let the assistant reuse durable facts across chats."
          control={(
            <Switch
              size="small"
              checked={form.memory_enabled}
              onChange={(event) => set('memory_enabled', event.target.checked)}
              inputProps={{ 'aria-label': 'Long-term memory' }}
            />
          )}
        />

        <SettingRow
          title="Usage alert threshold"
          hint="Warn when the monthly token budget crosses this percent."
          control={(
            <Box sx={{ width: 180, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Slider
                size="small"
                value={form.usage_alert_threshold}
                min={1}
                max={100}
                step={5}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `${value}%`}
                aria-label="Usage alert threshold"
                onChange={(event, value) => set('usage_alert_threshold', Number(value))}
              />
            </Box>
          )}
        />
      </Paper>
    </Box>
  );
}

export default AISettingsTab;
