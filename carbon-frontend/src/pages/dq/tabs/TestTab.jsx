// carbon-frontend/src/pages/dq/tabs/TestTab.jsx
// Client-side rule tester — evaluate a DQ rule definition against user-provided sample JSON.
//
// Supported rule types (pure client evaluation):
//   not_null, unique, allowed_values, range, regex, threshold
// Unsupported (require Pulse API or database):
//   nl_check, anomaly_detect, reference_integrity
import React, { useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { PlayArrow, CheckCircle, Cancel, RemoveCircle } from '@mui/icons-material';
import { useTranslation, Trans } from 'react-i18next';
import { ruleTypeLabel } from '../constants';
import { useAITaskTransfer } from '../../../shell/useAITaskTransfer';
import AIActionButton from '../../../components/dq/AIActionButton';

// ── Client-side evaluator (mirrors backend dq/engine.py evaluate) ──────────

const UNSUPPORTED_TYPES = ['nl_check', 'anomaly_detect', 'reference_integrity'];

function isEmpty(v) {
  return v === null || v === undefined || v === '';
}

function evaluateRule(definition, sampleRows, t) {
  const ruleType = definition.type || '';
  const params = definition.params || {};
  const bindings = definition.bindings || [];

  // Resolve the field to check: the first binding's field wins; for standalone
  // rules (no bindings) infer the key from the first sample row, falling back to
  // the 'value' key that defaultSampleForRule writes.
  const boundField =
    bindings.length > 0 && bindings[0].field ? bindings[0].field : null;
  const firstRow = sampleRows && sampleRows[0];
  const inferredField =
    firstRow && typeof firstRow === 'object' && !Array.isArray(firstRow)
      ? Object.keys(firstRow)[0]
      : null;
  const fieldName = boundField || inferredField || 'value';

  if (UNSUPPORTED_TYPES.includes(ruleType)) {
    return { unsupported: true, ruleType };
  }

  const results = [];
  const failures = [];

  if (ruleType === 'not_null') {
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      const passed = !isEmpty(v);
      results.push({ index: i, value: v, passed, reason: passed ? null : t('test.reasonNull') });
      if (!passed) failures.push({ index: i, value: v });
    });
  } else if (ruleType === 'unique') {
    const seen = new Map();
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      if (isEmpty(v)) {
        results.push({ index: i, value: v, passed: true, reason: null }); // nulls not checked for uniqueness
        return;
      }
      const key = String(v);
      if (!seen.has(key)) seen.set(key, []);
      seen.get(key).push(i);
    });
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      if (isEmpty(v)) return; // already handled above
      const key = String(v);
      const dupes = seen.get(key) || [];
      const passed = dupes.length <= 1;
      results.push({
        index: i,
        value: v,
        passed,
        reason: passed
          ? null
          : t('test.reasonDuplicate', { value: v, rows: dupes.map((d) => d + 1).join(', ') }),
      });
      if (!passed) failures.push({ index: i, value: v });
    });
  } else if (ruleType === 'allowed_values') {
    const allowed = new Set((params.values || []).map(String));
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      if (isEmpty(v)) {
        results.push({ index: i, value: v, passed: true, reason: null });
        return;
      }
      const passed = allowed.has(String(v));
      results.push({
        index: i,
        value: v,
        passed,
        reason: passed
          ? null
          : t('test.reasonNotAllowed', { value: v, values: [...allowed].join(', ') }),
      });
      if (!passed) failures.push({ index: i, value: v });
    });
  } else if (ruleType === 'range') {
    const lo = params.min;
    const hi = params.max;
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      if (isEmpty(v)) {
        results.push({ index: i, value: v, passed: true, reason: null });
        return;
      }
      const fv = Number(v);
      if (isNaN(fv)) {
        results.push({ index: i, value: v, passed: false, reason: t('test.reasonNotNumber', { value: v }) });
        failures.push({ index: i, value: v });
        return;
      }
      const below = lo !== undefined && lo !== null && fv < Number(lo);
      const above = hi !== undefined && hi !== null && fv > Number(hi);
      const passed = !below && !above;
      let reason = null;
      if (below) reason = t('test.reasonBelowMin', { value: fv, min: lo });
      if (above) reason = t('test.reasonAboveMax', { value: fv, max: hi });
      results.push({ index: i, value: v, passed, reason });
      if (!passed) failures.push({ index: i, value: v });
    });
  } else if (ruleType === 'regex') {
    const pattern = params.pattern || '';
    let rx = null;
    try {
      rx = pattern ? new RegExp(pattern) : null;
    } catch (_) { /* invalid pattern */ }
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      if (isEmpty(v)) {
        results.push({ index: i, value: v, passed: true, reason: null });
        return;
      }
      const passed = rx ? rx.test(String(v)) : true;
      results.push({
        index: i,
        value: v,
        passed,
        reason: passed ? null : t('test.reasonNoMatch', { value: v, pattern }),
      });
      if (!passed) failures.push({ index: i, value: v });
    });
  } else if (ruleType === 'threshold') {
    const op = params.operator || 'gte';
    const threshold = params.value;
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      if (isEmpty(v)) {
        results.push({ index: i, value: v, passed: true, reason: null });
        return;
      }
      const fv = Number(v);
      if (isNaN(fv)) {
        results.push({ index: i, value: v, passed: false, reason: t('test.reasonNotNumber', { value: v }) });
        failures.push({ index: i, value: v });
        return;
      }
      const tv = threshold !== undefined && threshold !== null ? Number(threshold) : null;
      let passed = true;
      if (tv !== null) {
        if (op === 'gte') passed = fv >= tv;
        else if (op === 'gt') passed = fv > tv;
        else if (op === 'lte') passed = fv <= tv;
        else if (op === 'lt') passed = fv < tv;
        else if (op === 'eq') passed = fv === tv;
        else if (op === 'neq') passed = fv !== tv;
      }
      const opLabels = { gte: '>=', gt: '>', lte: '<=', lt: '<', eq: '=', neq: '!=' };
      results.push({
        index: i,
        value: v,
        passed,
        reason: passed ? null : t('test.reasonCompareFalse', { value: fv, op: opLabels[op] || op, threshold: tv }),
      });
      if (!passed) failures.push({ index: i, value: v });
    });
  } else {
    return { unsupported: true, ruleType };
  }

  const checked = results.length;
  const failed = failures.length;
  const score = checked === 0 ? 100 : Math.round(((checked - failed) / checked) * 100);

  return { results, failures, checked, failed, score, fieldName, ruleType };
}

