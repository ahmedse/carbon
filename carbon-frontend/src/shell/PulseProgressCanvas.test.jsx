/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import PulseProgressCanvas from './PulseProgressCanvas';

describe('PulseProgressCanvas', () => {
  it('renders the committed ladder, intention banks, and soak', () => {
    render(<PulseProgressCanvas />);

    expect(screen.getByTestId('pulse-progress-canvas')).toBeInTheDocument();
    expect(screen.getByText('Excellence ladder')).toBeInTheDocument();
    // L0–L5 only — L6/L7 stay out (ADR-0049).
    expect(screen.getByText('L0 Safe')).toBeInTheDocument();
    expect(screen.getByText('L5 Autonomous')).toBeInTheDocument();
    expect(screen.queryByText('L6 Understands')).toBeNull();
    expect(screen.queryByText('L7 Lean')).toBeNull();
    expect(screen.getByText('Bank IB-04')).toBeInTheDocument();
    expect(screen.getByText('Bank IB-05')).toBeInTheDocument();
    expect(screen.getByText('20/20 intentions recognised')).toBeInTheDocument();
    expect(screen.getByText('5/5 green nights')).toBeInTheDocument();
    expect(screen.getByText('Soak complete')).toBeInTheDocument();
  });

  it('names the committed evidence it reads', () => {
    render(<PulseProgressCanvas />);
    expect(screen.getByText('docs/pulse/evidence/PV2-gauge-series.json')).toBeInTheDocument();
    expect(
      screen.getByText('docs/pulse/evidence/PV2-intention-IB05-2026-10-03-1134.json'),
    ).toBeInTheDocument();
  });
});
