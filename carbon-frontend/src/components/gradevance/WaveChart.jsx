// Reflective-wave profile — SG×SD quadrant ladder (Maton & Chen / NAA criteria).
// Source: raw/…/Legitimation Code Theory - Criteria for Reflective Waves
// L4 SG+SD+ specific+reflective · L3 SG-SD+ general+reflective
// L2 SG+SD- specific+descriptive · L1 SG-SD- general+descriptive

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Box, Chip, Paper, Stack, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';

/** Quadrant → wave level (top = 4). Matches Reflective Wave criteria grid. */
export function quadrantLevel(sg, sd) {
  const g = String(sg || '').replace('SG++', 'SG+').replace('SG--', 'SG-');
  const d = String(sd || '');
  const sgPlus = g === 'SG+';
  const sdPlus = d === 'SD+';
  if (sgPlus && sdPlus) return 4;
  if (!sgPlus && sdPlus) return 3;
  if (sgPlus && !sdPlus) return 2;
  return 1;
}

export function toProfileLevel(point = {}) {
  const n = Number(point.profile_level ?? point.sg_level_4);
  if (Number.isFinite(n) && n >= 1 && n <= 4 && (point.sg || point.sd)) {
    // Prefer recomputing from codes when both present (source of truth = quadrant)
    if (point.sg && point.sd) return quadrantLevel(point.sg, point.sd);
    return Math.round(n);
  }
  if (point.sg || point.sd) return quadrantLevel(point.sg, point.sd);
  if (Number.isFinite(n) && n >= 1 && n <= 4) return Math.round(n);
  return 2;
}

const LEVEL_META = {
  4: { code: 'SG+ / SD+', label: 'specific · reflective', color: '#2563eb' },
  3: { code: 'SG− / SD+', label: 'general · reflective', color: '#16a34a' },
  2: { code: 'SG+ / SD−', label: 'specific · descriptive', color: '#ca8a04' },
  1: { code: 'SG− / SD−', label: 'general · descriptive', color: '#db2777' },
};

function codeFor(seg, dimension) {
  return (seg?.codes || []).find((c) => c.dimension === dimension) || null;
}

function smoothPath(pts) {
  if (!pts.length) return '';
  if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
  if (pts.length === 2) return `M ${pts[0].x} ${pts[0].y} L ${pts[1].x} ${pts[1].y}`;
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
  }
  return d;
}

function moveGlyph(move) {
  if (move === 'up') return '↑';
  if (move === 'down') return '↓';
  if (move === 'flat') return '→';
  return '';
}

