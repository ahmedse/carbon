// src/config.js
// Central API config and endpoint management.

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// All backend API routes.
export const API_ROUTES = {
  token: "/api/token/",
  tokenRefresh: "/api/token/refresh/",
  myRoles: "/api/accounts/my-roles/",
  // myRoles: "/api/my-roles/",
  projects: "/api/core/projects/",
  modules: "/api/core/modules/",
  tables: "/api/dataschema/tables/",
  fields: "/api/dataschema/fields/",
  rows: "/api/dataschema/rows/",
  schemaLogs: "/api/dataschema/schema-logs/",
  // Add other endpoints as needed.
};