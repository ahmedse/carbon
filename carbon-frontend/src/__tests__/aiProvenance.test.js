// src/__tests__/aiProvenance.test.js
// PAQ-3A — non-envelope provenance source normalization: the same four facts
// (tool, rows_returned, truncated, resolved_at) the envelope chips render,
// read defensively from metadata / provenance payload / top-level fields.
import { describe, it, expect } from 'vitest';
import {
  normalizeProvenanceSource,
  normalizeProvenanceSources,
} from '../utils/aiProvenance';

describe('normalizeProvenanceSource', () => {
  it('normalizes an envelope-style source object', () => {
    expect(
      normalizeProvenanceSource({
        tool: 'people_query',
        rows_returned: 1200,
        truncated: true,
        resolved_at: '2026-09-14T10:30:00Z',
      }),
    ).toEqual({
      tool: 'people_query',
      rows_returned: 1200,
      truncated: true,
      resolved_at: '2026-09-14T10:30:00Z',
    });
  });

  it('coerces a bare tool-name string', () => {
    expect(normalizeProvenanceSource('analyze_employees')).toEqual({
      tool: 'analyze_employees',
      rows_returned: null,
      truncated: false,
      resolved_at: null,
    });
  });

  it('derives rows from row_count and from a rows array', () => {
    expect(normalizeProvenanceSource({ tool_name: 'q', row_count: 24 }).rows_returned).toBe(24);
    expect(normalizeProvenanceSource({ tool: 'q', rows: [1, 2, 3] }).rows_returned).toBe(3);
  });

  it('returns null for empty or invalid input', () => {
    expect(normalizeProvenanceSource(null)).toBeNull();
    expect(normalizeProvenanceSource({})).toBeNull();
    expect(normalizeProvenanceSource('')).toBeNull();
  });
});

describe('normalizeProvenanceSources', () => {
  it('collects and dedupes sources from metadata, provenance payload, and top-level field', () => {
    const metadata = { sources: [{ tool: 'a', rows_returned: 1 }] };
    const provenance = {
      sources: [{ tool: 'a', rows_returned: 1 }, { tool: 'b', truncated: true }],
    };
    const topLevel = [
      { tool: 'a', rows_returned: 1 },
      { tool: 'c', resolved_at: '2026-01-01T00:00:00Z' },
    ];

    const out = normalizeProvenanceSources(metadata, provenance, topLevel);
    expect(out.map((s) => s.tool)).toEqual(['a', 'b', 'c']);
  });

  it('falls back to flat metadata fields when no sources array exists', () => {
    const out = normalizeProvenanceSources({ row_count: 42, truncated: true }, null, null);
    expect(out).toEqual([{ tool: '', rows_returned: 42, truncated: true, resolved_at: null }]);
  });

  it('returns [] when nothing is available', () => {
    expect(normalizeProvenanceSources({}, null, null)).toEqual([]);
  });
});
