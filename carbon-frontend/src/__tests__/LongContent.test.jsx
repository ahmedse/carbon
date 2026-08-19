// src/__tests__/LongContent.test.jsx
// Phase 4C — long-content collapse/expand wrapper.
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LongContent from '../shell/LongContent';

describe('LongContent', () => {
  it('renders children untouched for short content', () => {
    render(
      <LongContent content="short">
        <p>Hello</p>
      </LongContent>,
    );
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Show/i })).not.toBeInTheDocument();
  });

  it('collapses long content and toggles Show more / Show less', () => {
    render(
      <LongContent content={'x'.repeat(2000)}>
        <p>Long body</p>
      </LongContent>,
    );

    const showMore = screen.getByRole('button', { name: /Show more/i });
    expect(showMore).toBeInTheDocument();

    fireEvent.click(showMore);
    expect(screen.getByRole('button', { name: /Show less/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Show less/i }));
    expect(screen.getByRole('button', { name: /Show more/i })).toBeInTheDocument();
  });

  it('respects a custom threshold', () => {
    render(
      <LongContent content="hello" threshold={3}>
        <p>Body</p>
      </LongContent>,
    );
    expect(screen.getByRole('button', { name: /Show more/i })).toBeInTheDocument();
  });
});
