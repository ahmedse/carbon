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
import { useIsMobile } from '../hooks/useIsMobile';
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
import { presentCaveats, presentSources } from './presentationPlane';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from 'chart.js';

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, ChartTooltip, Legend, Filler,
);

// Fixed render height so a chart never dominates or overlaps the thread.
const CHART_HEIGHT = 240;

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

// ── Charts ── Card shell + Chart.js with rich options ────────────────────────

const PALETTE = (theme) => [
  theme.palette.primary.main,
  theme.palette.info.main,
  theme.palette.warning.main,
  theme.palette.success.main,
  theme.palette.error.main,
  theme.palette.secondary.main,
];

// Inline Chart.js plugin — draws center text inside a Doughnut.
const centerTextPlugin = {
  id: 'centerText',
  afterDraw(chart) {
    const { ctx, data, chartArea } = chart;
    if (!chartArea) return;
    const total = (data.datasets[0]?.data || []).reduce((a, b) => a + Number(b), 0);
    if (!total) return;
    const cx = (chartArea.left + chartArea.right) / 2;
    const cy = (chartArea.top + chartArea.bottom) / 2;
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = `600 13px ${chart.options.plugins?.legend?.labels?.font?.family || 'inherit'}`;
    ctx.fillStyle = chart.options.plugins?.legend?.labels?.color || '#555';
    ctx.fillText(Number(total).toLocaleString(), cx, cy);
    ctx.restore();
  },
};

