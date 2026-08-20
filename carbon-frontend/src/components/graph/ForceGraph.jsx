// src/components/graph/ForceGraph.jsx
// W3-F — shared force-directed graph primitive (d3-force + drag + zoom/pan +
// hover tooltip + click-to-inspect + legend), extracted from the AI admin
// KnowledgeGraphPanel so BOTH AI surfaces render graphs through one
// component. The Admin surface reuses it in W3-G; this Workspace phase ships
// it as the shared d3 core.
//
// RULE_8: node/edge colors are supplied as theme tokens (theme.palette.* /
// chartPalette.*) by the caller — never inline raw hex. RULE_10: this is a
// pure presentational component — no fetching here.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Paper, Stack, Typography, useTheme } from '@mui/material';
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from 'd3-force';
import { select } from 'd3-selection';
import { drag as d3Drag } from 'd3-drag';
import { zoom as d3Zoom, zoomIdentity } from 'd3-zoom';

const DEFAULT_WIDTH = 960;
const DEFAULT_HEIGHT = 420;

function defaultRadius() {
  return 12;
}

/**
 * Generic force-directed graph with drag, zoom/pan, hover tooltip,
 * click-to-inspect and a legend row.
 *
 * @param {object} props
 * @param {Array<{id:number|string,label:string,subtitle?:string}>} props.nodes
 * @param {Array<{source:number|string,target:number|string,label?:string}>} props.edges
 * @param {function} props.nodeColor - (node) => theme color token
 * @param {function} [props.nodeRadius] - (node) => number (SVG geometry)
 * @param {number} [props.height] - SVG viewport height
 * @param {number} [props.width] - SVG viewport width
 * @param {function} [props.onSelect] - (node) => void, click-to-inspect
 * @param {number|string} [props.selectedId] - highlighted node id
 * @param {Array<{label:string,color:string}>} [props.legend] - legend chips
 * @param {string} [props.emptyMessage] - shown when there are no nodes
 * @param {string} [props.ariaLabel] - SVG accessibility label
 * @param {string} [props.testId] - data-testid for tests
 */
