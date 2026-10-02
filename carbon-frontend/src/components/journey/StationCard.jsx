import React, { forwardRef } from 'react';
import PropTypes from 'prop-types';
import { Box, CircularProgress, Typography } from '@mui/material';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import { stationProgress } from './journeyProgress';
import useReducedMotion from './useReducedMotion';

/**
 * One journey station: a compact, always-clickable enterprise tile.
 *
 * It shows the station title, a completion ring and an "n of m" count, plus a
 * subtle sense of place — "Here" on the current station and a check on a station
 * that is genuinely done. It never shows an available/locked label and never
 * shows a pack id pill: there is no lock state in the product.
 */
const StationCard = forwardRef(function StationCard({ station, active, onSelect }, ref) {
  const { t } = useTranslation('journey');
  const reduced = useReducedMotion();
  const { done, total, pct } = stationProgress(station);

  return (
    <Box
      ref={ref}
      role="tab"
      id={`journey-station-tab-${station.n}`}
      aria-controls={`journey-station-panel-${station.n}`}
      aria-selected={active}
      aria-current={station.state === 'current' ? 'step' : undefined}
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
        flex: '0 0 auto',
        width: { xs: 148, md: 152 },
        minWidth: 0,
        cursor: 'pointer',
        textAlign: 'start',
        border: '1px solid',
        borderColor: active ? 'primary.main' : 'divider',
        bgcolor: active ? 'action.selected' : 'background.paper',
        borderRadius: 1,
        p: 1,
        outline: 'none',
        transition: reduced ? 'none' : 'border-color 160ms ease, background-color 160ms ease',
        '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 1 },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <CircularProgress
          variant="determinate"
          value={pct}
          size={18}
          thickness={5}
          color={station.done ? 'success' : 'primary'}
          aria-hidden="true"
        />
        <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>
          {t('rail.progress', { done, total })}
        </Typography>
        {station.done && (
          <TaskAltIcon
            data-testid={`journey-station-done-${station.n}`}
            sx={{ fontSize: 14, color: 'success.main', marginInlineStart: 'auto' }}
            aria-hidden="true"
          />
        )}
      </Box>
      <Typography
        sx={{
          ...FONT.cardTitle,
          mt: 0.5,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {station.title}
      </Typography>
      {station.state === 'current' && (
        <Typography
          data-testid={`journey-station-here-${station.n}`}
          sx={{ ...FONT.caption, color: 'primary.main', mt: 0.25 }}
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
    outcomesTotal: PropTypes.number.isRequired,
    outcomesProven: PropTypes.number.isRequired,
    lessonsTotal: PropTypes.number.isRequired,
    lessonsDone: PropTypes.number.isRequired,
  }).isRequired,
  active: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
};

export default StationCard;
