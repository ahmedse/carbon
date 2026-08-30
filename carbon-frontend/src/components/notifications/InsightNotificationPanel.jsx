import React from 'react';
import { Box, Button, CircularProgress, Popover, Typography } from '@mui/material';
import { ErrorOutline, WarningAmber, InfoOutlined } from '@mui/icons-material';
import { keyframes } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useInsightStream } from '../../hooks/useInsightStream';

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
  const diff = Date.now() - created;
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < minute) return 'just now';
  if (diff < hour) return `${Math.floor(diff / minute)}m ago`;
  if (diff < day) return `${Math.floor(diff / hour)}h ago`;
  return `${Math.floor(diff / day)}d ago`;
}

export function InsightNotificationPanel({ anchorEl, onClose }) {
  const { t } = useTranslation('shell');
  const navigate = useNavigate();
  const { insights, unreadCount, loading, error, markRead, markAllRead, refresh } =
    useInsightStream();

  const handleRowClick = async (insight) => {
    if (!insight) return;
    await markRead(insight.id, 'read');
    navigate(deriveDeepLink(insight.insight_type));
    onClose();
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
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200, p: 2 }}>
          <CircularProgress size={24} />
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
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, p: 2 }}>
          <Typography color="text.secondary">{t('ui.insights.empty')}</Typography>
        </Box>
      ) : (
        <Box sx={{ maxHeight: 360, overflowY: 'auto', pr: 0.5 }}>
          {insights.map((insight) => {
            const config = SEVERITY_CONFIG[insight.severity] || SEVERITY_CONFIG.info;
            const Icon = config.icon;
            const actions = Array.isArray(insight.recommended_actions)
              ? insight.recommended_actions.slice(0, 2)
              : [];
            return (
              <Box
                key={insight.id}
                onClick={() => handleRowClick(insight)}
                sx={{
                  display: 'flex',
                  gap: 1,
                  alignItems: 'flex-start',
                  p: 1,
                  borderRadius: 1.5,
                  cursor: 'pointer',
                  bgcolor: insight.disposition === 'pending' ? 'action.hover' : 'transparent',
                  '&:hover': { bgcolor: 'action.hover' },
                  mb: 1,
                  '@media (prefers-reduced-motion: no-preference)': {
                    animation: `${fadeIn} 0.25s ease`,
                  },
                }}
              >
                <Icon sx={{ color: config.color, fontSize: '1.25rem', mt: '2px' }} />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
                    <Typography fontSize="0.8125rem" fontWeight={600} color="text.primary" noWrap>
                      {insight.title}
                    </Typography>
                    <Typography fontSize="0.6875rem" fontWeight={600} color={config.color}>
                      {t(config.labelKey)}
                    </Typography>
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
                  {actions.map((action, idx) => (
                    <Typography
                      key={idx}
                      fontSize="0.6875rem"
                      color="text.secondary"
                      sx={{ lineHeight: 1.4, mt: idx === 0 ? 0.5 : 0.25 }}
                    >
                      {action}
                    </Typography>
                  ))}
                  <Typography fontSize="0.6875rem" color="text.secondary" sx={{ mt: 0.5 }}>
                    {getRelativeTime(insight.created_at)}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Box>
      )}
    </Popover>
  );
}
