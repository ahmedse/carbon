import React from 'react';
import PropTypes from 'prop-types';
import { Paper, Box, Typography, Tooltip } from '@mui/material';
import { useTheme, alpha } from '@mui/material/styles';

function Sparkline({ data = [], color }) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const points = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * 80;
      const y = 24 - (value / max) * 20;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width="80" height="24" role="img" aria-label="sparkline">
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
    </svg>
  );
}

function StatCard({ title, value, unit, icon, color, sparkline, trend, trendLabel, loading, onClick, tooltip }) {
  const theme = useTheme();
  const paletteColor = theme.palette[color]?.main || theme.palette.primary.main;

  const cardContent = (
    <Paper
      elevation={0}
      onClick={onClick}
      sx={{
        p: 1.25,
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        '&:hover': onClick ? { 
          backgroundColor: 'action.hover',
          boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
          transform: 'translateY(-1px)',
          borderColor: alpha(paletteColor, 0.3)
        } : {
          boxShadow: '0 2px 6px rgba(0,0,0,0.08)'
        },
      }}
    >
      <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', mb: 0.5 }}>
        {icon && (
          <Box sx={{ 
            width: 24, 
            height: 24, 
            borderRadius: 1.5, 
            bgcolor: alpha(paletteColor, 0.1), 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            transition: 'all 0.25s ease'
          }}>
            {React.cloneElement(icon, { sx: { fontSize: 14, color: paletteColor } })}
          </Box>
        )}
        <Typography sx={{ fontSize: '0.625rem', fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {title}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: '1.25rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.1 }}>
        {loading ? '–' : value}
        {unit && (
          <Typography component="span" sx={{ fontSize: '0.8rem', color: 'text.secondary', ml: 0.5, fontWeight: 500 }}>
            {unit}
          </Typography>
        )}
      </Typography>
      {sparkline && sparkline.length > 1 && (
        <Box sx={{ mt: 1 }}>
          <Sparkline data={sparkline} color={paletteColor} />
        </Box>
      )}
      {trend != null && (
        <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', mt: 0.75 }}>
          {trend > 0 ? '+' : ''}
          {trend}% {trendLabel}
        </Typography>
      )}
    </Paper>
  );

  if (tooltip) {
    return (
      <Tooltip title={tooltip} arrow placement="top">
        {cardContent}
      </Tooltip>
    );
  }
  return cardContent;
}

StatCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  unit: PropTypes.string,
  icon: PropTypes.element,
  color: PropTypes.string,
  sparkline: PropTypes.arrayOf(PropTypes.number),
  trend: PropTypes.number,
  trendLabel: PropTypes.string,
  loading: PropTypes.bool,
  onClick: PropTypes.func,
  tooltip: PropTypes.string,
};

StatCard.defaultProps = {
  unit: '',
  icon: null,
  color: 'primary',
  sparkline: [],
  trend: undefined,
  trendLabel: '',
  loading: false,
  onClick: undefined,
};

export default React.memo(StatCard);
