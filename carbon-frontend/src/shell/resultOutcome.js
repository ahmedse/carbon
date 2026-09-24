// resultOutcome.js — title / facts / state for OutcomeReceipt (host-grounded).
import { planStatusMeta, effectivePlanStatus } from './aiTaskStatus';

/**
 * First meaningful line of answer prose as a short title.
 * Never invents numbers — only reuses existing text.
 */
export function receiptTitleFromAnswer(markdown, fallback = '') {
  const raw = String(markdown || '').trim();
  if (!raw) return fallback;
  const withoutHashes = raw.replace(/^#{1,6}\s+/, '');
  const firstLine = withoutHashes.split(/\n/)[0].trim();
  const sentence = firstLine.split(/(?<=[.!?。！؟])\s+/)[0].trim();
  const cleaned = sentence.replace(/\*\*|__/g, '').trim();
  if (!cleaned) return fallback;
  return cleaned.length > 120 ? `${cleaned.slice(0, 117)}…` : cleaned;
}

/** Join host navigate summaries into one facts line (deduped). */
export function receiptFactsFromActions(hostActions = []) {
  const parts = [];
  const seen = new Set();
  (Array.isArray(hostActions) ? hostActions : []).forEach((a) => {
    const s = String(a?.summary || '').trim();
    if (!s || seen.has(s)) return;
    seen.add(s);
    parts.push(s);
  });
  return parts.join(' · ');
}

export function receiptStateFromPlan(plan, phase) {
  const effective = effectivePlanStatus(plan) || plan?.status || '';
  // Durable success wins over a stale FE error phase (e.g. resume raced a
  // completed Approve). The host write already landed.
  if (effective === 'completed' || effective === 'completed_with_gaps') {
    const meta = planStatusMeta(effective);
    return {
      label: meta?.label || '',
      color: meta?.color || 'success',
    };
  }
  if (phase === 'error' || effective === 'failed') {
    return { labelKey: 'boardChipFailed', color: 'error' };
  }
  if (phase === 'stopped' || effective === 'cancelled') {
    return { labelKey: 'coworkerStopped', color: 'default', plain: true };
  }
  const meta = planStatusMeta(effective);
  return {
    label: meta?.label || '',
    color: meta?.color || 'default',
  };
}
