import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography, Chip } from '@mui/material';

function PageHeader({ icon: Icon = null, title, subtitle, description, badge, actions, titleComponent = undefined }) {
  return (
    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 0.5, mb: 1 }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 0.75 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75, minWidth: 0 }}>
          {Icon && <Icon sx={{ fontSize: '1rem', color: 'primary.main', mt: 0.125 }} />}
          <Box sx={{ minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
              <Typography component={titleComponent} sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{title}</Typography>
              {badge && (
                <Chip label={badge.label} size="small" color={badge.color} />
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
  titleComponent: PropTypes.elementType,
};

PageHeader.defaultProps = {
  subtitle: '',
  description: '',
  icon: null,
  badge: null,
  actions: null,
  titleComponent: undefined,
};

export default React.memo(PageHeader);
