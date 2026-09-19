// Comprehensive LCT SD/SG report — segment × codes × evidence × wave summary.
// Compact dense tables (ADR compact UI); optional HITL edit actions via props.

import React, { useMemo, useState } from 'react';
import {
  Box, Button, Chip, Collapse, IconButton, LinearProgress, Stack,
  Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

const SG_ORDER = ['SG+', 'SG-'];
const SD_ORDER = ['SD-', 'SD+'];

function codeFor(seg, dimension) {
  const codes = seg?.codes || [];
  return codes.find((c) => c.dimension === dimension) || null;
}

function countBy(values) {
  const out = {};
  for (const v of values) {
    if (!v) continue;
    out[v] = (out[v] || 0) + 1;
  }
  return out;
}

function DistributionChips({ order, counts, color }) {
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
      {order.map((k) => (
        <Chip
          key={k}
          size="small"
          color={color}
          variant={counts[k] ? 'filled' : 'outlined'}
          label={`${k}: ${counts[k] || 0}`}
        />
      ))}
    </Stack>
  );
}

function EvidenceBlock({ evidence }) {
  if (!evidence || typeof evidence !== 'object') return null;
  const keys = Object.keys(evidence);
  if (!keys.length) return null;
  const justification = evidence.justification || evidence.rationale || evidence.why;
  const gloss = evidence.gloss;
  const snippet = evidence.excerpt || evidence.span || evidence.quote || evidence.text;
  const cues = evidence.cues || evidence.features || evidence.signals;
  const method = evidence.method;
  const anchorId = evidence.anchor_id;
  return (
    <Box sx={{ mt: 0.5 }} data-testid="lct-evidence">
      {justification && (
        <Typography variant="body2" sx={{ mb: 0.5 }}>
          {justification}
        </Typography>
      )}
      {gloss && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
          {gloss}
        </Typography>
      )}
      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: 0.25 }}>
        {method && <Chip size="small" variant="outlined" label={method} />}
        {anchorId && <Chip size="small" variant="outlined" label={`anchor ${anchorId}`} />}
        {evidence.overlap != null && (
          <Chip size="small" variant="outlined" label={`overlap ${evidence.overlap}`} />
        )}
      </Stack>
      {snippet && (
        <Typography variant="caption" color="text.secondary" component="p" sx={{ m: 0 }}>
          Span: “{String(snippet).slice(0, 220)}
          {String(snippet).length > 220 ? '…' : ''}”
        </Typography>
      )}
      {Array.isArray(cues) && cues.length > 0 && (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.25 }}>
          {cues.slice(0, 8).map((c) => (
            <Chip key={String(c)} size="small" color="default" variant="outlined" label={String(c)} />
          ))}
        </Stack>
      )}
      {!justification && !snippet && !Array.isArray(cues) && (
        <Typography variant="caption" color="text.secondary" component="pre" sx={{ m: 0, whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(evidence).slice(0, 180)}
          {JSON.stringify(evidence).length > 180 ? '…' : ''}
        </Typography>
      )}
    </Box>
  );
}