// ── Default sample data template ────────────────────────────────────────────

function defaultSampleForRule(definition) {
  const bindings = definition?.bindings || [];
  const fieldName = bindings.length > 0 ? bindings[0].field : 'value';
  const ruleType = definition?.type || '';
  const params = definition?.params || {};

  // Generate sensible sample data based on rule type
  if (ruleType === 'not_null') {
    return [
      { [fieldName]: 'sample_value' },
      { [fieldName]: null },
      { [fieldName]: '' },
      { [fieldName]: 'another_value' },
    ];
  }
  if (ruleType === 'unique') {
    return [
      { [fieldName]: 'alpha' },
      { [fieldName]: 'beta' },
      { [fieldName]: 'alpha' },  // duplicate
      { [fieldName]: 'gamma' },
    ];
  }
  if (ruleType === 'allowed_values') {
    const allowed = params.values || ['A', 'B', 'C'];
    return [
      { [fieldName]: allowed[0] || 'A' },
      { [fieldName]: 'invalid_value' },
      { [fieldName]: allowed[1] || 'B' },
    ];
  }
  if (ruleType === 'range') {
    const lo = params.min ?? 0;
    const hi = params.max ?? 100;
    return [
      { [fieldName]: Number(lo) + 10 },
      { [fieldName]: Number(lo) - 1 },
      { [fieldName]: Number(hi) + 1 },
      { [fieldName]: Math.round((Number(lo) + Number(hi)) / 2) },
    ];
  }
  if (ruleType === 'regex') {
    return [
      { [fieldName]: 'abc123' },
      { [fieldName]: '!!!' },
      { [fieldName]: 'test@example.com' },
    ];
  }
  if (ruleType === 'threshold') {
    const tv = params.value ?? 50;
    return [
      { [fieldName]: Number(tv) + 5 },
      { [fieldName]: Number(tv) - 1 },
      { [fieldName]: Number(tv) },
      { [fieldName]: null },
    ];
  }
  return [
    { [fieldName]: 'row_1' },
    { [fieldName]: 'row_2' },
  ];
}

