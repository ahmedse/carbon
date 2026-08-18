// src/shell/AIModelSelect.jsx
// Phase 18 — chat-model picker for the AI Workspace footer.
// Fetches the provider's selectable models, shows a short description and
// per-1M-token pricing for each, and persists the choice in localStorage.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, CircularProgress, MenuItem, Select, Tooltip, Typography } from '@mui/material';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useAuth } from '../auth/AuthContext';
import { listModels } from '../api/aiWorkspace';

export const AI_MODEL_STORAGE_KEY = 'ai.selectedModel';

function formatCost(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return '—';
  return `$${n.toFixed(2)}`;
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
  // catalog default (or first model), then notifies the parent once.
  useEffect(() => {
    if (!models.length) return;
    const valid = models.some((m) => m.id === value);
    const next = valid ? value : (models.find((m) => m.is_default) || models[0])?.id;
    commit(next);
  }, [models, value, commit]);

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

  if (!models.length) return null;

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
            {models.find((m) => m.id === selectedId)?.label || selectedId}
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
        {models.map((m) => (
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
              {formatCost(m.input_cost_per_1m)} in · {formatCost(m.output_cost_per_1m)} out / 1M tokens
            </Typography>
          </MenuItem>
        ))}
      </Select>
    </Tooltip>
  );
}

AIModelSelect.propTypes = {
  onChange: PropTypes.func,
};

export default AIModelSelect;