function SegmentRow({
  seg, expanded, onToggle, onEditSg, onEditSd, editable,
}) {
  const sg = codeFor(seg, 'semantic_gravity');
  const sd = codeFor(seg, 'semantic_density');
  const text = seg.text || '';
  const preview = text.length > 220 ? `${text.slice(0, 220)}…` : text;

  return (
    <>
      <TableRow hover selected={expanded}>
        <TableCell>
          <IconButton
            size="small"
            aria-label={expanded ? `Collapse segment ${seg.ordinal}` : `Expand segment ${seg.ordinal}`}
            aria-expanded={expanded}
            onClick={onToggle}
          >
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </TableCell>
        <TableCell>{seg.ordinal ?? '—'}</TableCell>
        <TableCell>
          <Typography variant="caption" sx={{ fontVariantNumeric: 'tabular-nums' }}>
            {seg.start_word != null && seg.end_word != null
              ? `${seg.start_word}–${seg.end_word}`
              : '—'}
          </Typography>
        </TableCell>
        <TableCell>
          <Chip size="small" label={seg.stage_guess || '—'} variant="outlined" />
        </TableCell>
        <TableCell>
          <Stack spacing={0.25}>
            <Chip
              size="small"
              color="primary"
              variant={sg?.source === 'expert' ? 'filled' : 'outlined'}
              label={sg?.value || '—'}
              title={sg?.numeric != null ? `numeric ${sg.numeric}` : undefined}
            />
            {sg?.source && (
              <Typography variant="caption" color="text.secondary">{sg.source}</Typography>
            )}
          </Stack>
        </TableCell>
        <TableCell>
          <Stack spacing={0.25}>
            <Chip
              size="small"
              color="secondary"
              variant={sd?.source === 'expert' ? 'filled' : 'outlined'}
              label={sd?.value || '—'}
            />
            {sd?.source && (
              <Typography variant="caption" color="text.secondary">{sd.source}</Typography>
            )}
          </Stack>
        </TableCell>
        <TableCell>
          <Stack spacing={0.5} sx={{ minWidth: 88 }}>
            <Tooltip title={`SG confidence ${sg?.confidence ?? '—'}`}>
              <Box>
                <Typography variant="caption">SG {sg?.confidence != null ? Number(sg.confidence).toFixed(2) : '—'}</Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.round(Math.min(1, Math.max(0, Number(sg?.confidence) || 0)) * 100)}
                  sx={{ height: 4, borderRadius: 1 }}
                />
              </Box>
            </Tooltip>
            <Tooltip title={`SD confidence ${sd?.confidence ?? '—'}`}>
              <Box>
                <Typography variant="caption">SD {sd?.confidence != null ? Number(sd.confidence).toFixed(2) : '—'}</Typography>
                <LinearProgress
                  color="secondary"
                  variant="determinate"
                  value={Math.round(Math.min(1, Math.max(0, Number(sd?.confidence) || 0)) * 100)}
                  sx={{ height: 4, borderRadius: 1 }}
                />
              </Box>
            </Tooltip>
          </Stack>
        </TableCell>
        <TableCell sx={{ maxWidth: 360 }}>
          <Typography variant="body2">{preview || '—'}</Typography>
        </TableCell>
        {editable && (
          <TableCell>
            <Stack direction="row" spacing={0.5}>
              <Button size="small" onClick={() => onEditSg?.(seg)}>Edit SG</Button>
              <Button size="small" onClick={() => onEditSd?.(seg)}>Edit SD</Button>
            </Stack>
          </TableCell>
        )}
      </TableRow>
      <TableRow>
        <TableCell
          colSpan={editable ? 9 : 8}
          sx={{ py: 0, borderBottom: expanded ? undefined : 'none' }}
        >
          <Collapse in={expanded} timeout="auto" unmountOnExit>
            <Box sx={{ py: 1.25, px: 0.5 }}>
              <Typography variant="caption" color="text.secondary">Full segment text</Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mb: 1 }}>
                {text || '—'}
              </Typography>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">Semantic Gravity — analysis</Typography>
                  <Typography variant="body2">
                    {sg?.value || '—'}
                    {sg?.numeric != null ? ` (ordinal ${sg.numeric})` : ''}
                    {sg?.confidence != null ? ` · conf ${Number(sg.confidence).toFixed(2)}` : ''}
                    {sg?.source ? ` · ${sg.source}` : ''}
                  </Typography>
                  <EvidenceBlock evidence={sg?.evidence} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">Semantic Density — analysis</Typography>
                  <Typography variant="body2">
                    {sd?.value || '—'}
                    {sd?.confidence != null ? ` · conf ${Number(sd.confidence).toFixed(2)}` : ''}
                    {sd?.source ? ` · ${sd.source}` : ''}
                  </Typography>
                  <EvidenceBlock evidence={sd?.evidence} />
                </Box>
              </Stack>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

