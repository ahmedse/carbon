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
  params.append("page_size", 1000); // fetch all — admin-only list, no infinite scroll needed

  const endpoint = `${API_ROUTES.emissionsFactors}?${params.toString()}`;

  const data = await apiFetch(endpoint, { token });
  // Backend returns paginated envelope {count, results, ...} — unwrap it
  return Array.isArray(data) ? data : (data?.results ?? []);
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

// ═══════════════════════════════════════════════════════════════════════════════════
// GHG Protocol Phase 2 — Organizational Boundaries (admin CRUD)
// ═══════════════════════════════════════════════════════════════════════════════════

/**
 * Fetch all organizational boundaries
 */
export async function fetchOrganizationalBoundaries(token) {
  return apiFetch(API_ROUTES.emissionsBoundaries, { token });
}

/**
 * Create a new organizational boundary (admin only)
 */
export async function createOrganizationalBoundary(data, token) {
  return apiFetch(API_ROUTES.emissionsBoundaries, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing organizational boundary (admin only)
 */
export async function updateOrganizationalBoundary(id, data, token) {
  return apiFetch(`${API_ROUTES.emissionsBoundaries}${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete an organizational boundary (admin only)
 */
export async function deleteOrganizationalBoundary(id, token) {
  return apiFetch(`${API_ROUTES.emissionsBoundaries}${id}/`, {
    method: "DELETE",
    token,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════════
// GHG Protocol Phase 2 — Base Years (admin CRUD + recalculate)
// ═══════════════════════════════════════════════════════════════════════════════════

/**
 * Fetch all base years
 */
export async function fetchBaseYears(token) {
  return apiFetch(API_ROUTES.emissionsBaseYears, { token });
}

/**
 * Create a new base year (admin only)
 */
export async function createBaseYear(data, token) {
  return apiFetch(API_ROUTES.emissionsBaseYears, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing base year (admin only)
 */
export async function updateBaseYear(id, data, token) {
  return apiFetch(`${API_ROUTES.emissionsBaseYears}${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete a base year (admin only)
 */
export async function deleteBaseYear(id, token) {
  return apiFetch(`${API_ROUTES.emissionsBaseYears}${id}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Trigger a base year recalculation (creates a RecalculationTrigger)
 */
export async function recalculateBaseYear(id, data, token) {
  return apiFetch(`${API_ROUTES.emissionsBaseYears}${id}/recalculate/`, {
    method: "POST",
    body: data,
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
  
  if (params.output_format) query.append("output_format", params.output_format);
  
  const endpoint = `${API_ROUTES.emissionsReport}?${query.toString()}`;
  return apiFetch(endpoint, { token });
}

/**
 * Download report as CSV blob
 */
export async function downloadReportCsv(params, token) {
  const query = new URLSearchParams();
  query.append("output_format", "csv");
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

// ═══════════════════════════════════════════════════════════════════════════
// E2 — Verification & Period State-Machine Actions
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Verify a verification record (admin/analyst).
 * POST /carbon-api/carbon/verifications/{id}/verify/
 */
export async function verifyVerificationRecord(verificationId, token) {
  return apiFetch(`${API_ROUTES.emissionsVerification}${verificationId}/verify/`, {
    method: "POST",
    token,
  });
}

/**
 * Reject a verification record with notes (admin/analyst).
 * POST /carbon-api/carbon/verifications/{id}/reject/
 */
export async function rejectVerificationRecord(verificationId, notes, token) {
  return apiFetch(`${API_ROUTES.emissionsVerification}${verificationId}/reject/`, {
    method: "POST",
    body: { notes },
    token,
  });
}

// ── Reporting Period state-machine actions ──────────────────────────────

/**
 * Submit a period for verification (data_owner).
 * POST /carbon-api/carbon/periods/{id}/submit/
 */
export async function submitPeriod(periodId, token) {
  return apiFetch(`${API_ROUTES.emissionsPeriods}${periodId}/submit/`, {
    method: "POST",
    token,
  });
}

/**
 * Open a period for data entry (from draft or locked).
 * POST /carbon-api/carbon/periods/{id}/open/
 */
export async function openPeriod(periodId, token) {
  return apiFetch(`${API_ROUTES.emissionsPeriods}${periodId}/open/`, {
    method: "POST",
    token,
  });
}

/**
 * Lock a period for review (admin only).
 * POST /carbon-api/carbon/periods/{id}/lock/
 */
export async function lockPeriod(periodId, token) {
  return apiFetch(`${API_ROUTES.emissionsPeriods}${periodId}/lock/`, {
    method: "POST",
    token,
  });
}

/**
 * Close a verified period (admin only).
 * POST /carbon-api/carbon/periods/{id}/close/
 */
export async function closePeriod(periodId, token) {
  return apiFetch(`${API_ROUTES.emissionsPeriods}${periodId}/close/`, {
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

// ═══════════════════════════════════════════════════════════════════════════
// Phase 28-B — Inventory Coverage (ADR-0020) API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Fetch inventory sources (declared-universe bindings)
 */
export async function fetchInventorySources(token) {
  return apiFetch(API_ROUTES.emissionsInventorySources, { token });
}

/**
 * Create a new inventory source (admin only)
 */
export async function createInventorySource(data, token) {
  return apiFetch(API_ROUTES.emissionsInventorySources, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing inventory source (admin only)
 */
export async function updateInventorySource(sourceId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsInventorySources}${sourceId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete an inventory source (admin only)
 */
export async function deleteInventorySource(sourceId, token) {
  return apiFetch(`${API_ROUTES.emissionsInventorySources}${sourceId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Fetch inventory source statuses (optionally filtered by reporting period)
 */
export async function fetchInventorySourceStatuses({ reporting_period } = {}, token) {
  const params = new URLSearchParams();
  if (reporting_period) params.append("reporting_period", reporting_period);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsInventorySourceStatuses}${qs ? `?${qs}` : ""}`, { token });
}

/**
 * Create a new inventory source status (admin only)
 */
export async function createInventorySourceStatus(data, token) {
  return apiFetch(API_ROUTES.emissionsInventorySourceStatuses, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing inventory source status (admin only)
 */
export async function updateInventorySourceStatus(statusId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsInventorySourceStatuses}${statusId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete an inventory source status (admin only)
 */
export async function deleteInventorySourceStatus(statusId, token) {
  return apiFetch(`${API_ROUTES.emissionsInventorySourceStatuses}${statusId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Fetch coverage goals
 */
export async function fetchCoverageGoals(token) {
  return apiFetch(API_ROUTES.emissionsCoverageGoals, { token });
}

/**
 * Create a new coverage goal (admin only)
 */
export async function createCoverageGoal(data, token) {
  return apiFetch(API_ROUTES.emissionsCoverageGoals, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing coverage goal (admin only)
 */
export async function updateCoverageGoal(goalId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageGoals}${goalId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete a coverage goal (admin only)
 */
export async function deleteCoverageGoal(goalId, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageGoals}${goalId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Fetch coverage actions
 */
export async function fetchCoverageActions(token) {
  return apiFetch(API_ROUTES.emissionsCoverageActions, { token });
}

/**
 * Create a new coverage action (admin only)
 */
export async function createCoverageAction(data, token) {
  return apiFetch(API_ROUTES.emissionsCoverageActions, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Update an existing coverage action (admin only)
 */
export async function updateCoverageAction(actionId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageActions}${actionId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete a coverage action (admin only)
 */
export async function deleteCoverageAction(actionId, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageActions}${actionId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Compute declared-universe coverage for a reporting period (read-only).
 * GET /carbon/coverage/?reporting_period=<id>&org_unit=<id>
 */
export async function fetchCoverage({ reporting_period, org_unit } = {}, token) {
  const params = new URLSearchParams();
  if (reporting_period) params.append("reporting_period", reporting_period);
  if (org_unit) params.append("org_unit", org_unit);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsCoverage}${qs ? `?${qs}` : ""}`, { token });
}
