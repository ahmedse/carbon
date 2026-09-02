// src/__tests__/EntityChip.test.jsx
// Phase F1-F — inline entity chips in AI assistant messages:
//   * EntityChip renders the label + a per-kind icon
//   * clicking opens the Contextual Inspector (setContexts + setOpen)
//   * MarkdownMessage turns `[[kind:id:label]]` into an EntityChip
//   * refs inside fenced code blocks are NOT chipped
//   * unknown kinds stay literal text
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock useNotes at the module boundary so EntityChip can be rendered in
// isolation and its click handler can be asserted precisely.
const notesMock = vi.hoisted(() => ({
  setContexts: vi.fn(),
  setOpen: vi.fn(),
}));

vi.mock('../notes/NotesContext', () => ({
  useNotes: () => notesMock,
}));

import EntityChip from '../shell/EntityChip';
import MarkdownMessage from '../shell/MarkdownMessage';

const renderMessage = (content) =>
  render(
    <MemoryRouter>
      <MarkdownMessage content={content} />
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.clearAllMocks();
});

describe('EntityChip', () => {
  it('renders the label and the correct per-kind icon', () => {
    const { rerender } = render(<EntityChip kind="table" id="42" label="emissions_fuel" />);
    expect(screen.getByText('emissions_fuel')).toBeInTheDocument();
    expect(screen.getByTestId('entity-chip-icon-table')).toBeInTheDocument();

    rerender(<EntityChip kind="rule" id="7" label="dq_rule_x" />);
    expect(screen.getByText('dq_rule_x')).toBeInTheDocument();
    expect(screen.getByTestId('entity-chip-icon-rule')).toBeInTheDocument();

    rerender(<EntityChip kind="module" id="3" label="data_product_y" />);
    expect(screen.getByTestId('entity-chip-icon-module')).toBeInTheDocument();

    rerender(<EntityChip kind="org-unit" id="9" label="org_unit_z" />);
    expect(screen.getByTestId('entity-chip-icon-org-unit')).toBeInTheDocument();
  });

  it('renders a fallback icon for unknown kinds', () => {
    render(<EntityChip kind="foo" id="1" label="x" />);
    expect(screen.getByText('x')).toBeInTheDocument();
    expect(screen.getByTestId('entity-chip-icon-foo')).toBeInTheDocument();
  });

  it('opens the Inspector on click — setContexts then setOpen', () => {
    render(<EntityChip kind="table" id="42" label="emissions_fuel" />);
    fireEvent.click(screen.getByText('emissions_fuel'));

    expect(notesMock.setContexts).toHaveBeenCalledTimes(1);
    expect(notesMock.setContexts).toHaveBeenCalledWith([
      { entityType: 'table', entityId: '42', label: 'emissions_fuel' },
    ]);
    expect(notesMock.setOpen).toHaveBeenCalledTimes(1);
    expect(notesMock.setOpen).toHaveBeenCalledWith(true);
  });
});

describe('MarkdownMessage entity refs', () => {
  it('turns [[table:42:emissions_fuel]] into an EntityChip and removes the literal', () => {
    renderMessage('See [[table:42:emissions_fuel]] here.');
    expect(screen.getByText('emissions_fuel')).toBeInTheDocument();
    expect(screen.getByTestId('entity-chip-icon-table')).toBeInTheDocument();
    expect(screen.queryByText('[[table:42:emissions_fuel]]')).not.toBeInTheDocument();
  });

  it('does not chip a ref inside a fenced code block', () => {
    renderMessage('```\n[[table:42:emissions_fuel]]\n```');
    // The literal survives (inside the code block) …
    const codeEl = document.querySelector('code');
    expect(codeEl).not.toBeNull();
    expect(codeEl.textContent).toContain('[[table:42:emissions_fuel]]');
    // … and no chip is rendered.
    expect(screen.queryByTestId('entity-chip-icon-table')).not.toBeInTheDocument();
  });

  it('leaves unknown kinds as literal text', () => {
    renderMessage('Inspect [[foo:1:x]] now.');
    expect(screen.getByText('Inspect [[foo:1:x]] now.')).toBeInTheDocument();
    expect(screen.queryByTestId('entity-chip-icon-foo')).not.toBeInTheDocument();
  });
});
