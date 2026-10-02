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

export async function fetchDisclosureExport({ framework, reporting_period_id }, token) {
  const query = new URLSearchParams();
  query.append("framework", framework || "esrs_e1");
  query.append("reporting_period_id", String(reporting_period_id));
  return apiFetch(`${API_ROUTES.emissionsDisclosure}?${query.toString()}`, { token });
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

/**
 * Fetch the chairman overview payload (single round-trip for the Tier-1 screen).
 * GET /carbon/chairman/?reporting_period_id=<id>
 */
/**
 * Period calculation summary. Kilograms in the payload are the only figures
 * the onboarding screen may show. This call does not create a calculation.
 * GET /carbon/calculations/summary/?reporting_period_id=<id>
 */
export async function fetchPeriodCalculationSummary({ reporting_period_id } = {}, token) {
  const params = new URLSearchParams();
  if (reporting_period_id != null && reporting_period_id !== "") {
    params.append("reporting_period_id", String(reporting_period_id));
  }
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsCalculationSummary}${qs ? `?${qs}` : ""}`, { token });
}

/** Read-only O1 checklist. The server decides the codes. This call writes nothing. */
export async function fetchOnboardingO1(token) {
  return apiFetch(API_ROUTES.emissionsOnboardingO1, { token });
}

/** Campus intake catalogue. Kilograms in this payload are null. */
export async function fetchCampusIntake(token) {
  return apiFetch(API_ROUTES.emissionsIntake, { token });
}

export async function uploadCampusIntake(token, leafId, rows) {
  return apiFetch(`${API_ROUTES.emissionsIntake}${leafId}/upload/`, {
    token,
    method: 'POST',
    body: { rows },
  });
}

/** One missing stream. Same DataRow pipeline as the template upload. */
export async function enterCampusStream(token, fields) {
  return apiFetch(`${API_ROUTES.emissionsIntake}entry/`, {
    token,
    method: 'POST',
    body: fields,
  });
}

/**
 * Read ONE coverage row's state on the open period plus its Data Product
 * contract. GET carbon/inventory-sources/<id>/submit/
 */
export async function fetchCoverageRowSubmission(sourceId, token) {
  return apiFetch(`${API_ROUTES.emissionsInventorySources}${sourceId}/submit/`, { token });
}

/**
 * Submit one value against ONE coverage row. Campus, scope, unit and period
 * are prefilled from the row; the body carries the value only.
 * POST carbon/inventory-sources/<id>/submit/
 */
export async function submitCoverageRow(sourceId, fields, token) {
  return apiFetch(`${API_ROUTES.emissionsInventorySources}${sourceId}/submit/`, {
    token,
    method: 'POST',
    body: fields,
  });
}

/**
 * Declare or clear an exclusion for ONE coverage row on the single open period.
 * Writes only InventorySourceStatus (status + reason + notes); no kilogram and
 * no Calculation. POST carbon/inventory-sources/<id>/exclusion/
 */
export async function setCoverageRowExclusion(sourceId, { excluded, reason, notes } = {}, token) {
  return apiFetch(`${API_ROUTES.emissionsInventorySources}${sourceId}/exclusion/`, {
    token,
    method: 'POST',
    body: { excluded, reason, notes },
  });
}

/**
 * Required vs received counts for the open period and per active CoverageGoal.
 * Counts only — no kilogram and no claimed coverage percent.
 * GET carbon/coverage/reconciliation/
 */
export async function fetchCoverageReconciliation(token) {
  return apiFetch(API_ROUTES.emissionsCoverageReconciliation, { token });
}

/** Copy named-file quantities onto the period they belong to. The server stores no kilogram. */
export async function recordDiscoveredActivity(token) {
  return apiFetch(`${API_ROUTES.emissionsIntake}discovered/`, {
    token,
    method: 'POST',
    body: {},
  });
}

export async function fetchChairmanData({ reporting_period_id } = {}, token) {
  const params = new URLSearchParams();
  if (reporting_period_id) params.append("reporting_period_id", reporting_period_id);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsChairman}${qs ? `?${qs}` : ""}`, { token });
}

