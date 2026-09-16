// Shared payload builder for EmployeeWizard create/update.
// NSR-2B/4B: never writes `basic_salary` (ledger SoT). Optional `opening_basic`
// is write-only hire path — included only when non-empty.
// NSR-7C: governed FKs write as code strings on the FK field name (not `*_code`).

/**
 * @param {Record<string, unknown>} form
 * @param {{ includeOpeningBasic?: boolean }} [opts]
 */
export function buildEmployeeWizardPayload(form, { includeOpeningBasic = true } = {}) {
  const payload = {
    org_unit: Number(form.org_unit),
    employee_no: String(form.employee_no || '').trim(),
    full_name: String(form.full_name || '').trim(),
    join_date: form.join_date,
    is_active: Boolean(form.is_active),
    kuwaitization: Boolean(form.kuwaitization),
  };
  // Governed FK fields — write ReferenceValue codes (strings). Soft `*_code` gone.
  const optionalText = [
    ['nationality', form.nationality],
    ['gender', form.gender],
    ['civil_id', form.civil_id],
    ['date_of_birth', form.date_of_birth],
    ['employment_type', form.employment_type],
    ['contract_type', form.contract_type],
    ['rotation', form.rotation],
    ['name_en_given', form.name_en_given],
    ['name_en_family', form.name_en_family],
    ['name_ar_given', form.name_ar_given],
    ['name_ar_family', form.name_ar_family],
  ];
  for (const [key, val] of optionalText) {
    if (val && String(val).trim()) payload[key] = String(val).trim();
  }
  payload.position = form.position ? Number(form.position) : null;
  payload.manager = form.manager ? Number(form.manager) : null;
  if (includeOpeningBasic) {
    const opening = String(form.opening_basic ?? '').trim();
    if (opening !== '') payload.opening_basic = opening;
  }
  return payload;
}
