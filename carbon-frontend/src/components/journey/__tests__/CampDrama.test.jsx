import React from 'react';
import {
  describe, it, expect, vi,
} from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import CampDrama from '../CampDrama';

// Two beats, mirroring the shape the pack ships: a line, a question, choices and
// the reasoning that is revealed only after the honest move.
const BEATS = [
  {
    id: 'keep_one_open',
    cast: 'Carbon Lead',
    line: 'A period from last year is still open. Two doors, one record.',
    question: 'What do you do first?',
    choices: ['Lock the old period.', 'Keep both open and sort it out later.', 'Open one more, to be safe.'],
    explain: 'Exactly one period may be open at a time.',
  },
  {
    id: 'cover_or_exclude',
    cast: 'Carbon Lead',
    line: 'A declared generator has no rows this period. The gap is quiet.',
    question: 'What belongs in the record?',
    choices: ['Say nothing, and hope it is small.', 'Chase the meter, or exclude it with a reason.'],
    explain: 'Coverage is a decision, not an accident.',
  },
];

const station = (beat) => ({
  n: 1,
  key: 'setup',
  scenarioBeat: beat,
  scenario: { beats: BEATS },
});

const renderDrama = (props = {}) => render(
  <CampDrama station={station(0)} glossary={[]} onAnswer={vi.fn()} {...props} />,
);

describe('CampDrama — the camp scene, played honestly', () => {
  it('renders nothing when the pack declares no drama', () => {
    render(<CampDrama station={{ n: 1, key: 'setup' }} glossary={[]} onAnswer={vi.fn()} />);
    expect(screen.queryByTestId('journey-drama')).not.toBeInTheDocument();
  });

  it('plays the current beat with the cast, the line and the choices', () => {
    renderDrama();
    expect(screen.getByTestId('journey-drama-cast')).toHaveTextContent('Carbon Lead');
    expect(screen.getByTestId('journey-drama-line')).toHaveTextContent('Two doors, one record.');
    expect(screen.getByTestId('journey-drama-question')).toHaveTextContent('What do you do first?');
    expect(screen.getByTestId('journey-drama-option-0')).toBeInTheDocument();
    expect(screen.getByTestId('journey-drama-option-2')).toBeInTheDocument();
    expect(screen.getByTestId('journey-drama-pips')).toHaveTextContent('Beat 0 of 2');
  });

  it('will not check an empty answer', () => {
    const onAnswer = vi.fn();
    renderDrama({ onAnswer });
    fireEvent.click(screen.getByTestId('journey-drama-check'));
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it('sends the caller index and the chosen move', () => {
    const onAnswer = vi.fn().mockResolvedValue({ correct: true, beat: 1, total: 2, done: false });
    renderDrama({ onAnswer });
    fireEvent.click(screen.getByTestId('journey-drama-option-0'));
    fireEvent.click(screen.getByTestId('journey-drama-check'));
    expect(onAnswer).toHaveBeenCalledWith(0, 0);
  });

  it('a wrong move keeps the beat open and never reveals the reasoning', async () => {
    const onAnswer = vi.fn().mockResolvedValue({ correct: false, beat: 0, total: 2, done: false });
    renderDrama({ onAnswer });
    fireEvent.click(screen.getByTestId('journey-drama-option-1'));
    fireEvent.click(screen.getByTestId('journey-drama-check'));
    expect(await screen.findByTestId('journey-drama-wrong')).toBeInTheDocument();
    expect(screen.queryByTestId('journey-drama-explain')).not.toBeInTheDocument();
    // Still the same beat, so the caller can reason again.
    expect(screen.getByTestId('journey-drama-question')).toHaveTextContent('What do you do first?');
  });

  it('the honest move reveals the reasoning and holds the next beat', async () => {
    const onAnswer = vi.fn().mockResolvedValue({ correct: true, beat: 1, total: 2, done: false });
    const { rerender } = renderDrama({ onAnswer });
    fireEvent.click(screen.getByTestId('journey-drama-option-0'));
    fireEvent.click(screen.getByTestId('journey-drama-check'));
    expect(await screen.findByTestId('journey-drama-explain'))
      .toHaveTextContent('Exactly one period may be open at a time.');

    // The parent's reload advanced the beat; the reasoning stays until acknowledged.
    rerender(<CampDrama station={station(1)} glossary={[]} onAnswer={onAnswer} />);
    expect(screen.getByTestId('journey-drama-explain')).toBeInTheDocument();
    expect(screen.queryByTestId('journey-drama-question')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('journey-drama-next'));
    expect(screen.getByTestId('journey-drama-question')).toHaveTextContent('What belongs in the record?');
    expect(screen.getByTestId('journey-drama-pips')).toHaveTextContent('Beat 1 of 2');
  });

  it('shows a cleared camp, not a gate, once every beat is walked', () => {
    render(<CampDrama station={station(2)} glossary={[]} onAnswer={vi.fn()} />);
    expect(screen.getByTestId('journey-drama-done')).toBeInTheDocument();
    expect(screen.queryByTestId('journey-drama-question')).not.toBeInTheDocument();
    expect(screen.queryByTestId('journey-drama-check')).not.toBeInTheDocument();
  });

  it('reports a failed send without advancing', async () => {
    const onAnswer = vi.fn().mockRejectedValue(new Error('offline'));
    renderDrama({ onAnswer });
    fireEvent.click(screen.getByTestId('journey-drama-option-0'));
    fireEvent.click(screen.getByTestId('journey-drama-check'));
    expect(await screen.findByTestId('journey-drama-failed')).toBeInTheDocument();
    expect(screen.getByTestId('journey-drama-question')).toHaveTextContent('What do you do first?');
  });

  it('resets to the new camp when the caller switches station', async () => {
    const onAnswer = vi.fn().mockResolvedValue({ correct: true, beat: 1, total: 2, done: false });
    const { rerender } = renderDrama({ onAnswer });
    fireEvent.click(screen.getByTestId('journey-drama-option-0'));
    fireEvent.click(screen.getByTestId('journey-drama-check'));
    await screen.findByTestId('journey-drama-explain');
    rerender(
      <CampDrama
        station={{ ...station(1), n: 2, key: 'coverage' }}
        glossary={[]}
        onAnswer={onAnswer}
      />,
    );
    expect(screen.queryByTestId('journey-drama-explain')).not.toBeInTheDocument();
    expect(screen.getByTestId('journey-drama-question')).toHaveTextContent('What belongs in the record?');
  });
});
