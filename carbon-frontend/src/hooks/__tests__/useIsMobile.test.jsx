import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';

vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: vi.fn(() => false),
  default: vi.fn(() => false),
}));

import { useIsMobile } from '../../hooks/useIsMobile';

describe('useIsMobile mock wiring', () => {
  it('returns mocked boolean under ThemeProvider', () => {
    useIsMobile.mockReturnValue(true);
    function Probe() {
      const m = useIsMobile();
      return <div data-testid="m">{m ? 'mobile' : 'desktop'}</div>;
    }
    render(
      <ThemeProvider theme={createTheme()}>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('m').textContent).toBe('mobile');
  });
});
