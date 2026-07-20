// File: src/components/detail/DetailHeader.jsx
// Unified header component with breadcrumbs for all detail pages

import React from 'react';
import { Box, Typography, IconButton, Breadcrumbs, Link, useTheme, useMediaQuery } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import CloseIcon from '@mui/icons-material/Close';

/**
 * DetailHeader - Unified breadcrumb header for all detail pages
 * 
 * Props:
 * - breadcrumbs: Array of {label, icon, path, onClick} for breadcrumb trail
 * - title: Main title/heading
 * - description: Optional subtitle/description
 * - icon: Icon component to display
 * - onClose: Callback when close button clicked
 */
export default function DetailHeader({
  breadcrumbs = [],
  title = '',
  description = '',
  icon: Icon = null,
  onClose = () => {},
}) {
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const handleBreadcrumbClick = (breadcrumb) => {
    if (breadcrumb.onClick) {
      breadcrumb.onClick();
    } else if (breadcrumb.path) {
      navigate(breadcrumb.path);
    }
  };

  return (
    <Box
      sx={{
        bgcolor: 'white',
        borderBottom: '1px solid #e0e0e0',
        p: 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 2,
      }}
    >
      {/* Left: Breadcrumbs and title */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {breadcrumbs.length > 0 && (
          <Breadcrumbs
            separator="/"
            sx={{
              mb: 1,
              fontSize: '0.875rem',
              '& a': {
                cursor: 'pointer',
                '&:hover': {
                  textDecoration: 'underline',
                },
              },
            }}
          >
            {breadcrumbs.map((crumb, idx) => (
              <Link
                key={idx}
                component="button"
                type="button"
                onClick={() => handleBreadcrumbClick(crumb)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  color: 'inherit',
                  textDecoration: 'none',
                }}
              >
                {crumb.icon && <Box component="span" sx={{ fontSize: '1rem' }} children={crumb.icon} />}
                {crumb.label}
              </Link>
            ))}
          </Breadcrumbs>
        )}

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {Icon && <Icon sx={{ fontSize: '1.5rem', color: 'primary.main' }} />}
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, m: 0 }}>
              {title}
            </Typography>
            {description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
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
