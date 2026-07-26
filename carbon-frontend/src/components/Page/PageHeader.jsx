import React from 'react';
import PropTypes from 'prop-types';
import { Box, Breadcrumbs, Link, Typography, Chip } from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';

function PageHeader({ title, subtitle, breadcrumbs, badge, actions }) {
  return (
    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 1.5, mb: 2 }}>
      {breadcrumbs?.length > 0 && (
        <Breadcrumbs separator={<NavigateNextIcon fontSize="small" />} sx={{ mb: 0.75 }}>
          {breadcrumbs.map((crumb, index) => (
            crumb.path ? (
              <Link key={index} color="inherit" underline="hover" href={crumb.path} sx={{ fontSize: '0.6875rem' }}>
                {crumb.label}
              </Link>
            ) : (
              <Typography key={index} sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
                {crumb.label}
              </Typography>
            )
          ))}
        </Breadcrumbs>
      )}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1.5 }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography sx={{ fontSize: '1.125rem', fontWeight: 600 }}>{title}</Typography>
            {badge && (
              <Chip label={badge.label} size="small" variant="outlined" color={badge.color} sx={{ height: 20, fontSize: '0.625rem' }} />
            )}
          </Box>
          {subtitle && (
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.25 }}>{subtitle}</Typography>
          )}
        </Box>
        {actions && <Box>{actions}</Box>}
      </Box>
    </Box>
  );
}

PageHeader.propTypes = {
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  breadcrumbs: PropTypes.arrayOf(PropTypes.shape({ label: PropTypes.string.isRequired, path: PropTypes.string })),
  badge: PropTypes.shape({ label: PropTypes.string.isRequired, color: PropTypes.string }),
  actions: PropTypes.node,
};

PageHeader.defaultProps = {
  subtitle: '',
  breadcrumbs: [],
  badge: null,
  actions: null,
};

export default React.memo(PageHeader);
