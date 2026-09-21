/**
 * Strip engine jargon from Canvas Operator copy (RULE_23).
 * Pure — no React.
 */
const RULE_RE = /\bRULE[_\s]?\d+\b[:\s-]*/gi;
const CAP_RE = /\b[a-z]+:[a-z_]+\b/g;

const STATUS_FALLBACK = {
  completed: 'Done',
  done: 'Done',
  complete: 'Done',
  running: 'In progress',
  pending: 'Waiting',
  planned: 'Planned',
  blocked: 'Blocked',
  awaiting_approval: 'Needs your OK',
  failed: 'Failed',
  skipped: 'Skipped',
  partial: 'Partial',
  idle: 'Idle',
};

export function humanizeCanvasText(text) {
  if (text == null) return '';
  let s = String(text);
  s = s.replace(RULE_RE, '');
  // Soften capability tokens like people:view_compensation when embedded in prose
  s = s.replace(CAP_RE, (m) => m.split(':').pop().replace(/_/g, ' '));
  return s.replace(/\s{2,}/g, ' ').trim();
}

/**
 * @param {string} status
 * @param {(key: string) => string} [t] — optional i18n `t` from useTranslation('ai')
 */
export function humanStatusLabel(status, t) {
  if (t && status) {
    const key = `canvasStatus.${status}`;
    const translated = t(key);
    if (translated && translated !== key) return translated;
  }
  if (STATUS_FALLBACK[status]) return STATUS_FALLBACK[status];
  return status ? String(status).replace(/_/g, ' ') : (t ? t('canvasStatus.waiting') : 'Waiting');
}
