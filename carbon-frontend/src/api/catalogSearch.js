import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

/**
 * Search the catalog by text and optional type / trust_tier filters.
 * @param {string} token
 * @param {string} q
 * @param {string|string[]} [types]
 * @param {number} [page]
 * @param {string} [trustTier] — trusted | limited | untrustworthy
 */
export async function searchCatalog(token, q, types, page = 1, trustTier = null) {
  const params = new URLSearchParams();
  if (q != null) params.set("q", String(q));
  if (Array.isArray(types) && types.length > 0) {
    params.set("types", types.join(","));
  } else if (typeof types === "string" && types && types !== "all") {
    params.set("types", types);
  }
  if (page != null) params.set("page", String(page));
  if (trustTier) params.set("trust_tier", String(trustTier));

  const endpoint = `${API_ROUTES.catalogSearch}?${params.toString()}`;
  return apiFetch(endpoint, { token });
}
