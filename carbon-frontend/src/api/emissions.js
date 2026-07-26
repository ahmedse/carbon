// File: src/api/emissions.js
// API client for Emissions Calculator endpoints

import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

/**
 * Fetch emissions dashboard data
 * @param {Object} params - Query parameters
 * @param {string} params.project_id - Filter by project ID
 * @param {string} params.reporting_period_id - Filter by reporting period
 * @param {string} params.year - Filter by year
 * @param {string} token - JWT token
 */
export async function fetchEmissionsDashboard({ project_id, reporting_period_id, year } = {}, token) {
  const params = new URLSearchParams();
  if (project_id) params.append("project_id", project_id);
  if (reporting_period_id) params.append("reporting_period_id", reporting_period_id);
  if (year) params.append("year", year);
  
  const endpoint = params.toString() 
    ? `${API_ROUTES.emissionsDashboard}?${params.toString()}`
    : API_ROUTES.emissionsDashboard;
  
  return apiFetch(endpoint, { token });
}

/**
 * Fetch emissions report
 * @param {Object} params - Query parameters
 * @param {string} token - JWT token
 */
export async function fetchEmissionsReport({ project_id, reporting_period_id, year, format = "json" } = {}, token) {
  const params = new URLSearchParams();
  if (project_id) params.append("project_id", project_id);
  if (reporting_period_id) params.append("reporting_period_id", reporting_period_id);
  if (year) params.append("year", year);
  params.append("format", format);
  
  const endpoint = `${API_ROUTES.emissionsReport}?${params.toString()}`;
  return apiFetch(endpoint, { token });
}

/**
 * Trigger emissions calculations
 * @param {Object} data - Calculation parameters
 * @param {string} token - JWT token
 */
export async function triggerCalculations(data, token) {
  return apiFetch(API_ROUTES.emissionsCalculate, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Fetch reporting periods
 * @param {string} token - JWT token
 */
export async function fetchReportingPeriods(token) {
  return apiFetch(API_ROUTES.emissionsPeriods, { token });
}

/**
 * Fetch active reporting period
 * @param {string} token - JWT token
 */
export async function fetchActiveReportingPeriod(token) {
  return apiFetch(`${API_ROUTES.emissionsPeriods}active/`, { token });
}

/**
 * Fetch emission factors
 * @param {Object} params - Query parameters
 * @param {string} token - JWT token
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
 * @param {string} token - JWT token
 */
export async function fetchFactorCategories(token) {
  return apiFetch(`${API_ROUTES.emissionsFactors}categories/`, { token });
}

/**
 * Fetch calculation rules
 * @param {string} token - JWT token
 */
export async function fetchCalculationRules(token) {
  return apiFetch(API_ROUTES.emissionsRules, { token });
}

/**
 * Execute a calculation rule
 * @param {number} ruleId - Rule ID
 * @param {Object} data - Execution parameters
 * @param {string} token - JWT token
 */
export async function executeCalculationRule(ruleId, data, token) {
  return apiFetch(`${API_ROUTES.emissionsRules}${ruleId}/execute/`, {
    method: "POST",
    body: data,
    token,
  });
}

/**
 * Fetch calculations list
 * @param {Object} params - Query parameters
 * @param {string} token - JWT token
 */
export async function fetchCalculations({ project_id, module_id, scope, category, reporting_year } = {}, token) {
  const params = new URLSearchParams();
  if (project_id) params.append("project_id", project_id);
  if (module_id) params.append("module_id", module_id);
  if (scope) params.append("scope", scope);
  if (category) params.append("category", category);
  if (reporting_year) params.append("reporting_year", reporting_year);
  
  const endpoint = params.toString()
    ? `${API_ROUTES.emissionsCalculations}?${params.toString()}`
    : API_ROUTES.emissionsCalculations;
  
  return apiFetch(endpoint, { token });
}

/**
 * Fetch yearly comparison data for targets and trends
 * @param {Object} params - Query parameters
 * @param {string} params.project_id - Filter by project ID
 * @param {string} params.years - Comma-separated list of years (e.g., "2020,2021,2022,2023,2024,2025")
 * @param {string} token - JWT token
 * 
 * Returns:
 * - baseline_year: The year marked as baseline
 * - baseline_total_tonnes: Emissions in baseline year
 * - yearly_comparison: Array of yearly data with reduction metrics
 * - targets: Array of target values by year
 */
export async function fetchYearlyComparison({ project_id, years } = {}, token) {
  const params = new URLSearchParams();
  if (project_id) params.append("project_id", project_id);
  if (years) params.append("years", years);
  
  const endpoint = params.toString()
    ? `${API_ROUTES.emissionsYearlyComparison}?${params.toString()}`
    : API_ROUTES.emissionsYearlyComparison;
  
  return apiFetch(endpoint, { token });
}

/**
 * Fetch owner dashboard data (scoped to user's org unit)
 * @param {string} token - JWT token
 * @param {number} orgUnitId - Optional specific org_unit to scope to
 * @param {number} periodId - Optional reporting period ID
 */
export async function fetchOwnerDashboard(token, orgUnitId = null, periodId = null) {
  const params = new URLSearchParams();
  if (orgUnitId) params.append('org_unit', orgUnitId);
  if (periodId) params.append('period', periodId);
  
  const endpoint = params.toString()
    ? `${API_ROUTES.emissionsOwnerDashboard}?${params.toString()}`
    : API_ROUTES.emissionsOwnerDashboard;
  
  return apiFetch(endpoint, { token });
}

/**
 * Fetch data owner summary (org unit, modules, stats)
 * @param {string} token - JWT token
 */
export async function fetchOwnerSummary(token) {
  return apiFetch(`${API_ROUTES.emissionsAPI}owner/summary/`, { token });
}

/**
 * Fetch Carbon console data
 * @param {string} token - JWT token
 */
export async function fetchConsoleData(token) {
  return apiFetch(`${API_ROUTES.emissionsAPI}console/`, { token });
}

/**
 * Fetch consolidated My Data (Data Owner workspace)
 * @param {string} token - JWT token
 */
export async function fetchMyData(token) {
  return apiFetch(`${API_ROUTES.emissionsAPI}my-data/`, { token });
}

/**
 * Fetch emission-generating assets scoped to the user's org unit
 * @param {Object} params - Query parameters
 * @param {string} token - JWT token
 */
export async function fetchOwnerAssets({ search, scope } = {}, token) {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (scope) params.append('scope', scope);

  const endpoint = params.toString()
    ? `${API_ROUTES.emissionsAPI}owner/assets/?${params.toString()}`
    : `${API_ROUTES.emissionsAPI}owner/assets/`;

  return apiFetch(endpoint, { token });
}

/**
 * Fetch recent activity for a data owner
 * @param {Object} params - Query parameters
 * @param {number} params.limit - Max number of events to return
 * @param {string} token - JWT token
 */
export async function fetchOwnerActivity({ limit = 20 } = {}, token) {
  return apiFetch(`${API_ROUTES.emissionsAPI}owner/activity/?limit=${limit}`, { token });
}

/**
 * Fetch reporting periods with optional status filter
 * @param {string} token - JWT token
 * @param {string} status - Optional filter by status (open, closed, etc.)
 */
export async function fetchReportingPeriodsFiltered(token, status = null) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  
  const endpoint = params.toString()
    ? `${API_ROUTES.emissionsPeriods}?${params.toString()}`
    : API_ROUTES.emissionsPeriods;
  
  return apiFetch(endpoint, { token });
}
