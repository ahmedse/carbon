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
import { PlayArrow, CheckCircle, Cancel, RemoveCircle, SmartToy } from '@mui/icons-material';
import { RULE_TYPE_LABELS } from '../constants';
import { useAITaskTransfer } from '../../../shell/AITaskTransferContext';

// ── Client-side evaluator (mirrors backend dq/engine.py evaluate) ──────────

const UNSUPPORTED_TYPES = ['nl_check', 'anomaly_detect', 'reference_integrity'];

function isEmpty(v) {
  return v === null || v === undefined || v === '';
}

function evaluateRule(definition, sampleRows) {
  const ruleType = definition.type || '';
  const params = definition.params || {};
  const bindings = definition.bindings || [];

  // Resolve the field name to check from the first binding
  const fieldName = bindings.length > 0 ? bindings[0].field : null;

  if (UNSUPPORTED_TYPES.includes(ruleType)) {
    return { unsupported: true, ruleType };
  }

  const results = [];
  const failures = [];

  if (ruleType === 'not_null') {
    sampleRows.forEach((row, i) => {
      const v = fieldName ? row[fieldName] : undefined;
      const passed = !isEmpty(v);
      results.push({ index: i, value: v, passed, reason: passed ? null : 'Value is null or empty' });
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
        reason: passed ? null : `Duplicate value "${v}" found in rows ${dupes.map((d) => d + 1).join(', ')}`,
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
        reason: passed ? null : `"${v}" not in allowed values: [${[...allowed].join(', ')}]`,
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
        results.push({ index: i, value: v, passed: false, reason: `"${v}" is not a number` });
        failures.push({ index: i, value: v });
        return;
      }
      const below = lo !== undefined && lo !== null && fv < Number(lo);
      const above = hi !== undefined && hi !== null && fv > Number(hi);
      const passed = !below && !above;
      let reason = null;
      if (below) reason = `${fv} < min ${lo}`;
      if (above) reason = `${fv} > max ${hi}`;
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
        reason: passed ? null : `"${v}" does not match /${pattern}/`,
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
        results.push({ index: i, value: v, passed: false, reason: `"${v}" is not a number` });
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
        reason: passed ? null : `${fv} ${opLabels[op] || op} ${tv} is false`,
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
  const ruleTypeLabel = RULE_TYPE_LABELS[ruleType] || ruleType;

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
      title: `DQ Test: ${rule.name}`,
      source_page: 'dq-rule-test',
    });
    setTransferring(false);
  };

  const handleTest = useCallback(() => {
    setParseError(null);
    let parsed;
    try {
      parsed = JSON.parse(sampleText);
    } catch (err) {
      setParseError(`Invalid JSON: ${err.message}`);
      setResults(null);
      return;
    }
    if (!Array.isArray(parsed)) {
      setParseError('Sample data must be a JSON array of objects');
      setResults(null);
      return;
    }
    const evalResult = evaluateRule(definition, parsed);
    setResults(evalResult);
  }, [sampleText, definition]);

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
            Test Rule: {rule?.name || 'Rule'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Rule type: <strong>{ruleTypeLabel}</strong>
            {UNSUPPORTED_TYPES.includes(ruleType)
              ? ' — this rule type requires Pulse AI and cannot be tested locally. Use the Jobs tab to run it against real data.'
              : ' — provide sample rows below to preview how this rule evaluates data.'}
          </Typography>
        </Paper>

        {/* Sample data input */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700 }}>
              Sample Data (JSON)
            </Typography>
            <Button
              variant="outlined"
              size="small"
              onClick={() => setSampleText(JSON.stringify(defaultSampleForRule(definition), null, 2))}
            >
              Reset to template
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
              Test
            </Button>
            <Button
              variant="outlined"
              size="small"
              color="secondary"
              startIcon={<SmartToy />}
              onClick={handleTransferToAI}
              disabled={transferring}
            >
              {transferring ? 'Transferring…' : 'Check with AI'}
            </Button>
          </Stack>
        </Paper>

        {/* Results */}
        {results && !results.unsupported ? (
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1.5 }}>
              <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700 }}>
                Results
              </Typography>
              <Chip
                size="small"
                label={`${results.passedCount ?? results.checked - results.failed} / ${results.checked} passed`}
                color={results.failed === 0 ? 'success' : 'warning'}
                variant="outlined"
              />
              <Typography variant="body2" sx={{ color: scoreColor, fontWeight: 700 }}>
                Score: {results.score}%
              </Typography>
            </Stack>

            {results.failed > 0 ? (
              <Alert severity="warning" sx={{ mb: 1.5 }}>
                {results.failed} row{results.failed !== 1 ? 's' : ''} failed — fix the rule definition or sample data.
              </Alert>
            ) : (
              <Alert severity="success" sx={{ mb: 1.5 }}>
                All rows passed — the rule logic is valid for this sample data.
              </Alert>
            )}

            <Box sx={{ overflow: 'auto', maxHeight: 420 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>Row</TableCell>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>
                      {results.fieldName || 'Value'}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>Verdict</TableCell>
                    <TableCell sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase' }}>Reason</TableCell>
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
                        {r.value === null ? <em>null</em> : r.value === '' ? <em>empty</em> : String(r.value)}
                      </TableCell>
                      <TableCell sx={{ py: 0.5 }}>
                        {r.passed ? (
                          <Chip
                            size="small"
                            icon={<CheckCircle />}
                            label="Passed"
                            color="success"
                            variant="outlined"
                          />
                        ) : (
                          <Chip
                            size="small"
                            icon={<Cancel />}
                            label="Failed"
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
