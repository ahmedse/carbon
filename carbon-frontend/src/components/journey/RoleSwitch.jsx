import React from 'react';
import PropTypes from 'prop-types';
import { ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';

const ROLES = [
  { track: 'L', key: 'role.lead' },
  { track: 'D', key: 'role.owner' },
  { track: 'C', key: 'role.observer' },
];

/** Lead / Owner / Observer pills. A view filter — the server already decided access. */
export default function RoleSwitch({ value, onChange, disabled }) {
  const { t } = useTranslation('journey');
  return (
    <ToggleButtonGroup
      size="small"
      exclusive
      value={value}
      disabled={disabled}
      onChange={(event, next) => { if (next) onChange(next); }}
      aria-label={t('role.label')}
    >
      {ROLES.map((role) => (
        <ToggleButton
          key={role.track}
          value={role.track}
          sx={{ ...FONT.chip, textTransform: 'none', px: 1, py: 0.25 }}
        >
          {t(role.key)}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

RoleSwitch.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

RoleSwitch.defaultProps = {
  value: undefined,
  disabled: false,
};
