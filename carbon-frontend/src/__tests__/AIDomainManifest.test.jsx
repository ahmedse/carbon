// src/__tests__/AIDomainManifest.test.jsx
// Phase 7A — domain manifest wiring: AIEmptyState renders manifest-driven
// starter chips and forwards the exact starter args on click.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import AIEmptyState from '../shell/AIEmptyState';

const emissionsFixture = {
  app_identifier: 'emissions',
  display_name: 'Carbon Footprint',
  supported_task_types: ['chat', 'dq_validate'],
  entry_points: [],
  starter_prompts: {
    default: [
      {
        label: 'What can I ask here?',
        prompt: 'Tell me about my carbon footprint.',
        task_type: 'chat',
      },
      {
        label: 'Check data quality',
        prompt: '',
        task_type: 'dq_validate',
      },
    ],
  },
  system_prompt_extension: true,
};

describe('AIEmptyState domain manifest starter chips (Phase 7A)', () => {
  it('renders a Chip for each default starter prompt label', () => {
    render(
      <AIEmptyState manifests={[emissionsFixture]} onStartStarter={vi.fn()} />,
    );

    expect(
      screen.getByRole('button', { name: 'What can I ask here?' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Check data quality' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Carbon Footprint')).toBeInTheDocument();
  });

  it('calls onStartStarter with the exact starter args on chip click', () => {
    const onStartStarter = vi.fn();
    render(
      <AIEmptyState manifests={[emissionsFixture]} onStartStarter={onStartStarter} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'What can I ask here?' }));

    expect(onStartStarter).toHaveBeenCalledWith(
      'emissions',
      'chat',
      'What can I ask here?',
      'Tell me about my carbon footprint.',
    );
  });

  it('falls back to the plain empty state when no manifests are present', () => {
    render(
      <AIEmptyState onStartChat={vi.fn()} manifests={[]} onStartStarter={vi.fn()} />,
    );

    expect(
      screen.getByRole('button', { name: 'Start a Chat' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'What can I ask here?' }),
    ).not.toBeInTheDocument();
  });
});
