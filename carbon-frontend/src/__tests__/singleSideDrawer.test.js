// src/__tests__/singleSideDrawer.test.js
// Guardrail: there is exactly ONE side drawer system on the page — the standard
// Notes drawer — and Journey lives inside it as a tab. A second docked Journey
// panel must never come back.
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const SRC = join(process.cwd(), 'src');

describe('One side drawer system', () => {
  it('docks only the Notes drawer in the shell', () => {
    const shell = readFileSync(join(SRC, 'shell', 'Shell.jsx'), 'utf8');
    expect(shell).not.toMatch(/JourneyLauncher/);
    expect(shell).toMatch(/DOCKED_PANES = isMobile \? \[\] : \[<NotesDrawer key="notes" \/>\]/);
    expect(shell).toContain('JourneyInspectorTabRegistrar');
  });

  it('deletes the separate Journey dock and its parallel notes store', () => {
    const journeyDir = join(SRC, 'components', 'journey');
    const files = readdirSync(journeyDir);
    expect(files).not.toContain('JourneyLauncher.jsx');
    expect(files).not.toContain('useJourneyNotes.js');
  });

  it('has no leftover journey-launcher testids in the shell or journey components', () => {
    const roots = [join(SRC, 'shell'), join(SRC, 'components', 'journey'), join(SRC, 'inspector')];
    const offenders = [];
    const walk = (dir) => {
      readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (/\.(jsx?|tsx?)$/.test(entry.name)) {
          const text = readFileSync(full, 'utf8');
          if (/journey-launcher-/.test(text)) offenders.push(full);
        }
      });
    };
    roots.forEach(walk);
    expect(offenders).toEqual([]);
  });
});
