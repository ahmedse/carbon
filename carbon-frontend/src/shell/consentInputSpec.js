/**
 * Consent card fields for a staged host write.
 *
 * Fields and governed value options come from the step's ``consent_slots``
 * (backend, derived from the brand api_catalog + MDM reference values). The UI
 * keeps no copy of the leave / loan / permission lists, and does no synonym or
 * date inference of its own — the platform resolved that before staging.
 *
 * Change preview (what will hit the system) is built for Approve so operators
 * never see a thin "System check" with no payload.
 */
import { toolLabel } from './aiTaskStatus';
import { presentToolLabel } from './presentationPlane';

/** One-line consequence of approving (RULE_21 — say what changes). */
const MUTATION_CONSEQUENCE = {
  submit_my_leave:
    'Creates a leave request. Your manager reviews it in Team — not submitted as approved until they Approve.',
  create_leave_record:
    'Creates a leave record in the system.',
  submit_my_loan:
    'Creates a loan request. Manager then finance review it in Team — not approved until both steps complete.',
  submit_my_attendance_permission:
    'Creates an attendance permission request. Your manager reviews it in Team.',
  create_employee:
    'Creates an employee record in the system.',
  update_employee:
    'Updates an employee record in the system.',
  create_dq_rule:
    'Creates a data-quality rule in the system.',
};

const FIELD_LABEL_FALLBACK = {
  leave_type: 'Leave type',
  start_date: 'Start date',
  end_date: 'End date',
  days: 'Days',
  note: 'Note',
  reason: 'Reason',
  loan_type: 'Loan type',
  principal: 'Principal',
  term_months: 'Term (months)',
  interest_rate: 'Interest rate',
  amount: 'Amount',
  permission_type: 'Permission type',
  hours: 'Hours',
};

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

function fieldFromSlot(slot) {
  const key = String(slot?.field || '').trim();
  if (!key) return null;
  const type = String(slot?.type || 'text').trim();
  return {
    key,
    label: String(slot?.label || key.replace(/_/g, ' ')).trim(),
    type,
    required: slot?.required !== false,
    options: Array.isArray(slot?.options)
      ? slot.options
          .filter((o) => o && o.code)
          .map((o) => ({ value: String(o.code), label: String(o.label || o.code) }))
      : [],
  };
}

function fieldsFromBody(body) {
  if (!body || typeof body !== 'object') return [];
  return Object.keys(body)
    .filter((k) => body[k] != null && String(body[k]).trim() !== '')
    .filter((k) => !k.startsWith('_'))
    .map((key) => ({
      key,
      label: FIELD_LABEL_FALLBACK[key] || key.replace(/_/g, ' '),
      type: 'text',
      required: false,
      options: [],
    }));
}

/**
 * @param {object} step — plan step (awaiting_approval)
 * @returns {object | null}
 */
export function consentInputSpec(step) {
  if (!step || step.status !== 'awaiting_approval') return null;
  const slots = Array.isArray(step.consent_slots) ? step.consent_slots : [];
  let fields = slots.map(fieldFromSlot).filter(Boolean);
  const api = apiName(step);
  const values = stagedBody(step);
  // Fallback: no slots but a staged body — still preview the change.
  if (!fields.length && Object.keys(values).length) {
    fields = fieldsFromBody(values);
  }
  if (!fields.length && !api) return null;
  if (!fields.length && api) {
    return {
      api,
      fields: [],
      values,
      actionLabel: actionLabelForApi(api),
      requiresForm: false,
      prefilled: true,
      consequence: consequenceForApi(api),
      rows: [],
    };
  }
  return {
    api,
    fields,
    values,
    actionLabel: actionLabelForApi(api),
    requiresForm: fields.some((f) => f.required),
    prefilled: consentFormValid(fields, values),
    consequence: consequenceForApi(api),
    rows: bodySummaryRows(fields, values),
  };
}

export function actionLabelForApi(api) {
  if (!api) return 'System change';
  return (
    presentToolLabel('call_host_api', { audience: 'operator', apiName: api })
    || toolLabel(api)
    || String(api).replace(/_/g, ' ')
  );
}

export function consequenceForApi(api) {
  const key = String(api || '').trim();
  if (MUTATION_CONSEQUENCE[key]) return MUTATION_CONSEQUENCE[key];
  if (key.startsWith('submit_') || key.startsWith('create_') || key.startsWith('update_')) {
    return 'This will create or change a record in the system.';
  }
  return 'This will run a system action that may change records.';
}

export function consentFormValid(fields, values) {
  if (!fields?.length) return true;
  return fields.every((f) => {
    if (!f.required) return true;
    const v = values?.[f.key];
    return v != null && String(v).trim() !== '';
  });
}

export function firstMissingField(fields, values) {
  if (!fields?.length) return null;
  return (
    fields.find((f) => {
      if (!f.required) return false;
      const v = values?.[f.key];
      return v == null || String(v).trim() === '';
    }) || null
  );
}

export function bodySummaryRows(fields, values) {
  if (!fields?.length) return [];
  return fields
    .map((f) => {
      const v = values?.[f.key];
      if (v == null || String(v).trim() === '') return null;
      const option = f.options?.find((o) => o.value === String(v));
      return { label: f.label, value: option ? option.label : String(v) };
    })
    .filter(Boolean);
}

export function bodySummary(fields, values) {
  return bodySummaryRows(fields, values)
    .map((r) => `${r.label}: ${r.value}`)
    .join(' · ');
}

/**
 * Full change preview for Approve — works even when consent_slots were omitted
 * but tool_args.body is present.
 */
export function changePreview(step) {
  if (!step || step.status !== 'awaiting_approval') return null;
  const spec = consentInputSpec(step);
  if (!spec) return null;
  return {
    actionLabel: spec.actionLabel,
    consequence: spec.consequence,
    rows: spec.rows || bodySummaryRows(spec.fields, spec.values),
    summary: bodySummary(spec.fields, spec.values),
    ready: Boolean(spec.prefilled),
    api: spec.api,
  };
}
