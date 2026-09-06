// src/apps/my/components/myRequestsLabels.js
// Pure label / date helpers + code maps shared by the My Requests screens.
// No React or hooks here — components pass their `t` (useTranslation('my'))
// so labels stay localized. Kept in a plain .js module (not .jsx) so we never
// mix non-component exports into a component module (react-refresh hygiene).

export const STATUS_CODES = [
  'draft',
  'submitted',
  'in_review',
  'approved',
  'rejected',
  'cancelled',
  'sent_back',
  'expired',
  'archived',
];

export const STATUS_SUFFIX = {
  draft: 'draft',
  submitted: 'submitted',
  in_review: 'inReview',
  approved: 'approved',
  rejected: 'rejected',
  cancelled: 'cancelled',
  sent_back: 'sentBack',
  expired: 'expired',
  archived: 'archived',
};

export const STATUS_COLOR = {
  draft: 'default',
  submitted: 'info',
  in_review: 'warning',
  approved: 'success',
  rejected: 'error',
  cancelled: 'warning',
  sent_back: 'warning',
  expired: 'default',
  archived: 'default',
};

export const EVENT_SUFFIX = {
  submitted: 'submitted',
  approved: 'approved',
  rejected: 'rejected',
  sent_back: 'sentBack',
  cancelled: 'cancelled',
  resubmitted: 'resubmitted',
};

export const ROLE_SUFFIX = {
  manager: 'manager',
  hr: 'hr',
  finance: 'finance',
  specific_user: 'specificUser',
  any_admin: 'anyAdmin',
};

export const INTENT_SUFFIX = {
  approve: 'approve',
  acknowledge: 'acknowledge',
  review: 'review',
};

const SUBJECT_TYPE_KEY = {
  'people.LeaveRecord': 'type.leaveRequest',
};

/**
 * Localized label for a known code. Falls back to the raw code string when
 * the code has no mapped suffix or the translation key is missing.
 */
export function codeLabel(t, prefix, suffixMap, code) {
  if (!code) return '—';
  const suffix = suffixMap[code];
  if (!suffix) return String(code);
  return t(`${prefix}.${suffix}`, { defaultValue: String(code) });
}

/** Localized label for a subject_type (e.g. "people.LeaveRecord"). */
export function subjectTypeLabel(t, subjectType) {
  if (!subjectType) return '—';
  const key = SUBJECT_TYPE_KEY[subjectType];
  return key ? t(key, { defaultValue: subjectType }) : subjectType;
}

/** Localized label for a leave-type code. */
export function leaveTypeLabel(t, code) {
  if (!code) return '—';
  return t(`leaveType.${code}`, { defaultValue: code });
}

/** Localized date formatting, robust to ISO datetimes and timezone shift. */
export function formatDate(value, lang) {
  if (!value) return '—';
  const str = String(value).slice(0, 10);
  const [y, m, d] = str.split('-').map(Number);
  if (!y || !m || !d) return '—';
  const date = new Date(y, m - 1, d);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(lang === 'ar' ? 'ar' : 'en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** Localized date + time formatting for timeline entries. */
export function formatDateTime(value, lang) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return formatDate(value, lang);
  return date.toLocaleString(lang === 'ar' ? 'ar' : 'en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
