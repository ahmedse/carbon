import React from 'react';
import { Box, Button, Chip, CircularProgress, Popover, Typography } from '@mui/material';
import { InfoOutlined, Security, ErrorOutline, WarningAmber, AccountTree } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useNotifications } from '../../hooks/useNotifications';

const CATEGORY_CONFIG = {
  security: { color: 'error.main', icon: Security },
  dq_violation: { color: 'error.main', icon: ErrorOutline },
  backup: { color: 'warning.main', icon: WarningAmber },
  import: { color: 'info.main', icon: InfoOutlined },
  workflow: { color: 'info.main', icon: AccountTree },
  system: { color: 'info.main', icon: InfoOutlined },
  other: { color: 'text.secondary', icon: InfoOutlined },
};

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

export function NotificationCenter({ anchorEl, onClose }) {
  const { t } = useTranslation('shell');
  const navigate = useNavigate();
  const { alerts, unreadCount, total, loading, markRead, markAllRead, loadMore } = useNotifications();

  const handleRowClick = async (alert) => {
    if (!alert) return;
    await markRead(alert.id);
    if (alert.link) {
      navigate(alert.link);
    }
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
          {t('ui.notifications')}
        </Typography>
        <Button size="small" onClick={markAllRead} disabled={unreadCount === 0}>
          {t('ui.markAllRead')}
        </Button>
      </Box>

      <Box sx={{ borderTop: 1, borderColor: 'divider', mt: 0.5, mb: 1 }} />

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200, p: 2 }}>
          <CircularProgress size={24} />
        </Box>
      ) : alerts.length === 0 ? (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, p: 2 }}>
          <Typography color="text.secondary">{t('ui.noNotifications')}</Typography>
        </Box>
      ) : (
        <Box sx={{ maxHeight: 360, overflowY: 'auto', pr: 0.5 }}>
          {alerts.map((alert) => {
            const config = CATEGORY_CONFIG[alert.category] || CATEGORY_CONFIG.other;
            const Icon = config.icon;
            return (
              <Box
                key={alert.id}
                onClick={() => handleRowClick(alert)}
                sx={{
                  display: 'flex',
                  gap: 1,
                  alignItems: 'flex-start',
                  p: 1,
                  borderRadius: 1.5,
                  cursor: 'pointer',
                  bgcolor: alert.is_read ? 'transparent' : 'action.hover',
                  '&:hover': { bgcolor: 'action.hover' },
                  mb: 1,
                }}
              >
                <Icon sx={{ color: config.color, fontSize: 20, mt: '2px' }} />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
                    <Typography fontSize="0.8125rem" fontWeight={600} color="text.primary" noWrap>
                      {alert.title}
                    </Typography>
                    <Chip
                      size="small"
                      label={alert.category}
                      variant="outlined"
                      sx={{ height: 24, fontSize: '0.6875rem', textTransform: 'capitalize' }}
                    />
                  </Box>
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
                    {alert.body || ' '}
                  </Typography>
                  <Typography fontSize="0.6875rem" color="text.secondary" sx={{ mt: 0.5 }}>
                    {getRelativeTime(alert.created_at)}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Box>
      )}

      {!loading && alerts.length > 0 && alerts.length < total && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
          <Button size="small" onClick={loadMore}>
            {t('ui.loadMore')}
          </Button>
        </Box>
      )}
    </Popover>
  );
}
