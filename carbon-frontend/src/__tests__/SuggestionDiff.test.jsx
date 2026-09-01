// src/__tests__/SuggestionDiff.test.jsx
// Wave D3 — legible "will be created" consent summary: structured definition
// rows + severity/dimension + params + bindings, with label-map fallbacks and
// a defensive rationale-only render when the definition is missing.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SuggestionDiff from '../shell/SuggestionDiff';

const fullSuggestion = {
  definition: {
    name: 'Electricity threshold',
    type: 'threshold',
    level: 'business_rule',
    params: { operator: 'gte', value: 80 },
    bindings: [{ table: 'emissions', field: 'total_kwh' }],
    active: true,
  },
  rationale: 'Monthly electricity must stay under 80% of prior year.',
  severity: 'warn',
  confidence: 0.84,
  dimension: 'accuracy',
};

describe('SuggestionDiff', () => {
  it('renders name, type, level, severity, dimension, params, and bindings', () => {
    render(<SuggestionDiff suggestion={fullSuggestion} />);

    expect(screen.getByText('Electricity threshold')).toBeInTheDocument();
    expect(screen.getByText('Threshold')).toBeInTheDocument();
    expect(screen.getByText('Business Rule')).toBeInTheDocument();
    expect(screen.getByText('Warning')).toBeInTheDocument();
    expect(screen.getByText('Accuracy')).toBeInTheDocument();
    expect(screen.getByText('emissions.total_kwh')).toBeInTheDocument();
    expect(screen.getByText('operator: gte')).toBeInTheDocument();
    expect(screen.getByText('value: 80')).toBeInTheDocument();
    expect(
      screen.getByText('Monthly electricity must stay under 80% of prior year.'),
    ).toBeInTheDocument();
  });

  it('falls back to the raw value when a label map is missing the key', () => {
    render(
      <SuggestionDiff
        suggestion={{
          ...fullSuggestion,
          definition: { ...fullSuggestion.definition, type: 'custom_rule_type' },
          severity: 'weird',
        }}
      />,
    );

    expect(screen.getByText('custom_rule_type')).toBeInTheDocument();
    expect(screen.getByText('weird')).toBeInTheDocument();
  });

  it('renders rationale only (no crash) when definition is undefined', () => {
    render(
      <SuggestionDiff
        suggestion={{ rationale: 'Just a rationale.', severity: 'info' }}
      />,
    );

    expect(screen.getByText('Just a rationale.')).toBeInTheDocument();
    expect(screen.queryByText('Threshold')).not.toBeInTheDocument();
  });

  it('renders an em dash when bindings are empty', () => {
    render(
      <SuggestionDiff
        suggestion={{ ...fullSuggestion, definition: { ...fullSuggestion.definition, bindings: [] } }}
      />,
    );

    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
