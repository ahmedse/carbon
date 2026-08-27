// src/__tests__/inspectorTabRegistry.test.jsx
// ADR-0019 Phase A — Contextual Inspector tab registry unit tests.
// Verifies the contribution-point contract: registration, matches filtering,
// ordering, label resolution, unregister, and invalid-provider rejection.
import { describe, it, expect, beforeEach } from 'vitest';
import {
  registerInspectorTab,
  tabsFor,
  tabLabel,
  inspectorTabCount,
  _resetInspectorTabRegistry,
} from '../inspector/InspectorTabRegistry';

describe('InspectorTabRegistry', () => {
  beforeEach(() => {
    _resetInspectorTabRegistry();
  });

  it('rejects providers without a valid id', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    registerInspectorTab({ render: () => null });
    registerInspectorTab(null);
    expect(inspectorTabCount()).toBe(0);
    warn.mockRestore();
  });

  it('rejects providers without a render function', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    registerInspectorTab({ id: 'noop' });
    expect(inspectorTabCount()).toBe(0);
    warn.mockRestore();
  });

  it('registers a valid provider and returns an unregister function', () => {
    const unregister = registerInspectorTab({ id: 'health', render: () => null });
    expect(inspectorTabCount()).toBe(1);
    unregister();
    expect(inspectorTabCount()).toBe(0);
  });

  it('filters tabs by matches(context) and sorts by order', () => {
    registerInspectorTab({ id: 'activity', order: 30, matches: () => true, render: () => null });
    registerInspectorTab({ id: 'lineage', order: 20, matches: (c) => c?.entityType === 'module', render: () => null });
    registerInspectorTab({ id: 'health', order: 10, matches: (c) => c?.entityType === 'module', render: () => null });

    const moduleTabs = tabsFor({ entityType: 'module', entityId: 1 });
    expect(moduleTabs.map((p) => p.id)).toEqual(['health', 'lineage', 'activity']);

    const otherTabs = tabsFor({ entityType: 'org_unit', entityId: 42 });
    expect(otherTabs.map((p) => p.id)).toEqual(['activity']);
  });

  it('treats a missing matches() as always-true', () => {
    registerInspectorTab({ id: 'impact', render: () => null });
    expect(tabsFor(null).map((p) => p.id)).toEqual(['impact']);
  });

  it('resolves labels from string or t-factory', () => {
    registerInspectorTab({ id: 'a', label: 'Health', render: () => null });
    registerInspectorTab({ id: 'b', label: (t) => t('tabs.notes'), render: () => null });

    const t = (key) => `__${key}__`;
    const [a, b] = tabsFor(null);
    expect(tabLabel(a, t)).toBe('Health');
    expect(tabLabel(b, t)).toBe('__tabs.notes__');
    // Missing label falls back to id.
    registerInspectorTab({ id: 'c', render: () => null });
    const c = tabsFor(null).find((p) => p.id === 'c');
    expect(tabLabel(c, t)).toBe('c');
  });
});
