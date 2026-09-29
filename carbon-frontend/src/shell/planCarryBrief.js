/** Brief Plan should materialize. The last chip is not the request. */

const COMMIT = ['yes', 'ok', 'okay', 'go', 'sure', 'please', 'نعم', 'تمام', 'موافق'];

export function isShortCommit(text) {
  const words = String(text || '')
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  return words.length > 0 && words.length <= 4 && words.every((word) => COMMIT.includes(word));
}

function isShortAffirm(text) {
  const words = String(text || '')
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length || words.length > 4) return false;
  return words.every((word) => (
    ['yes', 'ok', 'okay', 'go', 'sure', 'please', 'نعم', 'تمام', 'موافق'].includes(word)
  ));
}

export function briefFromWriteDraft(draft, fallback = '') {
  if (draft && typeof draft === 'object' && !Array.isArray(draft)) {
    const type = String(
      draft.leave_type || draft.loan_type || draft.permission_type || '',
    ).trim();
    const bits = [];
    if (type) bits.push(type);
    if (draft.leave_type || draft.days || draft.start_date) bits.push('leave');
    else if (draft.loan_type || draft.principal || draft.amount) bits.push('loan');
    if (draft.days != null && draft.days !== '') bits.push(`for ${draft.days} days`);
    if (draft.hours != null && draft.hours !== '') bits.push(`for ${draft.hours} hours`);
    const amount = draft.principal ?? draft.amount;
    if (amount != null && amount !== '') bits.push(String(amount));
    const start = draft.start_date || draft.date;
    if (start) bits.push(`starting ${start}`);
    if (draft.end_date) bits.push(`ending ${draft.end_date}`);
    if (bits.length) return `I want ${bits.join(' ')}.`.replace(/\s+/g, ' ');
  }
  if (typeof draft === 'string') {
    const text = draft.trim();
    if (text && !text.startsWith('Prepared draft') && !isShortAffirm(text)) {
      return text;
    }
  }
  const fallbackText = String(fallback || '').trim();
  if (fallbackText && !isShortAffirm(fallbackText)) return fallbackText;
  return '';
}

/** Ask "yes go" after a Switch-to-Plan card is that button, not a new sentence. */
export function requestFromAskCommit(messages, text) {
  if (!isShortCommit(text)) return '';
  const list = [...(messages || [])].reverse();
  const planMessage = list.find((message) => {
    if (message?.role !== 'assistant') return false;
    const meta = message.metadata || message.metadata_json || {};
    return (meta.actions || []).some(
      (act) => act && act.type === 'open_panel' && act.panel === 'plan',
    );
  });
  if (!planMessage) return '';
  const meta = planMessage.metadata || planMessage.metadata_json || {};
  const plan = (meta.actions || []).find(
    (act) => act && act.type === 'open_panel' && act.panel === 'plan',
  );
  const fromAction = String(plan?.brief || '').trim();
  if (fromAction && !isShortAffirm(fromAction)) return fromAction;
  return briefFromWriteDraft(plan?.draft || meta.draft);
}

export function requestForPlanSwitch({ draft, brief, lastUser, userTurns = [] } = {}) {
  const fromAction = String(brief || '').trim();
  if (fromAction && !isShortAffirm(fromAction)) return fromAction;
  const fromDraft = briefFromWriteDraft(draft);
  if (fromDraft) return fromDraft;
  const last = String(lastUser || '').trim();
  if (last && !isShortAffirm(last) && last.length > 12) return last;
  const prior = (userTurns || [])
    .map((turn) => String(turn || '').trim())
    .filter((turn) => turn && !isShortAffirm(turn));
  return prior.join(' ').trim();
}
