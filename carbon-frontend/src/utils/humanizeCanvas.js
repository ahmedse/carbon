/**
 * Strip engine jargon from Canvas Operator copy (RULE_23).
 * Pure — no React.
 */
const RULE_RE = /\bRULE[_\s]?\d+\b[:\s-]*/gi;
const CAP_RE = /\b[a-z]+:[a-z_]+\b/g;

export function humanizeCanvasText(text) {
  if (text == null) return '';
  let s = String(text);
  s = s.replace(RULE_RE, '');
  // Soften capability tokens like people:view_compensation when embedded in prose
  s = s.replace(CAP_RE, (m) => m.split(':').pop().replace(/_/g, ' '));
  return s.replace(/\s{2,}/g, ' ').trim();
}

export function humanStatusLabel(status) {
  const map = {
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
  return map[status] || (status ? String(status).replace(/_/g, ' ') : 'Waiting');
}
