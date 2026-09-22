// src/apps/people/utils.js
// Pure, framework-free helpers for the People & Payroll screens.
// Kept separate from component files so components export only their component
// (react-refresh/only-export-components) and tests can unit-test these helpers
// without rendering.

/** Map employee id → "employee_no — full_name" label. */
export function buildEmployeeLabels(employees) {
  const map = {};
  for (const employee of employees || []) {
    if (employee?.id != null) {
      map[employee.id] = `${employee.employee_no ?? '—'} — ${employee.full_name ?? ''}`;
    }
  }
  return map;
}

/** Map benefit type id → "code — name" label. */
export function buildBenefitTypeLabels(types) {
  const map = {};
  for (const type of types || []) {
    if (type?.id != null) {
      map[type.id] = `${type.code ?? ''} — ${type.name ?? ''}`;
    }
  }
  return map;
}

/** i18n key for a status value, or null when unmapped. */
export function statusLabelKey(status) {
  const keys = {
    draft: 'statusDraft',
    computed: 'statusComputed',
    validated: 'statusValidated',
    committed: 'statusCommitted',
    failed: 'statusFailed',
    submitted: 'statusSubmitted',
    approved: 'statusApproved',
    rejected: 'statusRejected',
    cancelled: 'statusCancelled',
    present: 'statusPresent',
    absent: 'statusAbsent',
    leave: 'statusLeave',
    permission: 'statusPermission',
  };
  return keys[status] || null;
}

/** MUI Chip color for a People/Payroll status value. */
export function statusColor(status) {
  switch (status) {
    case 'committed':
    case 'approved':
    case 'present':
      return 'success';
    case 'failed':
    case 'rejected':
    case 'absent':
      return 'error';
    case 'validated':
    case 'permission':
      return 'warning';
    case 'computed':
    case 'submitted':
    case 'leave':
      return 'info';
    default:
      return 'default';
  }
}

/** Format a numeric amount for display (thousands separators, 2 decimals max). */
export function formatAmount(value) {
  if (value == null || value === '' || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 });
}

/** Trim an ISO datetime to a YYYY-MM-DD date string. */
export function formatDate(value) {
  if (!value) return '—';
  return String(value).slice(0, 10);
}

/**
 * Extract a ReferenceValue code from nested `{code}` (NSR-7B+) or a plain string.
 * Returns '' when absent.
 */
export function refCode(value) {
  if (value == null || value === '') return '';
  if (typeof value === 'object') return String(value.code ?? '').trim();
  return String(value).trim();
}

/**
 * Display label for a governed value: nested `.label` / `.code`, or plain string.
 * Returns '' when absent (callers may fall back to '—').
 */
export function refLabel(value) {
  if (value == null || value === '') return '';
  if (typeof value === 'object') {
    const label = String(value.label ?? '').trim();
    if (label) return label;
    return String(value.code ?? '').trim();
  }
  return String(value).trim();
}

/** Human-readable service tenure from a join date to today. */
export function tenureLabel(joinDate) {
  if (!joinDate) return null;
  const start = new Date(joinDate);
  const now = new Date();
  if (now < start) return null;
  const totalMs = now - start;
  const years = Math.floor(totalMs / (365.25 * 24 * 3600 * 1000));
  const months = Math.floor((totalMs - years * 365.25 * 24 * 3600 * 1000) / (30.44 * 24 * 3600 * 1000));
  if (years === 0 && months === 0) return '< 1 mo';
  if (years === 0) return `${months} mo`;
  if (months === 0) return `${years} yr`;
  return `${years} yr ${months} mo`;
}

/** Days until an expiry date (negative = already expired; null = no expiry set). */
export function daysUntilExpiry(expiryDate) {
  if (!expiryDate) return null;
  return Math.floor((new Date(expiryDate) - new Date()) / (24 * 3600 * 1000));
}

/** Urgency tier: 'expired' | 'critical' (≤7d) | 'warning' (≤30d) | 'notice' (≤90d) | null */
export function expiryUrgency(expiryDate) {
  const days = daysUntilExpiry(expiryDate);
  if (days === null) return null;
  if (days < 0) return 'expired';
  if (days <= 7) return 'critical';
  if (days <= 30) return 'warning';
  if (days <= 90) return 'notice';
  return null;
}

/** Host SoD code from apiFetch error (`err.data.code` — ADR-0045 / NPS-1). */
export function sodErrorCode(err) {
  const code = err?.data?.code || err?.code;
  if (typeof code === 'string' && code.startsWith('sod_')) return code;
  return null;
}

/** True when API refused for separation of duties. */
export function isSodError(err) {
  return Boolean(sodErrorCode(err));
}

/** Total remaining leave balance (entitled - used + carried_forward) across entitlement rows. */
export function totalLeaveBalance(entitlements) {
  return entitlements.reduce(
    (sum, e) => sum + Number(e.entitled_days) - Number(e.used_days) + Number(e.carried_forward || 0),
    0,
  );
}

/** Leave balance aggregated by leave_type (plus policy provenance), sorted by balance descending. */
export function leaveBalanceByType(entitlements) {
  const map = {};
  for (const e of entitlements) {
    const k = e.leave_type;
    if (!map[k]) map[k] = { entitled: 0, used: 0, carried: 0, policyNames: new Set() };
    map[k].entitled += Number(e.entitled_days);
    map[k].used += Number(e.used_days);
    map[k].carried += Number(e.carried_forward || 0);
    if (e.policy_name) map[k].policyNames.add(e.policy_name);
  }
  return Object.entries(map)
    .map(([type, v]) => ({
      type,
      ...v,
      policyNames: [...v.policyNames],
      balance: v.entitled - v.used + v.carried,
    }))
    .sort((a, b) => b.balance - a.balance);
}
