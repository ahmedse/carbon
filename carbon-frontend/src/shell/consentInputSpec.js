/**
 * Consent card fields for a staged host write.
 *
 * Fields and governed value options come from the step's ``consent_slots``
 * (backend, derived from the brand api_catalog + MDM reference values). The UI
 * keeps no copy of the leave / loan / permission lists, and does no synonym or
 * date inference of its own — the platform resolved that before staging.
 */
import { toolLabel } from './aiTaskStatus';

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

/**
 * @param {object} step — plan step (awaiting_approval)
 * @returns {{ api: string, fields: Array, values: object, actionLabel: string, prefilled: boolean } | null}
 */
export function consentInputSpec(step) {
  if (!step || step.status !== 'awaiting_approval') return null;
  const slots = Array.isArray(step.consent_slots) ? step.consent_slots : [];
  const fields = slots.map(fieldFromSlot).filter(Boolean);
  if (!fields.length) return null;
  const api = apiName(step);
  const values = stagedBody(step);
  return {
    api,
    fields,
    values,
    actionLabel: toolLabel(api) || api,
    requiresForm: true,
    prefilled: consentFormValid(fields, values),
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

export function bodySummary(fields, values) {
  if (!fields?.length) return '';
  return fields
    .map((f) => {
      const v = values?.[f.key];
      if (v == null || String(v).trim() === '') return null;
      const option = f.options?.find((o) => o.value === String(v));
      return `${f.label}: ${option ? option.label : v}`;
    })
    .filter(Boolean)
    .join(' · ');
}
