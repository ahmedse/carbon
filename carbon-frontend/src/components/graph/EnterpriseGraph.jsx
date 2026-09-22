// src/components/graph/EnterpriseGraph.jsx
// Layer-2 PRIMITIVE — a reusable, enterprise-grade graph/chart surface.
//
// This is the ONE shared component every visual graph/diagram in the platform
// renders through (plan DAG, agent topology, run timeline, future charts). It
// owns the interaction contract so every graph gets an IDENTICAL, modern,
// enterprise look & feel with zero per-graph code:
//
//   • MOVABLE canvas   — drag empty space to pan
//   • MOVABLE nodes    — drag a node to reposition it (free-form, saved per-node)
//   • RESIZABLE nodes  — drag the bottom-right handle to resize a node
//   • ZOOM             — wheel zoom + toolbar zoom in/out + zoom-to-fit
//   • REDRAW           — re-run the auto-layout (drops node position/size overrides)
//   • RESET            — restore zoom=1, pan=0
//   • EXPORT           — download the graph as a PNG (SVG → canvas, 2×)
//   • MAXIMIZE         — open the graph in a full-screen modal
//   • LIVE STATUS      — "running" nodes pulse with an animated outline
//
// Design rules honoured: RULE_1/RULE_8 (theme tokens only, never raw hex),
// RULE_2 (reuse before create — this IS the reusable primitive), RULE_3
// (compact density), RULE_5 (status as first-class, dot + label).
//
// The caller supplies the domain data (laid nodes/edges, phase lanes, node
// interior via `renderNode`, and an optional docked `sidebar`) — this component
// stays purely presentational (no fetching).
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Dialog,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined';
import CenterFocusStrongOutlinedIcon from '@mui/icons-material/CenterFocusStrongOutlined';
import CloseIcon from '@mui/icons-material/Close';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import { nodeShapePath, nodeShapeInnerPath } from './planGraphShapes';
import {
  computeEdgePath,
  computeBackEdgePath,
  assignCorridorOffsets,
} from '../../utils/graphEdgePath';

const ZOOM_MIN = 0.25;
const ZOOM_MAX = 3;
const ZOOM_STEP = 1.15;
/** Prefer pan/scroll over shrinking node type below readable size in the Pulse rail. */
const FIT_ZOOM_FLOOR = 0.55;
/**
 * Never auto-upscale. SVG `meet` + zoom>1 double-scales and blows compact
 * plans into a single giant clipped card ("graph corrupted"). Letterbox via
 * viewBox padding instead so small DAGs stay native size in the rail.
 */
const FIT_ZOOM_CEIL = 1;
const NODE_MIN_W = 120;
const NODE_MAX_W = 640;
const NODE_MIN_H = 48;
const NODE_MAX_H = 320;
const DRAG_THRESHOLD = 3;
const MINIMAP_NODE_THRESHOLD = 12;

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function edgePath(sx, sy, tx, ty, direction = 'lr', laneOffset = 0, isBack = false) {
  if (isBack && direction === 'tb') {
    return computeBackEdgePath(sx, sy, tx, ty, Math.min(sx, tx) - 28 + (laneOffset || 0));
  }
  return computeEdgePath(sx, sy, tx, ty, direction, laneOffset);
}

/**
 * Serialize the live SVG to a PNG download (2× resolution). Best-effort: in a
 * non-browser (jsdom/test) it no-ops gracefully.
 */
