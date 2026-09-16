// NSR-8B — Org-unit picker scope: tree sort/labels + orphan guard + wizard wiring.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('../hooks/useReferenceOptions', () => ({
  useReferenceOptions: () => ({ options: [], loading: false, error: null }),
}));

vi.mock('../components/MicroHelp', () => ({
  default: () => null,
}));

import {
  filterOrgUnitsToConnectedTree,
  orgUnitDepth,
  orgUnitOptionLabel,
  orgUnitSelectOptions,
  prepareOrgUnitsForPicker,
  sortOrgUnitsForTree,
} from '../api/orgUnits';
import EmployeeWizard from '../apps/people/EmployeeWizard';

const TREE = [
  { id: 3, name: 'Drilling', code: 'DRL', parent: 2 },
  { id: 1, name: 'GOFSCO', code: 'GOF', parent: null },
  { id: 2, name: 'Ahmadi', code: 'AHM', parent: 1 },
  { id: 4, name: 'Ops Support', code: 'OPS', parent: 2 },
];

const WITH_FOREIGN = [
  ...TREE,
  { id: 90, name: 'AAST Root', code: 'AAST', parent: null },
  { id: 91, name: 'Campus', code: 'CAM', parent: 90 },
  { id: 99, name: 'Orphan Leaf', code: 'ORP', parent: 777 },
];

describe('org unit tree helpers (NSR-8B)', () => {
  it('sortOrgUnitsForTree puts parents before children', () => {
    const sorted = sortOrgUnitsForTree(TREE);
    expect(sorted.map((u) => u.id)).toEqual([1, 2, 3, 4]);
  });

  it('orgUnitOptionLabel indents by depth', () => {
    const prepared = prepareOrgUnitsForPicker(TREE);
    const byId = new Map(prepared.map((u) => [u.id, u]));
    const labels = prepared.map((u) =>
      orgUnitOptionLabel(u, { depth: orgUnitDepth(u, byId) }),
    );
    expect(labels[0]).toBe('GOFSCO');
    expect(labels[1]).toBe('\u2003Ahmadi');
    expect(labels[2]).toBe('\u2003\u2003Drilling');
    expect(labels[3]).toBe('\u2003\u2003Ops Support');
  });

  it('orgUnitOptionLabel prefers full_path when requested', () => {
    const unit = {
      id: 3,
      name: 'Drilling',
      full_path: 'GOFSCO / Ahmadi / Drilling',
      parent: 2,
    };
    expect(orgUnitOptionLabel(unit, { preferPath: true })).toBe(
      'GOFSCO / Ahmadi / Drilling',
    );
  });

  it('filterOrgUnitsToConnectedTree drops orphans (parent missing from set)', () => {
    const filtered = filterOrgUnitsToConnectedTree([
      { id: 1, name: 'Root', parent: null },
      { id: 2, name: 'Child', parent: 1 },
      { id: 99, name: 'Orphan', parent: 777 },
    ]);
    expect(filtered.map((u) => u.id)).toEqual([1, 2]);
  });

  it('prepareOrgUnitsForPicker keeps multiple roots but drops orphans', () => {
    // API should already scope to one deployment; FE still drops orphans.
    const prepared = prepareOrgUnitsForPicker(WITH_FOREIGN);
    const ids = prepared.map((u) => u.id);
    expect(ids).toContain(1);
    expect(ids).toContain(90);
    expect(ids).toContain(91);
    expect(ids).not.toContain(99);
    // Tree order within each connected component
    expect(ids.indexOf(1)).toBeLessThan(ids.indexOf(2));
    expect(ids.indexOf(2)).toBeLessThan(ids.indexOf(3));
    expect(ids.indexOf(90)).toBeLessThan(ids.indexOf(91));
  });

  it('orgUnitSelectOptions emits value/label pairs with indent', () => {
    const opts = orgUnitSelectOptions(TREE);
    expect(opts).toHaveLength(4);
    expect(opts[0]).toMatchObject({ value: '1', label: 'GOFSCO', id: 1 });
    expect(opts[1].label.startsWith('\u2003')).toBe(true);
    expect(opts[1].label.trim()).toBe('Ahmadi');
  });
});

describe('EmployeeWizard org picker wiring (NSR-8B)', () => {
  it('shows indented org-unit options from a hierarchical list', async () => {
    render(
      <EmployeeWizard
        orgUnits={TREE}
        positions={[]}
        employees={[{ id: 5, employee_no: '1001', full_name: 'Sara Manager' }]}
        canViewCompensation={false}
        saving={false}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'New Hire' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    const orgField = screen.getByLabelText(/Org Unit/i);
    fireEvent.mouseDown(orgField);

    // Autocomplete listbox options — leaf names present; deep nodes indented
    const options = await screen.findAllByRole('option');
    const texts = options.map((el) => el.textContent || '');
    expect(texts.some((t) => t.includes('GOFSCO'))).toBe(true);
    expect(texts.some((t) => t.includes('Ahmadi'))).toBe(true);
    expect(texts.some((t) => t.includes('Drilling'))).toBe(true);
    // Order: root before child
    const gof = texts.findIndex((t) => t.includes('GOFSCO'));
    const ahm = texts.findIndex((t) => t.includes('Ahmadi'));
    expect(gof).toBeGreaterThanOrEqual(0);
    expect(ahm).toBeGreaterThan(gof);
  });
});
