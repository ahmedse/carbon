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
  'people.Loan': 'type.loanRequest',
  'people.Employee': 'type.profileChange',
  'people.AttendancePermission': 'type.attendancePermission',
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

/** Creatable types in New Request dialog (attendance has its own flow). */
export const CORR_TYPES = [
  'leave_request',
  'internal_memo',
  'circular',
  'decision',
  'loan_request',
  'profile_change',
];

/** Types shown in My Requests type filter (includes attendance). */
export const CORR_FILTER_TYPES = [
  'leave_request',
  'attendance_permission',
  'loan_request',
  'profile_change',
  'internal_memo',
  'circular',
  'decision',
];

const CORR_TYPE_SUFFIX = {
  leave_request: 'leaveRequest',
  internal_memo: 'internalMemo',
  circular: 'circular',
  decision: 'decision',
  loan_request: 'loanRequest',
  profile_change: 'profileChange',
  attendance_permission: 'attendancePermission',
};

/** Localized label for a corr_type code (e.g. "loan_request"). */
export function corrTypeLabel(t, code) {
  if (!code) return '—';
  const suffix = CORR_TYPE_SUFFIX[code];
  return suffix ? t(`type.${suffix}`, { defaultValue: code }) : String(code);
}

/**
 * Localized request type label. Prefers the authoritative `corr_type_code`
 * (present on the list/detail serializers); falls back to `subject_type`.
 */
export function requestTypeLabel(t, item) {
  const code = item?.corr_type_code;
  if (code) return corrTypeLabel(t, code);
  return subjectTypeLabel(t, item?.subject_type);
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

/**
 * Compact single-line payload summary for the list table. Returns null when
 * there is no meaningful summary (callers render '—').
 */
export function payloadSummary(t, item, lang) {
  const type = item?.corr_type_code || '';
  const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};

  switch (type) {
    case 'leave_request': {
      const start = formatDate(payload.start_date, lang);
      const end = formatDate(payload.end_date, lang);
      if (start === '—' && end === '—') return null;
      return `${start} → ${end}`;
    }
    case 'attendance_permission': {
      const day = formatDate(payload.date || payload.permission_date, lang);
      const hours = payload.hours != null ? String(payload.hours) : null;
      if (day === '—' && !hours) return null;
      if (hours) return `${day} (${hours}h)`;
      return day;
    }
    case 'loan_request':
      return t('summaryLoanAmount', {
        amount: payload.principal != null ? String(payload.principal) : '—',
        months: payload.term_months != null ? String(payload.term_months) : '—',
      });
    case 'profile_change': {
      const changes = payload.changes && typeof payload.changes === 'object' ? payload.changes : {};
      const fields = Object.keys(changes);
      if (fields.length === 0) return null;
      return fields.join(', ');
    }
    case 'internal_memo':
    case 'circular':
    case 'decision': {
      const body = typeof payload.body === 'string' ? payload.body : '';
      if (!body) return null;
      return body.length > 90 ? `${body.slice(0, 90)}…` : body;
    }
    default:
      return null;
  }
}

/**
 * Label/value rows for the detail summary card, per request type. Empty array
 * means "no payload to render".
 */
export function payloadRows(t, item, lang) {
  const type = item?.corr_type_code || '';
  const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
  const changes = payload.changes && typeof payload.changes === 'object' ? payload.changes : {};

  switch (type) {
    case 'leave_request':
      return [
        { label: t('summaryLeaveType'), value: leaveTypeLabel(t, payload.leave_type) },
        { label: t('summaryStart'), value: formatDate(payload.start_date, lang) },
        { label: t('summaryEnd'), value: formatDate(payload.end_date, lang) },
        { label: t('summaryDays'), value: payload.days != null ? String(payload.days) : '—' },
        { label: t('summaryNote'), value: payload.note || '—' },
      ];
    case 'attendance_permission':
      return [
        { label: t('summaryPermissionType'), value: payload.permission_type || '—' },
        { label: t('summaryDate'), value: formatDate(payload.date, lang) },
        { label: t('summaryHours'), value: payload.hours != null ? String(payload.hours) : '—' },
        { label: t('summaryNotes'), value: payload.notes || '—' },
      ];
    case 'loan_request':
      return [
        { label: t('summaryLoanType'), value: (typeof payload.loan_type === 'object' ? (payload.loan_type?.label || payload.loan_type?.code) : payload.loan_type) || '—' },
        { label: t('summaryPrincipal'), value: payload.principal != null ? String(payload.principal) : '—' },
        { label: t('summaryInterestRate'), value: payload.interest_rate != null ? String(payload.interest_rate) : '—' },
        { label: t('summaryTermMonths'), value: payload.term_months != null ? String(payload.term_months) : '—' },
        { label: t('summaryLoanStartDate'), value: formatDate(payload.start_date, lang) },
        { label: t('summaryNotes'), value: payload.notes || '—' },
      ];
    case 'profile_change': {
      const entries = Object.entries(changes);
      if (entries.length === 0) {
        return [{ label: t('summaryChanges'), value: '—' }];
      }
      return entries.map(([field, change]) => ({
        label: field || '—',
        value: `${change && typeof change === 'object' ? (change.from ?? '—') : '—'} → ${change && typeof change === 'object' ? (change.to ?? '—') : '—'}`,
      }));
    }
    case 'internal_memo':
    case 'circular':
    case 'decision':
      return [{ label: t('summaryBody'), value: payload.body || '—' }];
    default:
      return [];
  }
}
