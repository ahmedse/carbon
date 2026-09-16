import React, { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  IconButton,
  Popover,
  Skeleton,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  ChevronRight,
  Close,
  ErrorOutline,
  InfoOutlined,
  WarningAmber,
} from '@mui/icons-material';
import { keyframes } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useInsightStream } from '../../hooks/useInsightStream';
import ConfidenceIndicator from '../../shell/ConfidenceIndicator';

// Severity → icon + theme token color + localized label key. Severity is
// always shown as TEXT + icon (never color-only).
const SEVERITY_CONFIG = {
  critical: { color: 'error.main', icon: ErrorOutline, labelKey: 'ui.insights.severityCritical' },
  warning: { color: 'warning.main', icon: WarningAmber, labelKey: 'ui.insights.severityWarning' },
  info: { color: 'info.main', icon: InfoOutlined, labelKey: 'ui.insights.severityInfo' },
};

// Presentational route selection from insight_type (never rendered as text).
const DEEP_LINK_MAP = {
  threshold_alert: '/engines',
  trend_alert: '/engines',
  drift: '/engines',
  performance: '/engines',
  freshness: '/datasets',
  stale: '/datasets',
  error: '/jobs',
  failed: '/jobs',
  anomaly: '/dashboard',
};

function deriveDeepLink(insightType) {
  return DEEP_LINK_MAP[insightType] || '/dashboard';
}

