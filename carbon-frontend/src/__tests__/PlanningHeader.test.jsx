// src/__tests__/PlanningHeader.test.jsx
// Wave F3-F — collapsible "Considered: …" planning pill:
//   * collapsed pill shows the first step_label (+ "+N more")
//   * expands to list every step_label + formatted duration (ms and s)
//   * aria-expanded flips and the trigger toggles via Enter/Space
//   * renders nothing for []/null, persists + restores expanded state
//   * still renders when prefers-reduced-motion is reduce
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PlanningHeader from '../shell/PlanningHeader';

const STORAGE_KEY = 'pulse.planningHeader.expanded';

const TRACE_1 = [
  { step_label: 'Searched the knowledge base', tool_id: 'kb_search', duration_ms: 350 },
];

const TRACE_3 = [
  { step_label: 'Searched the knowledge base', tool_id: 'kb_search', duration_ms: 350 },
  { step_label: 'Retrieved emissions factors', tool_id: 'ef_lookup', duration_ms: 1200 },
  { step_label: 'Computed the estimate', tool_id: 'calc', duration_ms: 2500 },
];

beforeEach(() => {
  localStorage.clear();
});

describe('PlanningHeader', () => {
  it('renders the collapsed "Considered: …" pill with the first step_label', () => {
    render(<PlanningHeader trace={TRACE_1} />);
    expect(screen.getByText(/Considered:\s*Searched the knowledge base/)).toBeInTheDocument();
  });

  it('appends "+N-1 more" when there are multiple steps', () => {
    render(<PlanningHeader trace={TRACE_3} />);
    expect(screen.getByText(/\+2 more/)).toBeInTheDocument();
  });

  it('expands on click to show every step_label and a formatted duration', () => {
    render(<PlanningHeader trace={TRACE_3} />);
    fireEvent.click(screen.getByRole('button', { name: /Show planning steps/i }));

    expect(screen.getByText('Searched the knowledge base')).toBeInTheDocument();
    expect(screen.getByText('Retrieved emissions factors')).toBeInTheDocument();
    expect(screen.getByText('Computed the estimate')).toBeInTheDocument();
    expect(screen.getByText('350 ms')).toBeInTheDocument();
    expect(screen.getByText('1.2 s')).toBeInTheDocument();
    expect(screen.getByText('2.5 s')).toBeInTheDocument();

    // Outcome language only — never the raw tool_id.
    expect(screen.queryByText('kb_search')).not.toBeInTheDocument();
    expect(screen.queryByText('ef_lookup')).not.toBeInTheDocument();
  });

  it('flips aria-expanded on toggle and toggles via Enter and Space keys', async () => {
    const user = userEvent.setup();
    render(<PlanningHeader trace={TRACE_1} />);

    const trigger = screen.getByRole('button', { name: /Show planning steps/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await user.click(trigger);
    expect(screen.getByRole('button', { name: /Hide planning steps/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    );

    // Enter collapses it back.
    screen.getByRole('button', { name: /Hide planning steps/i }).focus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('button', { name: /Show planning steps/i })).toHaveAttribute(
      'aria-expanded',
      'false',
    );

    // Space re-expands it.
    screen.getByRole('button', { name: /Show planning steps/i }).focus();
    await user.keyboard(' ');
    expect(screen.getByRole('button', { name: /Hide planning steps/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('renders nothing for an empty or null trace', () => {
    const { container: empty } = render(<PlanningHeader trace={[]} />);
    expect(empty).toBeEmptyDOMElement();

    const { container: none } = render(<PlanningHeader trace={null} />);
    expect(none).toBeEmptyDOMElement();
  });

  it('persists expanded state to localStorage and reads it back on a fresh mount', () => {
    const { unmount } = render(<PlanningHeader trace={TRACE_1} />);
    fireEvent.click(screen.getByRole('button', { name: /Show planning steps/i }));
    expect(localStorage.getItem(STORAGE_KEY)).toBe('1');

    unmount();
    render(<PlanningHeader trace={TRACE_1} />);
    expect(screen.getByRole('button', { name: /Hide planning steps/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('renders without throwing when prefers-reduced-motion is reduce', () => {
    const original = window.matchMedia;
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: (query) => ({
        matches: true,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
      }),
    });
    try {
      render(<PlanningHeader trace={TRACE_1} />);
      expect(screen.getByText(/Considered:\s*Searched the knowledge base/)).toBeInTheDocument();
    } finally {
      window.matchMedia = original;
    }
  });
});