export default function LctCodesTable({
  segments = [],
  wave = null,
  onEditSg = null,
  onEditSd = null,
  onEditSegmentation = null,
  sgLevels = SG_ORDER,
  sdLevels = SD_ORDER,
}) {
  const [expandedId, setExpandedId] = useState(null);
  const editable = Boolean(onEditSg || onEditSd);
  const sgOrder = Array.isArray(sgLevels) && sgLevels.length ? sgLevels : SG_ORDER;
  const sdOrder = Array.isArray(sdLevels) && sdLevels.length ? sdLevels : SD_ORDER;

  const summary = useMemo(() => {
    const sgValues = segments.map((s) => codeFor(s, 'semantic_gravity')?.value);
    const sdValues = segments.map((s) => codeFor(s, 'semantic_density')?.value);
    const stages = segments.map((s) => s.stage_guess).filter(Boolean);
    const confs = segments
      .flatMap((s) => [
        codeFor(s, 'semantic_gravity')?.confidence,
        codeFor(s, 'semantic_density')?.confidence,
      ])
      .filter((v) => v != null)
      .map(Number);
    const meanConf = confs.length
      ? confs.reduce((a, b) => a + b, 0) / confs.length
      : null;
    const expertCount = segments.reduce((n, s) => {
      const sg = codeFor(s, 'semantic_gravity');
      const sd = codeFor(s, 'semantic_density');
      return n + (sg?.source === 'expert' ? 1 : 0) + (sd?.source === 'expert' ? 1 : 0);
    }, 0);
    return {
      sgCounts: countBy(sgValues),
      sdCounts: countBy(sdValues),
      stageCounts: countBy(stages),
      meanConf,
      expertCount,
      wordSpan: segments.length
        ? {
          start: Math.min(...segments.map((s) => s.start_word ?? 0)),
          end: Math.max(...segments.map((s) => s.end_word ?? 0)),
        }
        : null,
    };
  }, [segments]);

  if (!segments.length) {
    return (
      <Typography variant="caption" color="text.secondary">
        No LCT segments yet.
      </Typography>
    );
  }

  const metrics = wave?.metrics || {};

  return (
    <Box component="section" aria-labelledby="lct-report-heading">
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.75 }} flexWrap="wrap" useFlexGap>
        <Typography id="lct-report-heading" variant="subtitle2">
          LCT analysis — Semantic Gravity (SG±) &amp; Density (SD±)
        </Typography>
        {onEditSegmentation && (
          <Button size="small" variant="outlined" onClick={onEditSegmentation}>
            Resegment
          </Button>
        )}
      </Stack>

      <Stack spacing={1} sx={{ mb: 1.5 }} aria-label="LCT report summary">
        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
          <Chip size="small" label={`${segments.length} segments`} />
          {summary.wordSpan && (
            <Chip size="small" variant="outlined" label={`words ${summary.wordSpan.start}–${summary.wordSpan.end}`} />
          )}
          {summary.meanConf != null && (
            <Chip size="small" variant="outlined" label={`mean conf ${summary.meanConf.toFixed(2)}`} />
          )}
          {metrics.sg_range != null && (
            <Chip size="small" variant="outlined" label={`SG range ${metrics.sg_range}`} />
          )}
          {metrics.transitions != null && (
            <Chip size="small" variant="outlined" label={`${metrics.transitions} transitions`} />
          )}
          {summary.expertCount > 0 && (
            <Chip size="small" color="success" label={`${summary.expertCount} expert-coded`} />
          )}
        </Stack>

        <Box>
          <Typography variant="caption" color="text.secondary">SG distribution</Typography>
          <DistributionChips order={sgOrder} counts={summary.sgCounts} color="primary" />
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">SD distribution</Typography>
          <DistributionChips order={sdOrder} counts={summary.sdCounts} color="secondary" />
        </Box>
        {Object.keys(summary.stageCounts).length > 0 && (
          <Box>
            <Typography variant="caption" color="text.secondary">Reflective stages</Typography>
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {Object.entries(summary.stageCounts).map(([stage, n]) => (
                <Chip key={stage} size="small" variant="outlined" label={`${stage}: ${n}`} />
              ))}
            </Stack>
          </Box>
        )}
        {Array.isArray(metrics.stages_present) && metrics.stages_present.length > 0 && (
          <Typography variant="caption" color="text.secondary">
            Wave stages present: {metrics.stages_present.join(' → ')}
          </Typography>
        )}
      </Stack>

      <Table size="small" aria-label="LCT segment codes SG and SD">
        <TableHead>
          <TableRow>
            <TableCell scope="col" padding="checkbox" />
            <TableCell scope="col">#</TableCell>
            <TableCell scope="col">Words</TableCell>
            <TableCell scope="col">Stage</TableCell>
            <TableCell scope="col">SG</TableCell>
            <TableCell scope="col">SD</TableCell>
            <TableCell scope="col">Confidence</TableCell>
            <TableCell scope="col">Excerpt</TableCell>
            {editable && <TableCell scope="col">HITL</TableCell>}
          </TableRow>
        </TableHead>
        <TableBody>
          {segments.map((s) => {
            const key = s.id || s.ordinal;
            return (
              <SegmentRow
                key={key}
                seg={s}
                expanded={expandedId === key}
                onToggle={() => setExpandedId((cur) => (cur === key ? null : key))}
                onEditSg={onEditSg}
                onEditSd={onEditSd}
                editable={editable}
              />
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
}
