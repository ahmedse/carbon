// src/__tests__/OperationProgress.test.jsx
// Wave D1 — OperationProgress renders a bar + narrated human step (never a
// bare spinner), announces the message (aria-live), and uses terminal text.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import OperationProgress from '../components/OperationProgress';

describe('OperationProgress', () => {
  it('renders a determinate bar plus narrated message while running', () => {
    render(
      <OperationProgress status="running" message="Checking 3 rules…" percent={45} />
    );

    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '45');
    expect(screen.getByText('Checking 3 rules…')).toBeInTheDocument();
  });

  it('falls back to an indeterminate bar when percent is unknown', () => {
    render(<OperationProgress status="running" message="Running your check…" />);

    const bar = screen.getByRole('progressbar');
    expect(bar).not.toHaveAttribute('aria-valuenow');
    expect(screen.getByText('Running your check…')).toBeInTheDocument();
  });

  it('renders an indeterminate bar for queued', () => {
    render(<OperationProgress status="queued" message="Waiting…" />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByText('Waiting…')).toBeInTheDocument();
  });

  it('renders 100% and the completion message for done (no bar)', () => {
    render(<OperationProgress status="done" message="Quality check complete." />);

    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByText('Quality check complete.')).toBeInTheDocument();
  });

  it('renders a dash and the error message for failed (no bar)', () => {
    render(<OperationProgress status="failed" message="The check could not finish." />);

    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByText('–')).toBeInTheDocument();
    expect(screen.getByText('The check could not finish.')).toBeInTheDocument();
  });

  it('renders nothing when there is no status', () => {
    const { container } = render(<OperationProgress status={null} message="x" />);
    expect(container).toBeEmptyDOMElement();
  });
});
