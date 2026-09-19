// src/components/ai/StepOutputRenderer.jsx
// W5-C — semantic renderer for plan-step tool output. Picks the visual form
// from an `outputType` hint (or infers it from the output shape) and renders
// text / table / chart / artifact / json. Pure, dense, theme tokens only
// (RULE_8); renders nothing when there is no output yet.
// Never dumps base64 / Office binary / huge JSON walls (RULE_23).
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Collapse,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import DescriptionIcon from '@mui/icons-material/Description';
import DownloadIcon from '@mui/icons-material/Download';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useAuth } from '../../auth/AuthContext';
import { downloadArtifactUrl } from '../../api/aiWorkspace';

const MAX_TABLE_ROWS = 10;
const MAX_SCALAR_CHARS = 240;
const BLOB_KEY_RE = /(_b64|base64|binary)$/i;

/** Human-readable byte size (RULE_23 outcome copy). */
function formatBytes(bytes) {
  const n = Number(bytes);
  if (bytes == null || Number.isNaN(n)) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function looksLikeBinaryBlob(s) {
  if (typeof s !== 'string' || s.length < 120) return false;
  if (/^data:image\//i.test(s)) return true;
  const sample = s.slice(0, 200).replace(/\s/g, '');
  const ok = (sample.match(/[A-Za-z0-9+/=]/g) || []).length;
  return ok / Math.max(sample.length, 1) > 0.95;
}

function formatScalar(val, key = '') {
  if (val == null) return '—';
  if (typeof val === 'string') {
    if (BLOB_KEY_RE.test(key) || looksLikeBinaryBlob(val)) {
      return `[binary, ~${Math.max(0, Math.floor((val.length * 3) / 4))} bytes]`;
    }
    return val.length > MAX_SCALAR_CHARS ? `${val.slice(0, MAX_SCALAR_CHARS - 1)}…` : val;
  }
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (val && typeof val === 'object' && val.present === true) {
    return val.bytes_est != null ? `[binary, ~${val.bytes_est} bytes]` : '[binary]';
  }
  try {
    const s = JSON.stringify(val);
    return s.length > 80 ? `${s.slice(0, 80)}…` : s;
  } catch {
    return String(val);
  }
}

/** Unwrap execute-wrapper / sandbox payloads for typed rendering. */
function unwrapPayload(value) {
  if (value == null || typeof value !== 'object' || Array.isArray(value)) return value;
  let data = { ...value };
  let result = data.result;
  if (typeof result === 'string') {
    const stripped = result.trim();
    if (stripped && (stripped[0] === '{' || stripped[0] === '[')) {
      try {
        result = JSON.parse(stripped);
      } catch {
        /* keep string */
      }
    }
  }
  if (result && typeof result === 'object' && !Array.isArray(result)) {
    data = { ...result, ...data };
    if (typeof data.result === 'string' && looksLikeBinaryBlob(data.result)) {
      delete data.result;
    }
  }
  return data;
}

/** Human-readable byte size (RULE_23 outcome copy). */
function toText(value) {
  if (value == null) return '';
  if (typeof value === 'string') {
    return looksLikeBinaryBlob(value)
      ? `[binary, ~${Math.max(0, Math.floor((value.length * 3) / 4))} bytes]`
      : value.length > 1200
        ? `${value.slice(0, 1199)}…`
        : value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    return value
      .map((v) => (typeof v === 'string' ? formatScalar(v) : formatScalar(v)))
      .join('\n');
  }
  const data = unwrapPayload(value);
  const scalar =
    data.text ?? data.content ?? data.summary ?? data.message ?? data.result;
  if (typeof scalar === 'string') return formatScalar(scalar, 'result');
  if (typeof scalar === 'number' || typeof scalar === 'boolean') return String(scalar);
  // Never dump full objects as JSON walls — fall back to KeyValue/RawJson callers.
  return '';
}

/** Normalize a tool output into { headers, rows } or null when not tabular. */
function normalizeTable(value) {
  let data = unwrapPayload(value);
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    if (Array.isArray(data.table_rows)) {
      const records = data.table_rows;
      if (!records.length) return null;
      if (typeof records[0] === 'object' && records[0] !== null && !Array.isArray(records[0])) {
        const headers = Object.keys(records[0]);
        return {
          headers,
          rows: records.map((r) => headers.map((h) => (r[h] == null ? '' : r[h]))),
        };
      }
    }
    if (Array.isArray(data.breakdown) && data.breakdown.length && typeof data.breakdown[0] === 'object') {
      const headers = Object.keys(data.breakdown[0]);
      return {
        headers,
        rows: data.breakdown.map((r) => headers.map((h) => (r[h] == null ? '' : r[h]))),
      };
    }
    const hasDirectHeaders = Array.isArray(data.headers) || Array.isArray(data.columns);
    if (!hasDirectHeaders) {
      const inner = data.result ?? data.data ?? data.rows;
      if (inner && typeof inner === 'object') data = inner;
    }
  }

  if (Array.isArray(data)) {
    if (!data.length) return null;
    if (Array.isArray(data[0])) {
      const headers = data[0].map((h) => String(h));
      return {
        headers,
        rows: data.slice(1).map((r) =>
          headers.map((_, i) => (r[i] == null ? '' : r[i])),
        ),
      };
    }
    if (typeof data[0] === 'object' && data[0] !== null) {
      const headers = Object.keys(data[0]);
      return {
        headers,
        rows: data.map((r) => headers.map((h) => (r[h] == null ? '' : r[h]))),
      };
    }
    return null;
  }

  if (data && typeof data === 'object') {
    const headers = data.headers ?? data.columns;
    const rows = data.rows ?? data.data;
    if (Array.isArray(headers) && Array.isArray(rows)) {
      return {
        headers: headers.map(String),
        rows: rows.map((r) =>
          Array.isArray(r) ? r : headers.map((h) => (r?.[h] == null ? '' : r?.[h])),
        ),
      };
    }
    return null;
  }
  return null;
}

/** Extract a flat numeric series from a tool output, or null when malformed. */
function normalizeSeries(value) {
  let data = unwrapPayload(value);
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const candidate =
      data.series ?? data.values ?? data.data ?? data.result;
    if (Array.isArray(candidate)) {
      const nums = candidate.filter((v) => typeof v === 'number' && Number.isFinite(v));
      return nums.length ? nums : null;
    }
    if (Array.isArray(data.labels) && Array.isArray(data.values)) {
      const nums = data.values.filter((v) => typeof v === 'number' && Number.isFinite(v));
      return nums.length ? nums : null;
    }
    return null;
  }
  if (Array.isArray(data)) {
    const nums = data.filter((v) => typeof v === 'number' && Number.isFinite(v));
    return nums.length ? nums : null;
  }
  return null;
}

