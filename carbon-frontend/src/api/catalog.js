// src/api/catalog.js
// Catalog Studio API wrappers for catalog, MDM, connections, and importexport endpoints

import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

// ===== CATALOG: Domains, Glossary, Tags, Assets, Governance =====

/**
 * Fetch all data domains.
 */
export function fetchDataDomains(token) {
  return apiFetch(API_ROUTES.domains, { token });
}

/**
 * Create a new data domain.
 */
export function createDataDomain(token, data) {
  return apiFetch(API_ROUTES.domains, { method: "POST", token, body: data });
}

/**
 * Update a data domain.
 */
export function updateDataDomain(token, id, data) {
  return apiFetch(`${API_ROUTES.domains}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a data domain.
 */
export function deleteDataDomain(token, id) {
  return apiFetch(`${API_ROUTES.domains}${id}/`, { method: "DELETE", token });
}

// ----- Glossary Terms -----

/**
 * Fetch all glossary terms (optionally filtered by domain).
 */
export function fetchGlossaryTerms(token, domainId = null) {
  const url = domainId
    ? `${API_ROUTES.glossary}?domain=${domainId}`
    : API_ROUTES.glossary;
  return apiFetch(url, { token });
}

/**
 * Create a new glossary term.
 */
export function createGlossaryTerm(token, data) {
  return apiFetch(API_ROUTES.glossary, { method: "POST", token, body: data });
}

/**
 * Update a glossary term.
 */
export function updateGlossaryTerm(token, id, data) {
  return apiFetch(`${API_ROUTES.glossary}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a glossary term.
 */
export function deleteGlossaryTerm(token, id) {
  return apiFetch(`${API_ROUTES.glossary}${id}/`, { method: "DELETE", token });
}

// ----- Tags -----

/**
 * Fetch all tags.
 */
export function fetchTags(token) {
  return apiFetch(API_ROUTES.tags, { token });
}

/**
 * Create a new tag.
 */
export function createTag(token, data) {
  return apiFetch(API_ROUTES.tags, { method: "POST", token, body: data });
}

/**
 * Update a tag.
 */
export function updateTag(token, id, data) {
  return apiFetch(`${API_ROUTES.tags}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a tag.
 */
export function deleteTag(token, id) {
  return apiFetch(`${API_ROUTES.tags}${id}/`, { method: "DELETE", token });
}

// ----- Asset Profiles -----

/**
 * Fetch all asset profiles (optionally filtered by asset type).
 */
export function fetchAssetProfiles(token, assetType = null) {
  const url = assetType
    ? `${API_ROUTES.assets}?asset_type=${assetType}`
    : API_ROUTES.assets;
  return apiFetch(url, { token });
}

/**
 * Get a specific asset profile.
 */
export function fetchAssetProfile(token, id) {
  return apiFetch(`${API_ROUTES.assets}${id}/`, { token });
}

/**
 * Create a new asset profile.
 */
export function createAssetProfile(token, data) {
  return apiFetch(API_ROUTES.assets, { method: "POST", token, body: data });
}

/**
 * Update an asset profile.
 */
export function updateAssetProfile(token, id, data) {
  return apiFetch(`${API_ROUTES.assets}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete an asset profile.
 */
export function deleteAssetProfile(token, id) {
  return apiFetch(`${API_ROUTES.assets}${id}/`, { method: "DELETE", token });
}

// ----- Governance Events (Read-only) -----

/**
 * Fetch governance events (audit log) with optional filtering.
 */
export function fetchGovernanceEvents(token, filters = {}) {
  const query = new URLSearchParams(
    Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {})
  ).toString();
  const url = query ? `${API_ROUTES.governance}?${query}` : API_ROUTES.governance;
  return apiFetch(url, { token });
}

// ----- Catalog Search -----

/**
 * Search across catalog (domains, glossary terms, assets, etc).
 */
export function searchCatalog(token, query, filters = {}) {
  const params = { q: query, ...filters };
  const queryStr = new URLSearchParams(params).toString();
  return apiFetch(`${API_ROUTES.catalogSearch}?${queryStr}`, { token });
}

// ===== MDM: Reference Sets, Reference Values, Org Units =====

// ----- Reference Sets -----

/**
 * Fetch all reference sets.
 */
export function fetchReferenceSets(token) {
  return apiFetch(API_ROUTES.referenceSets, { token });
}

/**
 * Get a specific reference set with its values.
 */
export function fetchReferenceSet(token, id) {
  return apiFetch(`${API_ROUTES.referenceSets}${id}/`, { token });
}

/**
 * Create a new reference set.
 */
export function createReferenceSet(token, data) {
  return apiFetch(API_ROUTES.referenceSets, { method: "POST", token, body: data });
}

/**
 * Update a reference set.
 */
export function updateReferenceSet(token, id, data) {
  return apiFetch(`${API_ROUTES.referenceSets}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a reference set.
 */
export function deleteReferenceSet(token, id) {
  return apiFetch(`${API_ROUTES.referenceSets}${id}/`, { method: "DELETE", token });
}

/**
 * Get values for a reference set (convenience method).
 */
export function fetchReferenceSetValues(token, setId) {
  return apiFetch(`${API_ROUTES.referenceSets}${setId}/values/`, { token });
}

// ----- Reference Values -----

/**
 * Fetch all reference values (optionally filtered by set).
 */
export function fetchReferenceValues(token, setId = null) {
  const url = setId
    ? `${API_ROUTES.referenceValues}?reference_set=${setId}`
    : API_ROUTES.referenceValues;
  return apiFetch(url, { token });
}

/**
 * Create a new reference value.
 */
export function createReferenceValue(token, data) {
  return apiFetch(API_ROUTES.referenceValues, { method: "POST", token, body: data });
}

/**
 * Update a reference value.
 */
export function updateReferenceValue(token, id, data) {
  return apiFetch(`${API_ROUTES.referenceValues}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a reference value.
 */
export function deleteReferenceValue(token, id) {
  return apiFetch(`${API_ROUTES.referenceValues}${id}/`, { method: "DELETE", token });
}

// ----- Org Units (Master Data Hierarchy) -----

/**
 * Fetch all org units (organizational hierarchy).
 */
export function fetchOrgUnits(token) {
  return apiFetch(API_ROUTES.orgUnits, { token });
}

/**
 * Get a specific org unit.
 */
export function fetchOrgUnit(token, id) {
  return apiFetch(`${API_ROUTES.orgUnits}${id}/`, { token });
}

/**
 * Create a new org unit.
 */
export function createOrgUnit(token, data) {
  return apiFetch(API_ROUTES.orgUnits, { method: "POST", token, body: data });
}

/**
 * Update an org unit.
 */
export function updateOrgUnit(token, id, data) {
  return apiFetch(`${API_ROUTES.orgUnits}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete an org unit.
 */
export function deleteOrgUnit(token, id) {
  return apiFetch(`${API_ROUTES.orgUnits}${id}/`, { method: "DELETE", token });
}

// ----- MDM: Bind Field to Reference Set -----

/**
 * Bind a data field to a reference set (or unbind if setId is null).
 */
export function bindFieldToReferenceSet(token, dataFieldId, referenceSetId = null) {
  return apiFetch(API_ROUTES.bindField, {
    method: "POST",
    token,
    body: {
      data_field: dataFieldId,
      reference_set: referenceSetId,
    },
  });
}

/**
 * Get available reference values for a field (those bound to its reference set).
 */
export function fetchFieldOptions(token, dataFieldId) {
  return apiFetch(`${API_ROUTES.fieldOptions}?data_field=${dataFieldId}`, { token });
}

// ===== CONNECTIONS: Data Sources & Consuming Systems =====

// ----- Data Sources -----

/**
 * Fetch all data sources.
 */
export function fetchDataSources(token) {
  return apiFetch(API_ROUTES.dataSources, { token });
}

/**
 * Get a specific data source.
 */
export function fetchDataSource(token, id) {
  return apiFetch(`${API_ROUTES.dataSources}${id}/`, { token });
}

/**
 * Create a new data source.
 */
export function createDataSource(token, data) {
  return apiFetch(API_ROUTES.dataSources, { method: "POST", token, body: data });
}

/**
 * Update a data source.
 */
export function updateDataSource(token, id, data) {
  return apiFetch(`${API_ROUTES.dataSources}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a data source.
 */
export function deleteDataSource(token, id) {
  return apiFetch(`${API_ROUTES.dataSources}${id}/`, { method: "DELETE", token });
}

/**
 * Test connectivity to a data source.
 */
export function testDataSource(token, id) {
  return apiFetch(`${API_ROUTES.dataSources}${id}/test/`, { method: "POST", token });
}

// ----- Consuming Connections (API Keys for external systems) -----

/**
 * Fetch all consuming connections.
 */
export function fetchConsumingConnections(token) {
  return apiFetch(API_ROUTES.consumingConnections, { token });
}

/**
 * Get a specific consuming connection.
 */
export function fetchConsumingConnection(token, id) {
  return apiFetch(`${API_ROUTES.consumingConnections}${id}/`, { token });
}

/**
 * Create a new consuming connection (generates API key).
 */
export function createConsumingConnection(token, data) {
  return apiFetch(API_ROUTES.consumingConnections, { method: "POST", token, body: data });
}

/**
 * Update a consuming connection (metadata only, does not rotate key).
 */
export function updateConsumingConnection(token, id, data) {
  return apiFetch(`${API_ROUTES.consumingConnections}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a consuming connection.
 */
export function deleteConsumingConnection(token, id) {
  return apiFetch(`${API_ROUTES.consumingConnections}${id}/`, { method: "DELETE", token });
}

/**
 * Rotate (regenerate) API key for a consuming connection.
 * Returns the new plaintext key (only shown once).
 */
export function rotateConsumingConnectionKey(token, id) {
  return apiFetch(`${API_ROUTES.consumingConnections}${id}/rotate_key/`, {
    method: "POST",
    token,
  });
}

// ===== IMPORT/EXPORT: Bulk operations on data tables =====

// ----- Export Projects (reusable export templates) -----

/**
 * Fetch all export projects.
 */
export function fetchExportProjects(token) {
  return apiFetch(API_ROUTES.exportProjects, { token });
}

/**
 * Get a specific export project.
 */
export function fetchExportProject(token, id) {
  return apiFetch(`${API_ROUTES.exportProjects}${id}/`, { token });
}

/**
 * Create a new export project.
 */
export function createExportProject(token, data) {
  return apiFetch(API_ROUTES.exportProjects, { method: "POST", token, body: data });
}

/**
 * Update an export project.
 */
export function updateExportProject(token, id, data) {
  return apiFetch(`${API_ROUTES.exportProjects}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete an export project.
 */
export function deleteExportProject(token, id) {
  return apiFetch(`${API_ROUTES.exportProjects}${id}/`, { method: "DELETE", token });
}

/**
 * Run an export project (creates a new ExportJob).
 */
export function runExportProject(token, id) {
  return apiFetch(`${API_ROUTES.exportProjects}${id}/run/`, { method: "POST", token });
}

// ----- Import Jobs (bulk import records) -----

/**
 * Fetch all import jobs.
 */
export function fetchImportJobs(token) {
  return apiFetch(API_ROUTES.importJobs, { token });
}

/**
 * Get a specific import job.
 */
export function fetchImportJob(token, id) {
  return apiFetch(`${API_ROUTES.importJobs}${id}/`, { token });
}

/**
 * Create a new import job (upload file).
 * @param {string} token
 * @param {object} data - { data_table, source, file, format }
 * @note file should be a File object from <input type="file">
 */
export async function createImportJob(token, data) {
  // File upload requires FormData, not JSON
  const formData = new FormData();
  formData.append("data_table", data.data_table);
  if (data.source) formData.append("source", data.source);
  formData.append("file", data.file);
  formData.append("format", data.format || "csv");

  return apiFetch(API_ROUTES.importJobs, {
    method: "POST",
    token,
    body: formData,
  });
}

// ----- Export Jobs (bulk export records) -----

/**
 * Fetch all export jobs.
 */
export function fetchExportJobs(token) {
  return apiFetch(API_ROUTES.exportJobs, { token });
}

/**
 * Get a specific export job.
 */
export function fetchExportJob(token, id) {
  return apiFetch(`${API_ROUTES.exportJobs}${id}/`, { token });
}

/**
 * Download an export job file (only if status === 'ready').
 * Returns the download URL.
 */
export function getExportJobDownloadUrl(token, id) {
  return apiFetch(`${API_ROUTES.exportJobs}${id}/download/`, { token });
}

// ===== TABLE RELATIONS (explicit lineage) =====

/**
 * Fetch all table relations (optionally filtered by from_table or to_table).
 */
export function fetchTableRelations(token, filters = {}) {
  const query = new URLSearchParams(filters).toString();
  const url = query
    ? `${API_ROUTES.tableRelations}?${query}`
    : API_ROUTES.tableRelations;
  return apiFetch(url, { token });
}

/**
 * Get a specific table relation.
 */
export function fetchTableRelation(token, id) {
  return apiFetch(`${API_ROUTES.tableRelations}${id}/`, { token });
}

/**
 * Create a new table relation (explicit lineage link).
 */
export function createTableRelation(token, data) {
  return apiFetch(API_ROUTES.tableRelations, { method: "POST", token, body: data });
}

/**
 * Update a table relation.
 */
export function updateTableRelation(token, id, data) {
  return apiFetch(`${API_ROUTES.tableRelations}${id}/`, { method: "PUT", token, body: data });
}

/**
 * Delete a table relation.
 */
export function deleteTableRelation(token, id) {
  return apiFetch(`${API_ROUTES.tableRelations}${id}/`, { method: "DELETE", token });
}
