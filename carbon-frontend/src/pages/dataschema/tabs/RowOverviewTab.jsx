// File: src/pages/dataschema/tabs/RowOverviewTab.jsx
// Read-only overview of row data with metadata, calculation summary, and context.
// Now receives tableInfo, moduleInfo, calculations from parent for richer display.

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Stack,
  Chip,
} from '@mui/material';

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

export default function RowOverviewTab({ rowData, _tableInfo, _moduleInfo, calculations }) {

  // ── Extract metadata and field data ────────────────────────────────
  const metadataFields = ['created_at', 'updated_at', 'created_by', 'updated_by'];
  const nonDataFields = ['id', 'data_table', 'is_archived', 'version', 'values', ...metadataFields];
  const metadata = {};
  const fieldData = {};

  Object.entries(rowData).forEach(([key, value]) => {
    if (metadataFields.includes(key)) metadata[key] = value;
  });

  if (rowData.values && typeof rowData.values === 'object') {
    Object.entries(rowData.values).forEach(([key, value]) => { fieldData[key] = value; });
  }

  if (Object.keys(fieldData).length === 0) {
    Object.entries(rowData).forEach(([key, value]) => {
      if (!nonDataFields.includes(key)) fieldData[key] = value;
    });
  }

  // ── Calculations summary ───────────────────────────────────────────
  const totalCo2e = (calculations || []).reduce((sum, c) => sum + (Number(c.co2e_kg) || 0), 0);
  const calcCount = (calculations || []).length;

  return (
    <Box sx={{ maxWidth: '800px' }}>


      {/* ── Calculation summary card ───────────────────────────────── */}
      {calcCount > 0 && (
        <Card sx={{ mb: 3, borderLeft: '4px solid', borderColor: 'warning.main' }}>
          <CardContent sx={{ py: 1.5 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>Emission Calculations</Typography>
            {(calculations || []).map((c, i) => (
              <Box key={c.id || i} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5, borderBottom: i < calcCount - 1 ? '1px solid' : 'none', borderColor: 'divider' }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 500 }}>
                    {c.emission_factor__name || c.emission_factor_name || `Factor #${c.emission_factor_id}`}
                  </Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                    {c.calculation_rule__name || c.calculation_rule_name || '—'} · {c.category || '—'} · {fmtDate(c.calculated_at)}
                  </Typography>
                </Box>
                <Box sx={{ textAlign: 'right', ml: 2 }}>
                  <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'warning.main' }}>
                    {(Number(c.co2e_kg) / 1000).toFixed(3)} tCO₂e
                  </Typography>
                  <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>
                    {c.co2e_kg != null ? `${Number(c.co2e_kg).toFixed(1)} kg` : '—'} · Scope {c.scope || '—'}
                  </Typography>
                </Box>
              </Box>
            ))}
            {calcCount > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>Total</Typography>
                <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'warning.main' }}>
                  {(totalCo2e / 1000).toFixed(3)} tCO₂e
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>
      )}


      {/* ── Data fields ────────────────────────────────────────────── */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>Row Data</Typography>
          <Grid container spacing={2}>
            {Object.entries(fieldData).map(([key, value]) => (
              <Grid size={{ xs: 12, sm: 6 }} key={key}>
                <Box>
                  <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, color: 'text.secondary', textTransform: 'capitalize', mb: 0.5 }}>
                    {key.replace(/_/g, ' ')}
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.primary', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: '0.9rem' }}>
                    {value !== null && value !== undefined ? String(value) : '(empty)'}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      {/* ── Metadata ───────────────────────────────────────────────── */}
      {Object.keys(metadata).length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>Metadata</Typography>
            <Stack spacing={1.5}>
              {metadata.created_at && (
                <Box>
                  <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, color: '#666', mb: 0.3 }}>Created</Typography>
                  <Typography variant="body2">{new Date(metadata.created_at).toLocaleString()}</Typography>
                </Box>
              )}
              {metadata.updated_at && (
                <Box>
                  <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, color: '#666', mb: 0.3 }}>Updated</Typography>
                  <Typography variant="body2">{new Date(metadata.updated_at).toLocaleString()}</Typography>
                </Box>
              )}
            </Stack>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