function EnvelopeChart({ chart, t }) {
  const theme = useTheme();
  const isMobile = useIsMobile();
  if (!chart || typeof chart !== 'object') return null;

  const { chart_type: type = 'bar', title } = chart;
  const pairs = flattenSeries(chart.series);
  // Trust fix: never render a titled "No data" shell when series is empty.
  // Also skip single-point bars (e.g. lone headcount) — prose carries the scalar.
  if (pairs.length < 2) {
    return null;
  }

  const labels = pairs.map((p) => truncateLabel(p.label, 18));
  const values = pairs.map((p) => p.value);
  const palette = PALETTE(theme);

  const sharedTooltip = {
    backgroundColor: theme.palette.grey[900],
    titleColor: '#fff',
    bodyColor: alpha(theme.palette.common.white, 0.85),
    titleFont: { size: 12, weight: '600' },
    bodyFont: { size: 11 },
    padding: 10,
    cornerRadius: 8,
    displayColors: true,
    boxWidth: 10,
    boxHeight: 10,
  };

  let ChartComp, data, options, plugins;

  if (type === 'pie') {
    ChartComp = Doughnut;
    plugins = [centerTextPlugin];
    data = {
      labels,
      datasets: [{
        data: values,
        backgroundColor: palette.map((c, i) => i < values.length ? c : undefined).filter(Boolean),
        borderColor: theme.palette.background.paper,
        borderWidth: 3,
        hoverOffset: 6,
      }],
    };
    options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { animateRotate: true, duration: 700 },
      cutout: '62%',
      plugins: {
        legend: {
          position: isMobile ? 'bottom' : 'right',
          labels: {
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 14,
            font: { size: 11, family: theme.typography.fontFamily },
            color: theme.palette.text.secondary,
            generateLabels: (ch) => {
              const ds = ch.data.datasets[0];
              const total = (ds.data || []).reduce((a, b) => a + Number(b), 0);
              return ch.data.labels.map((lbl, i) => {
                const pct = total ? ((Number(ds.data[i]) / total) * 100).toFixed(0) : 0;
                return {
                  text: `${lbl}  ${pct}%`,
                  fillStyle: ds.backgroundColor[i],
                  strokeStyle: ds.backgroundColor[i],
                  hidden: false,
                  index: i,
                };
              });
            },
          },
        },
        tooltip: {
          ...sharedTooltip,
          callbacks: {
            label: (c) => {
              const total = c.dataset.data.reduce((a, b) => a + Number(b), 0);
              const pct = total ? ((c.parsed / total) * 100).toFixed(1) : 0;
              return `  ${c.label}: ${Number(c.parsed).toLocaleString()}  (${pct}%)`;
            },
          },
        },
      },
    };
  } else if (type === 'line') {
    ChartComp = Line;
    plugins = [];
    data = {
      labels,
      datasets: [{
        label: (chart.series?.[0]?.name) || title || '',
        data: values,
        borderColor: theme.palette.primary.main,
        backgroundColor: alpha(theme.palette.primary.main, 0.15),
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: theme.palette.primary.main,
        borderWidth: 2.5,
      }],
    };
    options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...sharedTooltip,
          callbacks: { label: (c) => `  ${c.dataset.label || ''}: ${Number(c.parsed.y).toLocaleString()}` },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: alpha(theme.palette.divider, 0.7) },
          ticks: { font: { size: 10 }, color: theme.palette.text.disabled, callback: (v) => Number(v).toLocaleString() },
          border: { display: false },
        },
        x: {
          grid: { display: false },
          ticks: { font: { size: 10 }, color: theme.palette.text.disabled, maxRotation: 0 },
          border: { display: false },
        },
      },
    };
  } else {
    // bar (default)
    ChartComp = Bar;
    plugins = [];
    data = {
      labels,
      datasets: [{
        label: (chart.series?.[0]?.name) || title || '',
        data: values,
        backgroundColor: labels.map((_, i) => alpha(palette[i % palette.length], 0.85)),
        hoverBackgroundColor: labels.map((_, i) => palette[i % palette.length]),
        borderRadius: 6,
        borderSkipped: false,
        maxBarThickness: 52,
      }],
    };
    options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600 },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...sharedTooltip,
          callbacks: {
            label: (c) => {
              const total = c.dataset.data.reduce((a, b) => a + Number(b), 0);
              const pct = total ? ` (${((Number(c.parsed.y) / total) * 100).toFixed(1)}%)` : '';
              return `  ${Number(c.parsed.y).toLocaleString()}${pct}`;
            },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: alpha(theme.palette.divider, 0.7), drawBorder: false },
          ticks: { font: { size: 10 }, color: theme.palette.text.disabled, callback: (v) => Number(v).toLocaleString() },
          border: { display: false },
        },
        x: {
          grid: { display: false },
          ticks: { font: { size: 10 }, color: theme.palette.text.disabled, maxRotation: 0 },
          border: { display: false },
        },
      },
    };
  }

  return (
    <Box
      data-testid="envelope-chart"
      sx={{
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        p: 2,
        boxShadow: '0 1px 4px 0 rgba(0,0,0,0.06)',
      }}
    >
      {title ? (
        <Typography
          variant="subtitle2"
          sx={{ mb: 1.5, fontWeight: 700, color: 'text.primary', letterSpacing: 0 }}
        >
          {cellString(title)}
        </Typography>
      ) : null}
      <Box sx={{ height: 260 }}>
        <ChartComp data={data} options={options} plugins={plugins} />
      </Box>
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
  const presented = presentCaveats(caveats, 'operator', {
    chatCannotSubmit: t('envelope.chatCannotSubmit'),
  });
  if (presented.length === 0) return null;
  return (
    <Box>
      <SectionLabel>{t('envelope.caveats')}</SectionLabel>
      {presented.map((c, i) => {
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
              {c.text}
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
  const { chips, softFallback } = presentSources(sources, 'operator', {
    rows: (count) => t('envelope.rows', { count }),
    truncated: t('envelope.truncated'),
  });
  if (!chips.length && !softFallback) return null;
  return (
    <Box data-testid="envelope-sources">
      <SectionLabel>{t('envelope.basedOn')}</SectionLabel>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
        {softFallback ? (
          <Chip
            data-testid="envelope-source"
            size="small"
            variant="outlined"
            label={t('envelope.yourRecords')}
          />
        ) : (
          chips.map((chip, i) => (
            <Box key={i} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.25 }}>
              <Chip
                data-testid="envelope-source"
                size="small"
                variant="outlined"
                label={chip.label}
              />
              {chip.resolvedAt ? (
                <Typography variant="caption" sx={{ color: 'text.disabled', px: 0.25 }}>
                  {formatResolvedAt(chip.resolvedAt)}
                </Typography>
              ) : null}
            </Box>
          ))
        )}
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
    <Stack
      spacing={2}
      sx={{
        width: '100%',
        maxWidth: '100%',
        '& .MuiTypography-root': { maxWidth: '72ch' },
      }}
    >
      {headline ? (
        <Typography
          variant="h5"
          component="div"
          sx={{
            fontWeight: 700,
            letterSpacing: '-0.01em',
            lineHeight: 1.35,
            color: 'text.primary',
            maxWidth: '56ch',
            '& p': {
              fontSize: 'inherit',
              fontWeight: 'inherit',
              color: 'inherit',
              mb: 0,
              lineHeight: 'inherit',
            },
          }}
        >
          <MarkdownMessage content={headline} />
        </Typography>
      ) : null}

      {Array.isArray(prose) && prose.length > 0 ? (
        <Stack
          spacing={1.25}
          sx={{
            color: 'text.secondary',
            '& p': { fontSize: '0.975rem', lineHeight: 1.75, mb: 0 },
          }}
        >
          {prose.map((paragraph, i) => (
            <MarkdownMessage key={i} content={paragraph} />
          ))}
        </Stack>
      ) : null}

      <EnvelopeCaveats caveats={caveats} t={t} />

      {Array.isArray(tables) && tables.length > 0 ? (
        <Stack spacing={1.5} sx={{ width: '100%', maxWidth: '100%', '& .MuiTypography-root': { maxWidth: 'none' } }}>
          {tables.map((table, i) => (
            <EnvelopeTable key={i} table={table} t={t} />
          ))}
        </Stack>
      ) : null}

      {Array.isArray(charts) && charts.length > 0 ? (
        <Stack spacing={1.5} sx={{ width: '100%', maxWidth: '100%', '& .MuiTypography-root': { maxWidth: 'none' } }}>
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
