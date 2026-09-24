// src/shell/EnvelopeMessage.test.jsx
// PAQ-2B — deterministic renderer for the typed AnswerEnvelope.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';

// react-chartjs-2 needs a canvas 2D context — not available in jsdom.
vi.mock('react-chartjs-2', () => ({
  Bar: () => <div data-testid="chartjs" data-type="bar" />,
  Doughnut: () => <div data-testid="chartjs" data-type="pie" />,
  Line: () => <div data-testid="chartjs" data-type="line" />,
}));

import EnvelopeMessage from './EnvelopeMessage';

const sampleEnvelope = {
  headline: 'Male employees outnumber female employees 6 to 2.',
  prose: ['Paragraph one with **bold**.', 'Paragraph two with *emphasis*.'],
  tables: [
    {
      title: 'Gender breakdown',
      columns: ['Gender', 'Employees'],
      rows: [['male', 6], ['female', 2]],
    },
  ],
  charts: [
    {
      chart_type: 'bar',
      title: 'Employees by gender',
      series: [{ name: 'Employees', data: [['male', 6], ['female', 2]] }],
    },
  ],
  caveats: [{ level: 'info', text: '8% have no gender recorded.' }],
  sources: [
    { tool: 'analyze_employees', rows_returned: 2, truncated: false, resolved_at: '2026-09-14T10:30:00Z' },
  ],
};

