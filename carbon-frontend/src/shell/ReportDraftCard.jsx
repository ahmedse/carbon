// src/shell/ReportDraftCard.jsx
// Presentational card that renders the result of a "Draft Report" run
// (conversation type `report_draft`). It shows the title, period range,
// narrative summary, per-section content with caveats, and the generated-at
// caption, plus three actions: Save as Artifact, Export .md, and Re-draft.
//
// The `metadata` prop mirrors the backend Phase 10-A contract:
//   {
//     type: 'report',
//     title, summary, report_type,
//     period_start, period_end,
//     generated_at,
//     sections: [ { title, content, sql, data, caveat } ],
//   }
//
// NOTE: this is a DRAFT (KG context + live host table volumes + a narrative).
// It is NOT the fully-calculated GHG report; render only what the backend
// returns and never invent emissions figures client-side.

import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Divider,
  Stack,
  Typography,
} from '@mui/material';
import SaveAltIcon from '@mui/icons-material/SaveAlt';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import { formatDisplayDateTime } from '../utils/dateUtils';

export default function ReportDraftCard({
  metadata,
  onSaveArtifact,
  onExport,
  onRedraft,
}) {
  const title = metadata?.title || 'Report';
  const summary = metadata?.summary || '';
  const periodStart = metadata?.period_start || '';
  const periodEnd = metadata?.period_end || '';
  const generatedAt = metadata?.generated_at || null;
  const sections = Array.isArray(metadata?.sections) ? metadata.sections : [];

  const periodLabel =
    periodStart || periodEnd
      ? `${periodStart}${periodEnd ? ` → ${periodEnd}` : ''}`
      : '';

  return (
    <Stack spacing={1.5} sx={{ my: 1 }}>
      {/* Header */}
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
        <Typography variant="subtitle2" component="span">
          {title}
        </Typography>
        <Chip size="small" variant="outlined" color="primary" label="Draft" />
      </Stack>

      {/* Period */}
      {periodLabel && (
        <Typography variant="caption" color="text.secondary">
          {periodLabel}
        </Typography>
      )}

      {/* Summary */}
      {summary && (
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
          {summary}
        </Typography>
      )}

      {/* Sections */}
      {sections.length > 0 && (
        <Stack spacing={1.5}>
          {sections.map((section, i) => (
            <Box key={section.title || i}>
              {section.title && (
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                  {section.title}
                </Typography>
              )}
              {section.content && (
                <Typography
                  variant="body2"
                  sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}
                >
                  {section.content}
                </Typography>
              )}
              {section.caveat && (
                <Typography
                  variant="caption"
                  color="warning.main"
                  sx={{ display: 'block', mt: 0.5, fontStyle: 'italic' }}
                >
                  {section.caveat}
                </Typography>
              )}
              {i < sections.length - 1 && <Divider sx={{ mt: 1.5 }} />}
            </Box>
          ))}
        </Stack>
      )}

      {/* Generated-at caption */}
      {generatedAt && (
        <Typography variant="caption" color="text.secondary">
          Generated {formatDisplayDateTime(new Date(generatedAt))}
        </Typography>
      )}

      {/* Actions */}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button
          size="small"
          variant="outlined"
          startIcon={<SaveAltIcon fontSize="small" />}
          onClick={() => onSaveArtifact?.(metadata)}
        >
          Save as Artifact
        </Button>
        <Button
          size="small"
          variant="outlined"
          startIcon={<DownloadIcon fontSize="small" />}
          onClick={() => onExport?.(metadata)}
        >
          Export .md
        </Button>
        <Button
          size="small"
          variant="outlined"
          startIcon={<RefreshIcon fontSize="small" />}
          onClick={() => onRedraft?.()}
        >
          Re-draft
        </Button>
      </Stack>
    </Stack>
  );
}

ReportDraftCard.propTypes = {
  metadata: PropTypes.shape({
    type: PropTypes.string,
    title: PropTypes.string,
    summary: PropTypes.string,
    report_type: PropTypes.string,
    period_start: PropTypes.string,
    period_end: PropTypes.string,
    generated_at: PropTypes.string,
    sections: PropTypes.arrayOf(PropTypes.object),
  }),
  onSaveArtifact: PropTypes.func,
  onExport: PropTypes.func,
  onRedraft: PropTypes.func,
};
