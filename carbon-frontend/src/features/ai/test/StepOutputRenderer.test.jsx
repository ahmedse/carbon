// src/features/ai/test/StepOutputRenderer.test.jsx
// W6-B1 — StepOutputRenderer: table/chart/artifact/json/text rendering paths.
// Asserts the REAL component contract: MUI table for tabular data (never a
// raw <pre>), bars with title tooltips for charts, a Download action (button,
// not href) for artifacts, and a hidden "Raw output" <pre> for JSON that only
// appears after expanding.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const { downloadArtifactUrl } = vi.hoisted(() => ({
  downloadArtifactUrl: vi.fn(),
}));

vi.mock('../../../api/aiWorkspace', () => ({
  downloadArtifactUrl: (...args) => downloadArtifactUrl(...args),
}));

import StepOutputRenderer from '../../../components/ai/StepOutputRenderer';

const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;

beforeEach(() => {
  vi.clearAllMocks();
  downloadArtifactUrl.mockReset();
  downloadArtifactUrl.mockResolvedValue('blob:mock');
  // jsdom lacks blob URL helpers — the artifact download path stubs them.
  URL.createObjectURL = vi.fn(() => 'blob:mock');
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  URL.createObjectURL = originalCreateObjectURL;
  URL.revokeObjectURL = originalRevokeObjectURL;
});

describe('StepOutputRenderer — output shapes', () => {
  it('renders tabular data as a real table, not a raw <pre>', () => {
    const { container } = render(
      <StepOutputRenderer
        outputType="table"
        value={{ headers: ['Rep', 'Qty'], rows: [['R1', 10], ['R2', 20]] }}
      />,
    );

    expect(container.querySelector('table')).toBeInTheDocument();
    // Tabular data must never fall back to the raw JSON dump.
    expect(container.querySelector('pre')).not.toBeInTheDocument();
    expect(screen.getByText('Rep')).toBeInTheDocument();
    expect(screen.getByText('Qty')).toBeInTheDocument();
    expect(screen.getByText('R1')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
  });

  it('renders a chart series as titled bars', () => {
    const { container } = render(
      <StepOutputRenderer outputType="chart" value={{ series: [3, 7, 2] }} />,
    );

    expect(container.querySelector('[title="3"]')).toBeInTheDocument();
    expect(container.querySelector('[title="7"]')).toBeInTheDocument();
    expect(container.querySelector('[title="2"]')).toBeInTheDocument();
  });

  it('falls back gracefully for an empty chart series (no crash, raw view available)', () => {
    const { container } = render(
      <StepOutputRenderer outputType="chart" value={{ series: [] }} />,
    );

    expect(container.querySelector('[title]')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /raw output/i })).toBeInTheDocument();
  });

  it('renders an artifact card with a Download action for the artifact', async () => {
    const { container } = render(
      <StepOutputRenderer
        outputType="artifact"
        value={{ name: 'report.csv', size_bytes: 2048, download_url: '/ai/artifacts/report.csv' }}
      />,
    );

    expect(screen.getByText('report.csv')).toBeInTheDocument();
    expect(screen.getByText('2.0 KB')).toBeInTheDocument();
    const download = screen.getByRole('button', { name: /download/i });
    expect(download).toBeInTheDocument();
    // The download is a button-driven blob flow — never a literal href.
    expect(container.querySelector('a[href]')).not.toBeInTheDocument();

    fireEvent.click(download);
    await waitFor(() => {
      expect(downloadArtifactUrl).toHaveBeenCalledWith('test-token', '/ai/artifacts/report.csv');
    });
  });

  it('keeps raw JSON collapsed behind the Raw output toggle', () => {
    const { container } = render(<StepOutputRenderer outputType="json" value={{ a: 1 }} />);

    // Hidden until expanded.
    expect(container.querySelector('pre')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /raw output/i }));

    const pre = container.querySelector('pre');
    expect(pre).toBeInTheDocument();
    expect(pre.textContent).toContain('"a": 1');
  });

  it('renders plain text output as prose', () => {
    render(<StepOutputRenderer outputType="text" value="Found 3 duplicate rows." />);

    expect(screen.getByText('Found 3 duplicate rows.')).toBeInTheDocument();
  });

  it('infers text from a bare string and returns nothing for empty values', () => {
    render(<StepOutputRenderer outputType={null} value="Inferred prose." />);
    expect(screen.getByText('Inferred prose.')).toBeInTheDocument();

    const { container } = render(<StepOutputRenderer outputType="text" value="" />);
    expect(container).toBeEmptyDOMElement();
  });
});
