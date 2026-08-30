// src/__tests__/AIMessageBubble.confidence.test.jsx
// Wave C2 — surface calibrated confidence (Faculty 7): the subtle indicator +
// honest-uncertainty styling render distinctly off the REAL backend signal.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';

const baseMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the answer.',
  created_at: '2026-08-16T10:00:00Z',
};

function renderBubble(message, props = {}) {
  return render(
    <MemoryRouter>
      <AIMessageBubble message={message} {...props} />
    </MemoryRouter>,
  );
}

describe('AIMessageBubble confidence indicator (Wave C2)', () => {
  it('renders a meter bar for high confidence (theme token, no hardcoded text)', () => {
    renderBubble({ ...baseMessage, confidence_label: 'high' });

    const meter = screen.getByRole('meter', { name: 'Answer confidence: high' });
    expect(meter).toBeInTheDocument();
    expect(meter).toHaveAttribute('aria-valuenow', '92');
    expect(meter).toHaveAttribute('aria-valuemax', '100');
    // No always-visible label text for the bar (tooltip-only).
    expect(screen.queryByText('High confidence')).not.toBeInTheDocument();
  });

  it('maps medium and low labels to their own meter states', () => {
    const { unmount } = renderBubble({ ...baseMessage, confidence_label: 'medium' });
    expect(screen.getByRole('meter', { name: 'Answer confidence: medium' })).toBeInTheDocument();
    unmount();

    renderBubble({ ...baseMessage, confidence_label: 'low' });
    const meter = screen.getByRole('meter', { name: 'Answer confidence: low' });
    expect(meter).toHaveAttribute('aria-valuenow', '35');
  });

  it('renders a calm caption (not an error) for a low-confidence turn', () => {
    renderBubble({ ...baseMessage, confidence_label: 'uncertain' });

    expect(screen.getByText('Best available — some gaps remain')).toBeInTheDocument();
    // No meter bar for the uncertain state.
    expect(screen.queryByRole('meter')).not.toBeInTheDocument();
  });

  it('renders the honest-uncertainty caption + flag styling off the boolean flag', () => {
    renderBubble({ ...baseMessage, honest_uncertainty: true, confidence_label: 'uncertain' });

    expect(screen.getByText('Best available — some gaps remain')).toBeInTheDocument();
    expect(screen.queryByRole('meter')).not.toBeInTheDocument();
  });

  it('reads the signal from metadata_json fallback (legacy payload shape)', () => {
    renderBubble({
      ...baseMessage,
      metadata_json: { confidence_label: 'low', honest_uncertainty: false },
    });

    expect(screen.getByRole('meter', { name: 'Answer confidence: low' })).toBeInTheDocument();
  });

  it('renders nothing when no confidence signal is present', () => {
    renderBubble(baseMessage);

    expect(screen.queryByRole('meter')).not.toBeInTheDocument();
    expect(screen.queryByText('Best available — some gaps remain')).not.toBeInTheDocument();
  });

  it('does not render a confidence signal on user messages', () => {
    renderBubble({ id: 'msg-2', role: 'user', content: 'Hello', confidence_label: 'high' });

    expect(screen.queryByRole('meter')).not.toBeInTheDocument();
  });
});
