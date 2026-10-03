/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PulseProgressButton from './PulseProgressButton';

describe('PulseProgressButton', () => {
  it('renders the Progress affordance and opens the canvas on click', () => {
    render(<PulseProgressButton canView />);

    const button = screen.getByTestId('pulse-progress-button');
    expect(button).toBeInTheDocument();
    expect(screen.queryByTestId('pulse-progress-canvas')).toBeNull();

    fireEvent.click(button);
    expect(screen.getByTestId('pulse-progress-canvas')).toBeInTheDocument();
  });

  it('is hidden when the viewer fails the same gate as the canvas surface', () => {
    render(<PulseProgressButton canView={false} />);
    expect(screen.queryByTestId('pulse-progress-button')).toBeNull();
  });
});
