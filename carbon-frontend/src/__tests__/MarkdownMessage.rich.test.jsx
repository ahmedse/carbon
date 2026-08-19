// src/__tests__/MarkdownMessage.rich.test.jsx
// Generic rich markdown renderer for AI assistant messages — content-driven,
// not bespoke per feature:
//   * GFM tables → MUI Table
//   * fenced code → dark block + language badge + copy button
//   * internal safe links → SPA <Link>; external → new-tab anchor
//   * task lists → checkboxes
//   * figures → image + optional caption
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MarkdownMessage from '../shell/MarkdownMessage';

const renderRich = (content) =>
  render(
    <MemoryRouter>
      <MarkdownMessage content={content} />
    </MemoryRouter>,
  );

describe('MarkdownMessage rich renderer', () => {
  it('renders a GFM table with headers and rows', () => {
    renderRich(
      '| Work area | Open |\n|---|---|\n| Data Quality | [Open](/dq) |\n| Catalog | [Open](/catalog) |',
    );
    expect(screen.getByText('Work area')).toBeInTheDocument();
    expect(screen.getByText('Data Quality')).toBeInTheDocument();
    expect(screen.getByText('Catalog')).toBeInTheDocument();
    const openLinks = screen.getAllByRole('link', { name: 'Open' });
    expect(openLinks).toHaveLength(2);
  });

  it('renders a fenced code block with language badge and copy button', () => {
    renderRich('```python\nprint("hi")\n```');
    expect(screen.getByText('python')).toBeInTheDocument();
    expect(screen.getByLabelText('Copy code')).toBeInTheDocument();
    // text is split across syntax-highlight spans — check the container text
    const codeEl = document.querySelector('code[class*="language-python"]');
    expect(codeEl).not.toBeNull();
    expect(codeEl.textContent.trim()).toBe('print("hi")');
  });

  it('renders inline code without a block', () => {
    renderRich('Use `range(1, 5)` here.');
    const code = screen.getByText('range(1, 5)');
    expect(code.tagName.toLowerCase()).toBe('code');
  });

  it('renders internal safe links as SPA links (not new-tab anchors)', () => {
    renderRich('[Data Quality](/dq/rules)');
    const link = screen.getByText('Data Quality').closest('a');
    expect(link).toBeInTheDocument();
    expect(link.getAttribute('href')).toBe('/dq/rules');
    expect(link.getAttribute('target')).not.toBe('_blank');
  });

  it('renders external links as new-tab anchors', () => {
    renderRich('[Docs](https://example.com/docs)');
    const link = screen.getByText('Docs').closest('a');
    expect(link.getAttribute('href')).toBe('https://example.com/docs');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
  });

  it('renders task lists as checkboxes', () => {
    renderRich('- [x] done\n- [ ] todo');
    const checked = screen.getByRole('checkbox', { checked: true });
    const unchecked = screen.getByRole('checkbox', { checked: false });
    expect(checked).toBeInTheDocument();
    expect(unchecked).toBeInTheDocument();
  });

  it('renders a figure with caption from image title', () => {
    renderRich('![trend](https://example.com/trend.png "Q3 trend")');
    const img = screen.getByAltText('trend');
    expect(img).toBeInTheDocument();
    expect(img.getAttribute('src')).toBe('https://example.com/trend.png');
    expect(screen.getByText('Q3 trend')).toBeInTheDocument();
  });

  it('renders blockquote and headings', () => {
    renderRich('## Title\n\n> quoted');
    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('quoted')).toBeInTheDocument();
  });

  it('does not break on empty content', () => {
    renderRich('');
    expect(document.body).toBeTruthy();
  });
});
