import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography, Chip } from '@mui/material';

function PageHeader({ icon: Icon = null, title, subtitle, description, badge, actions }) {
  return (
    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 1, mb: 1.5 }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, minWidth: 0 }}>
          {Icon && <Icon sx={{ fontSize: '1.25rem', color: 'primary.main', mt: 0.25 }} />}
          <Box sx={{ minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '1rem', fontWeight: 600 }}>{title}</Typography>
              {badge && (
                <Chip label={badge.label} size="small" variant="outlined" color={badge.color} sx={{ height: 20, fontSize: '0.625rem' }} />
              )}
            </Box>
            {subtitle && (
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{subtitle}</Typography>
            )}
            {description && (
              <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.5, lineHeight: 1.5, maxWidth: 720 }}>
                {description}
              </Typography>
            )}
          </Box>
        </Box>
        {actions && <Box sx={{ display: 'flex', gap: 1, flexShrink: 0 }}>{actions}</Box>}
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
