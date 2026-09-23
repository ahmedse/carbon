// src/api/people.js
// API helpers for the People & Payroll app (backend/people/*).
// All endpoints live under /carbon-api/people/ (see backend/people/urls.py).
// Every call goes through apiFetch (JWT refresh + error normalization) — never raw fetch().

import { apiFetch } from './api';

const ROOT = 'people/';

/**
 * List employees (paginated on the server).
 * Without `page`, walks every page under the server max (200) so directory
 * screens still get the full scoped population — never a single unbounded
 * response (SIM-QA N-HR-UI-01).
 */
export async function fetchEmployees(token, params = {}) {
  const pageSize = Math.min(Math.max(Number(params.page_size) || 100, 1), 200);
  if (params.page != null) {
    const qs = new URLSearchParams({
      page: String(params.page),
      page_size: String(pageSize),
    });
    return apiFetch(`${ROOT}employees/?${qs}`, { token });
  }
  const first = await apiFetch(
    `${ROOT}employees/?page=1&page_size=${pageSize}`,
    { token },
  );
  const results = [...(first?.results || [])];
  const total = Number(first?.count ?? results.length);
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages > 1) {
    const rest = await Promise.all(
      Array.from({ length: pages - 1 }, (_, i) =>
        apiFetch(
          `${ROOT}employees/?page=${i + 2}&page_size=${pageSize}`,
          { token },
        ),
      ),
    );
    for (const chunk of rest) {
      results.push(...(chunk?.results || []));
    }
  }
  return { count: total, page_size: pageSize, results };
}

/** List payroll runs. */
export function fetchPayrollRuns(token) {
  return apiFetch(`${ROOT}payroll-runs/`, { token });
}

/** Single payroll run. */
export function fetchPayrollRun(id, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/`, { token });
}

/** Create a payroll run. `data` = { org_unit, period_start, period_end }. */
export function createPayrollRun(data, token) {
  return apiFetch(`${ROOT}payroll-runs/`, { method: 'POST', body: data, token });
}

/** Update a payroll run (partial). Status is server-managed. */
export function updatePayrollRun(id, data, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a payroll run (blocked server-side once committed). */
export function deletePayrollRun(id, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/**
 * Download a committed run's WPS file (CSV). Returns the CSV text — the
 * caller triggers the browser download. Refuses (409) unless the run is
 * committed and an authoritative WPS rule is configured.
 */
export function exportWpsPayrollRun(id, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/wps/`, { token });
}

/** Advance a draft run to computed (people:manage). */
export function computePayrollRun(id, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/compute/`, { method: 'POST', token });
}

/** Validate a computed run (people:manage). */
export function validatePayrollRun(id, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/validate/`, { method: 'POST', token });
}