// Simple opacity fade, gated behind no-preference so reduced-motion users get
// no motion at all.
const fadeIn = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`;

function getRelativeTime(createdAt) {
  const created = new Date(createdAt).getTime();
  if (Number.isNaN(created)) return '';
  const diff = Date.now() - created;
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < minute) return 'just now';
  if (diff < hour) return `${Math.floor(diff / minute)}m ago`;
  if (diff < day) return `${Math.floor(diff / hour)}h ago`;
  return `${Math.floor(diff / day)}d ago`;
}

/** Human disposition label — never render raw engine values. */
function dispositionLabelKey(disposition) {
  if (disposition === 'acted_on') return 'ui.insights.dispositionActed';
  if (disposition === 'dismissed') return 'ui.insights.dispositionDismissed';
  if (disposition === 'read') return 'ui.insights.dispositionRead';
  return null;
}

/**
 * Render backend provenance (PEC-3A OUTCOME shape) only — never invent sources.
 * Expected: { basis?: string, sources?: [{ label, detail }] }
 */
function ProvenanceAffordance({ provenance, t }) {
  const [anchor, setAnchor] = useState(null);
  if (!provenance || typeof provenance !== 'object') return null;

  const sources = Array.isArray(provenance.sources) ? provenance.sources : [];
  const basis = typeof provenance.basis === 'string' ? provenance.basis.trim() : '';
  if (!basis && sources.length === 0) return null;

  return (
    <>
      <Tooltip title={t('ui.insights.provenanceHint')}>
        <IconButton
          size="small"
          aria-label={t('ui.insights.provenanceHint')}
          onClick={(e) => {
            e.stopPropagation();
            setAnchor(e.currentTarget);
          }}
          sx={{ p: 0.25, color: 'text.secondary' }}
        >
          <InfoOutlined sx={{ fontSize: '0.875rem' }} />
        </IconButton>
      </Tooltip>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={(e) => {
          e?.stopPropagation?.();
          setAnchor(null);
        }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{ paper: { sx: { p: 1.25, maxWidth: 280 } } }}
        onClick={(e) => e.stopPropagation()}
      >
        <Typography fontSize="0.75rem" fontWeight={600} color="text.primary" sx={{ mb: 0.75 }}>
          {t('ui.insights.provenanceTitle')}
        </Typography>
        {basis ? (
          <Typography fontSize="0.6875rem" color="text.secondary" sx={{ mb: sources.length ? 0.75 : 0 }}>
            {basis}
          </Typography>
        ) : null}
        {sources.slice(0, 5).map((src, idx) => {
          const label = typeof src?.label === 'string' ? src.label : '';
          const detail = typeof src?.detail === 'string' ? src.detail : '';
          if (!label && !detail) return null;
          return (
            <Box key={idx} sx={{ mb: 0.5 }}>
              {label ? (
                <Typography fontSize="0.6875rem" fontWeight={600} color="text.primary">
                  {label}
                </Typography>
              ) : null}
              {detail ? (
                <Typography fontSize="0.625rem" color="text.secondary">
                  {detail}
                </Typography>
              ) : null}
            </Box>
          );
        })}
      </Popover>
    </>
  );
}

function InsightRowSkeleton() {
  return (
    <Box sx={{ display: 'flex', gap: 1, p: 1, mb: 1 }}>
      <Skeleton variant="circular" width={20} height={20} sx={{ mt: 0.25 }} />
      <Box sx={{ flex: 1 }}>
        <Skeleton variant="text" width="70%" height={18} />
        <Skeleton variant="text" width="95%" height={14} />
        <Skeleton variant="text" width="40%" height={12} />
      </Box>
    </Box>
  );
}

function actionLabel(recommendedActions, t) {
  const first = Array.isArray(recommendedActions) ? recommendedActions[0] : null;
  if (typeof first === 'string' && first.trim()) return first.trim();
  if (first && typeof first === 'object' && typeof first.label === 'string') {
    return first.label.trim();
  }
  return t('ui.insights.act');
}

export function InsightNotificationPanel({ anchorEl, onClose }) {
  const { t } = useTranslation('shell');
  const navigate = useNavigate();
  const { insights, unreadCount, loading, error, markRead, markAllRead, refresh } =
    useInsightStream();

  /** Row click = acknowledge only (Principle 11 — navigate is the Act chip). */
  const handleRowClick = async (insight) => {
    if (!insight || insight.disposition !== 'pending') return;
    await markRead(insight.id, 'read');
  };

  const handleAct = async (e, insight) => {
    e.stopPropagation();
    if (!insight) return;
    await markRead(insight.id, 'acted_on');
    navigate(deriveDeepLink(insight.insight_type));
    onClose();
  };

  const handleDismiss = async (e, insight) => {
    e.stopPropagation();
    if (!insight) return;
    await markRead(insight.id, 'dismissed');
  };

  return (
    <Popover
      open={Boolean(anchorEl)}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      slotProps={{ paper: { sx: { width: 380, maxHeight: 480, borderRadius: 2, p: 1.5 } } }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.25, px: 0.5 }}>
        <Typography fontSize="0.9375rem" fontWeight={600} color="text.primary">
          {t('ui.insights.title')}
        </Typography>
        <Button size="small" onClick={markAllRead} disabled={unreadCount === 0}>
          {t('ui.insights.markAllRead')}
        </Button>
      </Box>

      <Box sx={{ borderTop: 1, borderColor: 'divider', mt: 0.5, mb: 1 }} />

      {loading ? (
        <Box sx={{ minHeight: 200, p: 0.5 }} aria-busy="true" aria-label={t('ui.insights.loading')}>
          <InsightRowSkeleton />
          <InsightRowSkeleton />
          <InsightRowSkeleton />
        </Box>
      ) : error ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200, p: 2, gap: 1 }}>
          <Typography color="text.secondary" textAlign="center">
            {t('ui.insights.error')}
          </Typography>
          <Button size="small" onClick={refresh}>
            {t('ui.insights.retry')}
          </Button>
        </Box>
      ) : insights.length === 0 ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200, p: 2, gap: 0.75 }}>
          <Typography color="text.primary" textAlign="center" fontWeight={500}>
            {t('ui.insights.empty')}
          </Typography>
          <Typography color="text.secondary" textAlign="center" fontSize="0.8125rem">
            {t('ui.insights.emptyHint')}
          </Typography>
        </Box>
      ) : (
        <Box sx={{ maxHeight: 360, overflowY: 'auto', pr: 0.5 }}>
          {insights.map((insight) => {
            const config = SEVERITY_CONFIG[insight.severity] || SEVERITY_CONFIG.info;
            const Icon = config.icon;
            const unread = insight.disposition === 'pending';
            const dispKey = dispositionLabelKey(insight.disposition);
            const confidenceLabel =
              typeof insight.confidence_label === 'string' ? insight.confidence_label : '';
            const actText = actionLabel(insight.recommended_actions, t);

            return (
              <Box
                key={insight.id}
                className="InsightRow"
                onClick={() => handleRowClick(insight)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleRowClick(insight);
                  }
                }}
                aria-label={`${insight.title}. ${t(config.labelKey)}`}
                sx={{
                  display: 'flex',
                  gap: 1,
                  alignItems: 'flex-start',
                  p: 1,
                  borderRadius: 1.5,
                  cursor: unread ? 'pointer' : 'default',
                  borderLeft: 3,
                  borderLeftColor: config.color,
                  bgcolor: unread ? 'action.selected' : 'transparent',
                  '&:hover': { bgcolor: 'action.hover' },
                  mb: 1,
                  '@media (prefers-reduced-motion: no-preference)': {
                    animation: `${fadeIn} 0.25s ease`,
                  },
                }}
              >
                <Icon sx={{ color: config.color, fontSize: '1.25rem', mt: '2px' }} aria-hidden />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5, flexWrap: 'wrap' }}>
                    <Typography
                      fontSize="0.8125rem"
                      fontWeight={unread ? 600 : 400}
                      color="text.primary"
                      noWrap
                      sx={{ maxWidth: '70%' }}
                    >
                      {insight.title}
                    </Typography>
                    <Typography fontSize="0.6875rem" fontWeight={600} color={config.color}>
                      {t(config.labelKey)}
                    </Typography>
                    <ProvenanceAffordance provenance={insight.provenance} t={t} />
                  </Box>
                  {insight.narrative ? (
                    <Typography
                      fontSize="0.75rem"
                      color="text.secondary"
                      sx={{
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {insight.narrative}
                    </Typography>
                  ) : null}

                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.75, flexWrap: 'wrap' }}>
                    {confidenceLabel ? (
                      <ConfidenceIndicator
                        label={confidenceLabel}
                        honest={confidenceLabel === 'uncertain'}
                      />
                    ) : null}
                    <Typography fontSize="0.6875rem" color="text.disabled">
                      {getRelativeTime(insight.created_at)}
                      {dispKey ? ` · ${t(dispKey)}` : ''}
                    </Typography>
                  </Box>

                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      mt: 0.75,
                      justifyContent: 'space-between',
                    }}
                  >
                    <Chip
                      size="small"
                      clickable
                      label={actText}
                      icon={<ChevronRight sx={{ fontSize: '0.875rem !important' }} />}
                      onClick={(e) => handleAct(e, insight)}
                      sx={{ fontSize: '0.65rem', height: 22, maxWidth: '75%' }}
                    />
                    <Tooltip title={t('ui.insights.dismiss')}>
                      <IconButton
                        size="small"
                        aria-label={t('ui.insights.dismiss')}
                        onClick={(e) => handleDismiss(e, insight)}
                        sx={{
                          opacity: { xs: 1, sm: 0 },
                          '.InsightRow:hover &': { opacity: 1 },
                          '.InsightRow:focus-within &': { opacity: 1 },
                        }}
                      >
                        <Close fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
              </Box>
            );
          })}
        </Box>
      )}
    </Popover>
  );
}