function hasChartSignal(value) {
  const data = unwrapPayload(value);
  if (!data || typeof data !== 'object') return false;
  if (typeof data.image_b64 === 'string' && data.image_b64) return true;
  if (data.image && typeof data.image === 'object' && data.image.present) return true;
  return Boolean(normalizeSeries(data));
}

/** Human-readable key→value rows for flat JSON objects (RULE_23 outcome copy).
 *  `{ rule_details: "…" }` renders as a labelled row instead of a raw blob;
 *  complex (nested/array) shapes fall back to the collapsible raw block. */
export function KeyValueOutput({ value }) {
  const data = unwrapPayload(value);
  const isPlainObject = data !== null && typeof data === 'object' && !Array.isArray(data);
  if (!isPlainObject) return <RawJson value={value} />;
  const entries = Object.entries(data).filter(([k]) => k !== '_output_type' && k !== 'image_b64');
  if (entries.length === 0) return null;
  const allScalar = entries.every(([, v]) => v === null || typeof v !== 'object');
  if (!allScalar) return <RawJson value={data} />;
  return (
    <Box sx={{ mt: 0.5 }}>
      <Stack spacing={0.25}>
        {entries.map(([key, val]) => (
          <Box key={key} sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
            <Typography
              variant="caption"
              sx={{
                fontSize: '0.625rem',
                fontWeight: 600,
                color: 'text.secondary',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                minWidth: 96,
                flexShrink: 0,
              }}
            >
              {key.replace(/_/g, ' ')}
            </Typography>
            <Typography sx={{ fontSize: '0.6875rem', wordBreak: 'break-word', minWidth: 0, whiteSpace: 'pre-wrap' }}>
              {formatScalar(val, key)}
            </Typography>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

/** Collapsible "Raw output" JSON block — hidden by default; redacts blobs. */
function RawJson({ value }) {
  const [open, setOpen] = useState(false);
  const safe = typeof value === 'string'
    ? formatScalar(value)
    : JSON.stringify(
      (function redact(v, key = '') {
        if (typeof v === 'string') return formatScalar(v, key);
        if (Array.isArray(v)) return v.slice(0, 40).map((x) => redact(x));
        if (v && typeof v === 'object') {
          const out = {};
          Object.entries(v).forEach(([k, val]) => {
            if (k === 'image_b64' || BLOB_KEY_RE.test(k)) {
              out[k] = formatScalar(typeof val === 'string' ? val : '', k);
            } else {
              out[k] = redact(val, k);
            }
          });
          return out;
        }
        return v;
      }(unwrapPayload(value))),
      null,
      2,
    );
  return (
    <Box sx={{ mt: 0.5 }}>
      <Button
        size="small"
        color="inherit"
        onClick={() => setOpen((v) => !v)}
        endIcon={open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        sx={{ fontSize: '0.625rem', textTransform: 'none', px: 0, minWidth: 0 }}
      >
        Raw output
      </Button>
      <Collapse in={open} unmountOnExit>
        <Box
          component="pre"
          sx={{
            m: 0,
            mt: 0.25,
            p: 1,
            borderRadius: 1,
            bgcolor: 'action.hover',
            fontSize: '0.6875rem',
            lineHeight: 1.45,
            maxHeight: 200,
            overflow: 'auto',
          }}
        >
          {safe}
        </Box>
      </Collapse>
    </Box>
  );
}

/** Table renderer with first-row header + "show more" accordion. */
function TableOutput({ value }) {
  const normalized = normalizeTable(value);
  const [showAll, setShowAll] = useState(false);
  if (!normalized || !normalized.headers.length) {
    return <RawJson value={value} />;
  }
  const { headers, rows } = normalized;
  const visible = showAll ? rows : rows.slice(0, MAX_TABLE_ROWS);
  return (
    <Box sx={{ mt: 0.5, overflow: 'auto' }}>
      <Table size="small" sx={{ '& th, & td': { px: 0.75, py: 0.25, fontSize: '0.6875rem' } }}>
        <TableHead>
          <TableRow>
            {headers.map((h, i) => (
              <TableCell key={i} sx={{ fontWeight: 600, color: 'text.secondary' }}>
                {h}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {visible.map((row, ri) => (
            <TableRow key={ri}>
              {headers.map((_, ci) => (
                <TableCell key={ci}>{String(row[ci] ?? '')}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {rows.length > MAX_TABLE_ROWS && (
        <Button
          size="small"
          color="inherit"
          onClick={() => setShowAll((v) => !v)}
          endIcon={showAll ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          sx={{ fontSize: '0.625rem', textTransform: 'none', mt: 0.25, px: 0, minWidth: 0 }}
        >
          {showAll ? 'Show fewer rows' : `Show all ${rows.length} rows`}
        </Button>
      )}
    </Box>
  );
}

/** Chart: prefer image signal summary, else simple bar series. */
function ChartOutput({ value }) {
  const data = unwrapPayload(value);
  const imageMeta = (data && data.image && typeof data.image === 'object')
    ? data.image
    : null;
  const rawB64 = typeof data?.image_b64 === 'string' ? data.image_b64 : '';
  if (imageMeta?.present || rawB64) {
    const bytes = imageMeta?.bytes_est
      ?? (rawB64 ? Math.floor((rawB64.length * 3) / 4) : null);
    return (
      <Stack spacing={0.5} sx={{ mt: 0.5 }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
          Chart generated{bytes != null ? ` (${formatBytes(bytes)})` : ''}.
          Open the exported document under Artifacts for the full figure.
        </Typography>
        {normalizeTable(data) ? <TableOutput value={data} /> : null}
      </Stack>
    );
  }
  const series = normalizeSeries(value);
  if (!series) return <TableOutput value={value} />;
  const max = Math.max(...series, 1);
  return (
    <Box sx={{ mt: 0.75, display: 'flex', alignItems: 'flex-end', gap: 0.5, height: 48 }}>
      {series.slice(0, 24).map((v, i) => (
        <Box
          key={i}
          sx={{
            flex: 1,
            minWidth: 4,
            height: `${Math.max(4, (v / max) * 44)}px`,
            bgcolor: 'primary.main',
            borderRadius: '2px 2px 0 0',
          }}
          title={String(v)}
        />
      ))}
    </Box>
  );
}

/** Artifact card: file icon + name + size + Download. */
export function ArtifactCard({ value }) {
  const { token } = useAuth();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');

  const data = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const name = data.name ?? data.filename ?? 'Artifact';
  const size = data.size_bytes ?? data.size ?? data.file_size;
  const downloadUrl = data.download_url ?? data.url ?? data.file_path ?? data.path;

  const handleDownload = async () => {
    if (!downloadUrl) return;
    setDownloading(true);
    setError('');
    try {
      const blobUrl = await downloadArtifactUrl(token, downloadUrl);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      setError(err?.message || 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={1}
      sx={{ mt: 0.5, p: 0.75, borderRadius: 1, border: '1px solid', borderColor: 'divider' }}
    >
      <DescriptionIcon sx={{ fontSize: '1.125rem', color: 'text.secondary', flexShrink: 0 }} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.6875rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {name}
        </Typography>
        {size != null && (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
            {formatBytes(size)}
          </Typography>
        )}
      </Box>
      {downloadUrl && (
        <Button
          size="small"
          variant="outlined"
          disabled={downloading}
          onClick={handleDownload}
          startIcon={<DownloadIcon sx={{ fontSize: '0.875rem' }} />}
          sx={{ fontSize: '0.625rem', textTransform: 'none', flexShrink: 0 }}
        >
          {downloading ? 'Downloading…' : 'Download'}
        </Button>
      )}
      {error && (
        <Typography variant="caption" color="error.main" sx={{ fontSize: '0.625rem' }}>
          {error}
        </Typography>
      )}
    </Stack>
  );
}

/**
 * Step output renderer — dispatches on `outputType`.
 * @param {object} props
 * @param {string|null} props.outputType - 'text'|'table'|'chart'|'artifact'|'json'
 * @param {*} props.value - the tool output payload
 */
function StepOutputRenderer({ outputType, value }) {
  if (value === null || value === undefined || value === '') return null;

  const data = unwrapPayload(value);
  let type = outputType;
  if (!type) {
    if (hasChartSignal(data)) type = 'chart';
    else if (normalizeTable(data)) type = 'table';
    else if (typeof value === 'string') type = 'text';
    else if (Array.isArray(value)) type = 'table';
    else if (typeof value === 'object') {
      if (value.files || value.download_url || value.filename) type = 'artifact';
      else type = 'json';
    }
  }
  // Promote sandbox shapes even when a stale hint said "text"/"json"
  if ((type === 'text' || type === 'json') && hasChartSignal(data)) type = 'chart';
  if ((type === 'text' || type === 'json') && normalizeTable(data)) type = 'table';

  switch (type) {
    case 'text': {
      const prose = toText(value);
      if (!prose) return <KeyValueOutput value={data} />;
      return (
        <Typography
          sx={{
            display: 'block',
            mt: 0.5,
            fontSize: '0.6875rem',
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {prose}
        </Typography>
      );
    }
    case 'table':
      return <TableOutput value={data} />;
    case 'chart':
      return <ChartOutput value={data} />;
    case 'artifact':
      return <ArtifactCard value={data} />;
    case 'json':
      return <KeyValueOutput value={data} />;
    default:
      return null;
  }
}

StepOutputRenderer.propTypes = {
  outputType: PropTypes.string,
  value: PropTypes.any,
};

StepOutputRenderer.defaultProps = {
  outputType: null,
  value: null,
};

export default React.memo(StepOutputRenderer);