function exportSvgToPng(svgEl, viewW, viewH, background, fileName) {
  if (typeof XMLSerializer === 'undefined') return;
  if (typeof URL === 'undefined' || !URL.createObjectURL) return;
  try {
    const clone = svgEl.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(viewW));
    clone.setAttribute('height', String(viewH));

    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('width', '100%');
    bg.setAttribute('height', '100%');
    bg.setAttribute('fill', background);
    clone.insertBefore(bg, clone.firstChild);

    const xml = new XMLSerializer().serializeToString(clone);
    const blob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const scale = 2;
      const canvas = document.createElement('canvas');
      canvas.width = viewW * scale;
      canvas.height = viewH * scale;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob((png) => {
        if (!png) return;
        const a = document.createElement('a');
        a.href = URL.createObjectURL(png);
        a.download = `${fileName}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      }, 'image/png');
    };
    img.src = url;
  } catch {
    /* non-browser environment — no-op */
  }
}

/** A single compact toolbar action (RULE_3 density). */
function Tool({ label, onClick, testId, children, disabled = false }) {
  return (
    <Tooltip title={label} arrow>
      <span>
        <IconButton
          size="small"
          onClick={onClick}
          aria-label={label}
          data-testid={testId}
          disabled={disabled}
          sx={{ p: 0.5 }}
        >
          {children}
        </IconButton>
      </span>
    </Tooltip>
  );
}

/**
 * EnterpriseGraph — the shared interactive graph/chart surface.
 *
 * @param {Array} nodes — laid nodes {id,label,subtitle?,status?,x,y,w,h,phase_id?,…}
 * @param {Array} edges — {source,target,label?}
 * @param {Array} phaseBands — {phase_id,name,x,width,strategy?}
 * @param {function} phaseColor — (phase_id) => theme color token
 * @param {function} nodeColor — (node) => theme color token (status colour)
 * @param {function} renderNode — (node) => node interior SVG elements
 * @param {number} width — layout width (SVG content units)
 * @param {number} layoutHeight — layout height (SVG content units)
 * @param {number} height — inline viewport height (px)
 * @param {boolean} fill — render to fill the container (full-screen modal)
 * @param {object} selected — currently selected node (or null)
 * @param {function} onSelect — (node|null) => void
 * @param {object|null} [selectedEdge] — currently selected edge {source,target,…}
 * @param {function} [onSelectEdge] — (edge|null) => void
 * @param {function} [nodeTitle] — (node) => tooltip string (SVG <title>)
 * @param {function} [edgeTitle] — (edge) => tooltip string
 * @param {boolean} [showStatusPulse] — animate running-node outline (default true)
 * @param {ReactNode} legend — legend row rendered above the canvas
 * @param {function} sidebar — (variant: 'inline'|'modal') => docked detail pane
 * @param {string} title — header title
 * @param {string} summary — header summary text (counts)
 * @param {boolean} live — show the Live badge (a run is in progress)
 * @param {string} markerId — arrowhead marker id (unique per SVG instance)
 * @param {string} testId — base data-testid for the canvas
 * @param {string} modalTestId — data-testid for the full-screen dialog
 * @param {string} modalCloseTestId — data-testid for the modal close button
 * @param {string} expandTestId — data-testid for the maximize button
 * @param {string} exportFileName — downloaded PNG filename (no extension)
 * @param {'lr'|'tb'} [direction] — edge flow; must match layoutExecutionGraph
 */
export default function EnterpriseGraph({
  nodes = [],
  edges = [],
  phaseBands = [],
  phaseColor = () => undefined,
  nodeColor = () => undefined,
  renderNode,
  nodeShape,
  edgeStyle,
  width = 960,
  layoutHeight = 420,
  height = 380,
  fill = false,
  selected,
  onSelect,
  selectedEdge = null,
  onSelectEdge,
  nodeTitle,
  edgeTitle,
  showStatusPulse = true,
  legend = null,
  sidebar,
  title = 'Graph',
  modalTitle,
  summary = '',
  live = false,
  emptyMessage = 'Nothing to show yet.',
  nodeAriaLabel,
  markerId = 'graph-arrow',
  modalMarkerId,
  testId = 'enterprise-graph',
  modalTestId = 'graph-modal',
  modalCloseTestId = 'graph-modal-close',
  expandTestId = 'graph-maximize',
  exportFileName = 'graph',
  direction = 'lr',
  /** 'contain' = fit both axes (may shrink); 'width' = fit width only; 'none' = 1× */
  fitMode = 'contain',
  /** Cap auto-fit scale-up (Plan graphs pass 1 — never blow up skinny DAGs). */
  fitZoomCeil = FIT_ZOOM_CEIL,
  /** Size the canvas to layoutHeight instead of stretching SVG into a tall empty rail. */
  contentSized = false,
  /** Set of node ids on the focus path — others are dimmed. Null = no dimming. */
  focusIds = null,
  /** Active step id for token accent (Run token strip). */
  tokenNodeId = null,
  /** Force minimap on/off; null = auto when visible nodes exceed threshold. */
  showMinimap = null,
}) {
  const theme = useTheme();
  const svgRef = useRef(null);
  const canvasRef = useRef(null);
  const drag = useRef(null);
  const moved = useRef(false);
  const [dragging, setDragging] = useState(false);

  // Viewport (move/resize the whole canvas) + per-node position/size overrides
  // (move/resize individual nodes, free-form).
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [overrides, setOverrides] = useState({});
  const [expanded, setExpanded] = useState(false);
  const [viewport, setViewport] = useState({ w: 0, h: 0 });

  const setZoomClamped = useCallback((updater) => {
    setZoom((z) => clamp(typeof updater === 'function' ? updater(z) : updater, ZOOM_MIN, ZOOM_MAX));
  }, []);

  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const redraw = useCallback(() => {
    setOverrides({});
    resetView();
  }, [resetView]);

  // Effective geometry: layout position/size unless the user moved/resized it.
  // The override is MERGED ON TOP of the layout node (not field-by-field) so a
  // partial override never erases the other geometry: a pure node-drag stores
  // only {x,y} and must keep the layout w/h, and a pure resize stores only
  // {w,h} and must keep the layout x/y. The old per-field copy (`x: o.x, y: o.y,
  // w: o.w, h: o.h`) wrote `undefined` for the missing field, so a moved node
  // collapsed to 0×0 and a resized node rendered `translate(NaN, NaN)`.
  const effectiveNodes = useMemo(
    () =>
      nodes.map((n) => {
        const o = overrides[n.id];
        return o ? { ...n, ...o } : n;
      }),
    [nodes, overrides],
  );

  const nodeById = useMemo(() => {
    const m = new Map();
    effectiveNodes.forEach((n) => m.set(n.id, n));
    return m;
  }, [effectiveNodes]);

  // Edges are re-anchored to the CURRENT node geometry so they stay glued to
  // nodes as the user drags/resizes them. Corridor offsets stagger parallel links.
  const effectiveEdges = useMemo(
    () => {
      const anchored = edges
        .map((e) => {
          const s = nodeById.get(e.source);
          const t = nodeById.get(e.target);
          if (!s || !t) return null;
          // Dummies are point nodes (w/h = 0, x/y already the channel mid).
          const sDummy = Boolean(s.is_dummy) || !(s.w > 0);
          const tDummy = Boolean(t.is_dummy) || !(t.w > 0);
          if (direction === 'tb') {
            return {
              ...e,
              sourceX: sDummy ? s.x : s.x + s.w / 2,
              sourceY: sDummy ? s.y : (e.is_back_edge ? s.y : s.y + s.h),
              targetX: tDummy ? t.x : t.x + t.w / 2,
              targetY: tDummy ? t.y : (e.is_back_edge ? t.y + t.h : t.y),
            };
          }
          return {
            ...e,
            sourceX: sDummy ? s.x : (e.is_back_edge ? s.x : s.x + s.w),
            sourceY: sDummy ? s.y : s.y + s.h / 2,
            targetX: tDummy ? t.x : (e.is_back_edge ? t.x + t.w : t.x),
            targetY: tDummy ? t.y : t.y + t.h / 2,
          };
        })
        .filter(Boolean);
      return assignCorridorOffsets(anchored, direction, 6);
    },
    [edges, nodeById, direction],
  );

  const visibleCount = useMemo(
    () => effectiveNodes.filter((n) => !n.is_dummy).length,
    [effectiveNodes],
  );
  const minimapOn = showMinimap == null
    ? visibleCount > MINIMAP_NODE_THRESHOLD || layoutHeight > height * 1.6
    : Boolean(showMinimap);

  const isDimmed = useCallback(
    (id) => focusIds != null && focusIds.size > 0 && !focusIds.has(id),
    [focusIds],
  );
  const edgeDimmed = useCallback(
    (e) => focusIds != null && focusIds.size > 0
      && (!focusIds.has(e.source) || !focusIds.has(e.target)),
    [focusIds],
  );

  // ViewBox is at least the canvas box (in px ≅ user units at zoom 1) so
  // preserveAspectRatio=meet cannot upscale a skinny DAG into a giant card.
  // Layout content sits top-left; extra space is empty letterboxing.
  const viewW = Math.max(1, width, viewport.w || 0);
  const viewH = Math.max(1, layoutHeight, viewport.h || 0);
  const transform = `translate(${pan.x}, ${pan.y}) scale(${zoom})`;

  // ── Pointer interaction (pan canvas / drag node / resize node) ──────────
  const startPan = (e) => {
    if (e.button !== 0) return;
    moved.current = false;
    drag.current = { mode: 'pan', startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
    setDragging(true);
  };

  const startNodeDrag = (e, node) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    moved.current = false;
    // Snapshot x/y from the EFFECTIVE node (layout + overrides merged) so a
    // drag that follows a resize starts from the resized position, not a
    // stale layout position (W5-E drag/resize NaN fix).
    const en = nodeById.get(node.id) || node;
    drag.current = { mode: 'node', id: node.id, startX: e.clientX, startY: e.clientY, origX: en.x, origY: en.y };
    setDragging(true);
  };

  const startResize = (e, node) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    moved.current = false;
    // Snapshot w/h from the EFFECTIVE node so a resize that follows a drag
    // keeps the dragged x/y and never computes NaN from a missing origin.
    const en = nodeById.get(node.id) || node;
    drag.current = { mode: 'resize', id: node.id, startX: e.clientX, startY: e.clientY, origW: en.w ?? node.w, origH: en.h ?? node.h };
    setDragging(true);
  };

  const onMouseMove = useCallback(
    (e) => {
      if (!drag.current) return;
      const dx = e.clientX - drag.current.startX;
      const dy = e.clientY - drag.current.startY;
      if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) moved.current = true;

      // Below the drag threshold the gesture is a click, not a drag. Do NOT move
      // the node/canvas — otherwise the pointer drifts off the element and the
      // browser synthesizes the `click` on an ancestor (e.g. <svg>), so the
      // node's own onClick never fires and selection silently breaks.
      if (!moved.current) return;

      if (drag.current.mode === 'pan') {
        setPan({ x: drag.current.panX + dx, y: drag.current.panY + dy });
      } else if (drag.current.mode === 'node') {
        setOverrides((prev) => ({
          ...prev,
          [drag.current.id]: { ...prev[drag.current.id], x: drag.current.origX + dx / zoom, y: drag.current.origY + dy / zoom },
        }));
      } else if (drag.current.mode === 'resize') {
        setOverrides((prev) => {
          const prevO = prev[drag.current.id];
          return {
            ...prev,
            [drag.current.id]: {
              ...prevO,
              w: clamp(drag.current.origW + dx / zoom, NODE_MIN_W, NODE_MAX_W),
              h: clamp(drag.current.origH + dy / zoom, NODE_MIN_H, NODE_MAX_H),
            },
          };
        });
      }
    },
    [zoom],
  );

  const endDrag = useCallback(() => {
    drag.current = null;
    setDragging(false);
  }, []);

  // Track the drag globally so a node/canvas keeps following the pointer even
  // when the cursor leaves the graph surface mid-drag (e.g. resizing a node
  // beyond the canvas edge). Without this, `onMouseLeave` would end the drag
  // early and the node would stop short of the clamped bounds.
  useEffect(() => {
    if (!dragging) return undefined;
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', endDrag);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', endDrag);
    };
  }, [dragging, onMouseMove, endDrag]);

  const onNodeClick = (node) => {
    if (moved.current) return; // a drag, not a click
    onSelectEdge?.(null);
    onSelect?.(selected?.id === node.id ? null : node);
  };

  const onEdgeClick = (edge, evt) => {
    if (moved.current) return;
    evt?.stopPropagation?.();
    onSelect?.(null);
    const same = selectedEdge
      && String(selectedEdge.source) === String(edge.source)
      && String(selectedEdge.target) === String(edge.target);
    onSelectEdge?.(same ? null : edge);
  };

  const exportPng = useCallback(() => {
    if (svgRef.current) {
      exportSvgToPng(svgRef.current, viewW, viewH, theme.palette.background.paper, exportFileName);
    }
  }, [viewW, viewH, theme, exportFileName]);

  // Measure the real canvas box so fit/zoom use the Pulse rail width, not the
  // SVG viewBox (which tracks layout width and made fitView a no-op).
  useEffect(() => {
    const el = canvasRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (!box) return;
      setViewport({ w: box.width, h: box.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [expanded, fill]);

  const fitView = useCallback(() => {
    if (fitMode === 'none') {
      setZoomClamped(1);
      setPan({ x: 0, y: 0 });
      return;
    }
    const availW = viewport.w > 0 ? viewport.w : Math.max(width, 1);
    const availH = viewport.h > 0 ? viewport.h : Math.max(height, layoutHeight);
    // Fit against the *layout* size (not padded viewBox) so large DAGs shrink.
    const fitX = availW / Math.max(width, 1);
    const fitY = availH / Math.max(layoutHeight, 1);
    const fitted = fitMode === 'width' ? fitX : Math.min(fitX, fitY);
    // Default ceil 1 — padded viewBox already prevents meet-upscale; zoom>1
    // is opt-in via fitZoomCeil for surfaces that truly want scale-up.
    const ceil = Number.isFinite(fitZoomCeil) ? fitZoomCeil : FIT_ZOOM_CEIL;
    setZoomClamped(clamp(fitted, FIT_ZOOM_FLOOR, ceil));
    setPan({ x: 0, y: 0 });
  }, [setZoomClamped, viewport.w, viewport.h, width, height, layoutHeight, fitMode, fitZoomCeil]);

  // Graph-first Run: fit the DAG when the layout size changes so the hero
  // isn't a tiny cluster in a sea of empty canvas.
  useEffect(() => {
    fitView();
  }, [fitView, nodes.length, width, layoutHeight, direction]);

  // ── Shared canvas renderer (inline + modal) ─────────────────────────────
  const renderCanvas = (canvasFill, marker = markerId) => {
    const boxH = canvasFill
      ? '100%'
      : (contentSized ? Math.max(layoutHeight + 8, 120) : height);
    return (
    <Box
      ref={(el) => {
        // Keep measuring the visible canvas (inline or full-screen).
        if (el) canvasRef.current = el;
      }}
      sx={{
        position: 'relative',
        overflow: 'auto',
        height: boxH,
        minHeight: 0,
        cursor: dragging ? 'grabbing' : 'grab',
        userSelect: 'none',
        touchAction: 'none',
      }}
      data-testid={canvasFill ? `${testId}-modal` : testId}
      onMouseDown={startPan}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${viewW} ${viewH}`}
        width="100%"
        height={contentSized && !canvasFill ? layoutHeight : '100%'}
        preserveAspectRatio="xMinYMin meet"
        role="img"
        aria-label="Graph — drag to pan, wheel to zoom, drag nodes to move or resize them"
      >
        <defs>
          <marker
            id={marker}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            markerUnits="userSpaceOnUse"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.palette.text.secondary} />
          </marker>
          <marker
            id={`${marker}-open`}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            markerUnits="userSpaceOnUse"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10" fill="none" stroke={theme.palette.text.secondary} strokeWidth="1.5" />
          </marker>
          <marker
            id={`${marker}-thin`}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            markerUnits="userSpaceOnUse"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.palette.text.disabled} />
          </marker>
        </defs>

        <g transform={transform}>
          {/* Phase lanes */}
          {phaseBands.map((b) => {
            const bandColor = phaseColor(b.phase_id);
            if (!bandColor) return null;
            const bandY = direction === 'tb' ? (b.y ?? 0) : 0;
            const bandH = direction === 'tb' ? (b.height ?? layoutHeight) : layoutHeight;
            return (
              <g key={`band-${b.phase_id}`}>
                <rect
                  x={b.x - 12}
                  y={bandY}
                  width={b.width + 24}
                  height={bandH}
                  rx={8}
                  fill={bandColor}
                  opacity={0.08}
                  stroke={bandColor}
                  strokeOpacity={0.35}
                  strokeWidth={1.25}
                />
                <text x={b.x - 12 + 8} y={bandY + 16} fontSize={11} fill={bandColor} fontWeight={650} letterSpacing={0.4}>
                  {b.name}
                  {b.strategy === 'parallel' ? ' · parallel' : ''}
                </text>
              </g>
            );
          })}

          {/* Edges — sequence / conditional / default (BPMN-style) */}
          {effectiveEdges.map((e) => {
            const branch = e.branch || 'pending';
            const styled = edgeStyle ? edgeStyle(e) : null;
            let stroke = styled?.stroke || theme.palette.text.secondary;
            let strokeWidth = styled?.strokeWidth ?? 2.25;
            let strokeOpacity = 0.95;
            let dash = styled?.dash;
            let markerKind = styled?.marker || 'arrow';
            if (!styled) {
              if (branch === 'chosen') {
                stroke = theme.palette.primary.main;
                strokeWidth = 3;
                strokeOpacity = 1;
              } else if (branch === 'unchosen') {
                stroke = theme.palette.text.disabled;
                strokeWidth = 1.5;
                strokeOpacity = 0.4;
                dash = '6 4';
                markerKind = 'arrowThin';
              }
            } else if (branch === 'chosen' && !styled.stroke) {
              stroke = theme.palette.primary.main;
            }
            const edgeSelected = selectedEdge
              && String(selectedEdge.source) === String(e.source)
              && String(selectedEdge.target) === String(e.target);
            if (edgeSelected) {
              stroke = theme.palette.primary.main;
              strokeWidth = Math.max(strokeWidth, 3);
              strokeOpacity = 1;
            }
            const markerRef = markerKind === 'arrowOpen'
              ? `url(#${marker}-open)`
              : markerKind === 'arrowThin'
                ? `url(#${marker}-thin)`
                : `url(#${marker})`;
            const d = edgePath(
              e.sourceX,
              e.sourceY,
              e.targetX,
              e.targetY,
              direction,
              e.laneOffset || 0,
              Boolean(e.is_back_edge),
            );
            const tip = edgeTitle ? edgeTitle(e) : (e.label || '');
            const edgeKey = `e-${e.source}-${e.target}-${e.is_back_edge ? 'b' : 'f'}`;
            const dim = edgeDimmed(e);
            return (
              <g
                key={edgeKey}
                data-testid={`${testId}-edge-${e.source}-${e.target}`}
                data-edge-kind={styled?.kind || branch}
                opacity={dim ? 0.18 : 1}
              >
                <path
                  d={d}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                  pointerEvents="stroke"
                  style={{ cursor: onSelectEdge ? 'pointer' : 'default' }}
                  onClick={(evt) => onEdgeClick(e, evt)}
                >
                  {tip ? <title>{tip}</title> : null}
                </path>
                <path
                  d={d}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={strokeWidth}
                  strokeOpacity={strokeOpacity}
                  strokeDasharray={dash}
                  markerEnd={markerRef}
                  pointerEvents="none"
                  data-branch={branch}
                />
              </g>
            );
          })}

          {/* Nodes (skip invisible Sugiyama dummies) */}
          {effectiveNodes.filter((n) => !n.is_dummy).map((n) => {
            const isSelected = selected?.id === n.id;
            const fill = nodeColor(n) || theme.palette.primary.main;
            const isRunning = showStatusPulse && n.status === 'running';
            const tip = nodeTitle ? nodeTitle(n) : '';
            const shape = nodeShape ? nodeShape(n) : 'roundedRect';
            const framePath = nodeShapePath(shape, n.w, n.h);
            const innerPath = nodeShapeInnerPath(shape, n.w, n.h);
            const isCard = shape === 'roundedRect' || shape === 'doubleRoundedRect' || shape === 'stadium'
              || shape === 'parallelogram' || shape === 'hexagon' || shape === 'chamfer';
            const strokeW = shape === 'thickCircle' ? 2.5 : (isSelected ? 2.25 : (isCard ? 1.5 : 1.75));
            const strokeColor = isSelected
              ? theme.palette.primary.main
              : (theme.palette.mode === 'dark' ? theme.palette.grey[600] : theme.palette.grey[400]);
            const fillBg = isSelected
              ? theme.palette.action.selected
              : theme.palette.background.paper;
            const isToken = tokenNodeId != null && String(tokenNodeId) === String(n.id);
            const dim = isDimmed(n.id);
            return (
              <g
                key={`n-${n.id}`}
                transform={`translate(${n.x}, ${n.y})`}
                onClick={() => onNodeClick(n)}
                onMouseDown={(e) => startNodeDrag(e, n)}
                style={{ cursor: 'move' }}
                role="button"
                aria-label={nodeAriaLabel ? nodeAriaLabel(n) : `Node ${n.id}: ${n.label || ''}`}
                data-shape={shape}
                data-node-w={n.w}
                data-node-h={n.h}
                data-token={isToken ? '1' : undefined}
                opacity={dim ? 0.22 : 1}
              >
                {tip ? <title>{tip}</title> : null}
                {/* Soft drop shadow for card boxes */}
                {isCard && (
                  <path
                    d={framePath}
                    fill={theme.palette.common.black}
                    opacity={0.06}
                    transform="translate(0, 1.5)"
                  />
                )}
                {isRunning && (
                  <path
                    d={framePath}
                    fill="none"
                    stroke={fill}
                    strokeWidth={2}
                    transform="translate(-2,-2) scale(1.04)"
                  >
                    <animate attributeName="opacity" values="0.9;0.15;0.9" dur="1.1s" repeatCount="indefinite" />
                  </path>
                )}
                {isToken && (
                  <path
                    d={framePath}
                    fill="none"
                    stroke={theme.palette.primary.main}
                    strokeWidth={2.5}
                    data-testid={`${testId}-token-${n.id}`}
                    transform="translate(-3,-3) scale(1.06)"
                  >
                    <animate attributeName="opacity" values="1;0.35;1" dur="1.4s" repeatCount="indefinite" />
                  </path>
                )}
                <path
                  d={framePath}
                  fill={fillBg}
                  stroke={isToken ? theme.palette.primary.main : strokeColor}
                  strokeWidth={isToken ? Math.max(strokeW, 2.25) : strokeW}
                />
                {innerPath && (
                  <path
                    d={innerPath}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={1}
                    transform={`translate(${shape === 'doubleCircle' || shape === 'doubleRoundedRect' ? 4 : 0}, ${shape === 'doubleCircle' || shape === 'doubleRoundedRect' ? 4 : 0})`}
                  />
                )}
                {shape === 'diamondPlus' && (
                  <g stroke={theme.palette.text.secondary} strokeWidth={1.75} fill="none">
                    <line x1={n.w / 2} y1={n.h * 0.28} x2={n.w / 2} y2={n.h * 0.72} />
                    <line x1={n.w * 0.28} y1={n.h / 2} x2={n.w * 0.72} y2={n.h / 2} />
                  </g>
                )}
                {renderNode ? renderNode(n) : (
                  <>
                    <rect x={3} y={5} width={3} height={n.h - 10} rx={1.5} fill={fill} />
                    <circle cx={13} cy={n.h / 2} r={4} fill={fill} />
                    <text x={22} y={n.h / 2 + 4} fontSize={11} fontWeight={600} fill={theme.palette.text.primary}>
                      {String(n.label || `Node ${n.id}`).slice(0, 26)}
                    </text>
                  </>
                )}
                {/* Resize handle (bottom-right) */}
                <g
                  data-testid={`${testId}-resize-${n.id}`}
                  onMouseDown={(e) => startResize(e, n)}
                  style={{ cursor: 'nwse-resize' }}
                >
                  <rect
                    x={n.w - 10}
                    y={n.h - 10}
                    width={10}
                    height={10}
                    fill={fillBg}
                    stroke={strokeColor}
                    strokeWidth={1}
                    rx={2}
                  />
                </g>
              </g>
            );
          })}        </g>
      </svg>
      {minimapOn && (
        <Box
          data-testid={`${testId}-minimap`}
          sx={{
            position: 'absolute',
            right: 8,
            bottom: 8,
            width: 120,
            height: 80,
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            bgcolor: 'background.paper',
            opacity: 0.92,
            overflow: 'hidden',
            pointerEvents: 'none',
            boxShadow: 1,
          }}
        >
          <svg
            viewBox={`0 0 ${viewW} ${viewH}`}
            width="100%"
            height="100%"
            preserveAspectRatio="xMinYMin meet"
            aria-hidden
          >
            {effectiveNodes.filter((n) => !n.is_dummy).map((n) => (
              <rect
                key={`mm-${n.id}`}
                x={n.x}
                y={n.y}
                width={Math.max(n.w, 4)}
                height={Math.max(n.h, 4)}
                fill={tokenNodeId != null && String(tokenNodeId) === String(n.id)
                  ? theme.palette.primary.main
                  : theme.palette.text.disabled}
                opacity={0.55}
                rx={1}
              />
            ))}
          </svg>
        </Box>
      )}
    </Box>
  );
  };

  // ── Header (title + live + summary + toolbar) ───────────────────────────
  const renderHeader = (closeButton, headerTitle = title) => (
    <Stack
      direction="row"
      alignItems="center"
      spacing={0.75}
      sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
    >
      <AccountTreeOutlinedIcon sx={{ fontSize: '0.9375rem', color: 'text.secondary' }} />
      <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
        {headerTitle}
      </Typography>
      {live && (
        <Box
          component="span"
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            px: 0.75,
            height: 16,
            borderRadius: 1,
            fontSize: '0.5625rem',
            fontWeight: 600,
            color: 'primary.main',
            bgcolor: 'action.selected',
          }}
        >
          <Box
            component="span"
            sx={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              bgcolor: 'primary.main',
              animation: 'egPulse 1.2s ease-in-out infinite',
            }}
          />
          Live
        </Box>
      )}
      {summary && (
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', whiteSpace: 'nowrap' }}>
          {summary}
        </Typography>
      )}
      <Tool label="Zoom out" testId={`${testId}-zoom-out`} onClick={() => setZoomClamped((z) => z / ZOOM_STEP)}>
        <ZoomOutIcon sx={{ fontSize: '0.9375rem' }} />
      </Tool>
      <Tool label="Zoom in" testId={`${testId}-zoom-in`} onClick={() => setZoomClamped((z) => z * ZOOM_STEP)}>
        <ZoomInIcon sx={{ fontSize: '0.9375rem' }} />
      </Tool>
      <Tool label="Zoom to fit" testId={`${testId}-fit`} onClick={fitView}>
        <CenterFocusStrongOutlinedIcon sx={{ fontSize: '0.9375rem' }} />
      </Tool>
      <Tool label="Reset view" testId={`${testId}-reset`} onClick={resetView}>
        <RestartAltIcon sx={{ fontSize: '0.9375rem' }} />
      </Tool>
      <Tool label="Redraw layout" testId={`${testId}-redraw`} onClick={redraw}>
        <AutoFixHighOutlinedIcon sx={{ fontSize: '0.9375rem' }} />
      </Tool>
      <Tool label="Export as PNG" testId={`${testId}-export`} onClick={exportPng}>
        <FileDownloadOutlinedIcon sx={{ fontSize: '0.9375rem' }} />
      </Tool>
      {closeButton || (
        <Tool label="Maximize" testId={expandTestId} onClick={() => setExpanded(true)}>
          <FullscreenIcon sx={{ fontSize: '0.9375rem' }} />
        </Tool>
      )}
    </Stack>
  );

  return (
    <>
      <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
        {renderHeader(null, title)}
        {nodes.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
              {emptyMessage}
            </Typography>
          </Box>
        ) : (
          <Stack direction="row" alignItems="stretch" sx={{ width: '100%', minHeight: contentSized ? undefined : height }}>
            <Box sx={{ flex: 1, minWidth: 0, position: 'relative', minHeight: 0 }}>
              {legend}
              {renderCanvas(false, markerId)}
            </Box>
            {sidebar ? sidebar('inline') : null}
          </Stack>
        )}
      </Paper>

      {/* Full-screen modal — the graph at maximum size */}
      <Dialog fullScreen open={expanded} onClose={() => setExpanded(false)} data-testid={modalTestId}>
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          {renderHeader(
            <Tool label="Close full view" testId={modalCloseTestId} onClick={() => setExpanded(false)}>
              <CloseIcon sx={{ fontSize: '1.125rem' }} />
            </Tool>,
            modalTitle,
          )}
          {nodes.length === 0 ? (
            <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                {emptyMessage}
              </Typography>
            </Box>
          ) : (
            <Stack direction="row" sx={{ flex: 1, minHeight: 0 }}>
              <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                {legend}
                <Box sx={{ flex: 1, minHeight: 0 }}>{renderCanvas(true, modalMarkerId)}</Box>
              </Box>
              {sidebar ? sidebar('modal') : null}
            </Stack>
          )}
        </Box>
      </Dialog>

      {/* One global keyframe for the live badge + running node pulse. */}
      <style>{`@keyframes egPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.25; } }`}</style>
    </>
  );
}

