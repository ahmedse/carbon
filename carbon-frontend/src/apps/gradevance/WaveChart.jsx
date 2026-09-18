// Compact SG wave chart — word-offset X, ordinal SG numeric Y (4=SG-- … 1=SG++).

import React from 'react';
import { Box, Typography } from '@mui/material';

const SG_LABEL = { 4: 'SG--', 3: 'SG-', 2: 'SG+', 1: 'SG++' };

export default function WaveChart({ points = [], height = 120 }) {
  if (!points.length) {
    return <Typography variant="caption" color="text.secondary">No wave points</Typography>;
  }
  const xs = points.map((p) => p.word_offset ?? 0);
  const ys = points.map((p) => p.sg_numeric ?? 3);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs, minX + 1);
  const pad = 8;
  const w = 320;
  const h = height;
  const toX = (x) => pad + ((x - minX) / (maxX - minX)) * (w - pad * 2);
  // Y: sg_numeric 4 at top (abstract), 1 at bottom (concrete) — matches NAA gold charts.
  const toY = (y) => pad + ((4 - y) / 3) * (h - pad * 2);
  const d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(p.word_offset)} ${toY(p.sg_numeric ?? 3)}`)
    .join(' ');

  const summary = points
    .map((p, i) => `S${i + 1} word ${p.word_offset ?? 0}: ${SG_LABEL[p.sg_numeric] || p.sg || p.sg_numeric}`)
    .join('; ');

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <svg width={w} height={h} role="img" aria-label={`Semantic gravity wave. ${summary}`}>
        <title>Semantic gravity wave</title>
        <desc>{summary}</desc>
        {[1, 2, 3, 4].map((lvl) => (
          <line
            key={lvl}
            x1={pad}
            x2={w - pad}
            y1={toY(lvl)}
            y2={toY(lvl)}
            stroke="#e5e7eb"
            strokeWidth={1}
          />
        ))}
        <path d={d} fill="none" stroke="#1d4ed8" strokeWidth={2} />
        {points.map((p, i) => (
          <circle key={i} cx={toX(p.word_offset)} cy={toY(p.sg_numeric ?? 3)} r={3.5} fill="#0f766e" />
        ))}
        <text x={pad} y={h - 2} fontSize={9} fill="#6b7280">word →</text>
        <text x={2} y={pad + 4} fontSize={9} fill="#6b7280">SG--</text>
        <text x={2} y={h - pad} fontSize={9} fill="#6b7280">SG++</text>
      </svg>
      <Typography
        component="ol"
        variant="caption"
        color="text.secondary"
        sx={{
          position: 'absolute',
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: 'hidden',
          clip: 'rect(0,0,0,0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
        aria-label="Semantic gravity wave data points"
      >
        {points.map((p, i) => (
          <li key={i}>
            Segment {i + 1}, word offset {p.word_offset ?? 0}, gravity {SG_LABEL[p.sg_numeric] || p.sg_numeric}
          </li>
        ))}
      </Typography>
    </Box>
  );
}
