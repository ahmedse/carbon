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