EnterpriseGraph.propTypes = {
  nodes: PropTypes.array,
  edges: PropTypes.array,
  phaseBands: PropTypes.array,
  phaseColor: PropTypes.func,
  nodeColor: PropTypes.func,
  renderNode: PropTypes.func,
  nodeShape: PropTypes.func,
  edgeStyle: PropTypes.func,
  width: PropTypes.number,
  layoutHeight: PropTypes.number,
  height: PropTypes.number,
  fill: PropTypes.bool,
  selected: PropTypes.object,
  onSelect: PropTypes.func,
  selectedEdge: PropTypes.object,
  onSelectEdge: PropTypes.func,
  nodeTitle: PropTypes.func,
  edgeTitle: PropTypes.func,
  showStatusPulse: PropTypes.bool,
  legend: PropTypes.node,
  sidebar: PropTypes.func,
  title: PropTypes.string,
  modalTitle: PropTypes.string,
  summary: PropTypes.string,
  live: PropTypes.bool,
  emptyMessage: PropTypes.string,
  nodeAriaLabel: PropTypes.func,
  markerId: PropTypes.string,
  modalMarkerId: PropTypes.string,
  testId: PropTypes.string,
  modalTestId: PropTypes.string,
  modalCloseTestId: PropTypes.string,
  expandTestId: PropTypes.string,
  exportFileName: PropTypes.string,
  direction: PropTypes.oneOf(['lr', 'tb']),
  fitMode: PropTypes.oneOf(['contain', 'width', 'none']),
  fitZoomCeil: PropTypes.number,
  contentSized: PropTypes.bool,
  focusIds: PropTypes.object,
  tokenNodeId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  showMinimap: PropTypes.bool,
};
