// src/shell/EnvelopeMessage.jsx
// ────────────────────────────────────────────────────────────────────────────
// Deterministic renderer for the typed "AnswerEnvelope" Pulse AI answers carry.
//
// This is ADDITIVE and DEFENSIVE: the envelope is flag-gated OFF by default in
// the backend (PULSE_ENVELOPE_ENABLED=false). When the envelope is absent this
// component degrades to the existing markdown path (zero regression):
//
//     <MarkdownMessage content={fallbackContent} />
//
// The envelope shape (pydantic AnswerEnvelope.model_dump()):
//
//   headline : markdown string (rendered via MarkdownMessage)
//   prose[]  : markdown paragraphs (rendered via MarkdownMessage)
//   tables[] : { title, columns[], rows[[label, value], …] } — typed cells
//   charts[] : { chart_type: bar|pie|line, title, series[{name, data[[l,v],…]}] }
//   caveats[]: { level: info|warning|critical, text }
//   sources[]: { tool, rows_returned, truncated, resolved_at }
//
// Nothing here is bespoke per feature — it renders whatever envelope the
// backend hands it, using only theme tokens / compact-ui density rules.
// ────────────────────────────────────────────────────────────────────────────
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { alpha, useTheme } from '@mui/material/styles';
import {
  Box,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ErrorOutlineOutlinedIcon from '@mui/icons-material/ErrorOutlineOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import MarkdownMessage from './MarkdownMessage';
import { formatDisplayDateTime } from '../utils/dateUtils';

// ── Chart geometry (fixed viewBox — deterministic, resolution-independent) ──
const CHART_W = 320;
const CHART_H = 180;
const PAD_L = 8;
const PAD_R = 8;
const PAD_T = 12;
const PAD_B = 30;

// ── Small helpers ────────────────────────────────────────────────────────────

/** Flatten series[] into deterministic {label, value} pairs. */
function flattenSeries(series) {
  const pairs = [];
  (Array.isArray(series) ? series : []).forEach((s) => {
    if (!s || !Array.isArray(s.data)) return;
    s.data.forEach((entry) => {
      if (!Array.isArray(entry)) return;
      const [label, value] = entry;
      pairs.push({
        label: label == null ? '' : String(label),
        value: Number(value) || 0,
      });
    });
  });
  return pairs;
}

/** Coerce a single table cell to its string form (typed str|int|float). */
function cellString(cell) {
  if (cell === null || cell === undefined) return '';
  return String(cell);
}

/** Truncate a chart label so bars/pie legends stay scannable. */
function truncateLabel(label, max = 12) {
  const s = String(label);
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/** Format a provenance timestamp; fall back to the raw string when unparsable. */
function formatResolvedAt(resolvedAt) {
  if (!resolvedAt) return '';
  const d = new Date(resolvedAt);
  if (Number.isNaN(d.getTime())) return String(resolvedAt);
  return formatDisplayDateTime(d);
}

// ── Section label (compact-ui caption tier) ─────────────────────────────────

function SectionLabel({ children }) {
  return (
    <Typography
      variant="caption"
      component="div"
      sx={{
        fontWeight: 600,
        color: 'text.secondary',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        mb: 0.5,
      }}
    >
      {children}
    </Typography>
  );
}

SectionLabel.propTypes = { children: PropTypes.node };

// ── Tables — compact-ui.md treatment (mirrors MarkdownMessage's GFM tables) ──

function EnvelopeTable({ table, t }) {
  if (!table || typeof table !== 'object') return null;
  const { title, columns, rows } = table;
  if (!Array.isArray(columns) || columns.length === 0) return null;

  const safeRows = Array.isArray(rows) ? rows : [];

  return (
    <Box data-testid="envelope-table">
      {title ? (
        <Typography variant="subtitle2" sx={{ mb: 0.5, fontWeight: 600 }}>
          {cellString(title)}
        </Typography>
      ) : null}
      <Box sx={{ overflowX: 'auto', borderRadius: 1, border: 1, borderColor: 'divider' }}>
        <Table size="small" sx={{ minWidth: 300 }}>
          <TableHead sx={{ bgcolor: 'background.dark' }}>
            <TableRow>
              {columns.map((col, i) => (
                <TableCell
                  key={i}
                  sx={(theme) => ({
                    py: 0.75,
                    px: 1,
                    fontWeight: 600,
                    fontSize: theme.typography.caption.fontSize,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    whiteSpace: 'nowrap',
                    color: 'text.secondary',
                    borderBottom: 2,
                    borderColor: 'divider',
                  })}
                >
                  {cellString(col)}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {safeRows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  sx={(theme) => ({
                    py: 0.5,
                    px: 1,
                    fontSize: theme.typography.body2.fontSize,
                    color: 'text.secondary',
                  })}
                >
                  {t('envelope.noData')}
                </TableCell>
              </TableRow>
            ) : (
              safeRows.map((row, ri) => {
                const cells = Array.isArray(row) ? row : [row];
                return (
                  <TableRow
                    key={ri}
                    sx={{
                      '&:nth-of-type(even)': { bgcolor: 'action.hover' },
                      '&:last-child td': { borderBottom: 0 },
                    }}
                  >
                    {cells.map((cell, ci) => (
                      <TableCell
                        key={ci}
                        sx={(theme) => ({
                          py: 0.5,
                          px: 1,
                          fontSize: theme.typography.body2.fontSize,
                        })}
                      >
                        {cellString(cell)}
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Box>
    </Box>
  );
}

EnvelopeTable.propTypes = {
  table: PropTypes.object,
  t: PropTypes.func.isRequired,
};

// ── Charts — deterministic pure-SVG (no chart library) ──────────────────────

function BarChartSvg({ pairs, theme }) {
  const max = Math.max(...pairs.map((p) => p.value), 0) || 1;
  const innerW = CHART_W - PAD_L - PAD_R;
  const innerH = CHART_H - PAD_T - PAD_B;
  const n = pairs.length || 1;
  const step = innerW / n;
  const barW = Math.min(36, step * 0.6);

  return (
    <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} width="100%" height="auto" role="img">
      <line
        x1={PAD_L}
        y1={CHART_H - PAD_B}
        x2={CHART_W - PAD_R}
        y2={CHART_H - PAD_B}
        stroke={theme.palette.divider}
        strokeWidth={1}
      />
      {pairs.map((p, i) => {
        const h = (p.value / max) * innerH;
        const x = PAD_L + i * step + (step - barW) / 2;
        const y = CHART_H - PAD_B - h;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={h} rx={2} fill={theme.palette.primary.main} />
            <text
              x={PAD_L + i * step + step / 2}
              y={CHART_H - PAD_B + 12}
              textAnchor="middle"
              fontSize={10}
              fill={theme.palette.text.secondary}
            >
              {truncateLabel(p.label)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function LineChartSvg({ pairs, theme }) {
  const max = Math.max(...pairs.map((p) => p.value), 0) || 1;
  const innerW = CHART_W - PAD_L - PAD_R;
  const innerH = CHART_H - PAD_T - PAD_B;
  const n = pairs.length;
  const xFor = (i) => (n <= 1 ? PAD_L + innerW / 2 : PAD_L + (i / (n - 1)) * innerW);
  const yFor = (v) => CHART_H - PAD_B - (v / max) * innerH;
  const points = pairs.map((p, i) => `${xFor(i)},${yFor(p.value)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} width="100%" height="auto" role="img">
      <line
        x1={PAD_L}
        y1={CHART_H - PAD_B}
        x2={CHART_W - PAD_R}
        y2={CHART_H - PAD_B}
        stroke={theme.palette.divider}
        strokeWidth={1}
      />
      {n > 1 && (
        <polyline points={points} fill="none" stroke={theme.palette.primary.main} strokeWidth={2} />
      )}
      {pairs.map((p, i) => (
        <g key={i}>
          <circle cx={xFor(i)} cy={yFor(p.value)} r={3} fill={theme.palette.primary.main} />
          <text
            x={xFor(i)}
            y={CHART_H - PAD_B + 12}
            textAnchor="middle"
            fontSize={10}
            fill={theme.palette.text.secondary}
          >
            {truncateLabel(p.label)}
          </text>
        </g>
      ))}
    </svg>
  );
}

function polar(cx, cy, r, angle) {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function donutPath(cx, cy, rOuter, rInner, startAngle, endAngle) {
  const [x1o, y1o] = polar(cx, cy, rOuter, startAngle);
  const [x2o, y2o] = polar(cx, cy, rOuter, endAngle);
  const [x2i, y2i] = polar(cx, cy, rInner, endAngle);
  const [x1i, y1i] = polar(cx, cy, rInner, startAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
  return [
    `M ${x1o} ${y1o}`,
    `A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${x2o} ${y2o}`,
    `L ${x2i} ${y2i}`,
    `A ${rInner} ${rInner} 0 ${largeArc} 0 ${x1i} ${y1i}`,
    'Z',
  ].join(' ');
}

const PIE_COLORS = ['primary', 'info', 'warning', 'success', 'error', 'secondary'];

function PieChartSvg({ pairs, theme }) {
  const size = 180;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = 68;
  const rInner = 40;
  const total = pairs.reduce((a, p) => a + p.value, 0) || 1;

  let angle = -Math.PI / 2; // start at 12 o'clock

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1.5 }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={140} height={140} role="img">
        {pairs.map((p, i) => {
          const frac = p.value / total;
          const start = angle;
          const end = angle + frac * Math.PI * 2;
          angle = end;
          return (
            <path
              key={i}
              d={donutPath(cx, cy, rOuter, rInner, start, end)}
              fill={theme.palette[PIE_COLORS[i % PIE_COLORS.length]].main}
            />
          );
        })}
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={10}
          fill={theme.palette.text.secondary}
        >
          {truncateLabel(`${total}`, 8)}
        </text>
      </svg>
      <Box component="ul" sx={{ pl: 2, my: 0, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
        {pairs.map((p, i) => (
          <Box component="li" key={i} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: 0.5,
                bgcolor: `${PIE_COLORS[i % PIE_COLORS.length]}.main`,
                flexShrink: 0,
              }}
            />
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {truncateLabel(p.label, 24)} · {p.value}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

function EnvelopeChart({ chart, t }) {
  const theme = useTheme();
  if (!chart || typeof chart !== 'object') return null;

  const { chart_type: type = 'bar', title } = chart;
  const pairs = flattenSeries(chart.series);

  return (
    <Box data-testid="envelope-chart">
      {title ? (
        <Typography variant="subtitle2" sx={{ mb: 0.5, fontWeight: 600 }}>
          {cellString(title)}
        </Typography>
      ) : null}
      {pairs.length === 0 ? (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {t('envelope.noData')}
        </Typography>
      ) : (
        <>
          {type === 'pie' && <PieChartSvg pairs={pairs} theme={theme} />}
          {type === 'line' && <LineChartSvg pairs={pairs} theme={theme} />}
          {type !== 'pie' && type !== 'line' && <BarChartSvg pairs={pairs} theme={theme} />}
        </>
      )}
    </Box>
  );
}

EnvelopeChart.propTypes = {
  chart: PropTypes.object,
  t: PropTypes.func.isRequired,
};

// ── Caveats — disclosure banners, level → semantic color ────────────────────

const CAVEAT_LEVEL = {
  info: { color: 'info', Icon: InfoOutlinedIcon },
  warning: { color: 'warning', Icon: WarningAmberOutlinedIcon },
  critical: { color: 'error', Icon: ErrorOutlineOutlinedIcon },
};

function EnvelopeCaveats({ caveats, t }) {
  if (!Array.isArray(caveats) || caveats.length === 0) return null;
  return (
    <Box>
      <SectionLabel>{t('envelope.caveats')}</SectionLabel>
      {caveats.map((c, i) => {
        const level = CAVEAT_LEVEL[c?.level] || CAVEAT_LEVEL.info;
        const Icon = level.Icon;
        return (
          <Box
            key={i}
            data-testid="envelope-caveat"
            sx={(theme) => ({
              display: 'flex',
              alignItems: 'flex-start',
              gap: 1,
              px: 1,
              py: 0.75,
              my: 0.5,
              borderRadius: 1,
              border: 1,
              borderColor: `${level.color}.main`,
              bgcolor: alpha(theme.palette[level.color].main, 0.08),
            })}
          >
            <Icon sx={{ fontSize: 16, color: `${level.color}.main`, mt: 0.125 }} />
            <Typography variant="body2" sx={{ color: 'text.primary', lineHeight: 1.5 }}>
              {c?.text}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );
}

EnvelopeCaveats.propTypes = {
  caveats: PropTypes.array,
  t: PropTypes.func.isRequired,
};

// ── Sources — provenance chips ───────────────────────────────────────────────

function EnvelopeSources({ sources, t }) {
  if (!Array.isArray(sources) || sources.length === 0) return null;
  return (
    <Box>
      <SectionLabel>{t('envelope.sources')}</SectionLabel>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
        {sources.map((src, i) => {
          const parts = [];
          if (src?.tool) parts.push(src.tool);
          if (src?.rows_returned != null) parts.push(t('envelope.rows', { count: src.rows_returned }));
          if (src?.truncated) parts.push(t('envelope.truncated'));
          const resolvedLabel = formatResolvedAt(src?.resolved_at);
          return (
            <Box key={i} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.25 }}>
              <Chip
                data-testid="envelope-source"
                size="small"
                variant="outlined"
                label={parts.join(' · ') || t('envelope.noData')}
              />
              {resolvedLabel ? (
                <Typography variant="caption" sx={{ color: 'text.disabled', px: 0.25 }}>
                  {resolvedLabel}
                </Typography>
              ) : null}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

EnvelopeSources.propTypes = {
  sources: PropTypes.array,
  t: PropTypes.func.isRequired,
};

// ── Public component ─────────────────────────────────────────────────────────

export default function EnvelopeMessage({ envelope, fallbackContent }) {
  const { t } = useTranslation('ai');

  // Zero regression: no envelope (or a malformed one) → existing markdown path.
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) {
    return <MarkdownMessage content={fallbackContent || ''} />;
  }

  const { headline, prose, tables, charts, caveats, sources } = envelope;

  return (
    <Stack spacing={1}>
      {headline ? (
        <Typography
          variant="h6"
          component="div"
          sx={{
            '& p': { fontSize: 'inherit', fontWeight: 'inherit', color: 'inherit', mb: 0 },
          }}
        >
          <MarkdownMessage content={headline} />
        </Typography>
      ) : null}

      {Array.isArray(prose) && prose.length > 0 ? (
        <Stack spacing={0.5}>
          {prose.map((paragraph, i) => (
            <MarkdownMessage key={i} content={paragraph} />
          ))}
        </Stack>
      ) : null}

      <EnvelopeCaveats caveats={caveats} t={t} />

      {Array.isArray(tables) && tables.length > 0 ? (
        <Stack spacing={1}>
          {tables.map((table, i) => (
            <EnvelopeTable key={i} table={table} t={t} />
          ))}
        </Stack>
      ) : null}

      {Array.isArray(charts) && charts.length > 0 ? (
        <Stack spacing={1}>
          {charts.map((chart, i) => (
            <EnvelopeChart key={i} chart={chart} t={t} />
          ))}
        </Stack>
      ) : null}

      <EnvelopeSources sources={sources} t={t} />
    </Stack>
  );
}

EnvelopeMessage.propTypes = {
  envelope: PropTypes.object,
  fallbackContent: PropTypes.string,
};

EnvelopeMessage.defaultProps = {
  envelope: null,
  fallbackContent: '',
};
