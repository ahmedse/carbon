// src/shell/__tests__/OutcomeReceipt.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import OutcomeReceipt from '../OutcomeReceipt';
import {
  receiptFactsFromActions,
  receiptTitleFromAnswer,
} from '../resultOutcome';

vi.mock('../MarkdownMessage', () => ({
  default: ({ content }) => <div data-testid="markdown-message">{content}</div>,
}));

const theme = createTheme();

function wrap(ui) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

describe('OutcomeReceipt', () => {
  it('renders title, facts, and prose once', () => {
    wrap(
      <OutcomeReceipt
        title="Loan request submitted"
        stateLabel="Done"
        stateColor="success"
        facts="CRS-2026-0115 · personal · 500"
        markdown="Awaiting manager then finance review."
      />,
    );
    expect(screen.getByTestId('outcome-receipt')).toBeInTheDocument();
    expect(screen.getByText('Loan request submitted')).toBeInTheDocument();
    expect(screen.getByTestId('outcome-receipt-facts')).toHaveTextContent('CRS-2026-0115');
    expect(screen.getByTestId('markdown-message')).toHaveTextContent('Awaiting manager');
  });
});

describe('resultOutcome helpers', () => {
  it('builds a short title from the first sentence', () => {
    expect(receiptTitleFromAnswer('### Hello world. More text.')).toBe('Hello world.');
  });

  it('joins unique host action summaries', () => {
    expect(receiptFactsFromActions([
      { summary: 'CRS-1 · submitted' },
      { summary: 'CRS-1 · submitted' },
      { summary: '500 · 12 mo' },
    ])).toBe('CRS-1 · submitted · 500 · 12 mo');
  });
});
