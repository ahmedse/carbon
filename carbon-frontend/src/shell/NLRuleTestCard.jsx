// src/shell/NLRuleTestCard.jsx
// Presentational card that renders the result of a live "NL rule test"
// (conversation type `nl_rule_test`). It shows the rule the AI inferred from
// natural language, a live pass-rate summary, the rows that would violate the
// rule, and a recommendation. When Execute Mode is on, the user may tune the
// numeric threshold (re-scored locally against the sample rows) and save the
// rule to the DQ catalog.
//
// The `metadata` prop mirrors the backend Phase 8-A contract:
//   {
//     type: 'nl_rule_test',
//     rule_preview: { type, params, severity, confidence, field, rule_text? },
//     test_summary:  { total_rows, applicable_rows, passed, failed, pass_rate },
//     violations:    [ { row, value } ],
//     rows:          [ { actual, expected } ],   // optional, for local re-scoring
//     recommendation: string,
//   }

import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  LinearProgress,
  Slider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import BoltIcon from '@mui/icons-material/Bolt';

const SEVERITY_LABELS = {
  info: 'Info',
  warn: 'Warning',
  error: 'Error',
};

const TYPE_LABELS = {
  threshold: 'Threshold',
  range: 'Range',
  not_null: 'Not null',
  unique: 'Unique',
  allowed_values: 'Allowed values',
  regex: 'Regex',
  reference_integrity: 'Reference integrity',
  nl_check: 'NL check',
  anomaly_detect: 'Anomaly detection',
};

const OFF_TOOLTIP = 'Enable Execute Mode to save';

// Threshold rules carry a single numeric bound: { operator, value }.
function findThresholdParam(rulePreview) {
  const params = rulePreview?.params || {};
  if (params && typeof params.value === 'number') return params.value;
  return null;
}

// Range rules carry a [min, max] bound.
function findRangeBounds(rulePreview) {
  const params = rulePreview?.params || {};
  if (Array.isArray(params) && params.length >= 2) return params;
  if (params && Array.isArray(params.bounds) && params.bounds.length >= 2) {
    return params.bounds;
  }
  return null;
}

function formatRate(rate) {
  if (rate == null || Number.isNaN(Number(rate))) return null;
  const numeric = Number(rate);
  const pct = numeric <= 1 ? Math.round(numeric * 100) : Math.round(numeric);
  return Math.max(0, Math.min(100, pct));
}

/**
 * Local re-score of the sample rows against an adjusted threshold value.
 * Returns { passed, total, rate } or null when no numeric threshold is present.
 */
function rescoreThreshold(rows, operator, value) {
  if (!Array.isArray(rows) || rows.length === 0 || value == null) return null;
  const op = operator || 'gte';
  const passes = (actual) => {
    switch (op) {
      case 'gte':
        return actual >= value;
      case 'gt':
        return actual > value;
      case 'lte':
        return actual <= value;
      case 'lt':
        return actual < value;
      case 'eq':
        return actual === value;
      case 'neq':
        return actual !== value;
      default:
        return actual >= value;
    }
  };
  let passed = 0;
  rows.forEach((r) => {
    const actual = Number(r?.actual ?? r?.value);
    if (Number.isNaN(actual)) return;
    if (passes(actual)) passed += 1;
  });
  const total = rows.length;
  return { passed, total, rate: total ? passed / total : null };
}

function toColumns(rows) {
  if (!Array.isArray(rows) || rows.length === 0) return [];
  const keys = Object.keys(rows[0] || {});
  return keys.map((key) => ({ key, label: key }));
}

