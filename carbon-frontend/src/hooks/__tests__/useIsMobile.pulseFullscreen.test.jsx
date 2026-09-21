import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';

const mq = vi.fn();

vi.mock('@mui/material', async () => {
  const actual = await vi.importActual('@mui/material');
  return {
    ...actual,
    useMediaQuery: (...args) => mq(...args),
  };
});

import { useIsMobile, useIsPhone, usePulseFullscreen } from '../useIsMobile';

function Probe({ hook: useHook }) {
  return <span data-testid="v">{String(useHook())}</span>;
}

describe('usePulseFullscreen tablet dock', () => {
  const theme = createTheme();

  beforeEach(() => {
    mq.mockReset();
  });

  function mount(hook) {
    return render(
      <ThemeProvider theme={theme}>
        <Probe hook={hook} />
      </ThemeProvider>,
    );
  }

  function queryText(q) {
    if (typeof q === 'function') return String(q(theme));
    return String(q);
  }

  it('phone portrait → fullscreen', () => {
    mq.mockImplementation((q) => queryText(q).includes('max-width'));
    mount(usePulseFullscreen);
    expect(screen.getByTestId('v').textContent).toBe('true');
  });

  it('tablet sm+ → docked (not fullscreen)', () => {
    mq.mockReturnValue(false);
    mount(usePulseFullscreen);
    expect(screen.getByTestId('v').textContent).toBe('false');
  });

  it('short landscape phone → fullscreen', () => {
    mq.mockImplementation((q) => queryText(q).includes('max-height: 500px'));
    mount(usePulseFullscreen);
    expect(screen.getByTestId('v').textContent).toBe('true');
    mount(useIsMobile);
    expect(screen.getAllByTestId('v').at(-1).textContent).toBe('true');
  });

  it('useIsPhone ignores short landscape', () => {
    mq.mockImplementation((q) => queryText(q).includes('max-height: 500px'));
    mount(useIsPhone);
    expect(screen.getByTestId('v').textContent).toBe('false');
  });
});
