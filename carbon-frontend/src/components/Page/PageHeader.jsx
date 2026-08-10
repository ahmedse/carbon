import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography, Chip } from '@mui/material';

function PageHeader({ icon: Icon = null, title, subtitle, description, badge, actions }) {
  return (
    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 0.5, mb: 1 }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 0.75 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75, minWidth: 0 }}>
          {Icon && <Icon sx={{ fontSize: '1rem', color: 'primary.main', mt: 0.125 }} />}
          <Box sx={{ minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{title}</Typography>
              {badge && (
                <Chip label={badge.label} size="small" variant="outlined" color={badge.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
              )}
            </Box>
            {subtitle && (
              <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>{subtitle}</Typography>
            )}
            {description && (
              <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', mt: 0.25, lineHeight: 1.4, maxWidth: 680 }}>
                {description}
              </Typography>
            )}
          </Box>
        </Box>
        {actions && <Box sx={{ display: 'flex', gap: 0.75, flexShrink: 0 }}>{actions}</Box>}
      </Box>
    </Box>
  );
}

PageHeader.propTypes = {
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  description: PropTypes.string,
  icon: PropTypes.elementType,
  badge: PropTypes.shape({ label: PropTypes.string.isRequired, color: PropTypes.string }),
  actions: PropTypes.node,
};

PageHeader.defaultProps = {
  subtitle: '',
  description: '',
  icon: null,
  badge: null,
  actions: null,
};

export default React.memo(PageHeader);
