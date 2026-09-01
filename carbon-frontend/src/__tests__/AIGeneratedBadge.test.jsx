// src/__tests__/AIGeneratedBadge.test.jsx
// Wave D3 — quiet AI-authored token: default "AI" copy + icon, custom label,
// and an aria-label so the meaning never rides on color alone.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AIGeneratedBadge from '../shell/AIGeneratedBadge';

describe('AIGeneratedBadge', () => {
  it('renders the default "AI" copy with a smart-toy icon', () => {
    render(<AIGeneratedBadge />);

    expect(screen.getByText('AI')).toBeInTheDocument();
    expect(screen.getByTestId('SmartToyOutlinedIcon')).toBeInTheDocument();
  });

  it('renders a custom label', () => {
    render(<AIGeneratedBadge label="AI-generated" />);

    expect(screen.getByText('AI-generated')).toBeInTheDocument();
  });

  it('exposes an aria-label for accessibility (text + icon, not color-only)', () => {
    render(<AIGeneratedBadge />);

    expect(screen.getByLabelText('AI')).toBeInTheDocument();
  });
});
