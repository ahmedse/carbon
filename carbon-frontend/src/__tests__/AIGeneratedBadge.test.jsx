// src/__tests__/AIGeneratedBadge.test.jsx
// Attribution tick: the visible word is Pulse, with the Pulse mark. Never "AI".
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AIGeneratedBadge from '../shell/AIGeneratedBadge';

describe('AIGeneratedBadge', () => {
  it('renders the Pulse mark and the word Pulse', () => {
    render(<AIGeneratedBadge />);

    const badge = screen.getByTestId('ai-generated-badge');
    expect(screen.getByText('Pulse')).toBeInTheDocument();
    expect(badge.querySelector('svg')).toBeTruthy();
  });

  it('renders a custom label', () => {
    render(<AIGeneratedBadge label="AI-generated" />);

    expect(screen.getByText('AI-generated')).toBeInTheDocument();
  });

  it('is not labeled AI', () => {
    render(<AIGeneratedBadge />);

    expect(screen.queryByText('AI')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('AI')).not.toBeInTheDocument();
  });
});
