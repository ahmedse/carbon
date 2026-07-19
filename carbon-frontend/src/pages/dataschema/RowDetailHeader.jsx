// File: src/pages/dataschema/RowDetailHeader.jsx
// Header with breadcrumbs, title, and close button

import React from 'react';
import { Box, Typography, IconButton, Breadcrumbs, Link, useTheme, useMediaQuery } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import CloseIcon from '@mui/icons-material/Close';
import HomeIcon from '@mui/icons-material/Home';
import StorageIcon from '@mui/icons-material/Storage';

export default function RowDetailHeader({ rowData, onClose }) {
  const navigate = useNavigate();
  const { tableId } = useParams();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const handleBreadcrumbClick = (path) => {
    navigate(path);
  };

  // Get display name for the row (use first field value as row name)
  const getRowDisplayName = () => {
    if (!rowData) return 'Row Details';
    
    // Try common name fields
    const nameFields = ['name', 'title', 'building', 'id', 'building_id'];
    for (const field of nameFields) {
      if (rowData[field]) {
        return `${field.replace(/_/g, ' ')}: ${rowData[field]}`;
      }
    }
    
    // Fall back to row ID if available
    if (rowData.id) return `Row #${rowData.id}`;
    return 'Row Details';
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
          <Link
            component="button"
            type="button"
            onClick={() => handleBreadcrumbClick('/dataschema')}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              color: 'inherit',
              textDecoration: 'none',
            }}
          >
            <HomeIcon sx={{ fontSize: '1rem' }} />
            Data Hub
          </Link>
          <Link
            component="button"
            type="button"
            onClick={() => handleBreadcrumbClick(`/dataschema/entry/${tableId}`)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              color: 'inherit',
              textDecoration: 'none',
            }}
          >
            <StorageIcon sx={{ fontSize: '1rem' }} />
            {isMobile ? 'Table' : 'Back to Table'}
          </Link>
        </Breadcrumbs>

        {/* Title */}
        <Typography
          variant="h6"
          sx={{
            fontWeight: 600,
            color: '#1a1a1a',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {getRowDisplayName()}
        </Typography>
      </Box>

      {/* Right: Close button */}
      <IconButton
        edge="end"
        color="inherit"
        onClick={onClose}
        sx={{
          flexShrink: 0,
          '&:hover': {
            bgcolor: '#f0f0f0',
          },
        }}
        title="Close (Esc)"
      >
        <CloseIcon />
      </IconButton>
    </Box>
  );
}
