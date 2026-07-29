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
