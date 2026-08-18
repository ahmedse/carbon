// src/shell/AIModelSelect.jsx
// Phase 18 — chat-model picker for the AI Workspace footer.
// Phase 20-B — catalog v2: options grouped by tier (⚡ Fast / ⚖ Balanced /
// 🧠 Brain), deprecated models hidden from the picker (endpoint still returns
// them for attribution), cost + context hint read from the catalog fields.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  CircularProgress,
  ListSubheader,
  MenuItem,
  Select,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useAuth } from '../auth/AuthContext';
import { listModels } from '../api/aiWorkspace';

export const AI_MODEL_STORAGE_KEY = 'ai.selectedModel';

// Tier order + header labels (user-facing buckets — never provider internals).
const TIER_ORDER = ['fast', 'balanced', 'brain'];
const TIER_META = {
  fast: { icon: '⚡', label: 'Fast' },
  balanced: { icon: '⚖', label: 'Balanced' },
  brain: { icon: '🧠', label: 'Brain' },
};

function formatCost(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return '—';
  return `$${n.toFixed(2)}`;
}

function formatContextWindow(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return null;
  return `${Math.round(n / 1000)}K context`;
}

function AIModelSelect({ onChange }) {
  const { token } = useAuth();
  const [models, setModels] = useState([]);
  const [value, setValue] = useState(() => {
    try {
      return localStorage.getItem(AI_MODEL_STORAGE_KEY) || '';
    } catch {
      return '';
    }
  });
  const [loading, setLoading] = useState(true);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  // Tracks the last model id we've told the parent about, so the resolved
  // default / restored selection is reported exactly once.
  const notifiedRef = useRef(null);

  // Fetch the catalog once per token.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listModels(token)
      .then((data) => {
        if (cancelled) return;
        setModels(Array.isArray(data?.models) ? data.models : []);
      })
      .catch(() => {
        if (!cancelled) setModels([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Deprecated models stay in the endpoint response (attribution) but are not
  // selectable — exclude them from every resolution path below.
  const activeModels = useMemo(() => models.filter((m) => !m.deprecated), [models]);

  const commit = useCallback((next) => {
    if (!next) return;
    setValue(next);
    try {
      localStorage.setItem(AI_MODEL_STORAGE_KEY, next);
    } catch {
      // ignore storage failures — selection still applies this session
    }
    if (notifiedRef.current !== next) {
      notifiedRef.current = next;
      onChangeRef.current?.(next);
    }
  }, []);

  // Resolve the initial selection: a stale/empty stored id falls back to the
  // catalog default (or first active model), then notifies the parent once.
  useEffect(() => {
    if (!activeModels.length) return;
    const valid = activeModels.some((m) => m.id === value);
    const next = valid
      ? value
      : (activeModels.find((m) => m.is_default) || activeModels[0])?.id;
    commit(next);
  }, [activeModels, value, commit]);

  const handleChange = useCallback(
    (event) => commit(event.target.value),
    [commit],
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 0.5 }}>
        <CircularProgress size={11} />
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
          Model
        </Typography>
      </Box>
    );
  }

  if (!activeModels.length) return null;

  return (
    <Tooltip title="Choose AI model">
      <Select
        size="small"
        variant="standard"
        disableUnderline
        value={value}
        onChange={handleChange}
        inputProps={{ 'aria-label': 'Select AI model' }}
        IconComponent={ArrowDropDownIcon}
        renderValue={(selectedId) => (
          <Typography
            variant="caption"
            sx={{ fontSize: '0.7rem', color: 'text.secondary', whiteSpace: 'nowrap' }}
          >
            {activeModels.find((m) => m.id === selectedId)?.label || selectedId}
          </Typography>
        )}
        sx={{
          fontSize: '0.7rem',
          color: 'text.secondary',
          '& .MuiSelect-select': {
            py: 0,
            pr: '18px !important',
            pl: 0.5,
            display: 'flex',
            alignItems: 'center',
          },
        }}
      >
        {/* Flat array (no Fragment wrappers) — MUI Select clones every child
            with role="option"; Fragments would swallow that clone. */}
        {TIER_ORDER.flatMap((tierKey) => {
          const tier = TIER_META[tierKey];
          const group = activeModels.filter((m) => (m.tier || 'balanced') === tierKey);
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
            ...group.map((m) => {
              const costHint = [
                `${formatCost(m.input_cost_per_1m)} in · ${formatCost(m.output_cost_per_1m)} out / 1M tokens`,
                formatContextWindow(m.context_window),
              ]
                .filter(Boolean)
                .join(' · ');
              return (
                <MenuItem
                  key={m.id}
                  value={m.id}
                  sx={{ flexDirection: 'column', alignItems: 'flex-start', py: 0.75 }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
                    {m.label}
                    {m.is_default ? ' · default' : ''}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>
                    {m.description}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>
                    {costHint}
                  </Typography>
                </MenuItem>
              );
            }),
          ];
        })}
      </Select>
    </Tooltip>
  );
}

AIModelSelect.propTypes = {
  onChange: PropTypes.func,
};

export default AIModelSelect;
