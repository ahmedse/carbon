// src/api/emissions-extended.js
// Extended API functions for P2 — Report Generator & Emission Factors

import { apiFetch, authFetch } from "./api";
import { API_ROUTES } from "../config";

/**
 * Fetch emission factors with optional filtering
 */
export async function fetchEmissionFactors({ category, scope, search, active = true } = {}, token) {
  const params = new URLSearchParams();
  if (category) params.append("category", category);
  if (scope) params.append("scope", scope);
  if (search) params.append("search", search);
  if (active !== undefined) params.append("active", active);
  
  const endpoint = params.toString()
    ? `${API_ROUTES.emissionsFactors}?${params.toString()}`
    : API_ROUTES.emissionsFactors;
  
  return apiFetch(endpoint, { token });
}

/**
 * Fetch emission factor categories
 */
export async function fetchFactorCategories(token) {
  return apiFetch(`${API_ROUTES.emissionsFactors}categories/`, { token });
}

/**
 * Create a new emission factor (admin only)
 */
export async function createEmissionFactor(data, token) {
  return apiFetch(API_ROUTES.emissionsFactors, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing emission factor (admin only)
 */
export async function updateEmissionFactor(factorId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsFactors}${factorId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete an emission factor (admin only)
 */
export async function deleteEmissionFactor(factorId, token) {
  return apiFetch(`${API_ROUTES.emissionsFactors}${factorId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Fetch reporting periods
 */
export async function fetchReportingPeriods(token) {
  return apiFetch(API_ROUTES.emissionsPeriods, { token });
}

/**
 * Create a reporting period
 */
export async function createReportingPeriod(data, token) {
  return apiFetch(API_ROUTES.emissionsPeriods, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update a reporting period
 */
export async function updateReportingPeriod(periodId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsPeriods}${periodId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete a reporting period
 */
export async function deleteReportingPeriod(periodId, token) {
  return apiFetch(`${API_ROUTES.emissionsPeriods}${periodId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Fetch report configurations
 */
export async function fetchReportConfigs(token) {
  return apiFetch(API_ROUTES.emissionsReportConfigs, { token });
}

/**
 * Create a report configuration
 */
export async function createReportConfig(data, token) {
  return apiFetch(API_ROUTES.emissionsReportConfigs, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update a report configuration
 */
export async function updateReportConfig(configId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsReportConfigs}${configId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase 07 G2 — SBTi Targets API (admin CRUD)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Fetch all SBTi targets
 */
export async function fetchSBTiTargets(token) {
  return apiFetch(API_ROUTES.emissionsTargets, { token });
}

/**
 * Create a new SBTi target (admin only)
 */
export async function createSBTiTarget(data, token) {
  return apiFetch(API_ROUTES.emissionsTargets, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing SBTi target (admin only)
 */
export async function updateSBTiTarget(id, data, token) {
  return apiFetch(`${API_ROUTES.emissionsTargets}${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete an SBTi target (admin only)
 */
export async function deleteSBTiTarget(id, token) {
  return apiFetch(`${API_ROUTES.emissionsTargets}${id}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Delete a report configuration
 */
export async function deleteReportConfig(configId, token) {
  return apiFetch(`${API_ROUTES.emissionsReportConfigs}${configId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Run a report configuration and get results
 */
export async function runReportConfig(configId, token) {
  return apiFetch(`${API_ROUTES.emissionsReportConfigs}${configId}/run/`, {
    method: "POST",
    token,
  });
}

/**
 * Generate a report with parameters
 */
export async function generateReport(params, token) {
  const query = new URLSearchParams();
  if (params.reporting_period_id) query.append("reporting_period_id", params.reporting_period_id);
  if (params.custom_start) query.append("custom_start", params.custom_start);
  if (params.custom_end) query.append("custom_end", params.custom_end);
  if (params.org_unit_id) query.append("org_unit_id", params.org_unit_id);
  if (params.ghg_scopes && Array.isArray(params.ghg_scopes)) {
    params.ghg_scopes.forEach(scope => query.append("ghg_scopes", scope));
  }
  if (params.categories && Array.isArray(params.categories)) {
    params.categories.forEach(cat => query.append("categories", cat));
  }
  if (params.grouping) query.append("grouping", params.grouping);
  
  const endpoint = `${API_ROUTES.emissionsReport}?${query.toString()}`;
  return apiFetch(endpoint, { token });
}

/**
 * Download report as CSV blob
 */
export async function downloadReportCsv(params, token) {
  const query = new URLSearchParams();
  query.append("format", "csv");
  if (params.reporting_period_id) query.append("reporting_period_id", params.reporting_period_id);
  if (params.custom_start) query.append("custom_start", params.custom_start);
  if (params.custom_end) query.append("custom_end", params.custom_end);
  if (params.org_unit_id) query.append("org_unit_id", params.org_unit_id);
  if (params.ghg_scopes && Array.isArray(params.ghg_scopes)) {
    params.ghg_scopes.forEach(scope => query.append("ghg_scopes", scope));
  }
  if (params.categories && Array.isArray(params.categories)) {
    params.categories.forEach(cat => query.append("categories", cat));
  }
  if (params.grouping) query.append("grouping", params.grouping);
  
  const endpoint = `${API_ROUTES.emissionsReport}?${query.toString()}`;
  
  const response = await authFetch(endpoint, { method: 'GET', token, rawResponse: true }); // CSV download
  
  if (!response.ok) {
    throw new Error(`CSV download failed: ${response.statusText}`);
  }
  
  return response.blob();
}

// ═══════════════════════════════════════════════════════════════════════════
// D3 — Calculations & Verification API (Phase 04 G2)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Fetch calculations with optional filters
 */
export async function fetchCalculations({ period, scope, status, search, page = 1, pageSize = 50 } = {}, token) {
  const params = new URLSearchParams();
  if (period) params.append("period", period);
  if (scope) params.append("scope", scope);
  if (status) params.append("status", status);
  if (search) params.append("search", search);
  params.append("page", page);
  params.append("page_size", pageSize);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsCalculations}${qs ? `?${qs}` : ""}`, { token });
}

/**
 * Fetch a single calculation summary
 */
export async function fetchCalculationSummary(calcId, token) {
  return apiFetch(`${API_ROUTES.emissionsCalculations}${calcId}/`, { token });
}

/**
 * Fetch calculation detail with traceability and DQ info
 */
export async function fetchCalculationDetail(calcId, token) {
  return apiFetch(`${API_ROUTES.emissionsCalculations}${calcId}/detail/`, { token });
}

/**
 * Recalculate a single calculation (admin/data_owner)
 */
export async function recalculateCalculation(calcId, token) {
  return apiFetch(`${API_ROUTES.emissionsCalculations}${calcId}/recalculate/`, {
    method: "POST",
    token,
  });
}

/**
 * Batch recalculate multiple calculations (admin only)
 */
export async function batchRecalculateCalculations(calcIds, token) {
  return apiFetch(`${API_ROUTES.emissionsCalculations}batch-recalculate/`, {
    method: "POST",
    body: { calculation_ids: calcIds },
    token,
  });
}

/**
 * Fetch verification records with optional filters
 */
export async function fetchVerificationRecords({ status, period, scope, page = 1, pageSize = 50 } = {}, token) {
  const params = new URLSearchParams();
  if (status) params.append("status", status);
  if (period) params.append("period", period);
  if (scope) params.append("scope", scope);
  params.append("page", page);
  params.append("page_size", pageSize);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsVerification}${qs ? `?${qs}` : ""}`, { token });
}

/**
 * Verify/submit a period's calculations (admin/analyst)
 */
export async function verifyPeriod(periodId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsVerification}${periodId}/verify/`, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Reject a period's calculations with notes
 */
export async function rejectPeriod(periodId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsVerification}${periodId}/reject/`, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Submit a period for verification (data_owner)
 */
export async function submitPeriod(periodId, token) {
  return apiFetch(`${API_ROUTES.emissionsCalculations}${periodId}/submit/`, {
    method: "POST",
    token,
  });
}

/**
 * Fetch calculation rules
 */
export async function fetchCalculationRules(token) {
  return apiFetch(API_ROUTES.emissionsRules, { token });
}

/**
 * Create a calculation rule (admin only)
 */
export async function createCalculationRule(data, token) {
  return apiFetch(API_ROUTES.emissionsRules, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update a calculation rule (admin only)
 */
export async function updateCalculationRule(ruleId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsRules}${ruleId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete a calculation rule (admin only)
 */
export async function deleteCalculationRule(ruleId, token) {
  return apiFetch(`${API_ROUTES.emissionsRules}${ruleId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Execute a calculation rule immediately (admin only)
 */
export async function executeCalculationRule(ruleId, data = {}, token) {
  return apiFetch(`${API_ROUTES.emissionsRules}${ruleId}/execute/`, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Fetch GWP reference values
 */
export async function fetchGWPValues(token) {
  return apiFetch(API_ROUTES.emissionsGWP, { token });
}

/**
 * Create a GWP reference value (admin only)
 */
export async function createGWPValue(data, token) {
  return apiFetch(API_ROUTES.emissionsGWP, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update a GWP reference value (admin only)
 */
export async function updateGWPValue(gwpId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsGWP}${gwpId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete a GWP reference value (admin only)
 */
export async function deleteGWPValue(gwpId, token) {
  return apiFetch(`${API_ROUTES.emissionsGWP}${gwpId}/`, {
    method: "DELETE",
    token,
  });
}
