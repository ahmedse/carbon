// src/api/people.js
// API helpers for the People & Payroll app (backend/people/*).
// All endpoints live under /carbon-api/people/ (see backend/people/urls.py).
// Every call goes through apiFetch (JWT refresh + error normalization) — never raw fetch().

import { apiFetch } from './api';

const ROOT = 'people/';

/** List employees. */
export function fetchEmployees(token) {
  return apiFetch(`${ROOT}employees/`, { token });
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

/** List leave entitlements. */
export function fetchLeaveEntitlements(token) {
  return apiFetch(`${ROOT}leave-entitlements/`, { token });
}

/** List leave records. */
export function fetchLeaveRecords(token) {
  return apiFetch(`${ROOT}leave-records/`, { token });
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

/** List benefit types. */
export function fetchBenefitTypes(token) {
  return apiFetch(`${ROOT}benefit-types/`, { token });
}

/** List employee benefits. */
export function fetchEmployeeBenefits(token) {
  return apiFetch(`${ROOT}benefits/`, { token });
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

/** Single employee. */
export function fetchEmployee(id, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/`, { token });
}

/** Chronicle events for one employee. */
export function fetchEmployeeTimeline(id, token) {
  return apiFetch(`${ROOT}employees/${encodeURIComponent(id)}/timeline/`, { token });
}

/** List employee loans. */
export function fetchLoans(token) {
  return apiFetch(`${ROOT}loans/`, { token });
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

/** List employee certifications. */
export function fetchCertifications(token) {
  return apiFetch(`${ROOT}certifications/`, { token });
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
