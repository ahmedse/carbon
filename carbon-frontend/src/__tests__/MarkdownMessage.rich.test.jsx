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
import MarkdownMessage, {
  normalizeMermaidFences,
  reflowSingleLineMermaid,
  reflowMarkdownStructure,
} from '../shell/MarkdownMessage';

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

  describe('normalizeMermaidFences', () => {
    it('moves an inline ```mermaid fence onto its own line', () => {
      const input =
        'Here are the factors: ```mermaid\nxychart-beta title "T" x-axis [A, B] y-axis "y" 0 --> 3 bar [1, 2]\n``` Thanks!';
      const out = normalizeMermaidFences(input);
      const lines = out.split('\n');
      expect(lines).toContain('```mermaid');
      expect(lines).toContain('```');
      expect(out).toMatch(/\n```mermaid\n/);
      expect(out).toMatch(/\n```\s*\n/);
    });

    it('splits a closing fence glued to a following opening fence on one line', () => {
      const input = '``` x ### Next ```mermaid\npie title S "A" : 1\n```';
      const out = normalizeMermaidFences(input);
      const lines = out.split('\n');
      expect(lines).toContain('```mermaid');
      expect(lines).toContain('```');
    });

    it('leaves well-formed multi-line mermaid unchanged', () => {
      const good =
        '**Takeaway**\n\n```mermaid\npie title Scope\n    "Scope 1" : 4\n```\n\nMore.';
      expect(normalizeMermaidFences(good)).toBe(good);
    });
  });

  describe('reflowSingleLineMermaid', () => {
    it('reflows a collapsed single-line xychart-beta into line directives', () => {
      const single =
        'xychart-beta title Emission Factors by Source (kg CO2e per unit) x-axis [Diesel, Gasoline, LPG] y-axis "kg CO2e" 0 --> 2.8 bar [2.51, 2.19, 1.52]';
      const out = reflowSingleLineMermaid(single);
      expect(out).toContain('xychart-beta\n    title Emission Factors by Source (kg CO2e per unit)');
      expect(out).toContain('x-axis [Diesel, Gasoline, LPG]');
      expect(out).toContain('y-axis "kg CO2e" 0 --> 2.8');
      expect(out).toContain('bar [2.51, 2.19, 1.52]');
    });

    it('reflows a collapsed single-line pie into title + slices', () => {
      const single = 'pie title Emission Factors by Scope "Scope 1" : 5 "Scope 2" : 2';
      const out = reflowSingleLineMermaid(single);
      expect(out).toContain('pie\n    title Emission Factors by Scope');
      expect(out).toContain('"Scope 1" : 5');
      expect(out).toContain('"Scope 2" : 2');
    });

    it('passes through already multi-line mermaid unchanged', () => {
      const multi = 'pie\n    title Scope\n    "Scope 1" : 4';
      expect(reflowSingleLineMermaid(multi)).toBe(multi);
    });
  });

  describe('reflowMarkdownStructure', () => {
    it('moves an inline ATX heading onto its own line', () => {
      const input = 'Paris goals. ### Key Features of SBTi:';
      const out = reflowMarkdownStructure(input);
      expect(out).toContain('Paris goals.\n### Key Features of SBTi:');
    });

    it('reflows a collapsed bold ordered list into one item per line', () => {
      const input =
        '1. **A**: first - bullet 2. **B**: second 3. **C**: third';
      const out = reflowMarkdownStructure(input);
      const lines = out.split('\n');
      expect(lines).toContain('1. **A**: first - bullet');
      expect(lines).toContain('2. **B**: second');
      expect(lines).toContain('3. **C**: third');
    });

    it('reflows a collapsed plain ordered list (2+ markers)', () => {
      const input = '1. Alpha 2. Beta 3. Gamma';
      const out = reflowMarkdownStructure(input);
      expect(out).toContain('1. Alpha\n2. Beta\n3. Gamma');
    });

    it('reflows collapsed bullets onto their own lines', () => {
      const input = '**Targets**: - Scope 1 - Scope 2';
      const out = reflowMarkdownStructure(input);
      const lines = out.split('\n');
      expect(lines).toContain('**Targets**:');
      expect(lines).toContain('- Scope 1');
      expect(lines).toContain('- Scope 2');
    });

    it('leaves fenced code blocks untouched', () => {
      const input = 'Text\n```python\n# 1. not a list - no bullet\n```\nMore';
      const out = reflowMarkdownStructure(input);
      expect(out).toContain('# 1. not a list - no bullet');
    });

    it('does not split prose decimals or em-dashes', () => {
      const input = 'Limit warming to 1.5°C - well below 2°C.';
      expect(reflowMarkdownStructure(input)).toBe(input);
    });

    it('does not mistake a 4-digit year for a list marker', () => {
      const input =
        '4. **Net-Zero**: net-zero by 2050. 5. **Global**: worldwide';
      const out = reflowMarkdownStructure(input);
      expect(out).toContain('net-zero by 2050.');
      expect(out).toContain('5. **Global**: worldwide');
      // The year must stay attached to "by" — not split onto its own line.
      expect(out).not.toContain('by\n2050.');
    });
  });
});
