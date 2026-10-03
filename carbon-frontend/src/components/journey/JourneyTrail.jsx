import React, { useRef } from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import StationCard from './StationCard';

/**
 * The Carbon Trail: the pack's stations, read as camps on ONE path.
 *
 * This is the same navigation contract the station rail always had — a
 * `tablist` of always-clickable waypoints, arrow keys to walk the path, one
 * panel below — but every camp now shows its name, wrapped so the whole trail
 * reads at a glance without a horizontal scroll. The trail is chrome only:
 * every state comes from the engine's station state, and there is no lock
 * state anywhere.
 *
 * `StationRail` is kept as an alias so every existing surface and test keeps
 * the same import.
 */
export default function JourneyTrail({ stations, selectedN, onSelect }) {
  const { t } = useTranslation('journey');
  const refs = useRef({});
  const list = Array.isArray(stations) ? stations : [];
  const currentIndex = Math.max(0, list.findIndex((station) => station.n === selectedN));

  if (list.length === 0) return null;

  const focusAt = (index) => {
    const target = list[index];
    if (!target) return;
    onSelect(target.n);
    window.requestAnimationFrame(() => refs.current[target.n]?.focus());
  };

  const onKeyDown = (event) => {
    const focused = list.findIndex((station) => refs.current[station.n] === document.activeElement);
    const index = focused >= 0 ? focused : currentIndex;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      focusAt((index + 1) % list.length);
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      focusAt((index - 1 + list.length) % list.length);
    } else if (event.key === 'Home') {
      event.preventDefault();
      focusAt(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      focusAt(list.length - 1);
    }
  };

  return (
    <Box data-testid="journey-trail" sx={{ mb: 2 }}>
      <Typography sx={{ ...FONT.sectionTitle, mb: 0.75 }} color="text.secondary">
        {t('trail.label')}
      </Typography>
      <Box
        role="tablist"
        aria-label={t('rail.label')}
        aria-orientation="horizontal"
        data-testid="journey-rail"
        onKeyDown={onKeyDown}
        sx={{
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          gap: 0.75,
          alignItems: 'center',
        }}
      >
        {list.map((station) => (
          <StationCard
            key={station.n}
            station={station}
            active={station.n === selectedN}
            onSelect={onSelect}
            ref={(node) => { refs.current[station.n] = node; }}
          />
        ))}
      </Box>
    </Box>
  );
}

JourneyTrail.propTypes = {
  stations: PropTypes.arrayOf(PropTypes.shape({})).isRequired,
  selectedN: PropTypes.number,
  onSelect: PropTypes.func.isRequired,
};

JourneyTrail.defaultProps = { selectedN: undefined };