// ── Component ───────────────────────────────────────────────────────────────

export default function TestTab({ rule }) {
  const { t } = useTranslation('dq');
  const definition = useMemo(() => rule?.definition || {}, [rule?.definition]);
  const ruleType = definition.type || rule?.rule_type || '';
  const { transferTask } = useAITaskTransfer();

  const [sampleText, setSampleText] = useState(() =>
    JSON.stringify(defaultSampleForRule(definition), null, 2)
  );
  const [results, setResults] = useState(null);
  const [parseError, setParseError] = useState(null);
  const [transferring, setTransferring] = useState(false);

  const isUnsupported = UNSUPPORTED_TYPES.includes(ruleType);
  const typeLabel = ruleTypeLabel(t, ruleType);
  // In-scope alias for <Trans> children interpolation ({{type}} shorthand
  // compiles to an object-literal reference on `type`).
  const type = typeLabel;

  const handleTransferToAI = async () => {
    setTransferring(true);
    const bindings = rule?.field_assignments || [];
    const tableName = bindings.length > 0 ? bindings[0].table_name : undefined;
    const fields = bindings.map((b) => b.field_name).filter(Boolean);
    await transferTask('dq_validate', {
      rule_id: rule.id,
      rule_name: rule.name,
      table_name: tableName,
      fields,
      prompt: `Test rule "${rule.name}" against data`,
    }, {
      title: t('test.transferTitle', { name: rule.name }),
      source_page: 'dq-rule-test',
      workspaceContext: {
        workspace: 'dq',
        current_view: 'rule_test',
        entity_type: 'rule',
        entity_id: rule?.id ?? null,
        entity_name: rule?.name ?? null,
        intent_signal: 'debug',
        recent_actions: [],
      },
    });
    setTransferring(false);
  };

  const handleTest = useCallback(() => {
    setParseError(null);
    let parsed;
    try {
      parsed = JSON.parse(sampleText);
    } catch (err) {
      setParseError(t('errors.invalidJson', { message: err.message }));
      setResults(null);
      return;
    }
    if (!Array.isArray(parsed)) {
      setParseError(t('test.sampleArrayError'));
      setResults(null);
      return;
    }
    const evalResult = evaluateRule(definition, parsed, t);
    setResults(evalResult);
  }, [sampleText, definition, t]);

  const scoreColor = useMemo(() => {
    if (results?.score == null) return 'text.secondary';
    if (results.score >= 80) return 'success.main';
    if (results.score >= 60) return 'warning.main';
    return 'error.main';
  }, [results]);

  return (
    <Box sx={{ p: 3 }}>
      <Stack spacing={2}>
        {/* Info banner */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'action.hover' }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 0.5 }}>
            {t('test.testRule', { name: rule?.name || t('test.ruleFallback') })}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {isUnsupported ? (
              <Trans i18nKey="test.ruleTypeLineUnsupported" ns="dq" values={{ type }}>
                Rule type: <strong>{{type}}</strong> — this rule type requires Pulse AI and cannot be tested locally. Use the Jobs tab to run it against real data.
              </Trans>
            ) : (
              <Trans i18nKey="test.ruleTypeLine" ns="dq" values={{ type }}>
                Rule type: <strong>{{type}}</strong> — provide sample rows below to preview how this rule evaluates data.
              </Trans>
            )}
          </Typography>
        </Paper>

        {/* Sample data input */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700 }}>
              {t('test.sampleData')}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              onClick={() => setSampleText(JSON.stringify(defaultSampleForRule(definition), null, 2))}
            >
              {t('test.resetTemplate')}
            </Button>
          </Stack>
          <TextField
            multiline
            minRows={6}
            maxRows={16}
            fullWidth
            size="small"
            value={sampleText}
            onChange={(e) => {
              setSampleText(e.target.value);
              setResults(null);
              setParseError(null);
            }}
            disabled={isUnsupported}
            sx={{
              '& .MuiInputBase-input': { fontFamily: 'monospace', fontSize: '0.75rem' },
            }}
          />
          {parseError ? (
            <Alert severity="error" sx={{ mt: 1 }}>
              {parseError}
            </Alert>
          ) : null}
          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
            <Button
              variant="contained"
              size="small"
              startIcon={<PlayArrow />}
              onClick={handleTest}
              disabled={isUnsupported}
            >
              {t('test.testButton')}
            </Button>
            <AIActionButton
              title={t('test.checkWithAi')}
              onClick={handleTransferToAI}
              busy={transferring}
            />
          </Stack>
        </Paper>

        {/* Results */}
        {results && !results.unsupported ? (
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1.5 }}>
              <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700 }}>
                {t('test.results')}
              </Typography>
              <Chip
                size="small"
                label={t('test.passedCount', {
                  passed: results.passedCount ?? results.checked - results.failed,
                  checked: results.checked,
                })}
                color={results.failed === 0 ? 'success' : 'warning'}
                variant="outlined"
              />
              <Typography variant="body2" sx={{ color: scoreColor, fontWeight: 700 }}>
                {t('test.score', { score: results.score })}
              </Typography>
            </Stack>

            {results.failed > 0 ? (
              <Alert severity="warning" sx={{ mb: 1.5 }}>
                {results.failed === 1
                  ? t('test.failedAlertOne', { count: results.failed })
                  : t('test.failedAlertMany', { count: results.failed })}
              </Alert>
            ) : (
              <Alert severity="success" sx={{ mb: 1.5 }}>
                {t('test.allPassed')}
              </Alert>
            )}

            <Box sx={{ overflow: 'auto', maxHeight: 420 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>{t('columns.row')}</TableCell>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>
                      {results.fieldName || t('test.value')}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>{t('columns.verdict')}</TableCell>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>{t('columns.reason')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results.results.map((r) => (
                    <TableRow
                      key={r.index}
                      sx={{
                        '&:nth-of-type(odd)': { bgcolor: 'action.hover' },
                      }}
                    >
                      <TableCell sx={{ fontSize: '0.6875rem', py: 0.5 }}>
                        {r.index + 1}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.6875rem', py: 0.5, fontFamily: 'monospace' }}>
                        {r.value === null ? (
                          <em>{t('test.nullValue')}</em>
                        ) : r.value === '' ? (
                          <em>{t('test.emptyValue')}</em>
                        ) : (
                          String(r.value)
                        )}
                      </TableCell>
                      <TableCell sx={{ py: 0.5 }}>
                        {r.passed ? (
                          <Chip
                            size="small"
                            icon={<CheckCircle />}
                            label={t('status.passed')}
                            color="success"
                            variant="outlined"
                          />
                        ) : (
                          <Chip
                            size="small"
                            icon={<Cancel />}
                            label={t('status.failed')}
                            color="error"
                            variant="outlined"
                          />
                        )}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.6875rem', py: 0.5, color: 'text.secondary' }}>
                        {r.reason || '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Paper>
        ) : null}
      </Stack>
    </Box>
  );
}

TestTab.propTypes = {
  rule: PropTypes.object,
};
