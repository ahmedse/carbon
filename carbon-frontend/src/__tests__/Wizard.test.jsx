// Shared Wizard primitive — opt-in clickable step nodes.
// RULE 2 (reuse the shared Wizard) + RULE 11 (keyboard + visible focus):
// clickable steps are MUI `StepButton` (a real focusable button), not a
// hand-rolled Box/onClick.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Wizard from '../components/Wizard';

const STEPS = [
  { key: 'one', label: 'Step One', content: <div>Content One</div> },
  { key: 'two', label: 'Step Two', content: <div>Content Two</div> },
  { key: 'three', label: 'Step Three', content: <div>Content Three</div> },
];

function renderWizard(props = {}) {
  const onStepChange = vi.fn();
  render(
    <Wizard
      steps={STEPS}
      onFinish={vi.fn()}
      onCancel={vi.fn()}
      onStepChange={onStepChange}
      {...props}
    />,
  );
  return { onStepChange };
}

describe('Wizard clickable steps', () => {
  it('default: step labels are not buttons and clicking a label does not change the step', () => {
    const { onStepChange } = renderWizard();

    // Default (no `clickableSteps`) keeps display-only StepLabels — no step button.
    expect(screen.queryByRole('button', { name: /Step Two/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Step Two'));

    // Linear behavior preserved: still on the first step.
    expect(screen.getByText('Content One')).toBeInTheDocument();
    expect(screen.queryByText('Content Two')).not.toBeInTheDocument();
    expect(onStepChange).not.toHaveBeenCalled();
  });

  it('clickableSteps: a reachable step is a button; click, Enter and Space navigate and fire onStepChange', async () => {
    const user = userEvent.setup();
    const { onStepChange } = renderWizard({ clickableSteps: true });

    // Reachable step renders as a real button (StepButton).
    const stepTwo = screen.getByRole('button', { name: /Step Two/i });

    await user.click(stepTwo);
    expect(onStepChange).toHaveBeenLastCalledWith(1);
    expect(screen.getByText('Content Two')).toBeInTheDocument();

    // Enter activates the focused step button.
    const stepThree = screen.getByRole('button', { name: /Step Three/i });
    act(() => stepThree.focus());
    await user.keyboard('{Enter}');
    expect(onStepChange).toHaveBeenLastCalledWith(2);
    expect(screen.getByText('Content Three')).toBeInTheDocument();

    // Space activates the focused step button.
    const stepOne = screen.getByRole('button', { name: /Step One/i });
    act(() => stepOne.focus());
    await user.keyboard(' ');
    expect(onStepChange).toHaveBeenLastCalledWith(0);
    expect(screen.getByText('Content One')).toBeInTheDocument();
  });

  it('clickableSteps: a disabled future step does not navigate when clicked', () => {
    const { onStepChange } = renderWizard({
      clickableSteps: true,
      isStepEnabled: (i) => i === 0,
    });

    const stepTwo = screen.getByRole('button', { name: /Step Two/i });
    expect(stepTwo).toBeDisabled();

    fireEvent.click(stepTwo);

    expect(screen.getByText('Content One')).toBeInTheDocument();
    expect(screen.queryByText('Content Two')).not.toBeInTheDocument();
    expect(onStepChange).not.toHaveBeenCalled();
  });
});
