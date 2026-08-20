// src/__tests__/PlanMermaidPreview.test.jsx
// W3-F — static Mermaid diagram preview: lazily loads mermaid, renders the
// plan DAG as `graph LR`, and falls back to an error chip when rendering
// fails.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import mermaid from 'mermaid';
import PlanMermaidPreview from '../components/graph/PlanMermaidPreview';

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({ svg: '<svg data-testid="rendered-svg"><g /></svg>' })),
  },
}));

const PLAN = {
  id: 'plan-1',
  steps: [
    { step_id: 0, intent: 'Search for duplicate records', status: 'pending', depends_on: [] },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', status: 'pending', depends_on: [0] },
  ],
};

describe('PlanMermaidPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the mermaid svg from the plan DAG', async () => {
    const { container } = render(<PlanMermaidPreview plan={PLAN} />);

    expect(await screen.findByTestId('plan-mermaid-preview')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="rendered-svg"]')).not.toBeNull();

    await waitFor(() => {
      expect(mermaid.initialize).toHaveBeenCalledWith(
        expect.objectContaining({ startOnLoad: false, securityLevel: 'loose' }),
      );
    });
    expect(mermaid.render).toHaveBeenCalledWith(
      expect.stringMatching(/^plan-mmd-/),
      expect.stringContaining('graph LR'),
    );
  });

  it('shows a fallback chip when the diagram fails to render', async () => {
    mermaid.render.mockRejectedValueOnce(new Error('boom'));

    render(<PlanMermaidPreview plan={PLAN} />);

    expect(await screen.findByText('Diagram could not be rendered')).toBeInTheDocument();
  });
});
