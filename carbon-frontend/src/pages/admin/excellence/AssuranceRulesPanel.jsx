import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Chip, CircularProgress, FormControlLabel, Stack, Switch,
  Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch, apiFetchStream } from '../../../api/api';

function labelColor(label) {
  if (label === 'passed') return 'success';
  if (label === 'failed' || label === 'conflict') return 'error';
  if (label === 'stale') return 'warning';
  return 'default';
}

/**
 * Rule × evidence board (legacy assurance pack). Lives under Excellence so there
 * is one Trust destination; the ladder is levels, this is release-blocking rules.
 */
export default function AssuranceRulesPanel({ pack = 'nibras', embedded = false }) {
  const { token } = useAuth();
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(null);
  const [stream, setStream] = useState('connecting');
  const [blocksOnly, setBlocksOnly] = useState(false);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    apiFetch(`assurance/report/?pack=${encodeURIComponent(pack)}`, { token })
      .then((data) => { if (!cancelled) setSnapshot(data); })
      .catch((err) => { if (!cancelled) setError(err?.message || 'Assurance report failed'); });
    return () => { cancelled = true; };
  }, [token, pack]);

  useEffect(() => {
    if (!token) return undefined;
    const controller = new AbortController();
    let stopped = false;

    async function listen() {
      try {
        const response = await apiFetchStream(`assurance/stream/?pack=${encodeURIComponent(pack)}`, {
          token,
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          setStream('disconnected');
          return;
        }
        setStream('live');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (!stopped) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop() || '';
          for (const chunk of chunks) {
            const line = chunk.split('\n').find((row) => row.startsWith('data: '));
            if (!line) continue;
            try {
              setSnapshot(JSON.parse(line.slice(6)));
              setStream('live');
            } catch {
              setStream('stale');
            }
          }
        }
      } catch (err) {
        if (!stopped && err?.name !== 'AbortError') setStream('disconnected');
      }
    }

    listen();
    return () => {
      stopped = true;
      controller.abort();
    };
  }, [token, pack]);

  const rows = useMemo(() => {
    const all = snapshot?.rows || [];
    return blocksOnly ? all.filter((row) => row.blocks_release) : all;
  }, [snapshot, blocksOnly]);

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }} flexWrap="wrap">
        {!embedded && <Typography variant="h6">Assurance</Typography>}
        <Chip size="small" label={stream} color={stream === 'live' ? 'success' : 'default'} />
        <Chip size="small" label={snapshot?.commit || '…'} variant="outlined" />
        <Chip
          size="small"
          color={snapshot?.blocking_not_passed ? 'warning' : 'success'}
          label={`${snapshot?.blocking_not_passed ?? '—'} blocking not passed`}
        />
        <FormControlLabel
          control={<Switch size="small" checked={blocksOnly} onChange={(e) => setBlocksOnly(e.target.checked)} />}
          label="Blocks release"
        />
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Rule × evidence on the current commit. Does not run payroll, WPS, or Chat.
        {snapshot?.ledger ? ` Ledger: ${snapshot.ledger}` : ' No ledger file — rows stay at their catalogue label.'}
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      {!snapshot && !error && <CircularProgress size={28} />}
      {snapshot && (
        <Box sx={{ overflow: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Rule</TableCell>
                <TableCell>Journey</TableCell>
                <TableCell>Meaning</TableCell>
                <TableCell>Evidence</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow
                  key={`${row.pack}-${row.rule_id}`}
                  hover
                  selected={selected?.rule_id === row.rule_id && selected?.pack === row.pack}
                  onClick={() => setSelected(row)}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell>{row.rule_id}</TableCell>
                  <TableCell>{row.journey}</TableCell>
                  <TableCell>{row.meaning}</TableCell>
                  <TableCell>
                    <Chip size="small" label={row.label} color={labelColor(row.label)} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
      {selected && (
        <Alert severity="info" sx={{ mt: 1 }}>
          <strong>{selected.rule_id}</strong> — {selected.reason}
          <br />
          Residual: {selected.residual}
        </Alert>
      )}
    </Box>
  );
}
