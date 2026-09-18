// Compact LCT SD/SG report — segment × codes (ADR compact UI: dense table).

import React from 'react';
import {
  Chip, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';

function codeFor(seg, dimension) {
  const codes = seg?.codes || [];
  return codes.find((c) => c.dimension === dimension) || null;
}

export default function LctCodesTable({ segments = [], wave = null }) {
  if (!segments.length) {
    return (
      <Typography variant="caption" color="text.secondary">
        No LCT segments yet.
      </Typography>
    );
  }

  const metrics = wave?.metrics || {};

  return (
    <Paper variant="outlined" sx={{ mt: 1.5 }} component="section" aria-labelledby="lct-report-heading">
      <Typography id="lct-report-heading" variant="subtitle2" sx={{ px: 1.5, pt: 1.25, pb: 0.5 }}>
        LCT analysis — Semantic Gravity (SG) &amp; Density (SD)
      </Typography>
      {(metrics.sg_range != null || metrics.transitions != null) && (
        <Typography variant="caption" color="text.secondary" sx={{ px: 1.5, display: 'block', mb: 0.75 }}>
          Wave range={metrics.sg_range ?? '—'} · transitions={metrics.transitions ?? '—'}
          {metrics.stages_present?.length
            ? ` · stages=${metrics.stages_present.join(', ')}`
            : ''}
        </Typography>
      )}
      <Table size="small" aria-label="LCT segment codes SG and SD">
        <TableHead>
          <TableRow>
            <TableCell scope="col">#</TableCell>
            <TableCell scope="col">Stage</TableCell>
            <TableCell scope="col">SG</TableCell>
            <TableCell scope="col">SD</TableCell>
            <TableCell scope="col">Conf.</TableCell>
            <TableCell scope="col">Excerpt</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {segments.map((s) => {
            const sg = codeFor(s, 'semantic_gravity');
            const sd = codeFor(s, 'semantic_density');
            const conf = [sg?.confidence, sd?.confidence]
              .filter((v) => v != null)
              .map((v) => Number(v).toFixed(2))
              .join(' / ') || '—';
            return (
              <TableRow key={s.id || s.ordinal} hover>
                <TableCell>{s.ordinal ?? '—'}</TableCell>
                <TableCell>
                  <Chip size="small" label={s.stage_guess || '—'} variant="outlined" />
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color="primary"
                    variant="outlined"
                    label={sg?.value || '—'}
                    title={sg?.numeric != null ? `numeric ${sg.numeric}` : undefined}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color="secondary"
                    variant="outlined"
                    label={sd?.value || '—'}
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="caption">{conf}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ maxWidth: 420 }}>
                    {(s.text || '').slice(0, 160)}
                    {(s.text || '').length > 160 ? '…' : ''}
                  </Typography>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Paper>
  );
}
