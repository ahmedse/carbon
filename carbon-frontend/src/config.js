// src/config.js
// Central API config and endpoint management.

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// All backend API routes.
export const API_ROUTES = {
  token: "token/",
  tokenRefresh: "token/refresh/",
  myRoles: "accounts/my-roles/",
  projects: "core/projects/",
  modules: "core/modules/",
  tables: "dataschema/tables/",
  fields: "dataschema/fields/",
  rows: "dataschema/rows/",
  schemaLogs: "dataschema/schema-logs/",
  feedback: "core/feedback/",
};