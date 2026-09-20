// src/components/graph/planGraphShapes.js
// BPMN / flowchart-aligned shapes for Plan DAG nodes and edges.
// Gateways follow BPMN; agent-role tasks follow common flowchart conventions.
// RULE_2: one resolver used by PlanDagGraph + EnterpriseGraph.

/** @typedef {'roundedRect'|'stadium'|'parallelogram'|'hexagon'|'chamfer'|'diamond'|'diamondPlus'|'circle'|'doubleCircle'|'doubleRoundedRect'|'thickCircle'} NodeShapeId */

/**
 * Resolve outer shape for a plan graph node.
 * Tasks = card boxes (readable). Gateways keep BPMN diamonds/circles.
 * Role is shown by accent + label, not by distorting the card.
 * @param {object} n
 * @returns {NodeShapeId}
 */
export function resolvePlanNodeShape(n) {
  if (!n || n.is_dummy) return 'roundedRect';
  const nt = String(n.node_type || '').toLowerCase();
  if (n.is_gateway || ['choice', 'parallel', 'observe', 'map', 'loop', 'wait', 'fail', 'succeed'].includes(nt)) {
    switch (nt) {
      case 'choice':
        return 'diamond';
      case 'parallel':
        return 'diamondPlus';
      case 'observe':
      case 'wait':
        return 'doubleCircle';
      case 'map':
      case 'loop':
        return 'doubleRoundedRect';
      case 'fail':
        return 'thickCircle';
      case 'succeed':
        return 'circle';
      default:
        return 'diamond';
    }
  }
  // All agent tasks: same card box — role via accent/meta, not polygon silhouette.
  return 'roundedRect';
}

/** Role → accent token key (mapped in PlanDagGraph via theme). */
export const PLAN_ROLE_ACCENT = {
  orchestrator: 'primary',
  researcher: 'info',
  domain_specialist: 'secondary',
  critic: 'warning',
  planner: 'success',
};

/** Operator-facing legend rows. */
export const PLAN_SHAPE_LEGEND = [
  { shape: 'roundedRect', label: 'Task (agent)' },
  { shape: 'diamond', label: 'Choice (XOR)' },
  { shape: 'diamondPlus', label: 'Parallel (AND)' },
  { shape: 'doubleCircle', label: 'Wait / observe' },
];

/**
 * SVG path for a node frame in local coords (0..w, 0..h).
 * @param {NodeShapeId} shape
 * @param {number} w
 * @param {number} h
 * @returns {string}
 */
export function nodeShapePath(shape, w, h) {
  const cx = w / 2;
  const cy = h / 2;
  switch (shape) {
    case 'parallelogram': {
      const skew = Math.min(18, w * 0.12);
      return `M ${skew} 0 L ${w} 0 L ${w - skew} ${h} L 0 ${h} Z`;
    }
    case 'hexagon': {
      const x = Math.min(16, w * 0.14);
      return `M ${x} 0 L ${w - x} 0 L ${w} ${cy} L ${w - x} ${h} L ${x} ${h} L 0 ${cy} Z`;
    }
    case 'chamfer': {
      const c = Math.min(10, w * 0.1, h * 0.2);
      return `M ${c} 0 L ${w - c} 0 L ${w} ${c} L ${w} ${h - c} L ${w - c} ${h} L ${c} ${h} L 0 ${h - c} L 0 ${c} Z`;
    }
    case 'diamond':
    case 'diamondPlus': {
      return `M ${cx} 0 L ${w} ${cy} L ${cx} ${h} L 0 ${cy} Z`;
    }
    case 'circle':
    case 'thickCircle':
    case 'doubleCircle': {
      const r = Math.min(w, h) / 2 - 1;
      // Approximate circle as path for stroke consistency
      return [
        `M ${cx + r} ${cy}`,
        `A ${r} ${r} 0 1 1 ${cx - r} ${cy}`,
        `A ${r} ${r} 0 1 1 ${cx + r} ${cy}`,
        'Z',
      ].join(' ');
    }
    case 'stadium': {
      const r = h / 2;
      return [
        `M ${r} 0`,
        `L ${w - r} 0`,
        `A ${r} ${r} 0 0 1 ${w - r} ${h}`,
        `L ${r} ${h}`,
        `A ${r} ${r} 0 0 1 ${r} 0`,
        'Z',
      ].join(' ');
    }
    case 'roundedRect':
    default: {
      const r = 8;
      return [
        `M ${r} 0`,
        `H ${w - r}`,
        `Q ${w} 0 ${w} ${r}`,
        `V ${h - r}`,
        `Q ${w} ${h} ${w - r} ${h}`,
        `H ${r}`,
        `Q 0 ${h} 0 ${h - r}`,
        `V ${r}`,
        `Q 0 0 ${r} 0`,
        'Z',
      ].join(' ');
    }
  }
}

/**
 * Inner inset path for double-border shapes (subprocess / double circle).
 * @param {NodeShapeId} shape
 * @param {number} w
 * @param {number} h
 * @returns {string|null}
 */
export function nodeShapeInnerPath(shape, w, h) {
  const inset = 4;
  if (shape === 'doubleRoundedRect') {
    return nodeShapePath('roundedRect', w - inset * 2, h - inset * 2);
  }
  if (shape === 'doubleCircle') {
    const cw = w - inset * 2;
    const ch = h - inset * 2;
    return nodeShapePath('circle', cw, ch);
  }
  return null;
}

/**
 * Resolve edge visual style (BPMN sequence / conditional / default).
 * @param {object} edge
 * @returns {{ kind: string, dash?: string, marker: 'arrow'|'arrowOpen'|'arrowThin', strokeWidth: number }}
 */
export function resolvePlanEdgeStyle(edge) {
  const branch = edge?.branch || 'pending';
  if (branch === 'unchosen') {
    return { kind: 'conditional-off', dash: '6 4', marker: 'arrowThin', strokeWidth: 1.5 };
  }
  if (branch === 'chosen') {
    return { kind: 'conditional-on', marker: 'arrow', strokeWidth: 3 };
  }
  if (edge?.is_default) {
    return { kind: 'default', dash: '2 3', marker: 'arrow', strokeWidth: 2.25 };
  }
  if (edge?.guard) {
    return { kind: 'conditional', dash: '5 3', marker: 'arrowOpen', strokeWidth: 2 };
  }
  // Parallel fan-in/out stays solid sequence flow
  return { kind: 'sequence', marker: 'arrow', strokeWidth: 2.25 };
}

/** Compact SVG sample for legends (12×12 viewBox). */
export function legendShapePath(shape) {
  return nodeShapePath(shape, 12, 12);
}
