import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Typography } from '@mui/material';
import {
  ASPECT_ORDER,
  LADDER_LEVELS,
  aspectLabel,
  levelName,
  stateColor,
} from './excellenceUi';

const STATE_WORD = {
  passed: 'passed',
  failed: 'failed',
  stale: 'stale',
  unknown: 'unknown',
  unmeasured: 'unmeasured',
  open: 'open',
  exempt: 'exempt',
  'n/a': 'n/a',
};

export default function ExcellenceCellMap({ cells, level, selected, onSelect }) {
  const dims = ASPECT_ORDER;
  const at = (dimension, lv) => cells.find((c) => c.dimension === dimension && c.level === lv);

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'minmax(7rem, 10rem) repeat(6, minmax(4rem, 1fr))',
        gap: 0.5,
        alignItems: 'center',
        width: '100%',
      }}
    >
      <Box />
      {LADDER_LEVELS.map((lv) => (
        <Typography
          key={lv}
          variant="caption"
          align="center"
          color={lv === level + 1 ? 'primary' : 'text.secondary'}
        >
          {levelName(lv)}
        </Typography>
      ))}
      {dims.map((dimension) => (
        <React.Fragment key={dimension}>
          <Typography variant="body2">{aspectLabel(dimension)}</Typography>
          {LADDER_LEVELS.map((lv) => {
            const cell = at(dimension, lv);
            const state = cell?.state || 'open';
            const word = STATE_WORD[state] || state;
            const on = selected && selected.dimension === dimension && selected.level === lv;
            const lvName = levelName(lv);
            return (
              <Button
                key={`${dimension}-${lv}`}
                size="small"
                variant="outlined"
                aria-label={`${aspectLabel(dimension)} ${lvName} ${state}`}
                aria-pressed={on}
                onClick={() => cell && onSelect(cell)}
                sx={{
                  minWidth: 0,
                  p: 0.5,
                  borderColor: on ? 'primary.main' : 'divider',
                  borderWidth: on ? 2 : 1,
                }}
              >
                <Chip size="small" label={word} color={stateColor(state)} />
              </Button>
            );
          })}
        </React.Fragment>
      ))}
    </Box>
  );
}

ExcellenceCellMap.propTypes = {
  cells: PropTypes.array.isRequired,
  level: PropTypes.number,
  selected: PropTypes.object,
  onSelect: PropTypes.func.isRequired,
};