export default function NLRuleTestCard({
  metadata,
  executeMode = false,
  onSave,
  onRetest,
  onDiscard,
}) {
  const rulePreview = metadata?.rule_preview || {};
  const testSummary = useMemo(() => metadata?.test_summary || {}, [metadata]);
  const violations = useMemo(
    () => (Array.isArray(metadata?.violations) ? metadata.violations : []),
    [metadata],
  );
  const rows = useMemo(
    () => (Array.isArray(metadata?.rows) ? metadata.rows : []),
    [metadata],
  );

  const [threshold, setThreshold] = useState(null);
  const [rescaled, setRescaled] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const numericParam = findThresholdParam(rulePreview);
  const rangeBounds = findRangeBounds(rulePreview);
  const operator = rulePreview?.params?.operator || 'gte';

  // Default the slider to the inferred numeric value (or a range lower bound).
  useEffect(() => {
    setThreshold(numericParam ?? (rangeBounds ? Number(rangeBounds[0]) : null));
  }, [numericParam, rangeBounds]);

  // Debounced local re-score when the user drags the slider.
  useEffect(() => {
    if (threshold == null || numericParam == null || threshold === numericParam) {
      setRescaled(null);
      return undefined;
    }
    const handle = setTimeout(() => {
      setRescaled(rescoreThreshold(rows, operator, threshold));
    }, 200);
    return () => clearTimeout(handle);
  }, [threshold, numericParam, rows, operator]);

  const summary = useMemo(() => {
    if (rescaled) return rescaled;
    const applicable = testSummary.applicable_rows ?? testSummary.total_rows ?? 0;
    const passed = testSummary.passed ?? 0;
    const rate =
      testSummary.pass_rate ?? (applicable ? passed / applicable : null);
    return { passed, total: applicable, rate };
  }, [rescaled, testSummary]);

  const passRate = formatRate(summary.rate);

  const handleSave = async () => {
    if (!onSave || saving) return;
    setSaving(true);
    try {
      await onSave({
        type: rulePreview.type,
        params: { ...(rulePreview.params || {}) },
        severity: rulePreview.severity,
        field: rulePreview.field,
        name: rulePreview.rule_text || rulePreview.name || null,
      });
      setSaved(true);
    } catch {
      // Save failure is surfaced by the parent (notifyFromError); stay editable.
    } finally {
      setSaving(false);
    }
  };

  const title = rulePreview.rule_text || rulePreview.name || 'Rule test';
  const typeLabel = TYPE_LABELS[rulePreview.type] || rulePreview.type || 'Rule';
  const severityLabel =
    SEVERITY_LABELS[rulePreview.severity] || rulePreview.severity || 'Info';

  const saveButton = (
    <Button
      size="small"
      variant="contained"
      color="success"
      startIcon={<BoltIcon fontSize="small" />}
      disabled={!executeMode || saving}
      onClick={handleSave}
    >
      Save Rule
    </Button>
  );

  const sliderMax = Math.max(100, numericParam ? numericParam * 2 : 100);

  return (
    <Stack spacing={1.5} sx={{ my: 1 }}>
      <Stack
        direction="row"
        spacing={1}
        sx={{ alignItems: 'center', justifyContent: 'space-between' }}
      >
        <Typography variant="subtitle2" component="span">
          {title}
        </Typography>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Chip
            size="small"
            label={typeLabel}
            color="primary"
            variant="outlined"
          />
          <Chip size="small" label={`Severity: ${severityLabel}`} />
        </Stack>
      </Stack>

      <Typography variant="caption" color="text.secondary">
        Pass rate: {passRate != null ? `${passRate}%` : '—'} ·{' '}
        {summary.passed}/{summary.total} applicable rows passed
        {typeof testSummary.failed === 'number' && ` · ${testSummary.failed} violations`}
      </Typography>

      <LinearProgress
        variant="determinate"
        value={passRate ?? 0}
        color={passRate != null && passRate >= 80 ? 'success' : 'warning'}
        sx={{ height: 8, borderRadius: 1 }}
      />

      {numericParam != null && (
        <Box sx={{ px: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Threshold: {threshold}
          </Typography>
          <Slider
            size="small"
            min={0}
            max={sliderMax}
            step={1}
            value={threshold ?? numericParam}
            onChange={(_, value) => setThreshold(value)}
            aria-label="Adjust threshold"
            valueLabelDisplay="auto"
          />
        </Box>
      )}

      {violations.length > 0 && (
        <Box sx={{ maxHeight: 220, overflow: 'auto' }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                {toColumns(violations).map((col) => (
                  <TableCell
                    key={col.key}
                    sx={{ textTransform: 'capitalize', fontWeight: 600 }}
                  >
                    {col.label}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {violations.map((v, idx) => (
                <TableRow key={v.row ?? idx}>
                  {toColumns(violations).map((col) => (
                    <TableCell key={col.key}>
                      {String(v[col.key] ?? '—')}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}

      {metadata?.recommendation && (
        <Typography variant="body2" color="text.secondary">
          {metadata.recommendation}
        </Typography>
      )}

      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        {saved ? (
          <Chip
            size="small"
            color="success"
            icon={<CheckCircleIcon />}
            label="Saved ✓"
          />
        ) : executeMode ? (
          saveButton
        ) : (
          <Tooltip title={OFF_TOOLTIP} arrow>
            <span>{saveButton}</span>
          </Tooltip>
        )}
        {onRetest && (
          <Button size="small" onClick={onRetest}>
            Retest
          </Button>
        )}
        {onDiscard && (
          <Button size="small" color="inherit" onClick={onDiscard}>
            Discard
          </Button>
        )}
      </Stack>
    </Stack>
  );
}
