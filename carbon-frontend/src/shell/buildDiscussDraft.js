/**
 * Prefill chat composer when jumping Agent → Discuss in Chat.
 *
 * Refine drafts must NOT paste the prior final_response: that text often
 * contains task verbs ("analyze", "call the endpoint") which trip Chat into
 * skill match / invoke_skill / ReAct instead of a prose suggestion.
 * Markers ("DISCUSSION ONLY") are detected server-side so Chat stays
 * tool-free until the operator explicitly confirms.
 *
 * Refine → composer process **plan** (edit the agreement).
 * Outcome discuss → composer process **ask** (read-only conversation).
 */
export function buildDiscussDraft(plan, finalResponse, { refine = false, failedStep = null } = {}) {
  const brief = (plan?.brief || '').trim() || 'this agent run';
  const id = plan?.id ? ` (plan ${plan.id})` : '';
  if (refine) {
    const stepLine = failedStep
      ? `Step ${Number(failedStep.step_id) + 1} "${String(failedStep.intent || '').trim()}" did not finish${
        failedStep.error ? `: ${String(failedStep.error).trim().slice(0, 200)}` : ''
      }. Suggest how to fix that step.`
      : null;
    return [
      `I'd like to refine plan${id}: "${brief}".`,
      stepLine || '',
      '',
      'DISCUSSION ONLY — reply in Chat with one improved brief and a short numbered step list.',
      'Do not call tools, invoke_skill, plan_task, or re-run the analysis.',
      'Do not change the Agent plan until I explicitly ask you to apply changes.',
    ].filter((l, i, arr) => !(l === '' && arr[i - 1] === '')).join('\n').trim();
  }
  const body = (finalResponse || '').trim();
  const clipped = body.length > 1800 ? `${body.slice(0, 1800)}\n…` : body;
  const parts = [
    `Let's discuss the outcome of: ${brief}${id}.`,
    clipped ? `\n---\nPrior outcome (context only — do not re-execute):\n${clipped}\n---` : '',
    '',
    'DISCUSSION ONLY — answer in Chat about findings, downloads, steps, or how to refine.',
    'Do not call tools or re-run the analysis unless I explicitly ask.',
    'Do not change the Agent plan until I explicitly ask you to apply changes.',
  ];
  return parts.join('\n').trim();
}

/**
 * Agent → Chat handoff payload: composer seed + linked-plan chip + process dial.
 * @param {object|null} plan
 * @param {string} [finalResponse]
 * @param {{ refine?: boolean, failedStep?: object|null }} [opts]
 * @returns {{ draft: string, planId: string|null, planBrief: string, process: 'plan'|'ask' }}
 */
export function buildDiscussHandoff(plan, finalResponse, opts = {}) {
  const refine = Boolean(opts.refine);
  return {
    draft: buildDiscussDraft(plan, finalResponse, opts),
    planId: plan?.id || null,
    planBrief: (plan?.brief || '').trim(),
    // Plan mode = change the agreement; Ask = talk about results only.
    process: refine ? 'plan' : 'ask',
  };
}
