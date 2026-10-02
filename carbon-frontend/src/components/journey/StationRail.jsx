import React, { useRef } from 'react';
import PropTypes from 'prop-types';
import { Box } from '@mui/material';
import { useTranslation } from 'react-i18next';

import StationCard from './StationCard';

/**
 * The station rail. A horizontally scrollable list of compact station tiles on
 * every breakpoint.
 *
 * Why scroll horizontally rather than stack vertically on mobile: the stations
 * are an ordered spine, so keeping them on one axis preserves the journey
 * reading order; the detail panel stays directly below without a long scroll
 * past seven stacked cards. Each tile is always clickable — no lock state.
 */
export default function StationRail({ stations, selectedN, onSelect }) {
  const { t } = useTranslation('journey');
  const refs = useRef({});
  const currentIndex = Math.max(0, stations.findIndex((station) => station.n === selectedN));

  const focusAt = (index) => {
    const target = stations[index];
    if (!target) return;
    onSelect(target.n);
    window.requestAnimationFrame(() => refs.current[target.n]?.focus());
  };

  const onKeyDown = (event) => {
    const focused = stations.findIndex((station) => refs.current[station.n] === document.activeElement);
    const index = focused >= 0 ? focused : currentIndex;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      focusAt((index + 1) % stations.length);
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      focusAt((index - 1 + stations.length) % stations.length);
    } else if (event.key === 'Home') {
      event.preventDefault();
      focusAt(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      focusAt(stations.length - 1);
    }
  };

  return (
    <Box
      role="tablist"
      aria-label={t('rail.label')}
      aria-orientation="horizontal"
      data-testid="journey-rail"
      onKeyDown={onKeyDown}
      sx={{
        display: 'flex',
        flexDirection: 'row',
        gap: 1,
        alignItems: 'stretch',
        overflowX: 'auto',
        overflowY: 'hidden',
        pb: 0.5,
        scrollbarWidth: 'thin',
      }}
    >
      {stations.map((station) => (
        <StationCard
          key={station.n}
          station={station}
          active={station.n === selectedN}
          onSelect={onSelect}
          ref={(node) => { refs.current[station.n] = node; }}
        />
      ))}
    </Box>
  );
}

StationRail.propTypes = {
  stations: PropTypes.arrayOf(PropTypes.shape({})).isRequired,
  selectedN: PropTypes.number,
  onSelect: PropTypes.func.isRequired,
};

StationRail.defaultProps = { selectedN: undefined };
