// src/shell/__tests__/AgentResultToolbar.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import AgentResultToolbar from '../AgentResultToolbar';

const theme = createTheme();

function wrap(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider theme={theme}>{ui}</ThemeProvider>
    </MemoryRouter>,
  );
}

describe('AgentResultToolbar', () => {
  it('shows host CTA, Discuss, Rerun, and More exports', async () => {
    const onDiscuss = vi.fn();
    const onRerun = vi.fn();
    const onExportLedger = vi.fn();
    wrap(
      <AgentResultToolbar
        hostActions={[{ route: '/my/requests/1', label: 'Open loan request', summary: 'CRS-1' }]}
        rerunnable
        canExportLedger
        canExportResponse
        onDiscuss={onDiscuss}
        onRerun={onRerun}
        onExportLedger={onExportLedger}
        onExportResponse={vi.fn()}
        onOpenPlan={vi.fn()}
      />,
    );
    expect(screen.getByTestId('result-primary-cta')).toHaveTextContent('Open loan request');
    fireEvent.click(screen.getByRole('button', { name: /Discuss in Chat/i }));
    expect(onDiscuss).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Rerun' }));
    expect(onRerun).toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('result-more-menu'));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Ledger JSON' }));
    expect(onExportLedger).toHaveBeenCalled();
  });
});
