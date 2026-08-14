// src/pages/admin/ai/KnowledgeGraphPanel.jsx
// Route /admin/ai/graph — read-only force-directed Knowledge Graph panel.
//
// Normalized graph read from /ai/pulse/graph/ (see backend ai.graph_api) and
// rendered as an SVG force-directed layout (d3-force) with drag + zoom/pan,
// a hover tooltip (label/relationship), a click-to-inspect side panel, a
// node-type legend, and a Graph/Table toggle (Table reuses PulseDataPanel).
//
// RULE_8 tokens only (chartPalette + theme.palette — no raw hex); RULE_10
// apiFetch only (via src/api/aiPulse.js).
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from 'd3-force';
import { select } from 'd3-selection';
import { drag as d3Drag } from 'd3-drag';
import { zoom as d3Zoom, zoomIdentity } from 'd3-zoom';

import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { getPulseGraph } from '../../../api/aiPulse';
import { chartPalette } from '../../../theme/carbonTheme';
import PulseDataPanel from './PulseDataPanel';

const WIDTH = 960;
const HEIGHT = 600;

/** Node radius grows with degree (number of incident edges), 6 → 24. */
function radiusFor(degrees, node) {
  const degree = degrees[node.id] ?? 0;
  return 6 + Math.min(degree, 12) * 1.5;
}

