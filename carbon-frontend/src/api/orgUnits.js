// src/api/orgUnits.js
// API calls for OrgUnit management (MDM). Admin-gated on the server.
// ADR-0028 / NSR-8B: list is deployment-subtree scoped (API); FE adds tree
// sort/labels + orphan-chain guard for pickers.
import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

/** Resolve parent PK from a unit (`parent` may be id, null, or nested object). */
export function orgUnitParentId(unit) {
  if (unit == null || unit.parent == null || unit.parent === "") return null;
  if (typeof unit.parent === "object") {
    const id = unit.parent.id;
    return id == null || id === "" ? null : id;
  }
  return unit.parent;
}

/**
 * Defense-in-depth: keep only units whose parent chain reaches a root that is
 * present in the returned set (parent null/missing). Drops orphans and units
 * attached to a foreign root not in the list.
 */
export function filterOrgUnitsToConnectedTree(units) {
  if (!Array.isArray(units) || units.length === 0) return [];
  const byId = new Map();
  for (const u of units) {
    if (u?.id != null) byId.set(u.id, u);
  }
  const keep = new Set();
  for (const unit of units) {
    if (unit?.id == null) continue;
    const seen = new Set();
    let cur = unit;
    let connected = false;
    while (cur) {
      if (seen.has(cur.id)) break;
      seen.add(cur.id);
      const pid = orgUnitParentId(cur);
      if (pid == null) {
        connected = true;
        break;
      }
      if (!byId.has(pid)) {
        connected = false;
        break;
      }
      cur = byId.get(pid);
    }
    if (connected) {
      for (const id of seen) keep.add(id);
    }
  }
  return units.filter((u) => u?.id != null && keep.has(u.id));
}

/**
 * Depth of a unit within `byId` (0 = root / parent not in set).
 */
export function orgUnitDepth(unit, byId) {
  if (!unit || !byId) return 0;
  let depth = 0;
  let pid = orgUnitParentId(unit);
  const seen = new Set();
  while (pid != null && byId.has(pid) && !seen.has(pid)) {
    seen.add(pid);
    depth += 1;
    pid = orgUnitParentId(byId.get(pid));
  }
  return depth;
}

/**
 * Parents before children; siblings by name then code. Stable for picker lists.
 */
export function sortOrgUnitsForTree(units) {
  if (!Array.isArray(units) || units.length === 0) return [];
  const byId = new Map();
  for (const u of units) {
    if (u?.id != null) byId.set(u.id, u);
  }
  const children = new Map();
  const roots = [];
  for (const u of units) {
    if (u?.id == null) continue;
    const pid = orgUnitParentId(u);
    if (pid == null || !byId.has(pid)) {
      roots.push(u);
    } else {
      if (!children.has(pid)) children.set(pid, []);
      children.get(pid).push(u);
    }
  }
  const labelKey = (u) =>
    String(u?.name || u?.code || u?.id || "").toLowerCase();
  const sortSiblings = (arr) =>
    arr.sort((a, b) => labelKey(a).localeCompare(labelKey(b), undefined, { sensitivity: "base" }));

  sortSiblings(roots);
  const out = [];
  const seen = new Set();
  const walk = (node) => {
    if (!node || seen.has(node.id)) return;
    seen.add(node.id);
    out.push(node);
    const kids = children.get(node.id) || [];
    sortSiblings(kids);
    kids.forEach(walk);
  };
  roots.forEach(walk);
  for (const u of units) {
    if (u?.id != null && !seen.has(u.id)) out.push(u);
  }
  return out;
}

/**
 * Tree-aware option label.
 * - default: indented leaf name (em-space × depth)
 * - preferPath: use API `full_path` when present
 */
export function orgUnitOptionLabel(unit, { depth = 0, preferPath = false } = {}) {
  if (!unit) return "";
  if (preferPath && unit.full_path) return String(unit.full_path);
  const name = unit.name || unit.code || String(unit.id ?? "");
  if (preferPath) return name;
  const indent = "\u2003".repeat(Math.max(0, depth));
  return `${indent}${name}`;
}

/** Filter orphans then sort for tree display. */
export function prepareOrgUnitsForPicker(units) {
  return sortOrgUnitsForTree(filterOrgUnitsToConnectedTree(units));
}

/**
 * Autocomplete / filter options: `{ value, label, id, unit }`.
 * Label is indented by depth (or full_path when preferPath).
 */
export function orgUnitSelectOptions(units, { preferPath = false } = {}) {
  const prepared = prepareOrgUnitsForPicker(units);
  const byId = new Map(prepared.map((u) => [u.id, u]));
  return prepared.map((u) => {
    const depth = orgUnitDepth(u, byId);
    return {
      value: String(u.id),
      label: orgUnitOptionLabel(u, { depth, preferPath }),
      id: u.id,
      unit: u,
    };
  });
}

/** Unwrap list payload + apply picker prepare (subtree sort / orphan guard). */
export function normalizeOrgUnitsList(data, { prepare = true } = {}) {
  let list = [];
  if (Array.isArray(data)) list = data;
  else if (data && Array.isArray(data.results)) list = data.results;
  return prepare ? prepareOrgUnitsForPicker(list) : list;
}

/** List org units for the deployment subtree. Returns a tree-sorted array. */
export async function fetchOrgUnits(token, { prepare = true } = {}) {
  const data = await apiFetch(API_ROUTES.orgUnits, { token });
  return normalizeOrgUnitsList(data, { prepare });
}

/** Create an org unit. `data` = { name, org_type, parent, code, description }. */
export function createOrgUnit(token, data) {
  return apiFetch(API_ROUTES.orgUnits, { method: "POST", token, body: data });
}

/** Update an org unit (partial). */
export function updateOrgUnit(token, id, data) {
  return apiFetch(`${API_ROUTES.orgUnits}${id}/`, { method: "PATCH", token, body: data });
}

/** Delete an org unit. */
export function deleteOrgUnit(token, id) {
  return apiFetch(`${API_ROUTES.orgUnits}${id}/`, { method: "DELETE", token });
}
