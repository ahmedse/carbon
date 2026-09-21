import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AIWorkspaceHeader from '../shell/AIWorkspaceHeader';

vi.mock('../shell/AIContextMenu', () => ({ default: () => null }));

describe('AIWorkspaceHeader continuity chip (DW-P1-2)', () => {
  it('shows a linked-plan chip in Chat mode and opens Agent on click', () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    render(
      <AIWorkspaceHeader
        onClose={vi.fn()}
        mode="chat"
        linkedPlan={{ id: 'plan-42', brief: 'Submit emergency leave tomorrow' }}
        onOpenLinkedPlan={onOpen}
        onDismissLinkedPlan={onDismiss}
      />,
    );
    const chip = screen.getByTestId('chat-agent-continuity-chip');
    expect(chip).toHaveTextContent(/Plan · Submit emergency leave tomorrow/i);
    fireEvent.click(chip);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('hides the chip in Agent mode even if linkedPlan is passed', () => {
    render(
      <AIWorkspaceHeader
        onClose={vi.fn()}
        mode="agent"
        linkedPlan={{ id: 'plan-42', brief: 'Leave' }}
      />,
    );
    expect(screen.queryByTestId('chat-agent-continuity-chip')).not.toBeInTheDocument();
  });
});
