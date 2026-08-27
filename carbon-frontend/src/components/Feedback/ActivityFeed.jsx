import React from 'react';
import PropTypes from 'prop-types';
import { Box, Paper, Stack, Typography } from '@mui/material';
import CalculateIcon from '@mui/icons-material/Calculate';
import UploadIcon from '@mui/icons-material/Upload';
import ShieldIcon from '@mui/icons-material/Shield';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import Skeleton from '@mui/material/Skeleton';

const ACTION_ICONS = {
  calculation: CalculateIcon,
  submission: UploadIcon,
  verification: ShieldIcon,
  dq_alert: WarningAmberIcon,
};

function ActivityFeed({ items, maxItems, emptyMessage, loading }) {
  if (loading) {
    return (
      <Paper elevation={0} sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
        {[...Array(5)].map((_, idx) => (
          <Box key={idx} sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: idx < 4 ? 2 : 0 }}>
            <Skeleton variant="circular" width={32} height={32} />
            <Box sx={{ flex: 1 }}>
              <Skeleton width="70%" height={16} sx={{ mb: 0.5 }} />
              <Skeleton width="50%" height={14} />
            </Box>
          </Box>
        ))}
      </Paper>
    );
  }

  if (!items.length) {
    return (
      <Paper elevation={0} sx={{ p: 3, borderRadius: 2, border: '1px solid', borderColor: 'divider', textAlign: 'center', bgcolor: 'background.paper' }}>
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', fontStyle: 'italic' }}>{emptyMessage}</Typography>
      </Paper>
    );
  }

  return (
    <Paper 
      elevation={0}
      sx={{ 
        borderRadius: 2, 
        border: '1px solid',
        borderColor: 'divider',
        maxHeight: 400, 
        overflow: 'auto',
        bgcolor: 'background.paper'
      }}
    >
      <Stack spacing={0}>
        {items.slice(0, maxItems).map((item, idx) => {
          const ActionIcon = ACTION_ICONS[item.action] || WarningAmberIcon;
          return (
            <React.Fragment key={item.id || idx}>
              <Box 
                sx={{ 
                  display: 'flex', 
                  gap: 1, 
                  alignItems: 'flex-start',
                  p: 1,
                  transition: 'background-color 0.2s ease',
                  '&:hover': {
                    bgcolor: 'action.hover'
                  }
                }}
              >
                <Box sx={{
                  width: 32,
                  height: 32,
                  borderRadius: 1.5,
                  bgcolor: 'action.selected',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <ActionIcon sx={{ fontSize: '1rem', color: 'primary.main' }} />
                </Box>
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.primary', lineHeight: 1.4 }}>
                    {item.module} · {item.detail}
                  </Typography>
                  <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', mt: 0.25 }}>
                    {new Date(item.timestamp).toLocaleString()}{item.user ? ` · ${item.user}` : ''}
                  </Typography>
                </Box>
              </Box>
              {idx < items.slice(0, maxItems).length - 1 && (
                <Box sx={{ borderBottom: '1px solid', borderColor: 'divider' }} />
              )}
            </React.Fragment>
          );
        })}
      </Stack>
    </Paper>
  );
}

ActivityFeed.propTypes = {
  items: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
    action: PropTypes.string.isRequired,
    module: PropTypes.string.isRequired,
    timestamp: PropTypes.string.isRequired,
    detail: PropTypes.string.isRequired,
    user: PropTypes.string,
  })),
  maxItems: PropTypes.number,
  emptyMessage: PropTypes.string,
  loading: PropTypes.bool,
};

ActivityFeed.defaultProps = {
  items: [],
  maxItems: 10,
  emptyMessage: 'No recent activity',
  loading: false,
};

export default React.memo(ActivityFeed);
