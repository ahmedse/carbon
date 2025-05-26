// src/api.js
import { API_BASE_URL } from "./config";
import { isJwtExpired } from "./jwt";

export async function apiFetch(endpoint, { method = "GET", body, context = {}, token } = {}) {
  const params = new URLSearchParams();
  if (context.context_id) {
    params.append("context_id", context.context_id);
  }
  const url = `${API_BASE_URL}${endpoint}${params.toString() ? "?" + params.toString() : ""}`;

  let accessToken = token || localStorage.getItem("access");

  // If token is expired, refresh before first request
  if (isJwtExpired(accessToken) && typeof window.refreshAccessToken === "function") {
    try {
      accessToken = await window.refreshAccessToken();
    } catch {
      if (typeof window.logout === "function") window.logout();
      throw new Error("Session expired. Please log in again.");
    }
  }

  let headers = {
    "Content-Type": "application/json",
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  let res = await fetch(url, { method, headers, ...(body ? { body: JSON.stringify(body) } : {}) });

  // If 401, try refresh once and retry
  if (res.status === 401 && typeof window.refreshAccessToken === "function") {
    try {
      accessToken = await window.refreshAccessToken();
      headers = { ...headers, Authorization: `Bearer ${accessToken}` };
      res = await fetch(url, { method, headers, ...(body ? { body: JSON.stringify(body) } : {}) });
    } catch {
      if (typeof window.logout === "function") window.logout();
      throw new Error("Session expired. Please log in again.");
    }
  }

  return res;
}