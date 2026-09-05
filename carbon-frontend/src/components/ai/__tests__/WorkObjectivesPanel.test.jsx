// src/components/ai/__tests__/WorkObjectivesPanel.test.jsx
// Pulse v2 Phase 8 — WorkObjectivesPanel unit tests.
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WorkObjectivesPanel from '../WorkObjectivesPanel';

vi.mock('../../../api/aiWorkspace', () => ({
  getWorkObjectives: vi.fn(),
  updateObjectiveStatus: vi.fn(),
}));

import { getWorkObjectives, updateObjectiveStatus } from '../../../api/aiWorkspace';

describe('WorkObjectivesPanel', () => {
  beforeEach(() => {
    getWorkObjectives.mockReset();
    updateObjectiveStatus.mockReset();
  });

  it('renders objectives returned by the API', async () => {
    getWorkObjectives.mockResolvedValue([
      { id: '1', title: 'Investigate Scope 2', status: 'open', latest_summary: 'Found 3 factors' },
      { id: '2', title: 'DQ audit', status: 'in_progress', latest_summary: '' },
    ]);

    render(<WorkObjectivesPanel />);

    await waitFor(() => {
      expect(screen.getByText('Investigate Scope 2')).toBeInTheDocument();
      expect(screen.getByText('DQ audit')).toBeInTheDocument();
    });
  });

  it('shows empty state when no objectives exist', async () => {
    getWorkObjectives.mockResolvedValue([]);

    render(<WorkObjectivesPanel />);

    await waitFor(() => {
      expect(screen.getByText(/No saved objectives/i)).toBeInTheDocument();
    });
  });

  it('calls onSelectObjective when an item is clicked', async () => {
    const onSelect = vi.fn();
    getWorkObjectives.mockResolvedValue([
      { id: '1', title: 'Test objective', status: 'open', latest_summary: '' },
    ]);

    render(<WorkObjectivesPanel onSelectObjective={onSelect} />);

    await waitFor(() => screen.getByText('Test objective'));
    fireEvent.click(screen.getByText('Test objective'));

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: '1', title: 'Test objective' }),
    );
  });

  it('removes objective from list after marking complete', async () => {
    updateObjectiveStatus.mockResolvedValue({});
    getWorkObjectives.mockResolvedValue([
      { id: '1', title: 'To complete', status: 'open', latest_summary: '' },
    ]);

    render(<WorkObjectivesPanel />);

    await waitFor(() => screen.getByText('To complete'));
    fireEvent.click(screen.getAllByRole('button', { name: /mark complete/i })[0]);

    await waitFor(() => {
      expect(screen.queryByText('To complete')).not.toBeInTheDocument();
    });
    expect(updateObjectiveStatus).toHaveBeenCalledWith('1', 'completed');
  });
});