export default function KnowledgeGraphPanel() {
  useDocumentTitle('Knowledge Graph');
  const { token } = useAuth();
  const theme = useTheme();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [view, setView] = useState('graph');
  const [selectedNode, setSelectedNode] = useState(null);
  const [hovered, setHovered] = useState(null);

  const svgRef = useRef(null);
  const zoomRef = useRef(null);

  // ── Fetch normalized graph ───────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getPulseGraph(token);
        if (!cancelled) {
          setData(payload);
          setOffline(false);
          setSelectedNode(null);
        }
      } catch {
        if (!cancelled) {
          setData(null);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const stats = data?.stats ?? {};

  // ── Derived: deterministic type → color mapping + node degrees ───────────
  const typeColors = useMemo(() => {
    const types = [...new Set(nodes.map((n) => n.type || 'unknown'))].sort();
    const palette = [
      chartPalette.blue,
      chartPalette.green,
      chartPalette.purple,
      chartPalette.orange,
      chartPalette.teal,
      chartPalette.pink,
      chartPalette.indigo,
      chartPalette.red,
      chartPalette.yellow,
    ];
    const map = { unknown: chartPalette.gray };
    types.forEach((t, i) => {
      map[t] = palette[i % palette.length];
    });
    return map;
  }, [nodes]);

  const degrees = useMemo(() => {
    const d = {};
    nodes.forEach((n) => {
      d[n.id] = 0;
    });
    edges.forEach((e) => {
      if (d[e.source] !== undefined) d[e.source] += 1;
      if (d[e.target] !== undefined) d[e.target] += 1;
    });
    return d;
  }, [nodes, edges]);

  // ── Build the force-directed layout + interactions (d3) ─────────────────
  useEffect(() => {
    if (view !== 'graph' || !svgRef.current || nodes.length === 0) return undefined;

    const svg = select(svgRef.current);
    svg.selectAll('*').remove();

    const simNodes = nodes.map((n) => ({ ...n }));
    const simEdges = edges.map((e) => ({
      source: e.source,
      target: e.target,
      confidence: e.confidence,
      relationship: e.relationship,
    }));

    const simulation = forceSimulation(simNodes)
      .force(
        'link',
        forceLink(simEdges)
          .id((d) => d.id)
          .distance(70)
          .strength(0.5),
      )
      .force('charge', forceManyBody().strength(-260))
      .force('center', forceCenter(WIDTH / 2, HEIGHT / 2))
      .force(
        'collide',
        forceCollide().radius((d) => radiusFor(degrees, d) + 3),
      );

    const root = svg.append('g');
    const edgeColor = theme.palette.text.disabled;
    const labelColor = theme.palette.text.primary;
    const nodeStroke = theme.palette.divider;

    // Edges — stroke opacity/width scaled by confidence.
    const link = root
      .append('g')
      .selectAll('line')
      .data(simEdges)
      .join('line')
      .attr('stroke', edgeColor)
      .attr('stroke-opacity', (d) => 0.25 + (d.confidence ?? 1) * 0.75)
      .attr('stroke-width', (d) => 0.75 + (d.confidence ?? 1) * 2.25);

    // Drag behavior: pin node under pointer while dragging.
    const dragBehavior = d3Drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    // Nodes.
    const node = root
      .append('g')
      .selectAll('circle')
      .data(simNodes)
      .join('circle')
      .attr('r', (d) => radiusFor(degrees, d))
      .attr('fill', (d) => typeColors[d.type] || typeColors.unknown)
      .attr('stroke', nodeStroke)
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .call(dragBehavior)
      .on('mouseover', (event, d) => {
        setHovered({
          kind: 'node',
          title: d.label,
          subtitle: `${d.type || 'unknown'} · confidence ${d.confidence ?? '—'}`,
          x: event.pageX,
          y: event.pageY,
        });
      })
      .on('mousemove', (event) => {
        setHovered((prev) => (prev ? { ...prev, x: event.pageX, y: event.pageY } : prev));
      })
      .on('mouseout', () => setHovered(null))
      .on('click', (event, d) => setSelectedNode(d));

    // Edge hover → relationship tooltip.
    link
      .on('mouseover', (event, d) => {
        setHovered({
          kind: 'edge',
          title: d.relationship || '—',
          subtitle: `confidence ${d.confidence ?? '—'}`,
          x: event.pageX,
          y: event.pageY,
        });
      })
      .on('mousemove', (event) => {
        setHovered((prev) => (prev ? { ...prev, x: event.pageX, y: event.pageY } : prev));
      })
      .on('mouseout', () => setHovered(null));

    // Labels.
    const label = root
      .append('g')
      .selectAll('text')
      .data(simNodes)
      .join('text')
      .text((d) => d.label)
      .attr('font-size', 10)
      .attr('fill', labelColor)
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => -radiusFor(degrees, d) - 4)
      .style('pointer-events', 'none');

    // Zoom + pan (applied to the root group).
    const zoomBehavior = d3Zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => {
        root.attr('transform', event.transform);
      });
    svg.call(zoomBehavior);
    zoomRef.current = zoomBehavior;

    // Tick → update positions.
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);
      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y);
      label.attr('x', (d) => d.x).attr('y', (d) => d.y);
    });

    return () => {
      simulation.stop();
      svg.on('.zoom', null);
      svg.selectAll('*').remove();
    };
  }, [view, nodes, edges, degrees, typeColors, theme]);

  const handleViewChange = (event, next) => {
    if (next !== null) {
      setSelectedNode(null);
      setHovered(null);
      setView(next);
    }
  };

  const resetZoom = () => {
    if (svgRef.current && zoomRef.current) {
      select(svgRef.current).transition().call(zoomRef.current.transform, zoomIdentity);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────
  const header = (
    <Stack spacing={1}>
      <Stack direction="row" spacing={1} alignItems="center">
        <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>
          Knowledge Graph
        </Typography>
        <ToggleButtonGroup
          value={view}
          exclusive
          size="small"
          onChange={handleViewChange}
          aria-label="graph view toggle"
        >
          <ToggleButton value="graph">Graph</ToggleButton>
          <ToggleButton value="table">Table</ToggleButton>
        </ToggleButtonGroup>
      </Stack>
      <Typography variant="body2" color="text.secondary">
        Normalized knowledge-graph nodes and edges from the AI engine.
      </Typography>
    </Stack>
  );

  if (view === 'table') {
    return (
      <PageContainer>
        <Box sx={{ mb: 2 }}>{header}</Box>
        <PulseDataPanel
          title="Knowledge Graph"
          description="Graph nodes, edges, provenance, query plans, and bootstrap runs."
          dataKey="graph"
          emptyHint="No graph nodes or edges yet. Run schema analysis to bootstrap the graph."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      {header}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={24} />
        </Box>
      ) : offline || !data ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
          <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
            Data unavailable
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            The Pulse graph read API is offline.
          </Typography>
        </Paper>
      ) : nodes.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="subtitle1" fontWeight={600}>Knowledge Graph</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            No graph nodes or edges yet. Run schema analysis to bootstrap the graph.
          </Typography>
        </Paper>
      ) : (
        <Stack direction="row" spacing={2} alignItems="flex-start">
          <Paper variant="outlined" sx={{ flex: 1, minWidth: 0, p: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 1, py: 0.5, flexWrap: 'wrap' }}>
              <Chip size="small" variant="outlined" label={`${stats.node_count ?? nodes.length} nodes`} />
              <Chip size="small" variant="outlined" label={`${stats.edge_count ?? edges.length} edges`} />
              {stats.truncated && (
                <Chip size="small" color="warning" label="truncated" />
              )}
              {Object.keys(typeColors)
                .filter((t) => t !== 'unknown')
                .map((t) => (
                  <Stack key={t} direction="row" spacing={0.5} alignItems="center">
                    <Box
                      sx={{
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        backgroundColor: typeColors[t],
                      }}
                    />
                    <Typography variant="caption" color="text.secondary">{t}</Typography>
                  </Stack>
                ))}
              <Box sx={{ flex: 1 }} />
              <Button size="small" onClick={resetZoom}>Reset view</Button>
            </Stack>
            <Box sx={{ position: 'relative' }}>
              <svg
                ref={svgRef}
                viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                width="100%"
                height={HEIGHT}
                role="img"
                aria-label="Knowledge graph force-directed layout"
              />
              {hovered && (
                <Paper
                  elevation={4}
                  sx={{
                    position: 'fixed',
                    left: (hovered.x ?? 0) + 14,
                    top: (hovered.y ?? 0) + 14,
                    px: 1.5,
                    py: 0.75,
                    pointerEvents: 'none',
                    zIndex: 1300,
                    maxWidth: 340,
                  }}
                >
                  <Typography variant="body2" fontWeight={600}>{hovered.title}</Typography>
                  {hovered.subtitle && (
                    <Typography variant="caption" color="text.secondary">
                      {hovered.subtitle}
                    </Typography>
                  )}
                </Paper>
              )}
            </Box>
          </Paper>

          {selectedNode && (
            <Paper variant="outlined" sx={{ width: 300, flexShrink: 0, p: 2 }}>
              <Stack spacing={1}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ wordBreak: 'break-word' }}>
                  {selectedNode.label}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Type: {selectedNode.type || 'unknown'}
                </Typography>
                <Typography variant="body2">
                  Confidence: {selectedNode.confidence ?? '—'}
                </Typography>
                <Typography variant="body2">
                  Verified: {selectedNode.verified ? 'Yes' : 'No'}
                </Typography>
                {selectedNode.source_model && (
                  <Typography variant="caption" color="text.secondary">
                    Source model: {selectedNode.source_model}
                  </Typography>
                )}
                <Divider />
                <Typography variant="caption" fontWeight={600}>Properties</Typography>
                <Typography
                  component="pre"
                  variant="caption"
                  sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}
                >
                  {JSON.stringify(selectedNode.properties ?? {}, null, 2)}
                </Typography>
                <Button size="small" onClick={() => setSelectedNode(null)}>Close</Button>
              </Stack>
            </Paper>
          )}
        </Stack>
      )}
    </PageContainer>
  );
}
