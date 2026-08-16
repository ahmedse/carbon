// src/__tests__/ReportDraftCard.test.jsx
// Phase 10-B — ReportDraftCard renders the frozen `report` metadata contract
// and wires its three actions (Save as Artifact / Export .md / Re-draft).
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ReportDraftCard from '../shell/ReportDraftCard';

const baseMetadata = {
  type: 'report',
  title: 'GHG Summary Report',
  summary: 'A draft of the organisation GHG summary.',
  report_type: 'ghg_summary',
  period_start: '2026-01-01',
  period_end: '2026-12-31',
  generated_at: '2026-08-16T12:00:00+00:00',
  sections: [
    {
      title: 'Summary',
      content: 'Total scope 2 electricity volume grew this period.',
      sql: null,
      data: { rows: 120 },
      caveat: 'Volumes are live host-table snapshots, not audited figures.',
    },
    {
      title: 'Data Volume (Live)',
      content: '12 monthly records were loaded.',
      sql: null,
      data: null,
      caveat: null,
    },
  ],
};

describe('ReportDraftCard', () => {
  it('renders title, summary, period, and sections', () => {
    render(<ReportDraftCard metadata={baseMetadata} />);

    expect(screen.getByText('GHG Summary Report')).toBeInTheDocument();
    expect(
      screen.getByText('A draft of the organisation GHG summary.'),
    ).toBeInTheDocument();
    expect(screen.getByText('2026-01-01 → 2026-12-31')).toBeInTheDocument();
    expect(screen.getByText('Summary')).toBeInTheDocument();
    expect(
      screen.getByText('Total scope 2 electricity volume grew this period.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Data Volume (Live)')).toBeInTheDocument();
    expect(screen.getByText('12 monthly records were loaded.')).toBeInTheDocument();
  });

  it('renders section caveats as warning text', () => {
    render(<ReportDraftCard metadata={baseMetadata} />);

    expect(
      screen.getByText('Volumes are live host-table snapshots, not audited figures.'),
    ).toBeInTheDocument();
  });

  it('calls onSaveArtifact with the metadata when Save as Artifact is clicked', async () => {
    const onSaveArtifact = vi.fn();
    const user = userEvent.setup();
    render(<ReportDraftCard metadata={baseMetadata} onSaveArtifact={onSaveArtifact} />);

    await user.click(screen.getByRole('button', { name: 'Save as Artifact' }));

    expect(onSaveArtifact).toHaveBeenCalledTimes(1);
    expect(onSaveArtifact).toHaveBeenCalledWith(baseMetadata);
  });

  it('calls onExport with the metadata when Export .md is clicked', async () => {
    const onExport = vi.fn();
    const user = userEvent.setup();
    render(<ReportDraftCard metadata={baseMetadata} onExport={onExport} />);

    await user.click(screen.getByRole('button', { name: 'Export .md' }));

    expect(onExport).toHaveBeenCalledTimes(1);
    expect(onExport).toHaveBeenCalledWith(baseMetadata);
  });

  it('calls onRedraft when Re-draft is clicked', async () => {
    const onRedraft = vi.fn();
    const user = userEvent.setup();
    render(<ReportDraftCard metadata={baseMetadata} onRedraft={onRedraft} />);

    await user.click(screen.getByRole('button', { name: 'Re-draft' }));

    expect(onRedraft).toHaveBeenCalledTimes(1);
  });
});
