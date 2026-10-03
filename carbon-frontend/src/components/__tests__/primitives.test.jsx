// Shared Layer-2 primitive contract tests (design-system RULE 2/3/5).
// These lock the small domain-neutral building blocks the coverage pages now
// compose instead of re-implementing seven near-copy chips and two progress
// forks. The components carry no domain words — labels come from the caller.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusChip from '../StatusChip';
import ProgressBar from '../ProgressBar';
import NumericText from '../NumericText';
import LtrText from '../LtrText';
import StatCard from '../Cards/StatCard';

describe('Layer-2 shared primitives', () => {
  it('StatusChip resolves the value through the caller-supplied map', () => {
    render(
      <StatusChip
        value="active"
        map={{ active: { label: 'Active', color: 'success' } }}
      />,
    );
    const chip = screen.getByText('Active').closest('.MuiChip-root');
    expect(chip).toHaveClass('MuiChip-colorSuccess');
  });

  it('StatusChip falls back to the raw value when the map has no entry', () => {
    render(<StatusChip value="weird" map={{ active: { label: 'Active' } }} />);
    expect(screen.getByText('weird')).toBeInTheDocument();
  });

  it('ProgressBar clamps an out-of-range percent and shows the formatter label', () => {
    const { container } = render(<ProgressBar value={140} tone="warning" label="140%" />);
    // Clamped to the 0–100 range for the determinate bar.
    const root = container.querySelector('.MuiLinearProgress-root');
    expect(root).toHaveAttribute('aria-valuenow', '100');
    expect(root).toHaveClass('MuiLinearProgress-colorWarning');
    expect(screen.getByText('140%')).toBeInTheDocument();
  });

  it('ProgressBar never crashes on a non-numeric value', () => {
    render(<ProgressBar value="n/a" label="—" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('NumericText is an LTR, tabular-numeric run (RULE 3)', () => {
    render(<NumericText>1,234.00</NumericText>);
    const el = screen.getByText('1,234.00');
    expect(el).toHaveAttribute('dir', 'ltr');
    expect(el.className).toMatch(/MuiTypography/);
  });

  it('LtrText isolates a Latin value with <bdi dir="ltr"> (ADR-0018)', () => {
    render(<LtrText>Scope 1+2</LtrText>);
    const el = screen.getByText('Scope 1+2');
    expect(el.tagName.toLowerCase()).toBe('bdi');
    expect(el).toHaveAttribute('dir', 'ltr');
  });

  it('StatCard renders an optional subtitle node (replaces page-local stat cards)', () => {
    render(<StatCard title="Goal" value="80%" subtitle={<span>Emissions value target</span>} />);
    expect(screen.getByText('Goal')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(screen.getByText('Emissions value target')).toBeInTheDocument();
  });
});