describe('EnvelopeMessage — full envelope', () => {
  it('renders headline and prose (markdown still works)', () => {
    render(<EnvelopeMessage envelope={sampleEnvelope} fallbackContent="" />);

    expect(screen.getByText(/Male employees outnumber female employees 6 to 2\./)).toBeInTheDocument();
    expect(screen.getByText(/Paragraph one with/)).toBeInTheDocument();
    expect(screen.getByText('bold')).toBeInTheDocument();
    expect(screen.getByText(/Paragraph two with/)).toBeInTheDocument();
  });

  it('headline-only envelopes use OutcomeReceipt (Result parity)', () => {
    render(
      <EnvelopeMessage
        envelope={{
          headline: 'Loan request submitted.',
          prose: ['Awaiting manager in Team.'],
          tables: [],
          charts: [],
          caveats: [],
          sources: [],
        }}
        fallbackContent=""
      />,
    );
    expect(screen.getByTestId('envelope-receipt')).toBeInTheDocument();
    expect(screen.getByTestId('outcome-receipt')).toBeInTheDocument();
  });

  it('renders table cells and column headers deterministically', () => {
    render(<EnvelopeMessage envelope={sampleEnvelope} fallbackContent="" />);

    const table = screen.getByTestId('envelope-table');
    expect(within(table).getByText('Gender breakdown')).toBeInTheDocument();
    expect(within(table).getByText('Gender')).toBeInTheDocument();
    expect(within(table).getByText('Employees')).toBeInTheDocument();
    expect(within(table).getByText('male')).toBeInTheDocument();
    expect(within(table).getByText('6')).toBeInTheDocument();
    expect(within(table).getByText('female')).toBeInTheDocument();
    expect(within(table).getByText('2')).toBeInTheDocument();
  });

  it('renders caveats as a disclosure banner with the text', () => {
    render(<EnvelopeMessage envelope={sampleEnvelope} fallbackContent="" />);

    expect(screen.getByTestId('envelope-caveat')).toBeInTheDocument();
    expect(screen.getByText('8% have no gender recorded.')).toBeInTheDocument();
  });

  it('rewrites ADR-0046 host-mutation caveats into operator language', () => {
    render(
      <EnvelopeMessage
        envelope={{
          headline: 'Leave prepared',
          prose: ['Draft ready.'],
          caveats: [
            {
              level: 'info',
              text: 'Chat cannot stage host mutations (ADR-0046 / G2).',
            },
          ],
        }}
        fallbackContent=""
      />,
    );
    const caveat = screen.getByTestId('envelope-caveat');
    expect(caveat).toHaveTextContent(/can’t be submitted in Chat/i);
    expect(caveat).not.toHaveTextContent(/ADR-0046/);
    expect(caveat).not.toHaveTextContent(/host mutations/i);
  });

  it('renders Based on chips in outcome language (no engine tool ids)', () => {
    render(<EnvelopeMessage envelope={sampleEnvelope} fallbackContent="" />);

    expect(screen.getByText(/Based on/i)).toBeInTheDocument();
    const source = screen.getByTestId('envelope-source');
    expect(source).toHaveTextContent('Employee data');
    expect(source).not.toHaveTextContent('analyze_employees');
    expect(source).not.toHaveTextContent('rows');
  });

  it('maps call_host_api leave sources without leaking the tool id or 0 rows', () => {
    render(
      <EnvelopeMessage
        envelope={{
          headline: 'Leave ready',
          sources: [
            {
              tool: 'call_host_api',
              rows_returned: 0,
              api_name: 'self/leave/balance',
              resolved_at: '2026-09-14T10:30:00Z',
            },
          ],
        }}
        fallbackContent=""
      />,
    );

    const source = screen.getByTestId('envelope-source');
    expect(source).toHaveTextContent('Leave balance');
    expect(source).not.toHaveTextContent('call_host_api');
    expect(source).not.toHaveTextContent('0');
  });

  it('renders proof-friendly people sources without raw tool ids on L0', () => {
    render(
      <EnvelopeMessage
        envelope={{
          headline: 'Answer',
          sources: [
            {
              tool: 'people_query',
              rows_returned: 1200,
              truncated: true,
              resolved_at: '2026-09-14T10:30:00Z',
            },
          ],
        }}
        fallbackContent=""
      />,
    );

    const source = screen.getByTestId('envelope-source');
    expect(source).toHaveTextContent('People records');
    expect(source).not.toHaveTextContent('people_query');
    expect(source).not.toHaveTextContent('1200');
  });

  it('renders a chart with the declared type', () => {
    render(<EnvelopeMessage envelope={sampleEnvelope} fallbackContent="" />);

    const chart = screen.getByTestId('envelope-chart');
    expect(screen.getByText('Employees by gender')).toBeInTheDocument();
    expect(within(chart).getByTestId('chartjs')).toHaveAttribute('data-type', 'bar');
  });

  it('omits empty-series charts (no title + No data shell)', () => {
    render(
      <EnvelopeMessage
        envelope={{
          headline: 'We have 530 active employees.',
          prose: ['Headcount is grounded on is_active=True.'],
          charts: [
            { chart_type: 'bar', title: 'Active Employee Count', series: [] },
            {
              chart_type: 'bar',
              title: 'Still empty',
              series: [{ name: 'Employees', data: [] }],
            },
          ],
          sources: [{ tool: 'aggregate_entity', rows_returned: 1, truncated: false }],
        }}
        fallbackContent=""
      />,
    );

    expect(screen.getByText(/530 active employees/)).toBeInTheDocument();
    expect(screen.queryByTestId('envelope-chart')).not.toBeInTheDocument();
    expect(screen.queryByText('Active Employee Count')).not.toBeInTheDocument();
    expect(screen.queryByText('No data')).not.toBeInTheDocument();
  });

  it('omits single-point headcount bars', () => {
    render(
      <EnvelopeMessage
        envelope={{
          headline: 'Company has 555 active employees.',
          prose: ['Headcount only — no distribution.'],
          charts: [
            {
              chart_type: 'bar',
              title: 'Total active employees',
              series: [{ name: 'Total', data: [['Total active employees', 555]] }],
            },
          ],
          sources: [{ tool: 'aggregate_entity', rows_returned: 1, truncated: false }],
        }}
        fallbackContent=""
      />,
    );

    expect(screen.getByText(/555 active employees/)).toBeInTheDocument();
    expect(screen.queryByTestId('envelope-chart')).not.toBeInTheDocument();
  });

  it('renders pie and line chart types without crashing', () => {
    render(
      <EnvelopeMessage
        envelope={{
          charts: [
            { chart_type: 'pie', title: 'Pie', series: [{ name: 's', data: [['a', 3], ['b', 1]] }] },
            { chart_type: 'line', title: 'Line', series: [{ name: 's', data: [['a', 1], ['b', 2]] }] },
          ],
        }}
        fallbackContent=""
      />,
    );

    const charts = screen.getAllByTestId('envelope-chart');
    expect(charts).toHaveLength(2);
    expect(within(charts[0]).getByTestId('chartjs')).toHaveAttribute('data-type', 'pie');
    expect(within(charts[1]).getByTestId('chartjs')).toHaveAttribute('data-type', 'line');
  });

  it('renders "No data" for an empty table', () => {
    render(
      <EnvelopeMessage
        envelope={{ tables: [{ title: 'Empty', columns: ['A', 'B'], rows: [] }] }}
        fallbackContent=""
      />,
    );

    expect(within(screen.getByTestId('envelope-table')).getByText('No data')).toBeInTheDocument();
  });
});

describe('EnvelopeMessage — fallback (zero regression)', () => {
  it('renders the markdown fallback when envelope is null', () => {
    render(<EnvelopeMessage envelope={null} fallbackContent="Fallback **text**" />);

    expect(screen.getByText(/Fallback/)).toBeInTheDocument();
    expect(screen.queryByTestId('envelope-table')).not.toBeInTheDocument();
    expect(screen.queryByTestId('envelope-chart')).not.toBeInTheDocument();
  });

  it('renders the markdown fallback when envelope is not an object', () => {
    render(<EnvelopeMessage envelope="not-an-object" fallbackContent="Plain fallback" />);

    expect(screen.getByText('Plain fallback')).toBeInTheDocument();
    expect(screen.queryByTestId('envelope-table')).not.toBeInTheDocument();
  });
});
