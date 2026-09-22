// src/__tests__/graphEdgePath.test.js
import { describe, it, expect } from 'vitest';
import {
  computeEdgePath,
  computeBackEdgePath,
  assignCorridorOffsets,
  focusPathIds,
} from '../utils/graphEdgePath';

describe('computeEdgePath', () => {
  it('draws a vertical line for same-lane TB hops', () => {
    expect(computeEdgePath(100, 10, 100, 90, 'tb')).toBe('M 100 10 L 100 90');
  });

  it('draws orthogonal elbows when TB lanes differ', () => {
    const d = computeEdgePath(40, 10, 200, 90, 'tb');
    expect(d).toContain('L 40 ');
    expect(d).toContain('L 200 ');
    expect(d).not.toMatch(/C /);
  });

  it('applies corridor offset on TB', () => {
    expect(computeEdgePath(100, 10, 100, 90, 'tb', 6)).toBe('M 106 10 L 106 90');
  });
});

describe('computeBackEdgePath', () => {
  it('routes on a left return channel', () => {
    const d = computeBackEdgePath(120, 200, 120, 40, 40);
    expect(d).toBe('M 120 200 L 40 200 L 40 40 L 120 40');
  });
});

describe('assignCorridorOffsets', () => {
  it('staggers parallel edges in the same corridor', () => {
    const edges = [
      { sourceX: 100, sourceY: 10, targetX: 100, targetY: 80 },
      { sourceX: 100, sourceY: 10, targetX: 100, targetY: 80 },
      { sourceX: 100, sourceY: 10, targetX: 100, targetY: 80 },
    ];
    const out = assignCorridorOffsets(edges, 'tb', 6);
    const offsets = out.map((e) => e.laneOffset).sort((a, b) => a - b);
    expect(offsets).toEqual([-6, 0, 6]);
  });
});

describe('focusPathIds', () => {
  it('includes ancestors and descendants', () => {
    const edges = [
      { source: 0, target: 1 },
      { source: 1, target: 2 },
      { source: 1, target: 3 },
      { source: 9, target: 10 },
    ];
    const ids = focusPathIds(edges, 1);
    expect([...ids].sort()).toEqual([0, 1, 2, 3]);
  });
});