export default function ForceGraph({
  nodes = [],
  edges = [],
  nodeColor,
  nodeRadius = defaultRadius,
  height = DEFAULT_HEIGHT,
  width = DEFAULT_WIDTH,
  onSelect,
  selectedId,
  legend = [],
  emptyMessage = 'Nothing to show yet.',
  ariaLabel = 'Force-directed graph',
  testId = 'force-graph',
}) {
  const theme = useTheme();
  const svgRef = useRef(null);
  const zoomRef = useRef(null);
  const [hovered, setHovered] = useState(null);

  const edgeStroke = theme.palette.text.disabled;
  const labelFill = theme.palette.text.primary;
  const nodeStroke = theme.palette.divider;
  const selectStroke = theme.palette.primary.main;
  const hoverPaper = theme.palette.background.paper;

  // Degree per node — feeds radius growth so connected steps read bigger.
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

  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl || nodes.length === 0) return undefined;

    const svg = select(svgEl);
    svg.selectAll('*').remove();

    const simNodes = nodes.map((n) => ({ ...n }));
    const simEdges = edges.map((e) => ({ ...e }));

    const simulation = forceSimulation(simNodes)
      .force(
        'link',
        forceLink(simEdges)
          .id((d) => d.id)
          .distance(90)
          .strength(0.4),
      )
      .force('charge', forceManyBody().strength(-320))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide().radius((d) => (nodeRadius(d) || 8) + 4));

    const root = svg.append('g');

    const link = root
      .append('g')
      .selectAll('line')
      .data(simEdges)
      .join('line')
      .attr('stroke', edgeStroke)
      .attr('stroke-opacity', 0.45)
      .attr('stroke-width', 1.25);

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

    const node = root
      .append('g')
      .selectAll('circle')
      .data(simNodes)
      .join('circle')
      .attr('r', (d) => nodeRadius(d))
      .attr('fill', (d) => nodeColor?.(d) || theme.palette.primary.main)
      .attr('stroke', (d) => (d.id === selectedId ? selectStroke : nodeStroke))
      .attr('stroke-width', (d) => (d.id === selectedId ? 2.5 : 1.25))
      .style('cursor', 'pointer')
      .call(dragBehavior)
      .on('mouseover', (event, d) => {
        setHovered({
          title: d.label || String(d.id),
          subtitle: d.subtitle || null,
          x: event.pageX,
          y: event.pageY,
        });
      })
      .on('mousemove', (event) => {
        setHovered((prev) => (prev ? { ...prev, x: event.pageX, y: event.pageY } : prev));
      })
      .on('mouseout', () => setHovered(null))
      .on('click', (event, d) => {
        if (onSelect) onSelect(d);
      });

    link
      .on('mouseover', (event, d) => {
        setHovered({
          title: d.label || 'depends on',
          subtitle: null,
          x: event.pageX,
          y: event.pageY,
        });
      })
      .on('mousemove', (event) => {
        setHovered((prev) => (prev ? { ...prev, x: event.pageX, y: event.pageY } : prev));
      })
      .on('mouseout', () => setHovered(null));

    const label = root
      .append('g')
      .selectAll('text')
      .data(simNodes)
      .join('text')
      .text((d) => d.label)
      .attr('font-size', 10)
      .attr('fill', labelFill)
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => -nodeRadius(d) - 5)
      .style('pointer-events', 'none');

    const zoomBehavior = d3Zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => {
        root.attr('transform', event.transform);
      });
    svg.call(zoomBehavior);
    zoomRef.current = zoomBehavior;

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
  }, [
    nodes,
    edges,
    nodeColor,
    nodeRadius,
    height,
    width,
    selectedId,
    edgeStroke,
    labelFill,
    nodeStroke,
    selectStroke,
    theme,
    onSelect,
  ]);

  const resetZoom = () => {
    if (svgRef.current && zoomRef.current) {
      select(svgRef.current).transition().call(zoomRef.current.transform, zoomIdentity);
    }
  };

  if (nodes.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', bgcolor: 'background.paper' }}>
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          {emptyMessage}
        </Typography>
      </Paper>
    );
  }

  return (
    <Box data-testid={testId}>
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        sx={{ px: 1, py: 0.5, flexWrap: 'wrap', rowGap: 0.25 }}
      >
        {legend.map((l) => (
          <Stack key={l.label} direction="row" spacing={0.5} alignItems="center">
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                backgroundColor: l.color,
              }}
            />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
              {l.label}
            </Typography>
          </Stack>
        ))}
        <Box sx={{ flex: 1 }} />
        <Button size="small" onClick={resetZoom} sx={{ fontSize: '0.625rem', textTransform: 'none', minWidth: 0, px: 0.75 }}>
          Reset view
        </Button>
      </Stack>
      <Box sx={{ position: 'relative' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height={height}
          role="img"
          aria-label={ariaLabel}
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
              bgcolor: hoverPaper,
            }}
          >
            <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem' }}>
              {hovered.title}
            </Typography>
            {hovered.subtitle && (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                {hovered.subtitle}
              </Typography>
            )}
          </Paper>
        )}
      </Box>
    </Box>
  );
}

ForceGraph.propTypes = {
  nodes: PropTypes.arrayOf(PropTypes.object),
  edges: PropTypes.arrayOf(PropTypes.object),
  nodeColor: PropTypes.func,
  nodeRadius: PropTypes.func,
  height: PropTypes.number,
  width: PropTypes.number,
  onSelect: PropTypes.func,
  selectedId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  legend: PropTypes.arrayOf(PropTypes.shape({ label: PropTypes.string, color: PropTypes.string })),
  emptyMessage: PropTypes.string,
  ariaLabel: PropTypes.string,
  testId: PropTypes.string,
};
