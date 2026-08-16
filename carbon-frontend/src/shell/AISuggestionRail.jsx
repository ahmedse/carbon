// src/shell/AISuggestionRail.jsx
// Phase 5B — 🔔 Suggestions rail (proactive KgProactiveInsight display).
// Read-only: these insights have no accept/reject endpoint in scope, so the
// rail is display-only. Non-blocking: it never displaces the thread rail.
import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  Collapse,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import NotificationsActiveOutlinedIcon from '@mui/icons-material/NotificationsActiveOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useAuth } from '../auth/AuthContext';
import { getSuggestions } from '../api/aiWorkspace';
import { formatDistanceToNow } from '../utils/dateUtils';

const STORAGE_KEY = 'carbon-ai-suggestions-rail-open';

const SEVERITY_COLORS = {
  error: 'error',
  warn: 'warning',
  warning: 'warning',
  info: 'info',
  success: 'success',
};

function severityColor(severity) {
  return SEVERITY_COLORS[severity] || 'default';
}

function severityLabel(severity) {
  return severity ? String(severity).toUpperCase() : 'INFO';
}

function createdAtLabel(createdAt) {
  if (!createdAt) return null;
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return null;
  return formatDistanceToNow(date);
}

function AISuggestionRail({ conversationId }) {
  const { token } = useAuth();
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== 'false';
    } catch {
      return true;
    }
  });

  // Load suggestions when the active conversation changes.
  useEffect(() => {
    let cancelled = false;
    setSuggestions([]);
    setExpandedId(null);
    if (!conversationId) {
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    getSuggestions(token, conversationId)
      .then((data) => {
        if (cancelled) return;
        setSuggestions(Array.isArray(data?.suggestions) ? data.suggestions : []);
      })
      .catch(() => {
        // Non-critical surface — fail silently so the thread rail is unaffected.
        if (!cancelled) setSuggestions([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, conversationId]);

  const toggleOpen = useCallback(() => {
    setOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const toggleExpand = useCallback((id) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  // Loading / error / empty → render nothing. The rail only appears when there
  // are actual insights to show, so it never displaces the thread rail.
  if (loading || suggestions.length === 0) return null;

  const items = suggestions;
  const count = items.length;

  return (
    <Box
      sx={{
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      {/* Collapsible header — 🔔 + pending count */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: 1,
          py: 0.5,
          minHeight: 32,
          cursor: 'pointer',
        }}
        onClick={toggleOpen}
        role="button"
        aria-expanded={open}
        aria-label="Toggle suggestions rail"
      >
        <NotificationsActiveOutlinedIcon
          sx={{ fontSize: '1rem', color: 'primary.main' }}
        />
        <Typography variant="caption" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
          Suggestions
        </Typography>
        {count > 0 && (
          <Chip
            size="small"
            label={count}
            sx={{ height: 16, fontSize: '0.625rem' }}
          />
        )}
        <Box sx={{ flex: 1 }} />
        <Tooltip title={open ? 'Collapse' : 'Expand'}>
          <IconButton size="small" onClick={(e) => { e.stopPropagation(); toggleOpen(); }} aria-label={open ? 'Collapse suggestions' : 'Expand suggestions'}>
            {open ? <ExpandLessIcon sx={{ fontSize: 16 }} /> : <ExpandMoreIcon sx={{ fontSize: 16 }} />}
          </IconButton>
        </Tooltip>
      </Box>

      <Collapse in={open} unmountOnExit>
        <Box
          sx={{
            maxHeight: 220,
            overflowY: 'auto',
            px: 1,
            pb: 1,
          }}
        >
          <Stack spacing={0.75}>
            {items.map((s) => {
              const id = s.id ?? s.title ?? `${s.title}-${s.created_at}`;
              const expanded = expandedId === id;
              const color = severityColor(s.severity);
              const secondary = [s.insight_type, createdAtLabel(s.created_at)]
                .filter(Boolean)
                .join(' · ');
              return (
                <Paper
                  key={id}
                  variant="outlined"
                  onClick={() => toggleExpand(id)}
                  sx={{ p: 1, cursor: 'pointer' }}
                >
                  <Stack direction="row" spacing={0.75} alignItems="flex-start">
                    <Chip
                      size="small"
                      color={color}
                      label={severityLabel(s.severity)}
                      sx={{ height: 18, fontSize: '0.625rem', flexShrink: 0 }}
                    />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 600, display: 'block', lineHeight: 1.3 }}
                      >
                        {s.title || 'Suggestion'}
                      </Typography>
                      {s.narrative && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{
                            display: 'block',
                            mt: 0.25,
                            whiteSpace: expanded ? 'normal' : 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {s.narrative}
                        </Typography>
                      )}
                      {secondary && (
                        <Typography
                          variant="caption"
                          color="text.disabled"
                          sx={{ display: 'block', mt: 0.25 }}
                        >
                          {secondary}
                        </Typography>
                      )}
                    </Box>
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        </Box>
      </Collapse>
    </Box>
  );
}

AISuggestionRail.propTypes = {
  conversationId: PropTypes.string,
};

AISuggestionRail.defaultProps = {
  conversationId: null,
};

export default AISuggestionRail;
