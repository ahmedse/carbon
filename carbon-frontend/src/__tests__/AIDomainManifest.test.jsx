// Empty Ask is a coworker introduction. Shortcuts are questions this user
// can ask — not the first chips of every registered domain app.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import AIEmptyState from '../shell/AIEmptyState';

const otherBrand = {
  app_identifier: 'finance',
  display_name: 'Finance Operations',
  starter_prompts: {
    default: [
      {
        label: 'Explain budget variance',
        prompt: 'Explain how to analyze a budget variance for @{entity_name}.',
        task_type: 'chat',
      },
    ],
  },
};

describe('AIEmptyState coworker introduction', () => {
  it('introduces Pulse and does not offer another brand’s catalog', () => {
    render(
      <AIEmptyState
        onStartChat={vi.fn()}
        manifests={[otherBrand]}
        onStartStarter={vi.fn()}
      />,
    );

    expect(screen.getByTestId('pulse-empty-state')).toHaveTextContent("I'm Pulse.");
    expect(screen.queryByRole('button', { name: 'Explain budget variance' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'What can you help me with?' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Catch me up' })).toBeInTheDocument();
  });

  it('starts a plain chat from a shortcut, with a real question', () => {
    const onStartStarter = vi.fn();
    render(<AIEmptyState onStartStarter={onStartStarter} />);

    fireEvent.click(screen.getByRole('button', { name: 'What can you help me with?' }));
    expect(onStartStarter).toHaveBeenCalledWith(
      '',
      'chat',
      'What can you help me with?',
      'What can you help me with on this system?',
    );
    expect(onStartStarter.mock.calls[0][3]).not.toMatch(/@\{entity_name\}/);
  });
});
