// File: src/components/detail/DetailHeader.jsx
// Unified header component with breadcrumbs for all detail pages

import React from 'react';
import { Box, Typography, IconButton, useTheme, useMediaQuery } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import CloseIcon from '@mui/icons-material/Close';

/**
 * DetailHeader - Unified header for all detail pages (breadcrumbs handled by shell)
 * 
 * Props:
 * - title: Main title/heading
 * - description: Optional subtitle/description
 * - icon: Icon component to display
 * - onClose: Callback when close button clicked
 */
export default function DetailHeader({
  title = '',
  description = '',
  icon: Icon = null,
  onClose = () => {},
}) {
  const _navigate = useNavigate();
  const theme = useTheme();
  const _isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box
      sx={{
        bgcolor: 'background.paper',
        borderBottom: 1,
        borderColor: 'divider',
        px: 2,
        py: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1.5,
      }}
    >
      {/* Left: Title */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {Icon && <Icon sx={{ fontSize: '1.125rem', color: 'primary.main' }} />}
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, m: 0, lineHeight: 1.3 }} noWrap>
              {title}
            </Typography>
            {description && (
              <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
                {description}
              </Typography>
            )}
          </Box>
        </Box>
      </Box>

      {/* Right: Close button */}
      <IconButton
        onClick={onClose}
        size="small"
        sx={{
          flexShrink: 0,
          bgcolor: 'action.hover',
          '&:hover': {
            bgcolor: 'action.selected',
          },
        }}
      >
        <CloseIcon fontSize="small" />
      </IconButton>
    </Box>
  );
}
