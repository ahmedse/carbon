/**
 * Operator-facing field forms for incomplete staged mutations.
 * No JSON — short labels + required hire/leave fields only.
 */
import { toolLabel } from './aiTaskStatus';

const CREATE_EMPLOYEE_FIELDS = [
  { key: 'employee_no', label: 'Employee number', type: 'text', required: true },
  { key: 'full_name', label: 'Full name', type: 'text', required: true },
  { key: 'org_unit', label: 'Org unit id', type: 'number', required: true },
  { key: 'join_date', label: 'Join date', type: 'date', required: true },
  { key: 'basic_salary', label: 'Basic salary', type: 'text', required: true },
];

const SUBMIT_LEAVE_FIELDS = [
  {
    key: 'leave_type',
    label: 'Leave type',
    type: 'select',
    required: true,
    options: [
      { value: 'annual', label: 'Annual' },
      { value: 'emergency', label: 'Emergency' },
      { value: 'sick', label: 'Sick' },
    ],
  },
  { key: 'start_date', label: 'Start date', type: 'date', required: true },
  { key: 'end_date', label: 'End date', type: 'date', required: true },
  { key: 'days', label: 'Days', type: 'number', required: true },
];

const SUBMIT_LOAN_FIELDS = [
  {
    key: 'loan_type',
    label: 'Loan type',
    type: 'select',
    required: true,
    options: [
      { value: 'emergency', label: 'Emergency' },
      { value: 'housing', label: 'Housing' },
    ],
  },
  { key: 'principal', label: 'Principal', type: 'text', required: true },
  { key: 'term_months', label: 'Term (months)', type: 'number', required: true },
  { key: 'start_date', label: 'Start date', type: 'date', required: true },
];

function stagedBody(step) {
  const args = step?.tool_args;
  if (!args || typeof args !== 'object') return {};
  if (args.body && typeof args.body === 'object') return { ...args.body };
  if (args.payload && typeof args.payload === 'object') return { ...args.payload };
  return {};
}

function apiName(step) {
  const args = step?.tool_args;
  if (!args || typeof args !== 'object') return '';
  return String(args.api_name || '').trim();
}

/**
 * @returns {{ api: string, fields: Array, values: object, actionLabel: string } | null}
 */
export function consentInputSpec(step) {
  if (!step || step.status !== 'awaiting_approval') return null;
  const api = apiName(step);
  const values = stagedBody(step);
  let fields = null;
  if (api === 'create_employee') {
    fields = CREATE_EMPLOYEE_FIELDS;
  } else if (api === 'submit_my_leave' || api === 'create_leave_record') {
    fields = SUBMIT_LEAVE_FIELDS;
  } else if (api === 'submit_my_loan') {
    fields = SUBMIT_LOAN_FIELDS;
  } else {
    return null;
  }
  const missing = fields.some((f) => {
    if (!f.required) return false;
    const v = values[f.key];
    return v == null || String(v).trim() === '';
  });
  // Always show form for these APIs when awaiting — empty staged body is common.
  if (!missing && Object.keys(values).length > 0) {
    // Body already filled — still allow review edits on the node.
    return {
      api,
      fields,
      values,
      actionLabel: toolLabel(api) || api,
      requiresForm: false,
    };
  }
  return {
    api,
    fields,
    values,
    actionLabel: toolLabel(api) || api,
    requiresForm: true,
  };
}

export function consentFormValid(fields, values) {
  if (!fields?.length) return true;
  return fields.every((f) => {
    if (!f.required) return true;
    const v = values?.[f.key];
    return v != null && String(v).trim() !== '';
  });
}