export default function WaveChart({
  points = [],
  segments = [],
  height = 280,
  showText = true,
}) {
  const theme = useTheme();
  const uid = useId().replace(/:/g, '');
  const gradId = `wave-fill-${uid}`;
  const stripRef = useRef(null);
  const [hoverIdx, setHoverIdx] = useState(null);
  const [pinnedIdx, setPinnedIdx] = useState(null);
  const [drawn, setDrawn] = useState(false);

  const series = useMemo(() => {
    if (!points.length) return [];
    return points.map((p, i) => {
      const seg = segments.find((s, idx) => (s.ordinal ?? idx) === (p.ordinal ?? i))
        || segments[i]
        || null;
      const sgCode = codeFor(seg, 'semantic_gravity');
      const sdCode = codeFor(seg, 'semantic_density');
      const sg = p.sg || sgCode?.value || 'SG-';
      const sd = p.sd || sdCode?.value || 'SD-';
      const level = toProfileLevel({ ...p, sg, sd });
      const progress = Number.isFinite(p.progress)
        ? p.progress
        : Number.isFinite(p.end_word)
          ? p.end_word
          : (p.word_offset ?? (i + 1) * 10);
      const justification = (
        sgCode?.evidence?.justification
        || sdCode?.evidence?.justification
        || p.justification
        || ''
      );
      let move = p.sg_move;
      if (!move && i > 0) {
        const prev = toProfileLevel({
          ...points[i - 1],
          sg: points[i - 1].sg || codeFor(segments[i - 1], 'semantic_gravity')?.value,
          sd: points[i - 1].sd || codeFor(segments[i - 1], 'semantic_density')?.value,
        });
        move = level > prev ? 'up' : (level < prev ? 'down' : 'flat');
      }
      if (i === 0) move = move || 'start';
      return {
        i,
        ordinal: p.ordinal ?? i,
        level,
        progress,
        sg,
        sd,
        meta: LEVEL_META[level],
        stage: p.stage_guess || p.stage || seg?.stage_guess || '',
        text: p.text || seg?.text || '',
        justification,
        move,
      };
    });
  }, [points, segments]);

  useEffect(() => {
    const t = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(t);
  }, [series.length]);

  useEffect(() => {
    if (pinnedIdx == null || !stripRef.current) return;
    const el = stripRef.current.querySelector(`[data-seg-idx="${pinnedIdx}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  }, [pinnedIdx]);

  if (!series.length) {
    return <Typography variant="caption" color="text.secondary">No wave points</Typography>;
  }

  const ml = 108;
  const mr = 20;
  const mt = 28;
  const mb = 40;
  const w = Math.max(480, 120 + series.length * 88);
  const h = height;
  const plotW = w - ml - mr;
  const plotH = h - mt - mb;

  const maxX = Math.max(...series.map((p) => p.progress), 1);
  const toX = (x) => ml + (x / maxX) * plotW;
  const toY = (lvl) => mt + ((4 - lvl) / 3) * plotH;

  const xy = series.map((p) => ({ x: toX(p.progress), y: toY(p.level) }));
  const lineD = smoothPath(xy);
  const areaD = series.length
    ? `${lineD} L ${xy[xy.length - 1].x} ${mt + plotH} L ${xy[0].x} ${mt + plotH} Z`
    : '';

  const activeIdx = hoverIdx != null ? hoverIdx : pinnedIdx;
  const active = activeIdx != null ? series[activeIdx] : null;
  const transitions = series.filter((p) => p.move === 'up' || p.move === 'down').length;
  const stroke = theme.palette.primary.main;
  const ink = theme.palette.text.secondary;
  const grid = alpha(theme.palette.text.primary, 0.1);

  return (
      <Box data-testid="semantic-wave-chart" sx={{ width: '100%', position: 'relative' }} dir="ltr">
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.25 }} alignItems="center">
        <Chip size="small" label={`${series.length} segments`} variant="outlined" />
        <Chip size="small" label={`${transitions} swings`} variant="outlined" />
        <Typography variant="caption" color="text.secondary">
          Reflective wave · SG×SD criteria grid (Maton &amp; Chen)
        </Typography>
      </Stack>

      <Box sx={{ overflowX: 'auto', position: 'relative' }}>
        <svg width={w} height={h} role="img" aria-label="Reflective semantic wave SG by SD" style={{ display: 'block' }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity="0.2" />
              <stop offset="100%" stopColor={stroke} stopOpacity="0.02" />
            </linearGradient>
          </defs>

          <rect x={ml} y={mt} width={plotW} height={plotH} fill={alpha(theme.palette.text.primary, 0.02)} stroke={grid} rx={6} />

          {[4, 3, 2, 1].map((lvl) => {
            const meta = LEVEL_META[lvl];
            const y = toY(lvl);
            return (
              <g key={`rail-${lvl}`}>
                <line
                  x1={ml}
                  x2={ml + plotW}
                  y1={y}
                  y2={y}
                  stroke={meta.color}
                  strokeWidth={1.75}
                  strokeDasharray="5 4"
                  opacity={0.85}
                />
                <rect
                  x={8}
                  y={y - 11}
                  width={92}
                  height={20}
                  rx={4}
                  fill={alpha(meta.color, 0.12)}
                  stroke={meta.color}
                  strokeWidth={1}
                />
                <text x={54} y={y + 4} fontSize={10} fill={meta.color} textAnchor="middle" fontWeight={700}>
                  {meta.code}
                </text>
              </g>
            );
          })}

          {areaD && (
            <path d={areaD} fill={`url(#${gradId})`} opacity={drawn ? 1 : 0} style={{ transition: 'opacity 0.45s ease' }} />
          )}
          <path
            d={lineD}
            fill="none"
            stroke={stroke}
            strokeWidth={2.75}
            strokeLinejoin="round"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={drawn ? 0 : 1}
            style={{ transition: 'stroke-dashoffset 0.55s ease' }}
          />

          {series.map((p, i) => {
            const cx = toX(p.progress);
            const cy = toY(p.level);
            const isOn = activeIdx === i;
            const c = p.meta.color;
            return (
              <g
                key={`node-${i}`}
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoverIdx(i)}
                onMouseLeave={() => setHoverIdx(null)}
                onClick={() => setPinnedIdx((cur) => (cur === i ? null : i))}
                role="button"
                tabIndex={0}
                aria-label={`Segment ${p.ordinal + 1}, level ${p.level}, ${p.sg} ${p.sd}`}
              >
                <circle cx={cx} cy={cy} r={isOn ? 14 : 11} fill={alpha(c, isOn ? 0.22 : 0.08)} />
                <circle cx={cx} cy={cy} r={6} fill={theme.palette.background.paper} stroke={c} strokeWidth={isOn ? 3 : 2.25} />
                <text x={cx} y={cy - 16} fontSize={10} fill={theme.palette.text.primary} textAnchor="middle" fontWeight={700}>
                  S{p.ordinal + 1}{moveGlyph(p.move) ? ` ${moveGlyph(p.move)}` : ''}
                </text>
                <text x={cx} y={mt + plotH + 18} fontSize={9} fill={ink} textAnchor="middle">
                  {Math.round(p.progress)}
                </text>
              </g>
            );
          })}

          <text x={ml + plotW / 2} y={h - 6} fontSize={11} fill={ink} textAnchor="middle" fontWeight={600}>
            TIME / No of Words →
          </text>
        </svg>

        {active && (
          <Paper
            elevation={3}
            data-testid="wave-hover-card"
            // Inline left/top — SVG plot coords must not be mirrored by stylis RTL.
            style={{
              position: 'absolute',
              left: Math.min(Math.max(toX(active.progress) - 120, 8), w - 260),
              top: Math.max(toY(active.level) - 110, 4),
              width: 240,
              padding: 10,
              pointerEvents: 'none',
              zIndex: 2,
              border: '1px solid',
              borderColor: theme.palette.divider,
              backgroundColor: alpha(theme.palette.background.paper, 0.97),
            }}
          >
            <Typography variant="caption" fontWeight={700} display="block">
              Seg {active.ordinal + 1} · L{active.level} {moveGlyph(active.move)}
              {active.stage ? ` · ${active.stage}` : ''}
            </Typography>
            <Stack direction="row" spacing={0.5} sx={{ my: 0.5 }} flexWrap="wrap" useFlexGap>
              <Chip size="small" sx={{ bgcolor: alpha(active.meta.color, 0.15), color: active.meta.color }} label={active.meta.code} />
              <Chip size="small" variant="outlined" label={active.meta.label} />
            </Stack>
            {active.justification ? (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.35 }}>
                {String(active.justification).slice(0, 180)}
                {String(active.justification).length > 180 ? '…' : ''}
              </Typography>
            ) : (
              <Typography variant="caption" color="text.secondary">
                Word {Math.round(active.progress)} · {active.sg} × {active.sd}
              </Typography>
            )}
          </Paper>
        )}
      </Box>

      {/* Criteria legend */}
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1 }} aria-label="Reflective wave levels">
        {[4, 3, 2, 1].map((lvl) => (
          <Chip
            key={`leg-${lvl}`}
            size="small"
            variant="outlined"
            label={`L${lvl} ${LEVEL_META[lvl].code}`}
            sx={{
              borderColor: LEVEL_META[lvl].color,
              color: LEVEL_META[lvl].color,
              '& .MuiChip-label': { fontSize: '0.7rem' },
            }}
          />
        ))}
      </Stack>

      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 1 }} aria-label="Level readout">
        <Typography variant="caption" color="text.secondary" fontWeight={600}>Profile</Typography>
        {series.map((p, i) => (
          <Chip
            key={`spark-${i}`}
            size="small"
            variant={activeIdx === i ? 'filled' : 'outlined'}
            label={`L${p.level}@${Math.round(p.progress)}`}
            onClick={() => setPinnedIdx(i)}
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx(null)}
            sx={{
              height: 22,
              borderColor: p.meta.color,
              bgcolor: activeIdx === i ? alpha(p.meta.color, 0.2) : undefined,
              '& .MuiChip-label': { px: 0.75, fontSize: '0.7rem' },
            }}
          />
        ))}
      </Stack>

      {showText && series.some((p) => p.text) && (
        <Box
          ref={stripRef}
          component="article"
          aria-label="Wave-aligned essay segments"
          sx={{
            mt: 1.5,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 0.5,
            maxHeight: 220,
            overflow: 'auto',
            p: 1,
            borderRadius: 1.5,
            border: '1px solid',
            borderColor: 'divider',
            bgcolor: alpha(theme.palette.text.primary, 0.02),
          }}
        >
          {series.map((p, i) => {
            const on = activeIdx === i;
            return (
              <Box
                key={`strip-${i}`}
                component="button"
                type="button"
                data-seg-idx={i}
                onClick={() => setPinnedIdx(i)}
                onMouseEnter={() => setHoverIdx(i)}
                onMouseLeave={() => setHoverIdx(null)}
                title={p.meta.label}
                sx={{
                  all: 'unset',
                  cursor: 'pointer',
                  flex: '1 1 160px',
                  maxWidth: '100%',
                  p: 1,
                  borderRadius: 1,
                  lineHeight: 1.55,
                  fontSize: '0.8rem',
                  bgcolor: on ? alpha(p.meta.color, 0.14) : alpha(p.meta.color, 0.05),
                  outline: on ? `2px solid ${p.meta.color}` : `1px solid ${alpha(p.meta.color, 0.25)}`,
                  transition: 'background-color 0.2s ease, outline-color 0.2s ease',
                }}
              >
                <Typography variant="caption" fontWeight={700} display="block" sx={{ mb: 0.35, color: p.meta.color }}>
                  S{p.ordinal + 1} · L{p.level} · {p.meta.code}
                </Typography>
                <Typography variant="body2" component="span">{p.text}</Typography>
              </Box>
            );
          })}
        </Box>
      )}
    </Box>
  );
}
