// src/__tests__/calculationTabs.test.jsx
// ADR-0019 Phase C — Calculation Inspector tabs regression tests.
// Verifies registerCalculationInspectorTabs(): contribution contract, matches
// filtering, ordering, unregister, and the Overview / Data Quality bodies
// (loaded + empty states).
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import {
  tabsFor,
  inspectorTabCount,
  _resetInspectorTabRegistry,
} from '../inspector/InspectorTabRegistry';
import { registerCalculationInspectorTabs } from '../inspector/tabs/calculationTabs';

const theme = createTheme();

const renderTab = (provider, context) =>
  render(<ThemeProvider theme={theme}>{provider.render(context)}</ThemeProvider>);

const calcContext = (entityData) => ({
  entityType: 'calculation',
  entityId: 4745,
  label: 'FY2026 Q1',
  payload: { entityData },
});

describe('registerCalculationInspectorTabs', () => {
  beforeEach(() => {
    _resetInspectorTabRegistry();
  });

  it('registers overview + data-quality tabs and returns an unregister fn', () => {
    const unregister = registerCalculationInspectorTabs();
    expect(inspectorTabCount()).toBe(2);

    const tabs = tabsFor(calcContext({}));
    expect(tabs.map((p) => p.id)).toEqual(['calculation-overview', 'calculation-quality']);
    expect(tabs.map((p) => p.label)).toEqual(['Overview', 'Data Quality']);

    unregister();
    expect(inspectorTabCount()).toBe(0);
  });

  it('matches only calculation contexts (sorted by order)', () => {
    registerCalculationInspectorTabs();
    expect(tabsFor({ entityType: 'module', entityId: 1 })).toEqual([]);
    expect(tabsFor({ entityType: 'calculation' }).map((p) => p.id)).toEqual([
      'calculation-overview',
      'calculation-quality',
    ]);
  });

  it('Overview tab renders calculation metadata when a calc is selected', () => {
    registerCalculationInspectorTabs();
    const [overview] = tabsFor(calcContext({}));

    renderTab(overview, calcContext({
      period_name: 'FY2026 Q1',
      scope: 1,
      status: 'draft',
      total_emissions: 1234.5,
      rule_name: 'GHG Protocol Fuel',
      rule_version: 'v2.1',
      org_unit_name: 'Campus A',
      data_source_count: 3,
      rows_processed: 512,
      last_calculated: '2026-08-20T10:00:00Z',
      calculated_by_name: 'ahmed',
    }));

    expect(screen.getByText('Calculation Metadata')).toBeInTheDocument();
    expect(screen.getByText('FY2026 Q1')).toBeInTheDocument();
    expect(screen.getByText('Scope 1')).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getByText('1,234.50')).toBeInTheDocument();
    expect(screen.getByText('GHG Protocol Fuel')).toBeInTheDocument();
    expect(screen.getByText('v2.1')).toBeInTheDocument();
    expect(screen.getByText('Campus A')).toBeInTheDocument();
    expect(screen.getByText('512')).toBeInTheDocument();
    expect(screen.getByText('ahmed')).toBeInTheDocument();
  });

  it('Overview tab shows an empty state when no calc is selected', () => {
    registerCalculationInspectorTabs();
    const [overview] = tabsFor(calcContext({}));

    renderTab(overview, { entityType: 'calculation', entityId: null, payload: {} });

    expect(screen.getByText('Select a calculation to view details.')).toBeInTheDocument();
  });

  it('Data Quality tab shows empty state when no metrics exist', () => {
    registerCalculationInspectorTabs();
    const [, quality] = tabsFor(calcContext({}));

    renderTab(quality, calcContext({ data_quality: {} }));

    expect(screen.getByText('No quality metrics available for this calculation.')).toBeInTheDocument();
  });

  it('Data Quality tab renders scores and issues when present', () => {
    registerCalculationInspectorTabs();
    const [, quality] = tabsFor(calcContext({}));

    renderTab(quality, calcContext({
      data_quality: {
        completeness_score: 95,
        accuracy_score: 70,
        timeliness_score: 50,
      },
      dq_issues: ['Missing fuel type on 2 rows'],
    }));

    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('70%')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
    expect(screen.getByText('1 Issue')).toBeInTheDocument();
    expect(screen.getByText('Missing fuel type on 2 rows')).toBeInTheDocument();
  });
});
