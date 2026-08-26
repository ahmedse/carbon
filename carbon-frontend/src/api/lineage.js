import { apiFetch } from "./api";

export function getTableLineage(token, tableId, direction = "both") {
  return apiFetch(`catalog/tables/${tableId}/lineage/?direction=${encodeURIComponent(direction)}`, {
    token,
  });
}

export function getTableImpact(token, tableId, depth = 5) {
  return apiFetch(`catalog/tables/${tableId}/impact/?depth=${encodeURIComponent(depth)}`, {
    token,
  });
}

export function createLineageEdge(token, data) {
  return apiFetch(`catalog/lineage/`, {
    method: "POST",
    token,
    body: data,
  });
}

export function deleteLineageEdge(token, id) {
  return apiFetch(`catalog/lineage/${id}/`, {
    method: "DELETE",
    token,
  });
}