// ═══════════════════════════════════════════════════════════════════════════
// Coverage targets (layer 1) + tasks (two-layer Coverage, locked 2 Oct 2026)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Cycle dropdown + the target grid for the defaulted open period.
 * GET carbon/coverage-targets/board/
 */
export async function fetchCoverageTargetBoard(token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageTargets}board/`, { token });
}

/**
 * Targets for ONE reporting period (defaults server-side to the open period).
 * GET carbon/coverage-targets/?reporting_period=<id>
 */
export async function fetchCoverageTargets({ reporting_period } = {}, token) {
  const params = new URLSearchParams();
  if (reporting_period) params.append("reporting_period", reporting_period);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsCoverageTargets}${qs ? `?${qs}` : ""}`, { token });
}

/** Target detail with its task list. GET carbon/coverage-targets/<id>/ */
export async function fetchCoverageTarget(targetId, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageTargets}${targetId}/`, { token });
}

/** Create a target (open period only). POST carbon/coverage-targets/ */
export async function createCoverageTarget(data, token) {
  return apiFetch(API_ROUTES.emissionsCoverageTargets, {
    method: 'POST',
    body: data,
    token,
  });
}

/** Update a target. PATCH carbon/coverage-targets/<id>/ */
export async function updateCoverageTarget(targetId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageTargets}${targetId}/`, {
    method: 'PATCH',
    body: data,
    token,
  });
}

/** Delete a target. DELETE carbon/coverage-targets/<id>/ */
export async function deleteCoverageTarget(targetId, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageTargets}${targetId}/`, {
    method: 'DELETE',
    token,
  });
}

/** Tasks under a target. GET carbon/coverage-tasks/?target=<id> */
export async function fetchCoverageTasks({ target } = {}, token) {
  const params = new URLSearchParams();
  if (target) params.append('target', target);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsCoverageTasks}${qs ? `?${qs}` : ''}`, { token });
}

/** Create a task under a target. POST carbon/coverage-tasks/ */
export async function createCoverageTask(data, token) {
  return apiFetch(API_ROUTES.emissionsCoverageTasks, {
    method: 'POST',
    body: data,
    token,
  });
}

/** Update a task. A done transition needs host evidence. PATCH carbon/coverage-tasks/<id>/ */
export async function updateCoverageTask(taskId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageTasks}${taskId}/`, {
    method: 'PATCH',
    body: data,
    token,
  });
}

/** Delete a task. DELETE carbon/coverage-tasks/<id>/ */
export async function deleteCoverageTask(taskId, token) {
  return apiFetch(`${API_ROUTES.emissionsCoverageTasks}${taskId}/`, {
    method: 'DELETE',
    token,
  });
}

// ── Coverage target form lookups (real sources only) ──────────────────────
// The target form needs a searchable Campus, a Campus-driven Org unit, and a
// searchable Owner. These read the REAL sources (mdm.OrgUnit / accounts.User)
// through carbon-scoped actions — no hardcoded ids, no fabricated options.

/** Real campuses (mdm.OrgUnit org_type='campus'). GET carbon/coverage-targets/campuses/ */
export async function fetchCoverageCampusOptions(token) {
  const data = await apiFetch(`${API_ROUTES.emissionsCoverageTargets}campuses/`, { token });
  return Array.isArray(data) ? data : (data?.results ?? []);
}

/**
 * The selected campus's REAL descendant org units (the dependency).
 * GET carbon/coverage-targets/org-units/?campus=<id>
 * Returns { campus, count, results }.
 */
export async function fetchCoverageOrgUnitOptions({ campus } = {}, token) {
  const params = new URLSearchParams();
  if (campus) params.append('campus', campus);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.emissionsCoverageTargets}org-units/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Real people who can own a target. GET carbon/coverage-targets/owners/?q=&page=&page_size=
 * Returns { count, page, page_size, results }.
 */
export async function fetchCoverageOwnerOptions({ q, page = 1, pageSize = 200 } = {}, token) {
  const params = new URLSearchParams();
  if (q) params.append('q', q);
  params.append('page', String(page));
  params.append('page_size', String(pageSize));
  return apiFetch(`${API_ROUTES.emissionsCoverageTargets}owners/?${params.toString()}`, { token });
}