/** Commit a validated run (people:manage). */
export function commitPayrollRun(id, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/commit/`, { method: 'POST', token });
}

/** Validation results for a single payroll run. */
export function fetchPayrollRunValidations(id, token) {
  return apiFetch(`${ROOT}payroll-runs/${encodeURIComponent(id)}/validations/`, { token });
}

/** List payslip lines, optionally filtered by payroll run. */
export function fetchPayslipLines({ payrollRun } = {}, token) {
  const query = payrollRun ? `?payroll_run=${encodeURIComponent(payrollRun)}` : '';
  return apiFetch(`${ROOT}payslip-lines/${query}`, { token });
}

/**
 * Walk a paginated people list endpoint into { count, results }.
 * Caps page_size at 200 (server max) so we never reintroduce unbounded GETs.
 */
async function fetchAllPages(path, token, params = {}) {
  const pageSize = Math.min(Math.max(Number(params.page_size) || 100, 1), 200);
  const base = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (k === 'page' || k === 'page_size') return;
    if (v != null && v !== '') base.set(k, String(v));
  });
  base.set('page', '1');
  base.set('page_size', String(pageSize));
  const first = await apiFetch(`${ROOT}${path}?${base}`, { token });
  if (Array.isArray(first)) {
    return { count: first.length, page_size: pageSize, results: first };
  }
  const results = [...(first?.results || [])];
  const total = Number(first?.count ?? results.length);
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages > 1) {
    const rest = await Promise.all(
      Array.from({ length: pages - 1 }, (_, i) => {
        const qs = new URLSearchParams(base);
        qs.set('page', String(i + 2));
        return apiFetch(`${ROOT}${path}?${qs}`, { token });
      }),
    );
    for (const chunk of rest) {
      results.push(...(chunk?.results || []));
    }
  }
  return { count: total, page_size: pageSize, results };
}

/** List leave entitlements (paginated; optional year / q). */
export function fetchLeaveEntitlements(token, params = {}) {
  const year = params.year ?? new Date().getFullYear();
  return fetchAllPages('leave-entitlements/', token, { ...params, year });
}

/** List leave records (paginated; optional status / q). */
export function fetchLeaveRecords(token, params = {}) {
  return fetchAllPages('leave-records/', token, params);
}

/** Create a leave record. */
export function createLeaveRecord(data, token) {
  return apiFetch(`${ROOT}leave-records/`, { method: 'POST', body: data, token });
}

/** Update a leave record (partial). */
export function updateLeaveRecord(id, data, token) {
  return apiFetch(`${ROOT}leave-records/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a leave record. */
export function deleteLeaveRecord(id, token) {
  return apiFetch(`${ROOT}leave-records/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** Create a leave entitlement. */
export function createLeaveEntitlement(data, token) {
  return apiFetch(`${ROOT}leave-entitlements/`, { method: 'POST', body: data, token });
}

/** Update a leave entitlement (partial). */
export function updateLeaveEntitlement(id, data, token) {
  return apiFetch(`${ROOT}leave-entitlements/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a leave entitlement. */
export function deleteLeaveEntitlement(id, token) {
  return apiFetch(`${ROOT}leave-entitlements/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** List leave policies (HR config). */
export function fetchLeavePolicies(token) {
  return apiFetch(`${ROOT}leave-policies/`, { token });
}

/** Single leave policy (registry detail). */
export function fetchLeavePolicy(id, token) {
  return apiFetch(`${ROOT}leave-policies/${encodeURIComponent(id)}/`, { token });
}

/** Update a leave policy (partial). */
export function updateLeavePolicy(id, data, token) {
  return apiFetch(`${ROOT}leave-policies/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Create a leave policy. */
export function createLeavePolicy(data, token) {
  return apiFetch(`${ROOT}leave-policies/`, { method: 'POST', body: data, token });
}

/** Deprecate a leave policy (lifecycle transition — no hard delete). */
export function deprecateLeavePolicy(id, token) {
  return updateLeavePolicy(id, { status: 'deprecated' }, token);
}

/**
 * Propagate a leave policy to employee entitlements for a given year.
 * Pass `dry_run: true` to preview (eligible/will_create/will_update/skipped)
 * without writing anything.
 */
export function propagateLeavePolicy(id, { year, dry_run = false }, token) {
  const query = dry_run ? '?dry_run=true' : '';
  return apiFetch(`${ROOT}leave-policies/${encodeURIComponent(id)}/propagate/${query}`, {
    method: 'POST',
    body: { year },
    token,
  });
}

/** List version history for a leave policy (LPR-3A). */
export function fetchLeavePolicyVersions(policyId, token) {
  return apiFetch(`${ROOT}leave-policies/${encodeURIComponent(policyId)}/versions/`, { token });
}

/** Fork a new version of a leave policy. `payload` = { change_summary?, effective_from? }. */
export function forkLeavePolicy(policyId, payload, token) {
  return apiFetch(`${ROOT}leave-policies/${encodeURIComponent(policyId)}/versions/`, {
    method: 'POST',
    body: payload,
    token,
  });
}

/** List benefit types. */
export function fetchBenefitTypes(token) {
  return apiFetch(`${ROOT}benefit-types/`, { token });
}

/** List employee benefits (optional ``employee`` filter). */
export function fetchEmployeeBenefits(token, params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') qs.set(k, String(v));
  });
  const suffix = qs.toString() ? `?${qs}` : '';
  return apiFetch(`${ROOT}benefits/${suffix}`, { token });
}

/** Create a benefit type. */
export function createBenefitType(data, token) {
  return apiFetch(`${ROOT}benefit-types/`, { method: 'POST', body: data, token });
}

/** Update a benefit type (partial). */
export function updateBenefitType(id, data, token) {
  return apiFetch(`${ROOT}benefit-types/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a benefit type. */
export function deleteBenefitType(id, token) {
  return apiFetch(`${ROOT}benefit-types/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** Create an employee benefit. */
export function createEmployeeBenefit(data, token) {
  return apiFetch(`${ROOT}benefits/`, { method: 'POST', body: data, token });
}

/** Update an employee benefit (partial). */
export function updateEmployeeBenefit(id, data, token) {
  return apiFetch(`${ROOT}benefits/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete an employee benefit. */
export function deleteEmployeeBenefit(id, token) {
  return apiFetch(`${ROOT}benefits/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** List attendance records. */
export function fetchAttendanceRecords(token) {
  return apiFetch(`${ROOT}attendance/`, { token });
}

/** List attendance permissions. */
export function fetchAttendancePermissions(token) {
  return apiFetch(`${ROOT}attendance-permissions/`, { token });
}

/** Create an attendance record. */
export function createAttendanceRecord(data, token) {
  return apiFetch(`${ROOT}attendance/`, { method: 'POST', body: data, token });
}

/** Update an attendance record (partial). */
export function updateAttendanceRecord(id, data, token) {
  return apiFetch(`${ROOT}attendance/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete an attendance record. */
export function deleteAttendanceRecord(id, token) {
  return apiFetch(`${ROOT}attendance/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** Create an attendance permission. */
export function createAttendancePermission(data, token) {
  return apiFetch(`${ROOT}attendance-permissions/`, { method: 'POST', body: data, token });
}

/** Update an attendance permission (partial). */
export function updateAttendancePermission(id, data, token) {
  return apiFetch(`${ROOT}attendance-permissions/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete an attendance permission. */
export function deleteAttendancePermission(id, token) {
  return apiFetch(`${ROOT}attendance-permissions/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** List compliance rules (statutory figures / config). */
export function fetchComplianceRules(token) {
  return apiFetch(`${ROOT}compliance-rules/`, { token });
}

/** Create a compliance rule. */
export function createComplianceRule(data, token) {
  return apiFetch(`${ROOT}compliance-rules/`, { method: 'POST', body: data, token });
}

/** Update a compliance rule (partial). */
export function updateComplianceRule(id, data, token) {
  return apiFetch(`${ROOT}compliance-rules/${encodeURIComponent(id)}/`, {
    method: 'PATCH', body: data, token,
  });
}

/** Delete a compliance rule. */
export function deleteComplianceRule(id, token) {
  return apiFetch(`${ROOT}compliance-rules/${encodeURIComponent(id)}/`, {
    method: 'DELETE', token,
  });
}

/** List positions. */
export function fetchPositions(token) {
  return apiFetch(`${ROOT}positions/`, { token });
}

/** Create a position. */
export function createPosition(data, token) {
  return apiFetch(`${ROOT}positions/`, { method: 'POST', body: data, token });
}

/** Update a position (partial). */
export function updatePosition(id, data, token) {
  return apiFetch(`${ROOT}positions/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a position. */
export function deletePosition(id, token) {
  return apiFetch(`${ROOT}positions/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** Create an employee. */
export function createEmployee(data, token) {
  return apiFetch(`${ROOT}employees/`, { method: 'POST', body: data, token });
}

/** Update an employee (partial). */
export function updateEmployee(id, data, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Deactivate an employee (soft delete — sets is_active=false). */
export function deleteEmployee(id, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** Governed deactivation: reason + effective date, audited chronicle entry. */
export function deactivateEmployee(id, data, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/deactivate/`, { method: 'POST', body: data, token });
}

/** Re-onboard an inactive employee (records a reactivated chronicle entry). */
export function reactivateEmployee(id, data, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/reactivate/`, { method: 'POST', body: data, token });
}

/** Full compensation ledger for one employee (GET — audited, requires permission). */
export function fetchCompensationLedger(id, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/compensation/`, { token });
}

/** Append a new effective-dated compensation line (POST — emits salary_change event). */
export function createCompensationLine(employeeId, data, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(employeeId)}/compensation/`, {
    method: 'POST', body: data, token,
  });
}

/** Verify a compensation line (marks it is_verified=true). */
export function verifyCompensationLine(employeeId, lineId, token) {
  return apiFetch(
    `${ROOT}employees/${encodeURIComponent(employeeId)}/compensation/${encodeURIComponent(lineId)}/verify/`,
    { method: 'POST', token },
  );
}

/** Governed component catalog (the types — basic, housing, transport, gosi, …). */
export function fetchCompensationComponents(token) {
  return apiFetch(`${ROOT}compensation-components/`, { token });
}

/** Create a compensation component (admin only on the API). */
export function createCompensationComponent(data, token) {
  return apiFetch(`${ROOT}compensation-components/`, { method: 'POST', body: data, token });
}

/** Update a compensation component (admin only). */
export function updateCompensationComponent(id, data, token) {
  return apiFetch(`${ROOT}compensation-components/${encodeURIComponent(id)}/`, {
    method: 'PATCH', body: data, token,
  });
}

/** Soft-deactivate a compensation component (admin only). */
export function deleteCompensationComponent(id, token) {
  return apiFetch(`${ROOT}compensation-components/${encodeURIComponent(id)}/`, {
    method: 'DELETE', token,
  });
}

/** Compensation plan matrix (config layer above the per-employee ledger). */
export function fetchCompensationPlan(token, { payGrade, jobFamily } = {}) {
  const params = new URLSearchParams();
  if (payGrade) params.set('pay_grade', payGrade);
  if (jobFamily) params.set('job_family', jobFamily);
  const qs = params.toString() ? `?${params}` : '';
  return apiFetch(`${ROOT}compensation-plan/${qs}`, { token });
}

/** Create a compensation plan row (admin only on the API). */
export function createCompensationPlan(data, token) {
  return apiFetch(`${ROOT}compensation-plan/`, { method: 'POST', body: data, token });
}

/** Update a compensation plan row (admin only). */
export function updateCompensationPlan(id, data, token) {
  return apiFetch(`${ROOT}compensation-plan/${encodeURIComponent(id)}/`, {
    method: 'PATCH', body: data, token,
  });
}

/** Soft-deactivate a compensation plan row (admin only). */
export function deleteCompensationPlan(id, token) {
  return apiFetch(`${ROOT}compensation-plan/${encodeURIComponent(id)}/`, {
    method: 'DELETE', token,
  });
}

/** Single employee. */
export function fetchEmployee(id, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/`, { token });
}

/** Chronicle events for one employee. */
export function fetchEmployeeTimeline(id, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/timeline/`, { token });
}

/**
 * EOSI (end-of-service indemnity) provision with lineage.
 * GET people/employees/<id>/eosi/?as_of=YYYY-MM-DD
 * Returns { value, lineage: { rule_id, rule_version, inputs }, as_of }.
 * 409 when no authoritative eosi ComplianceRule exists.
 */
export function fetchEmployeeEosi(id, token, { asOf } = {}) {
  const params = new URLSearchParams();
  if (asOf) params.set('as_of', asOf);
  const qs = params.toString() ? `?${params}` : '';
  return apiFetch(
    `${ROOT}employees/${encodeURIComponent(id)}/eosi/${qs}`,
    { token },
  );
}

/** Governed correspondence for one employee (HR 360 Requests tab). */
export function fetchEmployeeCorrespondence(id, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/correspondence/`, { token });
}

/** Single correspondence incl. timeline events (HR-scoped, GET
 * people/employees/{id}/correspondence/{corrId}/). */
export function fetchEmployeeCorrespondenceDetail(id, corrId, token) {
  return apiFetch(
    `${ROOT}employees/${encodeURIComponent(id)}/correspondence/${encodeURIComponent(corrId)}/`,
    { token },
  );
}

/** List employee loans (optional ``employee`` filter). */
export function fetchLoans(token, params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') qs.set(k, String(v));
  });
  const suffix = qs.toString() ? `?${qs}` : '';
  return apiFetch(`${ROOT}loans/${suffix}`, { token });
}

/** Create a loan. */
export function createLoan(data, token) {
  return apiFetch(`${ROOT}loans/`, { method: 'POST', body: data, token });
}

/** Update a loan (partial). */
export function updateLoan(id, data, token) {
  return apiFetch(`${ROOT}loans/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a loan (blocked server-side once installments exist). */
export function deleteLoan(id, token) {
  return apiFetch(`${ROOT}loans/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** List loan installments (read-only in the UI). */
export function fetchLoanInstallments(token) {
  return apiFetch(`${ROOT}loan-installments/`, { token });
}

/** List employee certifications (optional ``employee`` filter). */
export function fetchCertifications(token, params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') qs.set(k, String(v));
  });
  const suffix = qs.toString() ? `?${qs}` : '';
  return apiFetch(`${ROOT}certifications/${suffix}`, { token });
}

/** Create a certification. */
export function createCertification(data, token) {
  return apiFetch(`${ROOT}certifications/`, { method: 'POST', body: data, token });
}

/** Update a certification (partial). */
export function updateCertification(id, data, token) {
  return apiFetch(`${ROOT}certifications/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a certification. */
export function deleteCertification(id, token) {
  return apiFetch(`${ROOT}certifications/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}

/** List rotation schedules. */
export function fetchRotationSchedules(token) {
  return apiFetch(`${ROOT}rotation-schedules/`, { token });
}

/** Create a rotation schedule. */
export function createRotationSchedule(data, token) {
  return apiFetch(`${ROOT}rotation-schedules/`, { method: 'POST', body: data, token });
}

/** Update a rotation schedule (partial). */
export function updateRotationSchedule(id, data, token) {
  return apiFetch(`${ROOT}rotation-schedules/${encodeURIComponent(id)}/`, { method: 'PATCH', body: data, token });
}

/** Delete a rotation schedule. */
export function deleteRotationSchedule(id, token) {
  return apiFetch(`${ROOT}rotation-schedules/${encodeURIComponent(id)}/`, { method: 'DELETE', token });
}
