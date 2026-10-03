import React, { forwardRef } from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import useReducedMotion from './useReducedMotion';
import { stageArt } from './journeyArt';

/**
 * One camp on the trail: a clearly labelled, always-clickable chip.
 *
 * Every camp shows its name — the trail is the map and it should read without a
 * hover. The camp you are on is filled with its own colour and its own icon; a
 * camp the app proved is a green check; a camp with no work owed is dashed. The
 * marker testids and `data-marker` states are unchanged. Never a lock.
 */
const StationCard = forwardRef(function StationCard({ station, active, onSelect }, ref) {
  const { t } = useTranslation('journey');
  const reduced = useReducedMotion();
  const { Icon, color } = stageArt(station);

  const marker = station.pending
    ? 'interlude'
    : (station.done ? 'done' : (active ? 'current' : 'open'));
  const filled = marker === 'done' || marker === 'current';

  return (
    <Box
      ref={ref}
      role="tab"
      id={`journey-station-tab-${station.n}`}
      aria-controls={`journey-station-panel-${station.n}`}
      aria-selected={active}
      aria-current={station.state === 'current' ? 'step' : undefined}
      aria-label={t('trail.camp', { n: station.n })}
      tabIndex={active ? 0 : -1}
      data-testid={`journey-station-${station.n}`}
      data-state={station.state}
      data-motion={reduced ? 'reduced' : 'full'}
      onClick={() => onSelect(station.n)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(station.n);
        }
      }}
      sx={{
        flex: '0 1 auto',
        minWidth: 0,
        maxWidth: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 0.75,
        cursor: 'pointer',
        border: '1px solid',
        borderStyle: marker === 'interlude' ? 'dashed' : 'solid',
        borderColor: filled ? `${color}.main` : 'divider',
        bgcolor: filled ? `${color}.main` : 'background.paper',
        color: filled ? `${color}.contrastText` : 'text.primary',
        borderRadius: 999,
        py: 0.375,
        pl: 0.5,
        pr: 1,
        outline: 'none',
        transition: reduced ? 'none' : 'border-color 160ms ease, background-color 160ms ease',
        '&:hover': {
          bgcolor: filled ? `${color}.dark` : 'action.hover',
        },
        '&:focus-visible': { outline: '2px solid', outlineColor: `${color}.main`, outlineOffset: 2 },
      }}
    >
      <Box
        data-testid={`journey-station-marker-${station.n}`}
        data-marker={marker}
        aria-hidden="true"
        sx={{
          width: 20,
          height: 20,
          borderRadius: '50%',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: filled ? 'rgba(255,255,255,0.22)' : 'action.hover',
          color: filled ? `${color}.contrastText` : 'text.secondary',
        }}
      >
        {marker === 'done' ? (
          <CheckRoundedIcon
            data-testid={`journey-station-done-${station.n}`}
            sx={{ fontSize: 15 }}
          />
        ) : marker === 'current' ? (
          <Icon sx={{ fontSize: 14 }} />
        ) : (
          <Typography sx={{ ...FONT.caption, fontWeight: 700, lineHeight: 1 }}>
            {station.n}
          </Typography>
        )}
      </Box>

      <Typography noWrap sx={{ ...FONT.chip, fontWeight: 600 }}>
        {station.title}
      </Typography>

      {active && (
        <Typography
          data-testid={`journey-station-here-${station.n}`}
          component="span"
          sx={{
            ...FONT.caption,
            fontWeight: 700,
            borderRadius: 999,
            px: 0.625,
            py: 0.0625,
            bgcolor: 'rgba(255,255,255,0.24)',
          }}
        >
          {t('rail.here')}
        </Typography>
      )}
    </Box>
  );
});

StationCard.propTypes = {
  station: PropTypes.shape({
    n: PropTypes.number.isRequired,
    title: PropTypes.string.isRequired,
    state: PropTypes.string.isRequired,
    done: PropTypes.bool,
    pending: PropTypes.bool,
    key: PropTypes.string,
  }).isRequired,
  active: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
};

export default StationCard;
