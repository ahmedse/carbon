import React from 'react';
import PropTypes from 'prop-types';
import { Box, Paper, Typography, Chip, Button } from '@mui/material';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';

function PeriodBanner({ name, startDate, endDate, status, daysRemaining, onAction }) {
  const statusBg = status === 'open' ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : // gradient
                   status === 'closing' ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : // gradient
                   'linear-gradient(135deg, #64748b 0%, #475569 100%)'; // gradient

  return (
    <Paper 
      elevation={0}
      sx={{ 
        p: 1.5, 
        mb: 1.5, 
        background: statusBg,
        borderRadius: 2,
        display: 'flex', 
        flexDirection: { xs: 'column', sm: 'row' }, 
        gap: 1.25, 
        alignItems: 'center', 
        justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        border: 'none'
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
        <Box sx={{ 
          width: 32, 
          height: 32, 
          borderRadius: 1.5, 
          bgcolor: 'rgba(255,255,255,0.2)', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          backdropFilter: 'blur(10px)'
        }}>
          <CalendarMonthIcon sx={{ fontSize: 16, color: 'common.white' }} />
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: 'common.white' }}>{name}</Typography>
          <Typography sx={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.85)' }}>
            {startDate} — {endDate}
          </Typography>
          {daysRemaining != null && (
            <Typography sx={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.95)', fontWeight: 600, mt: 0.25 }}>
              {daysRemaining} days remaining
            </Typography>
          )}
        </Box>
      </Box>
      {onAction && (
        <Button 
          size="small" 
          variant="contained"
          onClick={onAction}
          sx={{
            bgcolor: 'rgba(255,255,255,0.25)',
            color: 'common.white',
            backdropFilter: 'blur(10px)',
            fontWeight: 600,
            fontSize: '0.7rem',
            '&:hover': {
              bgcolor: 'rgba(255,255,255,0.35)'
            }
          }}
        >
          View details
        </Button>
      )}
    </Paper>
  );
}

PeriodBanner.propTypes = {
  name: PropTypes.string,
  startDate: PropTypes.string,
  endDate: PropTypes.string,
  status: PropTypes.oneOf(['open', 'closing', 'closed']),
  daysRemaining: PropTypes.number,
  onAction: PropTypes.func,
};

PeriodBanner.defaultProps = {
  name: '',
  startDate: '',
  endDate: '',
  status: 'closed',
  daysRemaining: null,
  onAction: undefined,
};

export default React.memo(PeriodBanner);
