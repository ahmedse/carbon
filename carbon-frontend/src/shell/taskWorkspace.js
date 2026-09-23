// Tasks workspace copy — employee titles and one coworker sentence.
// Outcome language only (RULE_23). No tool ids, no engine names.

import { stripEngineJargon } from './humanizeOperatorCopy';
import { effectivePlanStatus } from './aiTaskStatus';

const OUTCOME_STATUS = new Set(['completed', 'completed_with_gaps', 'failed']);

/**
 * Human title for a task. Strips tool ids and dotted APIs from the brief.
 * @param {object|null|undefined} plan
 * @param {string} [fallback]
 * @returns {string}
 */
export function humanTaskTitle(plan, fallback = 'Task', maxLen = 72) {
  const raw = String(plan?.brief || plan?.user_message || '').trim();
  if (!raw) return fallback;
  if (/gosi|wps/i.test(raw) && /payroll|sif/i.test(raw)) {
    return 'Send the GOSI file for this payroll';
  }
  if (/gosi|wps/i.test(raw)) return 'Send the GOSI file';
  let cleaned = stripEngineJargon(raw);
  cleaned = cleaned.replace(/\b[a-z][a-z0-9]*(?:[._][a-z0-9]+)+\b/gi, ' ');
  cleaned = cleaned.replace(/\busing\b[:,]?\s*/gi, ' ');
  cleaned = cleaned.replace(/\bNever\b\.?/gi, '');
  cleaned = cleaned.replace(/\s+/g, ' ').replace(/\s+([.,])/g, '$1').trim();
  cleaned = cleaned.replace(/^Plan\s+/i, '').trim();
  const first = cleaned.split(/\n/)[0].split(/(?<=[.!?])\s+/)[0].trim();
  if (!first) return fallback;
  if (maxLen && first.length > maxLen) return `${first.slice(0, maxLen - 1)}…`;
  return first;
}

/**
 * Result exists only after an outcome — the tab is hidden until then.
 * @param {string} effectiveStatus
 * @param {string} [phase]
 * @returns {boolean}
 */
export function hasTaskOutcome(effectiveStatus, phase = 'idle') {
  if (phase === 'stopped' || phase === 'error') return true;
  if (phase === 'finished') return OUTCOME_STATUS.has(effectiveStatus);
  return OUTCOME_STATUS.has(effectiveStatus);
}

/**
 * One sentence from Pulse. Counts stay when the run is paused (F-28).
 * @param {object} args
 * @param {function} args.t
 * @param {string} [args.phase]
 * @param {string} [args.effective]
 * @param {boolean} [args.awaiting]
 * @param {{ done: number, pending: number }|null} [args.pausedCounts]
 * @returns {string}
 */
export function taskCoworkerLine({
  t,
  phase = 'idle',
  effective = '',
  awaiting = false,
  pausedCounts = null,
}) {
  if (awaiting) return t('coworkerWaiting');
  if (phase === 'paused' || effective === 'paused') {
    if (pausedCounts) {
      const { done, pending } = pausedCounts;
      const stepWord = done === 1 ? 'step' : 'steps';
      return `Paused — ${done} ${stepWord} completed, ${pending} to go`;
    }
    return t('coworkerPausedPlain');
  }
  if (phase === 'working' || effective === 'running') return t('coworkerWorking');
  if (phase === 'error' || effective === 'failed') return t('coworkerFailed');
  if (phase === 'stopped') return t('coworkerStopped');
  if (effective === 'cancelled') return t('coworkerCancelled');
  if (OUTCOME_STATUS.has(effective) || phase === 'finished') return t('coworkerDone');
  if (effective === 'pending_approval') return t('coworkerReview');
  return t('coworkerReady');
}

const ATTENTION_STATUSES = new Set(['pending_approval', 'paused', 'failed']);
const WORKING_STATUSES = new Set(['discovering', 'approved', 'running']);
const DONE_STATUSES = new Set(['completed', 'completed_with_gaps', 'cancelled']);

function newestFirst(a, b) {
  return String(b?.created_at || '').localeCompare(String(a?.created_at || ''));
}

/**
 * Tasks home groups: needs you, working, done.
 * @param {unknown} plans
 * @returns {{ attention: object[], working: object[], done: object[] }}
 */
export function groupTaskBoard(plans) {
  const attention = [];
  const working = [];
  const done = [];
  (Array.isArray(plans) ? plans : []).forEach((plan) => {
    if (!plan || typeof plan !== 'object') return;
    const status = effectivePlanStatus(plan);
    if (ATTENTION_STATUSES.has(status)) attention.push(plan);
    else if (WORKING_STATUSES.has(status)) working.push(plan);
    else if (DONE_STATUSES.has(status)) done.push(plan);
    else working.push(plan);
  });
  attention.sort(newestFirst);
  working.sort(newestFirst);
  done.sort(newestFirst);
  return { attention, working, done };
}

/**
 * One sentence on the Tasks board. Counts, not a selected-task line.
 * @param {{ attention: object[], working: object[], done: object[] }} groups
 * @param {function} t
 * @returns {string}
 */
export function taskBoardCoworkerLine(groups, t) {
  const n = groups?.attention?.length || 0;
  if (n === 1) return t('boardCoworkerNeedsOne');
  if (n > 1) return t('boardCoworkerNeedsMany', { count: n });
  if (groups?.working?.length) return t('boardCoworkerWorking');
  if (groups?.done?.length) return t('boardCoworkerDone');
  return t('boardCoworkerEmpty');
}

/**
 * Quiet chip for a board row.
 * @param {string} status
 * @returns {{ key: string, color: string }}
 */
export function taskBoardChip(status) {
  switch (String(status || '')) {
    case 'pending_approval':
      return { key: 'boardChipReview', color: 'warning' };
    case 'paused':
      return { key: 'boardChipWaiting', color: 'warning' };
    case 'failed':
      return { key: 'boardChipFailed', color: 'error' };
    case 'discovering':
      return { key: 'boardChipWriting', color: 'info' };
    case 'approved':
      return { key: 'boardChipReady', color: 'primary' };
    case 'running':
      return { key: 'boardChipWorking', color: 'primary' };
    case 'completed':
      return { key: 'boardChipDone', color: 'success' };
    case 'completed_with_gaps':
      return { key: 'boardChipDone', color: 'warning' };
    case 'cancelled':
      return { key: 'boardChipStopped', color: 'default' };
    default:
      return { key: 'boardChipWorking', color: 'default' };
  }
}
