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

const ZOOM_MIN = 0.25;
const ZOOM_MAX = 3;
const ZOOM_STEP = 1.15;
const NODE_MIN_W = 96;
const NODE_MAX_W = 640;
const NODE_MIN_H = 36;
const NODE_MAX_H = 320;
const DRAG_THRESHOLD = 3;

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/**
 * Cubic bezier path from a source node's right edge to a target node's left
 * edge — edges always flow left→right, matching the layered execution layout.
 */
function edgePath(sx, sy, tx, ty) {
  const dx = Math.max((tx - sx) * 0.5, 12);
  return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
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
 */
export default function EnterpriseGraph({
  nodes = [],
  edges = [],
  phaseBands = [],
  phaseColor = () => undefined,
  nodeColor = () => undefined,
  renderNode,
  width = 960,
  layoutHeight = 420,
  height = 380,
  fill = false,
  selected,
  onSelect,
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
}) {
  const theme = useTheme();
  const svgRef = useRef(null);
  const drag = useRef(null);
  const moved = useRef(false);
  const [dragging, setDragging] = useState(false);

  // Viewport (move/resize the whole canvas) + per-node position/size overrides
  // (move/resize individual nodes, free-form).
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [overrides, setOverrides] = useState({});
  const [expanded, setExpanded] = useState(false);

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
  // nodes as the user drags/resizes them.
  const effectiveEdges = useMemo(
    () =>
      edges
        .map((e) => {
          const s = nodeById.get(e.source);
          const t = nodeById.get(e.target);
          if (!s || !t) return null;
          return {
            ...e,
            sourceX: s.x + s.w,
            sourceY: s.y + s.h / 2,
            targetX: t.x,
            targetY: t.y + t.h / 2,
          };
        })
        .filter(Boolean),
    [edges, nodeById],
  );

  const viewW = Math.max(640, width);
  const viewH = fill ? layoutHeight : Math.max(height, layoutHeight);
  const transform = `translate(${pan.x + (viewW - width * zoom) / 2}, ${pan.y + (viewH - layoutHeight * zoom) / 2}) scale(${zoom})`;

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
    onSelect?.(selected?.id === node.id ? null : node);
  };

  const exportPng = useCallback(() => {
    if (svgRef.current) {
      exportSvgToPng(svgRef.current, viewW, viewH, theme.palette.background.paper, exportFileName);
    }
  }, [viewW, viewH, theme, exportFileName]);

  const fitView = useCallback(() => {
    setZoomClamped(Math.min(1, viewW / Math.max(width, 1)));
    setPan({ x: 0, y: 0 });
  }, [setZoomClamped, viewW, width]);

  // ── Shared canvas renderer (inline + modal) ─────────────────────────────
  const renderCanvas = (canvasFill, marker = markerId) => (
    <Box
      sx={{
        position: 'relative',
        overflow: 'auto',
        height: canvasFill ? '100%' : height,
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
        height={canvasFill ? '100%' : viewH}
        role="img"
        aria-label="Graph — drag to pan, wheel to zoom, drag nodes to move or resize them"
      >
        <defs>
          <marker
            id={marker}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 9 5 L 0 9 z" fill={theme.palette.text.secondary} />
          </marker>
        </defs>

        <g transform={transform}>
          {/* Phase lanes */}
          {phaseBands.map((b) => {
            const bandColor = phaseColor(b.phase_id);
            if (!bandColor) return null;
            return (
              <g key={`band-${b.phase_id}`}>
                <rect
                  x={b.x - 12}
                  y={0}
                  width={b.width + 24}
                  height={layoutHeight}
                  rx={6}
                  fill={bandColor}
                  opacity={0.05}
                />
                <text x={b.x - 12 + 6} y={16} fontSize={9} fill={bandColor} fontWeight={600} letterSpacing={0.4}>
                  {b.name}
                  {b.strategy === 'parallel' ? ' · parallel' : ''}
                </text>
              </g>
            );
          })}

          {/* Edges — always left→right with arrowheads */}
          {effectiveEdges.map((e) => (
            <path
              key={`e-${e.source}-${e.target}`}
              d={edgePath(e.sourceX, e.sourceY, e.targetX, e.targetY)}
              fill="none"
              stroke={theme.palette.divider}
              strokeWidth={1.25}
              strokeOpacity={0.9}
              markerEnd={`url(#${marker})`}
              pointerEvents="none"
            />
          ))}

          {/* Nodes */}
          {effectiveNodes.map((n) => {
            const isSelected = selected?.id === n.id;
            const fill = nodeColor(n) || theme.palette.primary.main;
            const isRunning = n.status === 'running';
            return (
              <g
                key={`n-${n.id}`}
                transform={`translate(${n.x}, ${n.y})`}
                onClick={() => onNodeClick(n)}
                onMouseDown={(e) => startNodeDrag(e, n)}
                style={{ cursor: 'move' }}
                role="button"
                aria-label={nodeAriaLabel ? nodeAriaLabel(n) : `Node ${n.id}: ${n.label || ''}`}
              >
                {/* Live pulse for running nodes */}
                {isRunning && (
                  <rect
                    x={-3}
                    y={-3}
                    width={n.w + 6}
                    height={n.h + 6}
                    rx={8}
                    fill="none"
                    stroke={fill}
                    strokeWidth={1.5}
                  >
                    <animate attributeName="opacity" values="0.9;0.1;0.9" dur="1.1s" repeatCount="indefinite" />
                  </rect>
                )}
                <rect
                  width={n.w}
                  height={n.h}
                  rx={6}
                  fill={isSelected ? theme.palette.action.selected : theme.palette.background.paper}
                  stroke={isSelected ? theme.palette.primary.main : theme.palette.divider}
                  strokeWidth={isSelected ? 2 : 1}
                />
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
                    x={n.w - 9}
                    y={n.h - 9}
                    width={9}
                    height={9}
                    fill={theme.palette.background.paper}
                    stroke={isSelected ? theme.palette.primary.main : theme.palette.divider}
                    strokeWidth={1}
                    rx={2}
                  />
                </g>
              </g>
            );
          })}
        </g>
      </svg>
    </Box>
  );

  // ── Header (title + live + summary + toolbar) ───────────────────────────
  const renderHeader = (closeButton, headerTitle = title) => (
    <Stack
      direction="row"
      alignItems="center"
      spacing={0.75}
      sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
    >
      <AccountTreeOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
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
        <ZoomOutIcon sx={{ fontSize: 15 }} />
      </Tool>
      <Tool label="Zoom in" testId={`${testId}-zoom-in`} onClick={() => setZoomClamped((z) => z * ZOOM_STEP)}>
        <ZoomInIcon sx={{ fontSize: 15 }} />
      </Tool>
      <Tool label="Zoom to fit" testId={`${testId}-fit`} onClick={fitView}>
        <CenterFocusStrongOutlinedIcon sx={{ fontSize: 15 }} />
      </Tool>
      <Tool label="Reset view" testId={`${testId}-reset`} onClick={resetView}>
        <RestartAltIcon sx={{ fontSize: 15 }} />
      </Tool>
      <Tool label="Redraw layout" testId={`${testId}-redraw`} onClick={redraw}>
        <AutoFixHighOutlinedIcon sx={{ fontSize: 15 }} />
      </Tool>
      <Tool label="Export as PNG" testId={`${testId}-export`} onClick={exportPng}>
        <FileDownloadOutlinedIcon sx={{ fontSize: 15 }} />
      </Tool>
      {closeButton || (
        <Tool label="Maximize" testId={expandTestId} onClick={() => setExpanded(true)}>
          <FullscreenIcon sx={{ fontSize: 15 }} />
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
          <Stack direction="row" sx={{ width: '100%' }}>
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
              <CloseIcon sx={{ fontSize: 18 }} />
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
  width: PropTypes.number,
  layoutHeight: PropTypes.number,
  height: PropTypes.number,
  fill: PropTypes.bool,
  selected: PropTypes.object,
  onSelect: PropTypes.func,
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
};
