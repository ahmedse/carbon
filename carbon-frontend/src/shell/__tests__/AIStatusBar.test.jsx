import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import AIStatusBar from '../AIStatusBar';

describe('AIStatusBar dense thinking switch', () => {
  it('is off by default and notifies on flip', () => {
    const onChange = vi.fn();
    render(
      <AIStatusBar
        variant="ready"
        label="Ready"
        denseThinking={false}
        onDenseThinkingChange={onChange}
      />,
    );
    const toggle = screen.getByRole('checkbox', { name: /Think/i });
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('hides the switch when no handler is given', () => {
    render(<AIStatusBar variant="ready" label="Ready" denseThinking />);
    expect(screen.queryByRole('checkbox')).toBeNull();
  });
});
