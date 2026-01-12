// src/config.js
// Central API config and endpoint management.
// ALWAYS uses environment variables - NEVER hardcode URLs or ports

// API Base URL - read from environment variable
// Fallback is for development only - should always be set in .env
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001/carbon-api/";

// API timeout (milliseconds)
export const API_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || "30000", 10);

// Validate configuration on load
if (!import.meta.env.VITE_API_BASE_URL) {
  console.warn("⚠️ VITE_API_BASE_URL not set in .env - using fallback URL");
}

console.log("🔧 API Configuration:", {
  baseUrl: API_BASE_URL,
  timeout: API_TIMEOUT,
  mode: import.meta.env.MODE,
});

// All backend API routes (relative to API_BASE_URL)
export const API_ROUTES = {
  token: "token/",
  tokenRefresh: "token/refresh/",
  logout: "accounts/logout/",
  myRoles: "accounts/my-roles/",
  projects: "core/projects/",
  modules: "core/modules/",
  tables: "dataschema/tables/",
  fields: "dataschema/fields/",
  rows: "dataschema/rows/",
  schemaLogs: "dataschema/schema-logs/",
  feedback: "core/feedback/",
};
