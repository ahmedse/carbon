import { describe, it, expect } from 'vitest';
import { computeFitScale } from '../utils/graphFit';

describe('computeFitScale', () => {
  it('keeps short plans near native size (no giant cards in a tall rail)', () => {
    const { scale } = computeFitScale({
      availW: 900,
      availH: 520,
      layoutW: 308,
      layoutH: 200,
      fitMode: 'smart',
      fitZoomCeil: 1.45,
      sampleNodeW: 260,
    });
    expect(scale).toBeLessThanOrEqual(1.08);
    expect(scale).toBeGreaterThanOrEqual(0.9);
  });

  it('does not upscale deep TB plans (zoom>1 would clip inside the viewBox)', () => {
    const contain = computeFitScale({
      availW: 900,
      availH: 480,
      layoutW: 600,
      layoutH: 920,
      fitMode: 'contain',
      fitZoomCeil: 1,
      sampleNodeW: 260,
    });
    const smart = computeFitScale({
      availW: 900,
      availH: 480,
      layoutW: 600,
      layoutH: 920,
      fitMode: 'smart',
      fitZoomCeil: 1.45,
      sampleNodeW: 260,
    });
    // contain would shrink; smart stays at 1 so meet can show the full spine
    expect(contain.scale).toBeLessThan(0.7);
    expect(smart.scale).toBe(1);
    expect(smart.panY).toBe(0);
    expect(smart.panX).toBeGreaterThan(0); // centered in the wide rail
  });

  it('centers short plans that fit entirely', () => {
    const { panY, scale } = computeFitScale({
      availW: 800,
      availH: 500,
      layoutW: 300,
      layoutH: 180,
      fitMode: 'smart',
      sampleNodeW: 260,
    });
    expect(scale).toBeLessThanOrEqual(1.08);
    expect(panY).toBeGreaterThan(0);
  });
});
