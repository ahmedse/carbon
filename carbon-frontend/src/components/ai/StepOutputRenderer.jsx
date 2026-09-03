// src/components/ai/StepOutputRenderer.jsx
// W5-C — semantic renderer for plan-step tool output. Picks the visual form
// from an `outputType` hint (or infers it from the output shape) and renders
// text / table / chart / artifact / json. Pure, dense, theme tokens only
// (RULE_8); renders nothing when there is no output yet.
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

/** Human-readable byte size (RULE_23 outcome copy). */
function formatBytes(bytes) {
  const n = Number(bytes);
  if (bytes == null || Number.isNaN(n)) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** Coerce an arbitrary tool output into a single string (prose or fallback). */
function toText(value) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    return value
      .map((v) => (typeof v === 'string' ? v : JSON.stringify(v)))
      .join('\n');
  }
  const scalar =
    value.text ?? value.content ?? value.summary ?? value.message ?? value.result;
  if (typeof scalar === 'string') return scalar;
  if (typeof scalar === 'number' || typeof scalar === 'boolean') return String(scalar);
  return JSON.stringify(value, null, 2);
}

/** Normalize a tool output into { headers, rows } or null when not tabular. */
function normalizeTable(value) {
  let data = value;
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    // Honor an explicit { headers, rows } shape at the top level — unwrapping
    // `rows` here would swallow the headers and eat the first row instead.
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
  let data = value;
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

/** Human-readable key→value rows for flat JSON objects (RULE_23 outcome copy).
 *  `{ rule_details: "…" }` renders as a labelled row instead of a raw blob;
 *  complex (nested/array) shapes fall back to the collapsible raw block. */
export function KeyValueOutput({ value }) {
  const isPlainObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  if (!isPlainObject) return <RawJson value={value} />;
  const entries = Object.entries(value);
  if (entries.length === 0) return null;
  const allScalar = entries.every(([, v]) => v === null || typeof v !== 'object');
  if (!allScalar) return <RawJson value={value} />;
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
              {typeof val === 'string' ? val : val == null ? '—' : String(val)}
            </Typography>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

/** Collapsible "Raw output" JSON block — hidden by default. */
function RawJson({ value }) {
  const [open, setOpen] = useState(false);
  const text =
    typeof value === 'string' ? value : JSON.stringify(value, null, 2);
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
          {text}
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

/** Simple bar chart from a numeric series (falls back to table/json). */
function ChartOutput({ value }) {
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

  let type = outputType;
  if (!type) {
    if (typeof value === 'string') type = 'text';
    else if (Array.isArray(value)) type = 'table';
    else if (typeof value === 'object') type = 'json';
  }

  switch (type) {
    case 'text':
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
          {toText(value)}
        </Typography>
      );
    case 'table':
      return <TableOutput value={value} />;
    case 'chart':
      return <ChartOutput value={value} />;
    case 'artifact':
      return <ArtifactCard value={value} />;
    case 'json':
      return <KeyValueOutput value={value} />;
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
