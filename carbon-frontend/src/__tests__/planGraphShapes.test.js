// src/__tests__/planGraphShapes.test.js
import { describe, it, expect } from 'vitest';
import {
  resolvePlanNodeShape,
  resolvePlanEdgeStyle,
  nodeShapePath,
} from '../components/graph/planGraphShapes';

describe('resolvePlanNodeShape', () => {
  it('maps agent tasks to card boxes; gateways keep BPMN shapes', () => {
    expect(resolvePlanNodeShape({ agent_role: 'orchestrator', node_type: 'task' })).toBe('roundedRect');
    expect(resolvePlanNodeShape({ agent_role: 'researcher', node_type: 'task' })).toBe('roundedRect');
    expect(resolvePlanNodeShape({ agent_role: 'domain_specialist', node_type: 'task' })).toBe('roundedRect');
    expect(resolvePlanNodeShape({ agent_role: 'critic', node_type: 'task' })).toBe('roundedRect');
    expect(resolvePlanNodeShape({ agent_role: 'planner', node_type: 'task' })).toBe('roundedRect');
  });

  it('maps gateways to BPMN diamonds / events', () => {
    expect(resolvePlanNodeShape({ is_gateway: true, node_type: 'choice' })).toBe('diamond');
    expect(resolvePlanNodeShape({ is_gateway: true, node_type: 'parallel' })).toBe('diamondPlus');
    expect(resolvePlanNodeShape({ is_gateway: true, node_type: 'observe' })).toBe('doubleCircle');
    expect(resolvePlanNodeShape({ is_gateway: true, node_type: 'wait' })).toBe('doubleCircle');
    expect(resolvePlanNodeShape({ is_gateway: true, node_type: 'fail' })).toBe('thickCircle');
  });

  it('gateway type wins over agent role', () => {
    expect(resolvePlanNodeShape({
      is_gateway: true,
      node_type: 'choice',
      agent_role: 'researcher',
    })).toBe('diamond');
  });
});

describe('resolvePlanEdgeStyle', () => {
  it('uses sequence / conditional / default markers', () => {
    expect(resolvePlanEdgeStyle({}).kind).toBe('sequence');
    expect(resolvePlanEdgeStyle({ guard: 'x > 0' }).marker).toBe('arrowOpen');
    expect(resolvePlanEdgeStyle({ is_default: true }).dash).toBeTruthy();
    expect(resolvePlanEdgeStyle({ branch: 'unchosen' }).marker).toBe('arrowThin');
    expect(resolvePlanEdgeStyle({ branch: 'chosen' }).strokeWidth).toBe(3);
  });
});

describe('nodeShapePath', () => {
  it('emits closed paths for each shape', () => {
    for (const shape of ['roundedRect', 'parallelogram', 'hexagon', 'chamfer', 'diamond', 'stadium', 'circle']) {
      const d = nodeShapePath(shape, 100, 40);
      expect(d).toMatch(/^M /);
      expect(d.toUpperCase()).toContain('Z');
    }
  });
});
