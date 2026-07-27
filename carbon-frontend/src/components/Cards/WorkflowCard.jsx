import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography, Tooltip } from '@mui/material';

function WorkflowCard({ icon, title, description, onClick, disabled }) {
  const content = (
    <Box
      onClick={disabled ? undefined : onClick}
      sx={{
        p: 1.25,
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        bgcolor: 'background.paper',
        '&:hover': disabled ? {} : { 
          borderColor: 'primary.main',
          backgroundColor: 'action.hover',
          boxShadow: '0 4px 12px rgba(37, 99, 235, 0.12)',
          transform: 'translateY(-1px)'
        },
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        width: 32, 
        height: 32, 
        borderRadius: 2, 
        background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(37, 99, 235, 0.15) 100%)',
        flexShrink: 0,
        transition: 'transform 0.2s ease'
      }}>
        {icon && React.cloneElement(icon, { sx: { fontSize: 16, color: 'primary.main' } })}
      </Box>
      <Box sx={{ minWidth: 0, textAlign: 'left', flex: 1 }}>
        <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.primary', lineHeight: 1.2 }}>{title}</Typography>
        <Typography 
          sx={{ 
            fontSize: '0.65rem', 
            color: 'text.secondary', 
            lineHeight: 1.3,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden'
          }}
        >
          {description}
        </Typography>
      </Box>
    </Box>
  );

  if (description) {
    return (
      <Tooltip title={description} arrow placement="top">
        {content}
      </Tooltip>
    );
  }
  return content;
}

WorkflowCard.propTypes = {
  icon: PropTypes.element,
  title: PropTypes.string.isRequired,
  description: PropTypes.string.isRequired,
  onClick: PropTypes.func,
  disabled: PropTypes.bool,
};

WorkflowCard.defaultProps = {
  icon: null,
  onClick: undefined,
  disabled: false,
};

export default React.memo(WorkflowCard);
