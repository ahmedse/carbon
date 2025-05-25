// frontend/src/api.js
import { API_BASE_URL } from "./config";
import { useAuth } from "./context/AuthContext";

export function apiFetch(endpoint, { method = "GET", body, context = {}, token } = {}) {
  // context: { context_type: "project", context_name: "AAST Carbon" }
  const params = new URLSearchParams();
  if (context.context_type && context.context_name) {
    params.append("context_type", context.context_type);
    params.append(context.context_type, context.context_name);
  }
  const url = `${API_BASE_URL}${endpoint}${params.toString() ? "?" + params.toString() : ""}`;
  return fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {})
  });
}